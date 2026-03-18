from __future__ import annotations

import hashlib
import secrets
from decimal import Decimal, InvalidOperation
from hmac import compare_digest

from django.db import transaction
from django.utils import timezone

from .models import Subscription, SubscriptionPlan


class ClickError:
    SUCCESS = 0
    SIGN_CHECK_FAILED = -1
    INVALID_AMOUNT = -2
    ACTION_NOT_FOUND = -3
    ALREADY_PAID = -4
    ORDER_NOT_FOUND = -5
    PREPARE_ID_INVALID = -6
    REQUEST_ERROR = -8
    TRANSACTION_CANCELLED = -9


def parse_click_amount(raw_amount: str | None) -> Decimal:
    raw_amount = (raw_amount or "").strip()
    if not raw_amount:
        raise ValueError("amount is required")

    try:
        amount = Decimal(raw_amount)
    except InvalidOperation as exc:
        raise ValueError("amount is invalid") from exc

    if amount <= 0:
        raise ValueError("amount must be positive")

    return amount


def amounts_match(request_amount: str | None, expected_amount: int) -> bool:
    try:
        incoming_amount = parse_click_amount(request_amount)
    except ValueError:
        return False
    return incoming_amount == Decimal(expected_amount)


def _sign_payload(
    click_trans_id: str,
    service_id: str,
    secret_key: str,
    merchant_trans_id: str,
    amount: str,
    action: str,
    sign_time: str,
    merchant_prepare_id: str = "",
) -> str:
    base_parts = [click_trans_id, service_id, secret_key, merchant_trans_id]
    if merchant_prepare_id:
        base_parts.append(merchant_prepare_id)
    base_parts.extend([amount, action, sign_time])
    return "".join(base_parts)


def verify_click_signature(
    sign_string: str,
    click_trans_id: str,
    service_id: str,
    secret_key: str,
    merchant_trans_id: str,
    amount: str,
    action: str,
    sign_time: str,
    merchant_prepare_id: str = "",
) -> bool:
    if not secret_key:
        return False

    payload = _sign_payload(
        click_trans_id=click_trans_id,
        service_id=service_id,
        secret_key=secret_key,
        merchant_trans_id=merchant_trans_id,
        amount=amount,
        action=action,
        sign_time=sign_time,
        merchant_prepare_id=merchant_prepare_id,
    )
    sign_string = (sign_string or "").strip().lower()

    md5_sign = hashlib.md5(payload.encode("utf-8")).hexdigest().lower()
    return compare_digest(sign_string, md5_sign)


def generate_merchant_trans_id(order_id: int) -> str:
    """
    Generate a unique Click merchant transaction id.
    Format: ORD-{order_id}-{YYYYMMDDHHMMSSffffff}-{RANDOM_HEX}
    """
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S%f")
    random_suffix = secrets.token_hex(4).upper()
    return f"ORD-{order_id}-{timestamp}-{random_suffix}"


@transaction.atomic
def give_subscription(user, plan: SubscriptionPlan) -> Subscription:
    """
    Give or extend a user's subscription.

    Rules:
    - If user has active and non-expired subscription: extend end_date by plan.duration_days.
    - If expired (or missing): start from today for plan.duration_days.
    """
    today = timezone.localdate()
    duration_days = int(getattr(plan, "duration_days", 0) or 0)
    if duration_days <= 0:
        duration_days = 30

    active_sub = (
        Subscription.objects.select_for_update()
        .filter(user=user, is_active=True)
        .order_by("-end_date", "-id")
        .first()
    )

    if active_sub and active_sub.end_date and active_sub.end_date >= today:
        active_sub.plan = plan
        active_sub.end_date = active_sub.end_date + timezone.timedelta(days=duration_days)
        active_sub.is_active = True
        active_sub.save(update_fields=["plan", "end_date", "is_active"])
        return active_sub

    # Expired or missing subscription: reset active flags and create a new active period.
    Subscription.objects.select_for_update().filter(user=user, is_active=True).update(is_active=False)
    return Subscription.objects.create(
        user=user,
        plan=plan,
        start_date=today,
        end_date=today + timezone.timedelta(days=duration_days),
        is_active=True,
    )
