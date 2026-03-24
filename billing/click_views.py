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
    activate_center_subscription_from_click,
    calculate_price,
    click_transaction_key_for_request,
)
from .telegram_notifications import send_payment_success_notification
from .utils import (
    ClickError,
    amounts_match,
    generate_merchant_trans_id,
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


def _service_id_is_valid(service_id: str) -> bool:
    expected_service_id = str(getattr(settings, "CLICK_SERVICE_ID", "")).strip()
    if not service_id:
        return True
    return service_id == expected_service_id


def _gateway_ids_are_valid(service_id: str, merchant_id: str) -> tuple[bool, str]:
    if not _service_id_is_valid(service_id):
        return False, "Invalid service_id"
    if not _merchant_id_is_valid(merchant_id):
        return False, "Invalid merchant_id"
    return True, ""


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
    merchant_trans_id = _request_value(data, "merchant_trans_id")
    service_id = _request_value(data, "service_id")
    merchant_id = _request_value(data, "merchant_id")
    action = _request_value(data, "action")
    amount = _request_value(data, "amount")
    sign_time = _request_value(data, "sign_time")
    sign_string = _request_value(data, "sign_string", "signature", "sign")

    current_host = request.get_host()
    client_ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")

    logger.info(
        "[CLICK] PREPARE received: host=%s ip=%s merchant_trans_id=%s click_trans_id=%s amount=%s",
        current_host, client_ip, merchant_trans_id, click_trans_id, amount
    )
    logger.debug("[CLICK] PREPARE payload: %s", _safe_payload_for_log(data))

    if request.method == "GET":
        return JsonResponse({
            "ok": True,
            "message": "Click PREPARE endpoint is active at root level.",
            "hint": "Click must send a POST request with payload. Browser GET is for diagnostics only.",
            "service_id": getattr(settings, "CLICK_SERVICE_ID", "not_set"),
            "merchant_id": getattr(settings, "CLICK_MERCHANT_ID", "not_set"),
        })

    if not data:
        logger.warning("[CLICK] PREPARE rejected: empty payload")
        return _click_response(error=ClickError.REQUEST_ERROR, error_note="Empty payload", click_trans_id="", merchant_trans_id="")

    try:
        sub_request, resolved_merchant_trans_id = _resolve_subscription_request(data, require_merchant_trans_id=True)
    except SubscriptionRequest.DoesNotExist:
        logger.warning("[CLICK] PREPARE rejected: order not found merchant_trans_id=%s", merchant_trans_id)
        return _click_response(
            error=ClickError.ORDER_NOT_FOUND,
            error_note="Order not found",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )
    except Exception as e:
        logger.warning("[CLICK] PREPARE rejected: invalid request %s", str(e))
        return _click_response(
            error=ClickError.REQUEST_ERROR,
            error_note=str(e),
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )

    logger.info(
        "[CLICK] PREPARE request resolved: request_id=%s center_id=%s user_id=%s status=%s",
        sub_request.id,
        sub_request.center_id,
        sub_request.user_id,
        sub_request.status,
    )

    if action != "0":
        logger.warning("[CLICK] PREPARE rejected: invalid action=%s", action)
        return _click_response(
            error=ClickError.ACTION_NOT_FOUND,
            error_note="Action not found",
            click_trans_id=click_trans_id,
            merchant_trans_id=resolved_merchant_trans_id,
        )

    ids_valid, ids_error = _gateway_ids_are_valid(service_id, merchant_id)
    if not ids_valid:
        logger.warning(
            "[CLICK] PREPARE rejected: %s request_id=%s service_id=%s merchant_id=%s",
            ids_error,
            sub_request.id,
            service_id,
            merchant_id,
        )
        return _click_response(
            error=ClickError.REQUEST_ERROR,
            error_note=ids_error,
            click_trans_id=click_trans_id,
            merchant_trans_id=resolved_merchant_trans_id,
        )

    # Signature Validation
    secret_key = str(getattr(settings, "CLICK_SECRET_KEY", "")).strip()
    sign_ok = verify_click_signature(
        sign_string=sign_string,
        click_trans_id=click_trans_id,
        service_id=service_id,
        secret_key=secret_key,
        merchant_trans_id=resolved_merchant_trans_id,
        amount=amount,
        action=action,
        sign_time=sign_time,
    )
    logger.info(
        "[CLICK] PREPARE signature_check request_id=%s result=%s",
        sub_request.id,
        sign_ok,
    )
    if not sign_ok:
        logger.warning("[CLICK] PREPARE rejected: signature mismatch request_id=%s", sub_request.id)
        return _click_response(
            error=ClickError.SIGN_CHECK_FAILED,
            error_note="Signature mismatch",
            click_trans_id=click_trans_id,
            merchant_trans_id=resolved_merchant_trans_id,
        )

    # Amount Validation
    expected_amount = _request_amount(sub_request)
    if not amounts_match(amount, expected_amount):
        logger.warning(
            "[CLICK] PREPARE rejected: amount mismatch request_id=%s expected=%s got=%s",
            sub_request.id, expected_amount, amount
        )
        return _click_response(
            error=ClickError.INVALID_AMOUNT,
            error_note="Amount mismatch",
            click_trans_id=click_trans_id,
            merchant_trans_id=resolved_merchant_trans_id,
        )

    # Status Validation
    if sub_request.status == SubscriptionRequest.Status.PAID:
        logger.info("[CLICK] PREPARE info: already paid request_id=%s", sub_request.id)
        return _click_response(
            error=ClickError.ALREADY_PAID,
            error_note="Already paid",
            click_trans_id=click_trans_id,
            merchant_trans_id=resolved_merchant_trans_id,
        )

    logger.info("[CLICK] PREPARE success: request_id=%s merchant_trans_id=%s", sub_request.id, resolved_merchant_trans_id)
    return _click_response(
        error=ClickError.SUCCESS,
        error_note="Success",
        click_trans_id=click_trans_id,
        merchant_trans_id=resolved_merchant_trans_id,
        merchant_prepare_id=str(sub_request.id),
    )


@csrf_exempt
def click_complete(request):
    data = _request_payload(request)
    click_trans_id = _request_value(data, "click_trans_id", "transaction_id")
    merchant_trans_id = _request_value(data, "merchant_trans_id")
    merchant_prepare_id = _request_value(data, "merchant_prepare_id")
    service_id = _request_value(data, "service_id")
    merchant_id = _request_value(data, "merchant_id")
    action = _request_value(data, "action")
    amount = _request_value(data, "amount")
    sign_time = _request_value(data, "sign_time")
    sign_string = _request_value(data, "sign_string", "signature", "sign")

    current_host = request.get_host()
    client_ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")

    logger.info(
        "[CLICK] COMPLETE received: host=%s ip=%s merchant_trans_id=%s click_trans_id=%s amount=%s",
        current_host, client_ip, merchant_trans_id, click_trans_id, amount
    )
    logger.debug("[CLICK] COMPLETE payload: %s", _safe_payload_for_log(data))

    if request.method == "GET":
        return JsonResponse({
            "ok": True,
            "message": "Click COMPLETE endpoint is active at root level.",
            "hint": "Click must send a POST request with payload. Browser GET is for diagnostics only.",
            "service_id": getattr(settings, "CLICK_SERVICE_ID", "not_set"),
            "merchant_id": getattr(settings, "CLICK_MERCHANT_ID", "not_set"),
        })

    if not data:
        logger.warning("[CLICK] COMPLETE rejected: empty payload")
        return _click_response(error=ClickError.REQUEST_ERROR, error_note="Empty payload", click_trans_id="", merchant_trans_id="")

    try:
        sub_request, resolved_merchant_trans_id = _resolve_subscription_request(data, require_merchant_trans_id=True)
    except SubscriptionRequest.DoesNotExist:
        logger.warning("[CLICK] COMPLETE rejected: order not found merchant_trans_id=%s", merchant_trans_id)
        return _click_response(
            error=ClickError.ORDER_NOT_FOUND,
            error_note="Order not found",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )
    except Exception as e:
        logger.warning("[CLICK] COMPLETE rejected: invalid request %s", str(e))
        return _click_response(
            error=ClickError.REQUEST_ERROR,
            error_note=str(e),
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
        )

    logger.info(
        "[CLICK] COMPLETE request resolved: request_id=%s center_id=%s user_id=%s status=%s",
        sub_request.id,
        sub_request.center_id,
        sub_request.user_id,
        sub_request.status,
    )

    if action != "1":
        logger.warning("[CLICK] COMPLETE rejected: invalid action=%s", action)
        return _click_response(
            error=ClickError.ACTION_NOT_FOUND,
            error_note="Action not found",
            click_trans_id=click_trans_id,
            merchant_trans_id=resolved_merchant_trans_id,
        )

    ids_valid, ids_error = _gateway_ids_are_valid(service_id, merchant_id)
    if not ids_valid:
        logger.warning(
            "[CLICK] COMPLETE rejected: %s request_id=%s service_id=%s merchant_id=%s",
            ids_error,
            sub_request.id,
            service_id,
            merchant_id,
        )
        return _click_response(
            error=ClickError.REQUEST_ERROR,
            error_note=ids_error,
            click_trans_id=click_trans_id,
            merchant_trans_id=resolved_merchant_trans_id,
        )

    # Signature Validation
    secret_key = str(getattr(settings, "CLICK_SECRET_KEY", "")).strip()
    sign_ok = verify_click_signature(
        sign_string=sign_string,
        click_trans_id=click_trans_id,
        service_id=service_id,
        secret_key=secret_key,
        merchant_trans_id=resolved_merchant_trans_id,
        merchant_prepare_id=merchant_prepare_id,
        amount=amount,
        action=action,
        sign_time=sign_time,
    )
    logger.info(
        "[CLICK] COMPLETE signature_check request_id=%s result=%s",
        sub_request.id,
        sign_ok,
    )
    if not sign_ok:
        logger.warning("[CLICK] COMPLETE rejected: signature mismatch request_id=%s", sub_request.id)
        return _click_response(
            error=ClickError.SIGN_CHECK_FAILED,
            error_note="Signature mismatch",
            click_trans_id=click_trans_id,
            merchant_trans_id=resolved_merchant_trans_id,
        )

    # Prepare ID Validation
    expected_prepare_id = str(sub_request.id)
    if merchant_prepare_id != expected_prepare_id:
        logger.warning("[CLICK] COMPLETE rejected: prepare_id mismatch request_id=%s expected=%s got=%s", sub_request.id, expected_prepare_id, merchant_prepare_id)
        return _click_response(
            error=ClickError.PREPARE_ID_INVALID,
            error_note="Incorrect merchant_prepare_id",
            click_trans_id=click_trans_id,
            merchant_trans_id=resolved_merchant_trans_id,
        )

    # Click Error Check
    try:
        click_error = int(str(data.get("error") or "0").strip() or 0)
    except ValueError:
        logger.warning("[CLICK] COMPLETE rejected: invalid error code request_id=%s raw_error=%s", sub_request.id, data.get("error"))
        return _click_response(error=ClickError.REQUEST_ERROR, error_note="Invalid error code", click_trans_id=click_trans_id, merchant_trans_id=resolved_merchant_trans_id)

    if click_error < 0:
        logger.warning("[CLICK] COMPLETE cancelled by Click: request_id=%s error=%s note=%s", sub_request.id, click_error, data.get("error_note"))
        with transaction.atomic():
            sub_request = SubscriptionRequest.objects.select_for_update().get(pk=sub_request.id)
            if sub_request.status == SubscriptionRequest.Status.PENDING:
                sub_request.status = SubscriptionRequest.Status.CANCELLED
                sub_request.save(update_fields=["status", "updated_at"])
        return _click_response(error=click_error, error_note=data.get("error_note", "Cancelled"), click_trans_id=click_trans_id, merchant_trans_id=resolved_merchant_trans_id)

    # Main Processing
    try:
        with transaction.atomic():
            sub_request = SubscriptionRequest.objects.select_for_update().select_related("user", "center", "plan").get(pk=sub_request.id)

            # Amount Re-validation
            expected_amount = _request_amount(sub_request)
            if not amounts_match(amount, expected_amount):
                logger.warning(
                    "[CLICK] COMPLETE rejected: amount mismatch request_id=%s expected=%s got=%s",
                    sub_request.id,
                    expected_amount,
                    amount,
                )
                return _click_response(
                    error=ClickError.INVALID_AMOUNT,
                    error_note="Amount mismatch",
                    click_trans_id=click_trans_id,
                    merchant_trans_id=resolved_merchant_trans_id,
                )

            plan = _resolve_plan_for_request(sub_request)
            if not plan:
                logger.error("[CLICK] COMPLETE failed: plan not found request_id=%s", sub_request.id)
                return _click_response(error=ClickError.ORDER_NOT_FOUND, error_note="Plan not found", click_trans_id=click_trans_id, merchant_trans_id=resolved_merchant_trans_id)

            tx_id = click_transaction_key_for_request(sub_request.id)
            existing_tx = (
                PaymentTransaction.objects
                .select_for_update()
                .filter(transaction_id=tx_id)
                .first()
            )

            # Idempotency: this request has already been finalized before.
            if sub_request.status == SubscriptionRequest.Status.PAID:
                if existing_tx:
                    if existing_tx.status != PaymentTransaction.Status.PAID or existing_tx.amount != expected_amount:
                        existing_tx.status = PaymentTransaction.Status.PAID
                        existing_tx.amount = expected_amount
                        existing_tx.click_trans_id = (click_trans_id or "")[:64]
                        existing_tx.paid_at = existing_tx.paid_at or timezone.now()
                        existing_tx.save(update_fields=["status", "amount", "click_trans_id", "paid_at"])
                else:
                    PaymentTransaction.objects.create(
                        transaction_id=tx_id,
                        user=sub_request.user,
                        amount=expected_amount,
                        status=PaymentTransaction.Status.PAID,
                        click_trans_id=(click_trans_id or "")[:64],
                        paid_at=timezone.now(),
                    )

                logger.info(
                    "[CLICK] COMPLETE success (idempotent): request_id=%s tx_id=%s",
                    sub_request.id,
                    tx_id,
                )
                return _click_response(
                    error=ClickError.SUCCESS,
                    error_note="Success",
                    click_trans_id=click_trans_id,
                    merchant_trans_id=resolved_merchant_trans_id,
                    merchant_confirm_id=str(sub_request.id),
                )

            if existing_tx and existing_tx.status == PaymentTransaction.Status.PAID:
                # Safety net: if transaction was paid but request status lagged behind.
                sub_request.status = SubscriptionRequest.Status.PAID
                sub_request.save(update_fields=["status", "updated_at"])
                logger.warning(
                    "[CLICK] COMPLETE idempotent recovery: request_id=%s had pending status but paid transaction exists tx_id=%s",
                    sub_request.id,
                    tx_id,
                )
                return _click_response(
                    error=ClickError.SUCCESS,
                    error_note="Success",
                    click_trans_id=click_trans_id,
                    merchant_trans_id=resolved_merchant_trans_id,
                    merchant_confirm_id=str(sub_request.id),
                )

            normalized_months = sub_request.duration_months if sub_request.duration_months in DURATIONS else 1
            activation_result = activate_center_subscription_from_click(
                sub_request=sub_request,
                plan=plan,
                click_trans_id=click_trans_id,
                payment_amount=expected_amount,
                duration_months=normalized_months,
            )

            # Finalize Request
            sub_request.status = SubscriptionRequest.Status.PAID
            update_fields = ["status", "updated_at"]
            if not sub_request.plan_id:
                sub_request.plan = plan
                update_fields.append("plan")
            sub_request.save(update_fields=update_fields)

            notification_end_date = (
                activation_result.owner_subscription_end_date
                or activation_result.new_end_date.date()
            )

            # Telegram Notification
            transaction.on_commit(lambda: send_payment_success_notification(
                user=sub_request.user,
                plan_name=plan.name or plan.title or plan.code,
                end_date=notification_end_date,
            ))

            logger.info(
                (
                    "[CLICK] COMPLETE success: request_id=%s user_id=%s center_id=%s "
                    "old_end_date=%s new_end_date=%s tx_id=%s order_id=%s"
                ),
                sub_request.id,
                sub_request.user_id,
                sub_request.center_id,
                activation_result.old_end_date.isoformat() if activation_result.old_end_date else None,
                activation_result.new_end_date.isoformat(),
                activation_result.transaction_id,
                activation_result.order_id,
            )
            return _click_response(
                error=ClickError.SUCCESS,
                error_note="Success",
                click_trans_id=click_trans_id,
                merchant_trans_id=resolved_merchant_trans_id,
                merchant_confirm_id=str(sub_request.id),
            )

    except Exception:
        logger.exception("[CLICK] COMPLETE error: request_id=%s", sub_request.id)
        return _click_response(error=ClickError.REQUEST_ERROR, error_note="Internal error", click_trans_id=click_trans_id, merchant_trans_id=resolved_merchant_trans_id)


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
