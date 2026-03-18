from __future__ import annotations

import json
import logging
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import PaymentTransaction, SubscriptionPlan, SubscriptionRequest
from .services import (
    DURATIONS,
    calculate_price,
    create_order,
    mark_order_paid,
)
from .telegram_notifications import send_payment_success_notification
from .utils import (
    ClickError,
    amounts_match,
    generate_merchant_trans_id,
    give_subscription,
    verify_click_signature,
)

logger = logging.getLogger(__name__)


def _click_response(
    *,
    error: int,
    error_note: str,
    click_trans_id: str,
    merchant_trans_id: str,
    **extra,
) -> JsonResponse:
    payload = {
        "error": error,
        "error_note": error_note,
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
    }
    payload.update(extra)
    return JsonResponse(payload)


def _request_post_value(data, key: str) -> str:
    value = data.get(key)
    return str(value).strip() if value is not None else ""


def _request_value(data, *keys: str) -> str:
    for key in keys:
        raw_value = data.get(key)
        value = str(raw_value).strip() if raw_value is not None else ""
        if value:
            return value
    return ""


def _safe_payload_for_log(data) -> dict:
    if not hasattr(data, "items"):
        return {}
    payload = {}
    hidden_keys = {"sign_string", "signature", "sign"}
    for key, value in data.items():
        if key in hidden_keys:
            payload[key] = "***"
        else:
            payload[key] = value
    return payload


def _request_payload(request):
    """
    Supports form POST (Click default) and JSON POST payloads.
    """
    if request.POST:
        return request.POST

    content_type = (request.content_type or "").split(";")[0].strip().lower()
    if request.method == "POST" and content_type == "application/json":
        try:
            payload = json.loads((request.body or b"").decode("utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception:
            logger.warning("Click webhook JSON payload parse failed")

    if request.method == "POST" and request.body:
        # Fallback for incorrect/missing content-type from payment gateway.
        try:
            return dict(parse_qsl((request.body or b"").decode("utf-8"), keep_blank_values=True))
        except Exception:
            logger.warning("Click webhook form payload parse failed")

    return request.GET


def _extract_merchant_params(data, *, require_merchant_trans_id: bool = False) -> tuple[str, str]:
    merchant_trans_id = _request_value(data, "merchant_trans_id")
    transaction_param = _request_value(data, "transaction_param")
    if require_merchant_trans_id and not merchant_trans_id:
        raise ValueError("merchant_trans_id is required")
    if not merchant_trans_id and not transaction_param:
        raise ValueError("merchant_trans_id/transaction_param is required")
    return merchant_trans_id, transaction_param


def _resolve_subscription_request(data, *, require_merchant_trans_id: bool = False):
    merchant_trans_id, transaction_param = _extract_merchant_params(
        data,
        require_merchant_trans_id=require_merchant_trans_id,
    )
    queryset = SubscriptionRequest.objects.select_related("user", "center", "plan")

    sub_request = None
    if require_merchant_trans_id:
        # Security: Click callbacks must be matched by exact merchant_trans_id only.
        sub_request = queryset.filter(merchant_trans_id=merchant_trans_id).first()
    elif merchant_trans_id:
        sub_request = queryset.filter(merchant_trans_id=merchant_trans_id).first()
        # Backward compatibility for old numeric merchant_trans_id values.
        if not sub_request and merchant_trans_id.isdigit():
            sub_request = queryset.filter(pk=int(merchant_trans_id)).first()

    if (
        not sub_request
        and not require_merchant_trans_id
        and transaction_param
        and transaction_param.isdigit()
    ):
        sub_request = queryset.filter(pk=int(transaction_param)).first()

    if not sub_request:
        raise SubscriptionRequest.DoesNotExist

    if transaction_param and transaction_param.isdigit() and sub_request.pk != int(transaction_param):
        raise SubscriptionRequest.DoesNotExist

    # Security: if request carries both identifiers they must resolve to the same order.
    if merchant_trans_id and sub_request.merchant_trans_id and merchant_trans_id != sub_request.merchant_trans_id:
        raise SubscriptionRequest.DoesNotExist

    resolved_merchant_trans_id = sub_request.merchant_trans_id or merchant_trans_id or str(sub_request.id)
    return sub_request, resolved_merchant_trans_id


def _request_amount(sub_request: SubscriptionRequest) -> int:
    return int(sub_request.amount or sub_request.price or 0)


def _merchant_id_is_valid(merchant_id: str) -> bool:
    expected_merchant_id = str(getattr(settings, "CLICK_MERCHANT_ID", "")).strip()
    if not merchant_id:
        return True
    return merchant_id == expected_merchant_id


def _resolve_plan_for_request(sub_request: SubscriptionRequest) -> SubscriptionPlan | None:
    if sub_request.plan_id:
        return sub_request.plan
    return (
        SubscriptionPlan.objects.filter(
            Q(code__iexact=sub_request.plan_name)
            | Q(name__iexact=sub_request.plan_name)
            | Q(title__iexact=sub_request.plan_name),
            active=True,
        )
        .order_by("-id")
        .first()
    )


def _redirect_url_for_status(sub_request: SubscriptionRequest) -> str:
    trans_id = sub_request.merchant_trans_id or str(sub_request.id)
    if sub_request.status == SubscriptionRequest.Status.PAID:
        return f"{reverse('billing:payment_success')}?merchant_trans_id={trans_id}"
    if sub_request.status == SubscriptionRequest.Status.CANCELLED:
        return f"{reverse('billing:payment_cancel')}?merchant_trans_id={trans_id}"
    return ""


def _payment_status_payload(sub_request: SubscriptionRequest) -> dict:
    expires_at = sub_request.created_at + timedelta(minutes=15)
    seconds_left = max(int((expires_at - timezone.now()).total_seconds()), 0)

    # If the timer has expired and the order is still pending, auto-cancel it
    # so the frontend stops polling and clears the UI.
    if seconds_left == 0 and sub_request.status == SubscriptionRequest.Status.PENDING:
        sub_request.status = SubscriptionRequest.Status.CANCELLED
        sub_request.save(update_fields=["status", "updated_at"])
        logger.info(
            "Auto-cancelled expired pending order req_id=%s (>15 min elapsed)",
            sub_request.id,
        )

    frontend_status = "success" if sub_request.status == SubscriptionRequest.Status.PAID else sub_request.status
    return {
        "id": sub_request.id,
        "merchant_trans_id": sub_request.merchant_trans_id,
        "status": sub_request.status,
        "frontend_status": frontend_status,
        "status_display": sub_request.get_status_display(),
        "amount": _request_amount(sub_request),
        "created_at": sub_request.created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "seconds_left": seconds_left,
        "redirect_url": _redirect_url_for_status(sub_request),
    }


def _assign_unique_merchant_trans_id(sub_request: SubscriptionRequest, max_attempts: int = 10) -> str:
    if sub_request.merchant_trans_id:
        return sub_request.merchant_trans_id

    for _ in range(max_attempts):
        candidate = generate_merchant_trans_id(sub_request.id)
        sub_request.merchant_trans_id = candidate
        try:
            sub_request.save(update_fields=["merchant_trans_id", "updated_at"])
            return candidate
        except IntegrityError:
            logger.warning("merchant_trans_id collision detected, retrying: %s", candidate)
            continue

    raise RuntimeError("Could not generate unique merchant_trans_id")


@login_required
@require_POST
def create_order_and_redirect(request):
    role = getattr(request.user, "role", None)
    if role in ("student", "parent"):
        return JsonResponse(
            {"error": "permission_denied", "error_note": "You do not have permission."},
            status=403,
        )

    center = getattr(request, "center", None)
    if not center:
        return JsonResponse(
            {"error": "center_not_found", "error_note": "Center topilmadi."},
            status=400,
        )

    service_id = str(getattr(settings, "CLICK_SERVICE_ID", "")).strip()
    merchant_id = str(getattr(settings, "CLICK_MERCHANT_ID", "")).strip()
    return_url = str(getattr(settings, "CLICK_RETURN_URL", "")).strip()
    if not return_url:
        return_url = request.build_absolute_uri("/platform/")
    webhook_prepare_url = str(getattr(settings, "CLICK_PREPARE_URL", "")).strip()
    webhook_complete_url = str(getattr(settings, "CLICK_COMPLETE_URL", "")).strip()
    webhook_url = str(getattr(settings, "CLICK_WEBHOOK_URL", "")).strip()

    if not service_id or not merchant_id:
        return JsonResponse(
            {
                "error": "config_error",
                "error_note": "CLICK_SERVICE_ID yoki CLICK_MERCHANT_ID sozlanmagan.",
            },
            status=500,
        )

    plan_code = (request.POST.get("plan") or "").strip().upper()
    try:
        months = int(request.POST.get("months") or 1)
    except (TypeError, ValueError):
        months = 1
    if months not in DURATIONS:
        months = 1
    promo = (request.POST.get("promo") or "").strip().upper()

    plan = SubscriptionPlan.objects.filter(code=plan_code, active=True).first()
    if not plan:
        return JsonResponse(
            {"error": "plan_not_found", "error_note": "Tarif topilmadi."},
            status=404,
        )

    pricing = calculate_price(plan, months, promo, center=center)
    if pricing.final_price <= 0:
        return JsonResponse(
            {
                "error": "invalid_amount",
                "error_note": "Click to'lovi uchun summa 0 bo'lmasligi kerak.",
            },
            status=400,
        )

    try:
        with transaction.atomic():
            sub_request = SubscriptionRequest.objects.create(
                user=request.user,
                center=center,
                plan=plan,
                plan_name=plan.title,
                duration_months=months,
                amount=pricing.final_price,
                price=pricing.final_price,
                promo_code=promo,
                status=SubscriptionRequest.Status.PENDING,
            )
            merchant_trans_id = _assign_unique_merchant_trans_id(sub_request)
    except Exception:
        logger.exception("Failed to create Click order: user_id=%s", request.user.id)
        return JsonResponse(
            {"error": "order_create_failed", "error_note": "Order yaratishda xatolik."},
            status=500,
        )

    params = {
        "service_id": service_id,
        "merchant_id": merchant_id,
        "merchant_trans_id": merchant_trans_id,
        "transaction_param": sub_request.id,
        "amount": pricing.final_price,
        "return_url": return_url,
    }

    payment_url = "https://my.click.uz/services/pay?" + urlencode(params)

    logger.info(
        "Click payment URL created merchant_trans_id=%s user_id=%s center=%s amount=%s",
        merchant_trans_id,
        request.user.id,
        center.id,
        pricing.final_price,
    )
    return JsonResponse(
        {
            "payment_url": payment_url,
            "merchant_trans_id": merchant_trans_id,
            "order_id": sub_request.id,
            "amount": pricing.final_price,
            "return_url": return_url,
            "webhook_prepare_url": webhook_prepare_url,
            "webhook_complete_url": webhook_complete_url,
            "webhook_url": webhook_url,
        }
    )


@login_required
def payment_status_api(request):
    raw_ids = (request.GET.get("ids") or "").strip()
    raw_merchant_trans_id = (request.GET.get("merchant_trans_id") or "").strip()
    if not raw_ids and not raw_merchant_trans_id:
        return JsonResponse({"items": [], "checked_at": timezone.now().isoformat()})

    parsed_ids: list[int] = []
    merchant_ids: list[str] = []
    for value in raw_ids.split(","):
        value = value.strip()
        if not value:
            continue
        if value.isdigit():
            parsed = int(value)
            if parsed > 0:
                parsed_ids.append(parsed)
        else:
            merchant_ids.append(value)
    if raw_merchant_trans_id:
        merchant_ids.append(raw_merchant_trans_id)

    if not parsed_ids and not merchant_ids:
        return JsonResponse(
            {"error": "invalid_ids", "error_note": "ids parameter is invalid"},
            status=400,
        )

    ids = list(dict.fromkeys(parsed_ids))
    merchant_ids = list(dict.fromkeys(merchant_ids))

    filters = Q()
    if ids:
        filters |= Q(pk__in=ids)
    if merchant_ids:
        filters |= Q(merchant_trans_id__in=merchant_ids)

    queryset = SubscriptionRequest.objects.filter(filters).order_by("pk")
    if not request.user.is_superuser:
        center = getattr(request, "center", None)
        if center:
            queryset = queryset.filter(center=center)
        else:
            queryset = queryset.filter(user=request.user)

    by_pk = {}
    by_merchant = {}
    for req in queryset:
        payload = _payment_status_payload(req)
        by_pk[req.pk] = payload
        if req.merchant_trans_id:
            by_merchant[req.merchant_trans_id] = payload

    ordered_items = []
    seen_ids = set()
    for item_id in ids:
        payload = by_pk.get(item_id)
        if payload and payload["id"] not in seen_ids:
            ordered_items.append(payload)
            seen_ids.add(payload["id"])
    for item_id in merchant_ids:
        payload = by_merchant.get(item_id)
        if payload and payload["id"] not in seen_ids:
            ordered_items.append(payload)
            seen_ids.add(payload["id"])

    return JsonResponse(
        {
            "items": ordered_items,
            "checked_at": timezone.now().isoformat(),
        }
    )


@csrf_exempt
def click_prepare(request):
    data = _request_payload(request)
    click_trans_id = _request_value(data, "click_trans_id", "transaction_id")
    service_id = _request_value(data, "service_id")
    merchant_id = _request_value(data, "merchant_id")
    action = _request_value(data, "action")
    amount = _request_value(data, "amount")
    sign_time = _request_value(data, "sign_time")
    sign_string = _request_value(data, "sign_string", "signature", "sign")
    logger.info(
        "Click PREPARE webhook: method=%s path=%s host=%s params=%s data=%s",
        request.method,
        request.path,
        request.get_host(),
        request.GET.dict(),
        _safe_payload_for_log(data),
    )
    if not data:
        logger.warning("Click PREPARE received EMPTY payload. Raw body: %s", request.body[:500] if request.body else "None")

    try:
        incoming_merchant_trans_id, _ = _extract_merchant_params(data, require_merchant_trans_id=True)
        sub_request, merchant_trans_id = _resolve_subscription_request(data, require_merchant_trans_id=True)
        request_id = sub_request.id
    except ValueError as exc:
        logger.warning("Click prepare invalid trans id: %s", exc)
        return _click_response(
            error=ClickError.ORDER_NOT_FOUND,
            error_note="Order not found",
            click_trans_id=click_trans_id,
            merchant_trans_id="",
        )
    except SubscriptionRequest.DoesNotExist:
        logger.warning("Click prepare rejected: request not found merchant_trans_id=%s", incoming_merchant_trans_id)
        return _click_response(
            error=ClickError.ORDER_NOT_FOUND,
            error_note="Order not found",
            click_trans_id=click_trans_id,
            merchant_trans_id=incoming_merchant_trans_id,
        )

    if action != "0":
        return _click_response(
            error=ClickError.ACTION_NOT_FOUND,
            error_note="Action not found",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )

    expected_service_id = str(getattr(settings, "CLICK_SERVICE_ID", "")).strip()
    if service_id != expected_service_id:
        logger.warning(
            "Click prepare rejected: invalid service_id=%s expected=%s",
            service_id,
            expected_service_id,
        )
        return _click_response(
            error=ClickError.REQUEST_ERROR,
            error_note="Incorrect service_id",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )

    if not _merchant_id_is_valid(merchant_id):
        logger.warning("Click prepare rejected: invalid merchant_id=%s", merchant_id)
        return _click_response(
            error=ClickError.REQUEST_ERROR,
            error_note="Incorrect merchant_id",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )

    sign_ok = verify_click_signature(
        sign_string=sign_string,
        click_trans_id=click_trans_id,
        service_id=service_id,
        secret_key=str(getattr(settings, "CLICK_SECRET_KEY", "")),
        merchant_trans_id=merchant_trans_id,
        amount=amount,
        action=action,
        sign_time=sign_time,
    )
    if not sign_ok:
        logger.warning("Click prepare rejected: sign mismatch request_id=%s", request_id)
        return _click_response(
            error=ClickError.SIGN_CHECK_FAILED,
            error_note="SIGN CHECK FAILED!",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )

    expected_amount = _request_amount(sub_request)
    if expected_amount <= 0 or not amounts_match(amount, expected_amount):
        logger.warning(
            "Click prepare rejected: amount mismatch request_id=%s expected=%s got=%s",
            request_id,
            expected_amount,
            amount,
        )
        return _click_response(
            error=ClickError.INVALID_AMOUNT,
            error_note="Incorrect parameter amount",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )

    if sub_request.status == SubscriptionRequest.Status.CANCELLED:
        return _click_response(
            error=ClickError.TRANSACTION_CANCELLED,
            error_note="Transaction cancelled",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )

    if sub_request.status == SubscriptionRequest.Status.PAID:
        return _click_response(
            error=ClickError.ALREADY_PAID,
            error_note="Already paid",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )

    merchant_prepare_id = str(sub_request.id)
    logger.info(
        "Click PREPARE success request_id=%s click_trans_id=%s amount=%s",
        request_id,
        click_trans_id,
        amount,
    )

    return _click_response(
        error=ClickError.SUCCESS,
        error_note="Success",
        click_trans_id=click_trans_id,
        merchant_trans_id=merchant_trans_id,
        merchant_prepare_id=merchant_prepare_id,
    )


@csrf_exempt
def click_complete(request):
    data = _request_payload(request)
    click_trans_id = _request_value(data, "click_trans_id", "transaction_id")
    service_id = _request_value(data, "service_id")
    merchant_id = _request_value(data, "merchant_id")
    action = _request_value(data, "action")
    amount = _request_value(data, "amount")
    sign_time = _request_value(data, "sign_time")
    sign_string = _request_value(data, "sign_string", "signature", "sign")
    merchant_prepare_id = _request_value(data, "merchant_prepare_id")
    logger.info(
        "Click COMPLETE webhook: method=%s path=%s host=%s params=%s data=%s",
        request.method,
        request.path,
        request.get_host(),
        request.GET.dict(),
        _safe_payload_for_log(data),
    )
    if not data:
        logger.warning("Click COMPLETE received EMPTY payload. Raw body: %s", request.body[:500] if request.body else "None")

    try:
        incoming_merchant_trans_id, _ = _extract_merchant_params(data, require_merchant_trans_id=True)
        sub_request, merchant_trans_id = _resolve_subscription_request(data, require_merchant_trans_id=True)
        request_id = sub_request.id
    except ValueError as exc:
        logger.warning("Click complete invalid trans id: %s", exc)
        return _click_response(
            error=ClickError.ORDER_NOT_FOUND,
            error_note="Order not found",
            click_trans_id=click_trans_id,
            merchant_trans_id="",
        )
    except SubscriptionRequest.DoesNotExist:
        logger.warning("Click complete rejected: request not found merchant_trans_id=%s", incoming_merchant_trans_id)
        return _click_response(
            error=ClickError.ORDER_NOT_FOUND,
            error_note="Order not found",
            click_trans_id=click_trans_id,
            merchant_trans_id=incoming_merchant_trans_id,
        )

    if action != "1":
        return _click_response(
            error=ClickError.ACTION_NOT_FOUND,
            error_note="Action not found",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )

    expected_service_id = str(getattr(settings, "CLICK_SERVICE_ID", "")).strip()
    if service_id != expected_service_id:
        logger.warning(
            "Click complete rejected: invalid service_id=%s expected=%s",
            service_id,
            expected_service_id,
        )
        return _click_response(
            error=ClickError.REQUEST_ERROR,
            error_note="Incorrect service_id",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )

    if not _merchant_id_is_valid(merchant_id):
        logger.warning("Click complete rejected: invalid merchant_id=%s", merchant_id)
        return _click_response(
            error=ClickError.REQUEST_ERROR,
            error_note="Incorrect merchant_id",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )

    sign_ok = verify_click_signature(
        sign_string=sign_string,
        click_trans_id=click_trans_id,
        service_id=service_id,
        secret_key=str(getattr(settings, "CLICK_SECRET_KEY", "")),
        merchant_trans_id=merchant_trans_id,
        merchant_prepare_id=merchant_prepare_id,
        amount=amount,
        action=action,
        sign_time=sign_time,
    )
    if not sign_ok:
        logger.warning("Click complete rejected: sign mismatch request_id=%s", request_id)
        return _click_response(
            error=ClickError.SIGN_CHECK_FAILED,
            error_note="SIGN CHECK FAILED!",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )

    try:
        click_error = int((data.get("error") or "0").strip() or 0)
    except ValueError:
        return _click_response(
            error=ClickError.REQUEST_ERROR,
            error_note="Incorrect parameter error",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )
    click_error_note = (data.get("error_note") or "").strip() or "Payment cancelled"

    try:
        with transaction.atomic():
            sub_request = (
                SubscriptionRequest.objects.select_for_update()
                .select_related("user", "center", "plan")
                .get(pk=request_id)
            )

            expected_prepare_id = str(sub_request.id)
            if merchant_prepare_id != expected_prepare_id:
                logger.warning(
                    "Click complete rejected: prepare_id mismatch request_id=%s expected=%s got=%s",
                    request_id,
                    expected_prepare_id,
                    merchant_prepare_id,
                )
                return _click_response(
                    error=ClickError.PREPARE_ID_INVALID,
                    error_note="Incorrect merchant_prepare_id",
                    click_trans_id=click_trans_id,
                    merchant_trans_id=merchant_trans_id,
                )

            expected_amount = _request_amount(sub_request)
            if expected_amount <= 0 or not amounts_match(amount, expected_amount):
                logger.warning(
                    "Click complete rejected: amount mismatch request_id=%s expected=%s got=%s",
                    request_id,
                    expected_amount,
                    amount,
                )
                return _click_response(
                    error=ClickError.INVALID_AMOUNT,
                    error_note="Incorrect parameter amount",
                    click_trans_id=click_trans_id,
                    merchant_trans_id=merchant_trans_id,
                )

            if click_error < 0:
                if sub_request.status == SubscriptionRequest.Status.PENDING:
                    sub_request.status = SubscriptionRequest.Status.CANCELLED
                    sub_request.save(update_fields=["status", "updated_at"])

                logger.warning(
                    "Click complete cancelled by Click request_id=%s click_error=%s",
                    request_id,
                    click_error,
                )
                return _click_response(
                    error=click_error,
                    error_note=click_error_note,
                    click_trans_id=click_trans_id,
                    merchant_trans_id=merchant_trans_id,
                )

            if sub_request.status == SubscriptionRequest.Status.CANCELLED:
                return _click_response(
                    error=ClickError.TRANSACTION_CANCELLED,
                    error_note="Transaction cancelled",
                    click_trans_id=click_trans_id,
                    merchant_trans_id=merchant_trans_id,
                )

            tx_id = f"click:{sub_request.id}:{click_trans_id}"[:64]
            if sub_request.status == SubscriptionRequest.Status.PAID:
                if PaymentTransaction.objects.filter(
                    transaction_id=tx_id,
                    status=PaymentTransaction.Status.PAID,
                ).exists():
                    logger.info(
                        "Click COMPLETE idempotent success request_id=%s click_trans_id=%s",
                        request_id,
                        click_trans_id,
                    )
                    return _click_response(
                        error=ClickError.SUCCESS,
                        error_note="Success",
                        click_trans_id=click_trans_id,
                        merchant_trans_id=merchant_trans_id,
                        merchant_confirm_id=str(sub_request.id),
                    )

                logger.warning(
                    "Click complete rejected: request already paid request_id=%s click_trans_id=%s",
                    request_id,
                    click_trans_id,
                )
                return _click_response(
                    error=ClickError.ALREADY_PAID,
                    error_note="Already paid",
                    click_trans_id=click_trans_id,
                    merchant_trans_id=merchant_trans_id,
                )

            plan = _resolve_plan_for_request(sub_request)
            if not plan:
                logger.error(
                    "Click complete failed: plan not found request_id=%s plan_name=%s",
                    request_id,
                    sub_request.plan_name,
                )
                return _click_response(
                    error=ClickError.ORDER_NOT_FOUND,
                    error_note="Plan not found",
                    click_trans_id=click_trans_id,
                    merchant_trans_id=merchant_trans_id,
                )

            tx, created = PaymentTransaction.objects.get_or_create(
                transaction_id=tx_id,
                defaults={
                    "user": sub_request.user,
                    "amount": expected_amount,
                    "status": PaymentTransaction.Status.PAID,
                    "click_trans_id": click_trans_id,
                    "paid_at": timezone.now(),
                },
            )
            if not created:
                tx.user = sub_request.user
                tx.amount = expected_amount
                tx.status = PaymentTransaction.Status.PAID
                tx.click_trans_id = click_trans_id
                tx.paid_at = timezone.now()
                tx.save(update_fields=["user", "amount", "status", "click_trans_id", "paid_at"])
            elif hasattr(tx, "paid_at"):
                tx.paid_at = timezone.now()
                tx.save(update_fields=["paid_at"])

            normalized_months = sub_request.duration_months if sub_request.duration_months in DURATIONS else 1
            subscription = give_subscription(sub_request.user, plan, duration_months=normalized_months)

            legacy_order = create_order(
                center=sub_request.center,
                plan=plan,
                months=normalized_months,
                promo_code=sub_request.promo_code,
            )
            mark_order_paid(legacy_order)

            sub_request.status = SubscriptionRequest.Status.PAID
            sub_request.save(update_fields=["status", "updated_at"])

            notify_user = sub_request.user
            notify_plan_name = plan.name or plan.title or plan.code
            notify_end_date = subscription.end_date
            transaction.on_commit(
                lambda: send_payment_success_notification(
                    user=notify_user,
                    plan_name=notify_plan_name,
                    end_date=notify_end_date,
                )
            )

            logger.info(
                "Click COMPLETE success request_id=%s click_trans_id=%s amount=%s user_id=%s",
                request_id,
                click_trans_id,
                expected_amount,
                sub_request.user_id,
            )
            return _click_response(
                error=ClickError.SUCCESS,
                error_note="Success",
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                merchant_confirm_id=str(sub_request.id),
            )

    except SubscriptionRequest.DoesNotExist:
        logger.warning("Click complete rejected: request_id=%s not found", request_id)
        return _click_response(
            error=ClickError.ORDER_NOT_FOUND,
            error_note="Order not found",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )
    except Exception:
        logger.exception("Click complete unexpected error request_id=%s", request_id)
        return _click_response(
            error=ClickError.REQUEST_ERROR,
            error_note="Internal server error",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )


@csrf_exempt
def click_webhook(request):
    """
    Single public webhook endpoint for Click Shop API.
    Dispatches by action:
    - 0: prepare
    - 1: complete
    """
    data = _request_payload(request)
    action = _request_post_value(data, "action")
    client_ip = (
        request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        or request.META.get("REMOTE_ADDR", "")
    )
    logger.info(
        "Click webhook hit method=%s path=%s action=%s ip=%s payload=%s",
        request.method,
        request.path,
        action,
        client_ip,
        _safe_payload_for_log(data),
    )

    if request.method == "GET" and not action:
        return JsonResponse(
            {
                "ok": True,
                "endpoint": "/api/click/webhook/",
                "message": "Webhook is alive. Click must send POST with action=0|1.",
            }
        )

    if request.method not in {"POST", "GET"}:
        return JsonResponse(
            {
                "ok": False,
                "error": "method_not_allowed",
                "message": "Use POST (or GET only for diagnostics).",
            },
            status=405,
        )

    if action == "0":
        return click_prepare(request)
    if action == "1":
        return click_complete(request)

    logger.warning("Click webhook rejected: unknown action=%s", action)
    return _click_response(
        error=ClickError.ACTION_NOT_FOUND,
        error_note="Action not found",
        click_trans_id=_request_post_value(data, "click_trans_id"),
        merchant_trans_id=_request_post_value(data, "merchant_trans_id"),
    )


def payment_success(request):
    click_trans_id = request.GET.get("click_trans_id", "")
    merchant_trans_id = request.GET.get("merchant_trans_id", "")
    transaction_param = request.GET.get("transaction_param", "")
    payment_status = request.GET.get("payment_status", "")
    error_code = request.GET.get("error", "")

    sub_request = None
    if merchant_trans_id:
        sub_request = SubscriptionRequest.objects.select_related("center").filter(
            merchant_trans_id=merchant_trans_id
        ).first()
    if not sub_request and transaction_param and transaction_param.isdigit():
        sub_request = SubscriptionRequest.objects.select_related("center").filter(
            pk=int(transaction_param)
        ).first()
    if not sub_request and merchant_trans_id.isdigit():
        sub_request = SubscriptionRequest.objects.select_related("center").filter(
            pk=int(merchant_trans_id)
        ).first()

    status_hint = (payment_status or "").strip().lower()
    is_cancelled_hint = status_hint in {"cancel", "cancelled", "canceled", "failed", "error"}
    is_negative_error = bool(str(error_code).strip().startswith("-"))
    if sub_request and sub_request.status == SubscriptionRequest.Status.CANCELLED:
        cancel_url = reverse("billing:payment_cancel")
        cancel_trans_id = sub_request.merchant_trans_id or str(sub_request.id)
        return redirect(f"{cancel_url}?merchant_trans_id={cancel_trans_id}&click_trans_id={click_trans_id}")
    if is_cancelled_hint or is_negative_error:
        cancel_url = reverse("billing:payment_cancel")
        return redirect(f"{cancel_url}?merchant_trans_id={merchant_trans_id}&click_trans_id={click_trans_id}")

    success_redirect_url = str(getattr(settings, "CLICK_SUCCESS_REDIRECT_URL", "")).strip() or "/platform/"
    return redirect(success_redirect_url)


def payment_cancel(request):
    click_trans_id = request.GET.get("click_trans_id", "")
    merchant_trans_id = request.GET.get("merchant_trans_id", "")
    transaction_param = request.GET.get("transaction_param", "")

    sub_request = None
    if merchant_trans_id:
        sub_request = SubscriptionRequest.objects.select_related("center").filter(
            merchant_trans_id=merchant_trans_id
        ).first()
    if not sub_request and transaction_param and transaction_param.isdigit():
        sub_request = SubscriptionRequest.objects.select_related("center").filter(
            pk=int(transaction_param)
        ).first()
    if not sub_request and merchant_trans_id.isdigit():
        sub_request = SubscriptionRequest.objects.select_related("center").filter(
            pk=int(merchant_trans_id)
        ).first()

    return render(
        request,
        "billing/payment_cancel.html",
        {
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id or (sub_request.merchant_trans_id if sub_request else ""),
            "sub_req": sub_request,
        },
    )
