# billing/services.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from django.db import models
from django.db.models import Q
import logging

from accounts.models import Center
from .models import (
    SubscriptionPlan,
    CenterSubscription,
    PromoCode,
    SubscriptionOrder,
    PlanFeature,
    Subscription,
    PaymentTransaction,
    SubscriptionRequest,
)


# ============================================================
# FEATURE SERVICES — Professional Feature Flag System
# ============================================================

def get_plan_features(plan: SubscriptionPlan) -> list[dict]:
    """
    Planga bog'liq barcha featurelarni kategoriyalar bo'yicha qaytaradi.
    Returns: [{"code":..., "name":..., "category":..., "is_core":..., "enabled": True/False}, ...]
    """
    all_features = PlanFeature.objects.all().order_by("category", "order", "name")
    enabled_codes = set(plan.plan_features.values_list("code", flat=True))
    result = []
    for f in all_features:
        result.append({
            "id": f.id,
            "code": f.code,
            "name": f.name,
            "description": f.description,
            "category": f.category,
            "category_display": f.get_category_display(),
            "is_core": f.is_core,
            "enabled": f.code in enabled_codes,
        })
    return result


def apply_plan_to_center(center: Center, plan: SubscriptionPlan) -> None:
    """
    Markazga tarif biriktirilganda — tarifning featurelari markazga avtomatik qo'llanadi.
    Center.features JSONField ham sinxronlanadi (backward-compat).
    """
    enabled_codes = set(plan.plan_features.values_list("code", flat=True))
    current_overrides = center.features or {}

    # Rebuild center.features: plan features = True, missing = False (unless manually overridden)
    new_features = {}
    all_features = PlanFeature.objects.all()
    for f in all_features:
        if f.code in current_overrides:
            # Manual override preserved
            new_features[f.code] = current_overrides[f.code]
        else:
            new_features[f.code] = f.code in enabled_codes

    center.features = new_features
    center.save(update_fields=["features"])


def can_center_use_feature(center: Center, feature_code: str) -> bool:
    """
    Markazda ma'lum bir feature ishlash-yo'qligini tekshiradi.
    Priority: center.features (manual overrides) > plan.plan_features
    """
    # 1. Check explicit manual override in center.features JSONField
    center_features = center.features or {}
    if feature_code in center_features:
        return bool(center_features[feature_code])

    # 2. Check active subscription plan's M2M features
    sub = get_active_subscription(center)
    if sub and sub.plan:
        return sub.plan.plan_features.filter(code=feature_code).exists()

    return False


# ============================================================
# SUBSCRIPTION HELPERS (No cached_property)
# ============================================================

def get_active_subscription(center: Center) -> CenterSubscription | None:
    """
    Returns the currently ACTIVE center subscription from DB.
    """
    return CenterSubscription.objects.filter(
        center=center,
        status=CenterSubscription.Status.ACTIVE
    ).select_related("plan").order_by("-expires_at", "-id").first()


def get_paused_subscription(center: Center) -> CenterSubscription | None:
    """
    Returns the best candidate for resumption (PAUSED with remaining time).
    Priority: Highest Tier first, then oldest started_at.
    """
    return CenterSubscription.objects.filter(
        center=center,
        status=CenterSubscription.Status.PAUSED,
        remaining_seconds__gt=0
    ).select_related("plan").order_by("-plan__tier", "started_at").first()




DURATIONS = [1, 3, 6, 9, 12]


# ============================================================
# UPGRADE CREDIT CONVERSION
# ============================================================

from decimal import Decimal, ROUND_DOWN


def calculate_upgrade_preview(
    active_sub: "CenterSubscription",
    new_plan: "SubscriptionPlan",
    paid_days: int = 0,
) -> dict:
    """
    Upgrade qilganda qolgan kreditni yangi tarifga konvertatsiya qilish.

    Formula:
      old_daily  = old_plan.monthly_price / 30
      credit     = old_daily * remaining_days
      new_daily  = new_plan.monthly_price / 30
      new_days   = credit / new_daily
      total_days = new_days + paid_days (to'langan yangi muddat)

    Faqat upgrade (new_plan.tier > active_sub.plan.tier) uchun ishlaydi.

    Returns dict:
      {
        "is_upgrade": bool,
        "old_plan_title": str,
        "old_monthly_price": int,
        "old_daily_price": Decimal,
        "remaining_days": int,
        "remaining_credit": Decimal,
        "new_plan_title": str,
        "new_monthly_price": int,
        "new_daily_price": Decimal,
        "credit_days": int,          # qolgan kredit → yangi tarifda kun
        "paid_days": int,            # to'langan yangi tarif kunlari
        "total_new_days": int,       # credit_days + paid_days
        "new_expires_at": datetime,  # bugundan boshlab total_new_days
      }
    """
    now = timezone.now()

    is_upgrade = (
        active_sub is not None
        and new_plan.tier > active_sub.plan.tier
        and active_sub.expires_at > now
    )

    if not is_upgrade or not active_sub:
        return {
            "is_upgrade": False,
            "remaining_days": 0,
            "remaining_credit": Decimal(0),
            "credit_days": 0,
            "paid_days": paid_days,
            "total_new_days": paid_days,
            "new_expires_at": now + timezone.timedelta(days=paid_days),
        }

    old_monthly = Decimal(active_sub.plan.monthly_price or 0)
    new_monthly = Decimal(new_plan.monthly_price or 0)

    # Remaining days (floor, no negative)
    remaining_days = max(0, (active_sub.expires_at.date() - now.date()).days)

    if old_monthly <= 0 or new_monthly <= 0 or remaining_days <= 0:
        return {
            "is_upgrade": False,
            "remaining_days": remaining_days,
            "remaining_credit": Decimal(0),
            "credit_days": 0,
            "paid_days": paid_days,
            "total_new_days": paid_days,
            "new_expires_at": now + timezone.timedelta(days=paid_days),
        }

    old_daily = old_monthly / Decimal(30)
    new_daily = new_monthly / Decimal(30)
    remaining_credit = old_daily * remaining_days
    credit_days_exact = remaining_credit / new_daily
    credit_days = int(credit_days_exact.to_integral_value(rounding=ROUND_DOWN))

    total_new_days = credit_days + paid_days
    new_expires_at = now + timezone.timedelta(days=total_new_days)

    return {
        "is_upgrade": True,
        "old_plan_title": active_sub.plan.title,
        "old_monthly_price": int(old_monthly),
        "old_daily_price": old_daily.quantize(Decimal("0.01")),
        "remaining_days": remaining_days,
        "remaining_credit": remaining_credit.quantize(Decimal("1")),
        "new_plan_title": new_plan.title,
        "new_monthly_price": int(new_monthly),
        "new_daily_price": new_daily.quantize(Decimal("0.01")),
        "credit_days": credit_days,
        "paid_days": paid_days,
        "total_new_days": total_new_days,
        "new_expires_at": new_expires_at,
    }

FEATURES_BY_PLAN = {
    "FREE": set(),
    "STANDARD": {"finance", "tasks"},
    "PREMIUM": {"finance", "tasks", "leads"},
    "PRO": {"finance", "tasks", "leads", "kpi", "store", "sms"},
    "START": set(),
    "ENTERPRISE": {"finance", "tasks", "leads", "kpi", "store", "sms"},
}

@dataclass
class PricingResult:
    base_price: int
    discount_percent: int
    final_price: int
    promo: PromoCode | None


@dataclass
class ClickSubscriptionActivationResult:
    old_end_date: datetime | None
    new_end_date: datetime
    center_subscription_id: int
    transaction_id: str
    payment_transaction_id: int
    order_id: int
    owner_subscription_end_date: date | None


def click_transaction_key_for_request(request_id: int) -> str:
    """
    Stable idempotency key for Click callbacks.
    Same request must always map to one PaymentTransaction.
    """
    return f"click:req:{int(request_id)}"


def _resolve_plan(plan: SubscriptionPlan | int | str) -> SubscriptionPlan:
    if isinstance(plan, SubscriptionPlan):
        if not plan.pk:
            raise ValidationError("Subscription plan does not exist.")
        return plan

    if isinstance(plan, int):
        resolved = SubscriptionPlan.objects.filter(pk=plan, active=True).first()
    else:
        plan_key = str(plan or "").strip()
        resolved = SubscriptionPlan.objects.filter(
            Q(code__iexact=plan_key) | Q(name__iexact=plan_key) | Q(title__iexact=plan_key),
            active=True,
        ).order_by("-id").first()

    if not resolved:
        raise ValidationError("Subscription plan not found or inactive.")
    return resolved


@transaction.atomic
def activate_subscription(
    user,
    plan: SubscriptionPlan | int | str,
    start_date: date | datetime | None = None,
) -> Subscription:
    """
    Activates a user subscription:
    1) deactivates old active subscriptions
    2) creates a new active subscription
    3) auto-calculates end_date from plan.duration_days
    """
    if not user or not getattr(user, "pk", None):
        raise ValidationError("Valid user is required.")

    plan_obj = _resolve_plan(plan)

    if start_date is None:
        start = timezone.localdate()
    elif isinstance(start_date, datetime):
        start = start_date.date()
    else:
        start = start_date

    Subscription.objects.select_for_update().filter(user_id=user.pk, is_active=True).update(is_active=False)

    subscription = Subscription.objects.create(
        user=user,
        plan=plan_obj,
        start_date=start,
        is_active=True,
    )
    return subscription


def check_subscription(user) -> Subscription | None:
    """
    Returns active subscription for user.
    If expired, deactivates it automatically and returns None.
    """
    if not user or not getattr(user, "pk", None):
        return None

    sub = (
        Subscription.objects
        .filter(user_id=user.pk, is_active=True)
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )
    if not sub:
        return None

    today = timezone.localdate()
    if sub.end_date and sub.end_date < today:
        Subscription.objects.filter(pk=sub.pk).update(is_active=False)
        return None

    return sub


def get_subscription_owner_for_center(center: Center, actor=None):
    """
    Resolves which user's subscription should be used for center-level limits.
    Priority:
    1) director of center
    2) actor in same center
    3) manager of center
    """
    if not center:
        return None

    UserModel = get_user_model()
    owner = UserModel.objects.filter(center=center, role="director").order_by("id").first()
    if owner:
        return owner

    if actor and getattr(actor, "center_id", None) == center.id:
        return actor

    return UserModel.objects.filter(center=center, role="manager").order_by("id").first()


def get_student_limit_for_user(user, free_limit: int = 50) -> int:
    sub = check_subscription(user)
    if not sub or not sub.plan:
        return free_limit

    plan_code = (sub.plan.code or sub.plan.name or sub.plan.title or "").upper()
    if plan_code == "FREE":
        return free_limit

    return sub.plan.max_students or free_limit


def get_center_student_limit(center: Center, actor=None, free_limit: int = 50) -> int:
    """
    Student limit policy:
    - FREE  -> 50
    - PRO/* -> plan.max_students
    """
    owner = get_subscription_owner_for_center(center=center, actor=actor)
    if owner:
        return get_student_limit_for_user(owner, free_limit=free_limit)

    # Backward compatibility fallback for older center-based subscriptions.
    sub = get_active_subscription(center)
    if sub and getattr(sub, "plan", None):
        plan_code = (sub.plan.code or sub.plan.name or sub.plan.title or "").upper()
        if plan_code == "FREE":
            return free_limit
        return sub.plan.max_students or free_limit
    return free_limit


def get_user_subscription_dashboard_data(user) -> dict:
    """
    Dashboard payload for frontend/API:
    - current plan
    - start_date
    - end_date
    - remaining_days
    """
    sub = check_subscription(user)
    if not sub:
        return {
            "has_active_subscription": False,
            "plan": "FREE",
            "start_date": None,
            "end_date": None,
            "remaining_days": 0,
        }

    return {
        "has_active_subscription": True,
        "plan": sub.plan.name or sub.plan.title or sub.plan.code,
        "plan_code": sub.plan.code,
        "start_date": sub.start_date,
        "end_date": sub.end_date,
        "remaining_days": sub.remaining_days,
    }


def get_billing_history(user):
    if not user or not getattr(user, "pk", None):
        return PaymentTransaction.objects.none()
    return PaymentTransaction.objects.filter(user_id=user.pk).order_by("-created_at")


def get_plan_list_payload() -> list[dict]:
    plans = SubscriptionPlan.objects.filter(active=True).order_by("price", "monthly_price", "id")
    payload = []
    for plan in plans:
        payload.append({
            "id": plan.id,
            "code": plan.code,
            "name": plan.name or plan.title,
            "price": plan.price or plan.monthly_price,
            "duration_days": plan.duration_days,
            "max_students": plan.max_students,
        })
    return payload


def ensure_center_subscription(center: Center) -> CenterSubscription | None:
    """
    Ensure at least one subscription exists. IF no active/paused sub exists, create FREE one.
    """
    try:
        # Check active or paused
        sub = CenterSubscription.objects.filter(
            center=center,
            status__in=[
                CenterSubscription.Status.ACTIVE,
                CenterSubscription.Status.PAUSED
            ]
        ).order_by("-started_at").first()
        if sub:
            return sub

        # Fallback plan
        allowed_plans = ["FREE", "STANDARD", "PREMIUM", "PRO", "START", "ENTERPRISE"]
        plan_code = center.plan if center.plan in allowed_plans else "FREE"
        
        plan = SubscriptionPlan.objects.filter(code=plan_code, active=True).first()
        if not plan:
            plan = SubscriptionPlan.objects.order_by("monthly_price").first()

        if not plan:
            return None

        # Create new ACTIVE subscription
        sub = CenterSubscription.objects.create(
            center=center, 
            plan=plan,
            status=CenterSubscription.Status.ACTIVE,
            started_at=timezone.now(),
            expires_at=default_trial_expires()
        )
        return sub
    except Exception as e:
        logging.error(f"ensure_center_subscription error: {str(e)}")
        return None

def default_trial_expires():
    return timezone.now() + timezone.timedelta(days=7)


def get_feature_flags(center: Center) -> set[str]:
    sub = get_active_subscription(center)
    # Fallback to center.plan if no active sub exists
    code = sub.plan.code if (sub and sub.plan) else center.plan
    
    features = FEATURES_BY_PLAN.get(code, set()).copy()
    manual_features = getattr(center, 'features', {}) or {}
    for feature_name, enabled in manual_features.items():
        if enabled:
            features.add(feature_name)
        elif feature_name in features:
            features.remove(feature_name)
    
    return features


def validate_promocode(code: str, plan: SubscriptionPlan, center: Center | None = None) -> PromoCode | None:
    code = (code or "").strip().upper()
    if not code: return None
    promo = PromoCode.objects.filter(code=code).first()
    if not promo or not promo.is_valid_now(): return None
    
    if promo.plans.exists() and not promo.plans.filter(id=plan.id).exists():
        return None

    if center and promo.once_per_center:
        already_used = SubscriptionOrder.objects.filter(
            center=center, 
            promo=promo, 
            status=SubscriptionOrder.Status.PAID
        ).exists()
        if already_used: return None

    return promo


def calculate_price(plan: SubscriptionPlan, months: int, promo_code: str | None, center: Center | None = None) -> PricingResult:
    months = int(months or 1)
    if months not in DURATIONS: months = 1

    base_price = plan.monthly_price * months
    promo = validate_promocode(promo_code or "", plan, center=center)
    
    plan_discount = getattr(plan, 'discount_percent', 0) or 0
    promo_discount = promo.percent_off if promo else 0
    total_discount = min(plan_discount + promo_discount, 100)
    
    final_price = int(base_price * (100 - total_discount) / 100)
    return PricingResult(base_price, total_discount, final_price, promo)


@transaction.atomic
def create_order(center: Center, plan: SubscriptionPlan, months: int, promo_code: str | None) -> SubscriptionOrder:
    pricing = calculate_price(plan, months, promo_code, center=center)
    order = SubscriptionOrder.objects.create(
        center=center,
        plan=plan,
        duration_months=months,
        base_price=pricing.base_price,
        discount_percent=pricing.discount_percent,
        final_price=pricing.final_price,
        promo=pricing.promo,
        status=SubscriptionOrder.Status.PENDING,
    )
    return order


@transaction.atomic
def activate_center_subscription_from_click(
    *,
    sub_request: SubscriptionRequest,
    plan: SubscriptionPlan,
    click_trans_id: str,
    payment_amount: int,
    duration_months: int,
) -> ClickSubscriptionActivationResult:
    """
    Deterministic center extension logic for successful Click callback.
    Rules:
    - if current end date is in the future -> extend from current end date
    - else -> start from now
    """
    logger = logging.getLogger(__name__)
    now = timezone.now()

    months = int(duration_months or 1)
    if months not in DURATIONS:
        months = 1

    duration_days = int(getattr(plan, "duration_days", 0) or 0)
    if duration_days <= 0:
        duration_days = 30
    total_days = duration_days * months

    center = Center.objects.select_for_update().get(pk=sub_request.center_id)
    active_sub = (
        CenterSubscription.objects
        .select_for_update()
        .select_related("plan")
        .filter(center_id=center.id, status=CenterSubscription.Status.ACTIVE)
        .order_by("-expires_at", "-id")
        .first()
    )

    old_end_date = active_sub.expires_at if active_sub else center.expires_at

    # ── Upgrade credit conversion ──────────────────────────────────────────
    # If upgrading (new plan tier > current plan tier) and there is remaining
    # time, convert the old credit into new plan days instead of stacking.
    is_upgrade = (
        active_sub is not None
        and plan.tier > active_sub.plan.tier
        and active_sub.expires_at > now
    )

    if is_upgrade:
        preview = calculate_upgrade_preview(
            active_sub=active_sub,
            new_plan=plan,
            paid_days=total_days,
        )
        final_total_days = preview["total_new_days"]
        logger.info(
            "Click upgrade conversion: center=%s old=%s→new=%s "
            "remaining_days=%s credit=%s credit_days=%s paid_days=%s total=%s",
            center.id,
            active_sub.plan.code, plan.code,
            preview["remaining_days"],
            preview["remaining_credit"],
            preview["credit_days"],
            total_days,
            final_total_days,
        )
        new_end_date = now + timezone.timedelta(days=final_total_days)

        # Expire old subscription — credit already converted
        active_sub.status = CenterSubscription.Status.EXPIRED
        active_sub.save(update_fields=["status"])

        target_sub = CenterSubscription.objects.create(
            center=center,
            plan=plan,
            status=CenterSubscription.Status.ACTIVE,
            started_at=now,
            expires_at=new_end_date,
            paused_at=None,
            remaining_seconds=0,
            manual_block=False,
        )
    elif active_sub:
        # Same tier (extend) or downgrade → old logic
        base_date = old_end_date if old_end_date and old_end_date > now else now
        new_end_date = base_date + timezone.timedelta(days=total_days)
        is_fresh_period = not active_sub.expires_at or active_sub.expires_at <= now
        if is_fresh_period:
            active_sub.started_at = now
        active_sub.plan = plan
        active_sub.status = CenterSubscription.Status.ACTIVE
        active_sub.expires_at = new_end_date
        active_sub.paused_at = None
        active_sub.remaining_seconds = 0
        active_sub.manual_block = False
        active_sub.save(
            update_fields=[
                "plan",
                "status",
                "started_at",
                "expires_at",
                "paused_at",
                "remaining_seconds",
                "manual_block",
            ]
        )
        target_sub = active_sub
    else:
        base_date = old_end_date if old_end_date and old_end_date > now else now
        new_end_date = base_date + timezone.timedelta(days=total_days)
        target_sub = CenterSubscription.objects.create(
            center=center,
            plan=plan,
            status=CenterSubscription.Status.ACTIVE,
            started_at=now,
            expires_at=new_end_date,
            paused_at=None,
            remaining_seconds=0,
            manual_block=False,
        )

    center.plan = plan.code
    center.max_users = plan.max_users
    center.max_groups = plan.max_groups
    center.max_students = plan.max_students
    center.status = Center.STATUS_ACTIVE
    center.expires_at = new_end_date
    center.monthly_price = plan.monthly_price
    center.save(
        update_fields=[
            "plan",
            "max_users",
            "max_groups",
            "max_students",
            "status",
            "expires_at",
            "monthly_price",
        ]
    )

    # Keep feature flags in sync with selected plan.
    apply_plan_to_center(center, plan)

    tx_id = click_transaction_key_for_request(sub_request.id)
    paid_at = now
    payment_tx, _ = PaymentTransaction.objects.select_for_update().update_or_create(
        transaction_id=tx_id,
        defaults={
            "user": sub_request.user,
            "amount": int(payment_amount),
            "status": PaymentTransaction.Status.PAID,
            "click_trans_id": (click_trans_id or "")[:64],
            "paid_at": paid_at,
        },
    )

    promo = None
    promo_code = (sub_request.promo_code or "").strip()
    if promo_code:
        promo = PromoCode.objects.filter(code__iexact=promo_code).first()

    base_price = int((plan.monthly_price or plan.price or 0) * months)
    if base_price <= 0:
        base_price = int(payment_amount)
    discount_percent = 0
    if base_price > 0 and payment_amount < base_price:
        discount_percent = int(round((base_price - payment_amount) * 100 / base_price))
        discount_percent = max(0, min(100, discount_percent))

    order = SubscriptionOrder.objects.create(
        center=center,
        plan=plan,
        duration_months=months,
        base_price=base_price,
        discount_percent=discount_percent,
        final_price=int(payment_amount),
        promo=promo,
        status=SubscriptionOrder.Status.PAID,
        paid_at=paid_at,
    )

    from .utils import give_subscription

    owner = get_subscription_owner_for_center(center=center, actor=sub_request.user)
    owner_sub = None
    if owner:
        owner_sub = give_subscription(owner, plan, duration_months=months)

    logger.info(
        (
            "Click subscription activation applied: request_id=%s center_id=%s "
            "center_sub_id=%s old_end_date=%s new_end_date=%s total_days=%s "
            "payment_tx_id=%s order_id=%s"
        ),
        sub_request.id,
        center.id,
        target_sub.id,
        old_end_date.isoformat() if old_end_date else None,
        new_end_date.isoformat(),
        total_days,
        payment_tx.id,
        order.id,
    )

    return ClickSubscriptionActivationResult(
        old_end_date=old_end_date,
        new_end_date=new_end_date,
        center_subscription_id=target_sub.id,
        transaction_id=tx_id,
        payment_transaction_id=payment_tx.id,
        order_id=order.id,
        owner_subscription_end_date=owner_sub.end_date if owner_sub else None,
    )


@transaction.atomic
def mark_order_paid(order: SubscriptionOrder) -> None:
    """
    PAID Logic with PAUSE/RESUME support.
    Explicit DB queries, no cached_property.
    """
    import logging
    from .utils import give_subscription
    
    logger = logging.getLogger(__name__)
    
    print(f"🔥 PAID START - Order ID: {order.id}")
    logger.info("mark_order_paid started: order_id=%s center=%s", order.id, order.center.slug)

    if order.status == SubscriptionOrder.Status.PAID:
        print(f"ℹ️ Order {order.id} is already marked as PAID. Skipping.")
        return

    try:
        now = timezone.now()
        center = order.center
        new_plan = order.plan
        duration_months = int(order.duration_months or 1)
        duration_days = 30 * duration_months

        # 1. Update Order Status
        print(f"👉 Order: {order.id}, Center: {center.slug}, Plan: {new_plan.code}")
        order.status = SubscriptionOrder.Status.PAID
        order.paid_at = now
        order.save(update_fields=["status", "paid_at"])
        print(f"✅ Order status updated to PAID")

        # 2. Update PromoCode Usage
        if order.promo:
             PromoCode.objects.filter(id=order.promo.id).update(used_count=models.F("used_count") + 1)

        # 3. Ensure Center has basic subscription setup
        ensure_center_subscription(center)

        # 4. Handle Stacking Logic (Upgrade, Extend, Downgrade)
        active_sub = get_active_subscription(center)
        print(f"👉 Active Sub found in DB: {active_sub}")

        if not active_sub:
            print("👉 No active sub, creating new one")
            CenterSubscription.objects.create(
                center=center,
                plan=new_plan,
                status=CenterSubscription.Status.ACTIVE,
                started_at=now,
                expires_at=now + timezone.timedelta(days=duration_days)
            )
        else:
            current_tier = active_sub.plan.tier
            new_tier = new_plan.tier
            print(f"👉 Tiers: Current={current_tier}, New={new_tier}")

            if new_tier > current_tier:
                print("🚀 UPGRADE: Converting old credit to new plan days")
                # ── Credit conversion formula ──────────────────────────────
                # 1) old_daily  = old_plan.monthly_price / 30
                # 2) credit     = old_daily * remaining_days
                # 3) new_daily  = new_plan.monthly_price / 30
                # 4) credit_days = credit / new_daily  (floor)
                # 5) total_days = duration_days (paid) + credit_days
                from decimal import Decimal, ROUND_DOWN as _RD
                preview = calculate_upgrade_preview(
                    active_sub=active_sub,
                    new_plan=new_plan,
                    paid_days=duration_days,
                )
                total_days = preview["total_new_days"]
                credit_days = preview["credit_days"]
                remaining_credit = preview["remaining_credit"]
                remaining_days_old = preview["remaining_days"]

                print(
                    f"   old_plan={active_sub.plan.code} remaining_days={remaining_days_old} "
                    f"credit={remaining_credit} → credit_days={credit_days} "
                    f"paid_days={duration_days} total={total_days}"
                )

                # Expire the old subscription (credit is already converted)
                active_sub.status = CenterSubscription.Status.EXPIRED
                active_sub.save(update_fields=["status"])

                CenterSubscription.objects.create(
                    center=center,
                    plan=new_plan,
                    status=CenterSubscription.Status.ACTIVE,
                    started_at=now,
                    expires_at=now + timezone.timedelta(days=total_days),
                )
            elif new_tier == current_tier:
                print("➕ EXTEND: Same tier, adding time")
                if active_sub.expires_at > now:
                     active_sub.expires_at += timezone.timedelta(days=duration_days)
                else:
                     active_sub.expires_at = now + timezone.timedelta(days=duration_days)
                active_sub.save(update_fields=["expires_at"])
            else:
                print("📉 DOWNGRADE: Queueing as PAUSED")
                CenterSubscription.objects.create(
                    center=center,
                    plan=new_plan,
                    status=CenterSubscription.Status.PAUSED,
                    remaining_seconds=duration_days * 86400,
                    started_at=now, 
                    expires_at=now
                )

        # 5. Sync Center fields from the now ACTIVE subscription
        final_active = get_active_subscription(center)
        print(f"👉 Final Active Sub (DB): {final_active}")

        if final_active:
            print(f"👉 Syncing Center fields to Plan: {final_active.plan.code}")
            center.plan = final_active.plan.code
            center.max_users = final_active.plan.max_users
            center.max_groups = final_active.plan.max_groups
            center.max_students = final_active.plan.max_students
            center.status = Center.STATUS_ACTIVE
            center.expires_at = final_active.expires_at
            center.monthly_price = final_active.plan.monthly_price
            center.save(update_fields=[
                "plan", "max_users", "max_groups", "max_students", 
                "status", "expires_at", "monthly_price"
            ])
            print("✅ Center fields updated")

        # 6. Sync User-Level Subscription for Director
        owner = get_subscription_owner_for_center(center)
        if owner:
            print(f"👉 Syncing Director: {owner.email}")
            give_subscription(owner, new_plan, duration_months=duration_months)

        print(f"✅ PAID DONE")

    except Exception as e:
        import traceback
        logger.error("mark_order_paid error: %s", traceback.format_exc())
        raise e


def check_subscription_expiry(center: Center):
    """
    Checks if active subscription expired. 
    If yes -> Resume a PAUSED one if exists.
    """
    now = timezone.now()
    active = get_active_subscription(center)
    
    if active and active.expires_at <= now:
        active.status = CenterSubscription.Status.EXPIRED
        active.save(update_fields=["status"])
        # Fetch again to be sure it's gone from "active" lookup
        active = None

    if not active:
        paused = get_paused_subscription(center)
        if paused:
            paused.status = CenterSubscription.Status.ACTIVE
            paused.expires_at = now + timezone.timedelta(seconds=paused.remaining_seconds)
            paused.remaining_seconds = 0
            paused.save(update_fields=["status", "expires_at", "remaining_seconds"])
            
            # Sync Center
            center.plan = paused.plan.code
            center.expires_at = paused.expires_at
            center.status = Center.STATUS_ACTIVE
            center.save(update_fields=["plan", "expires_at", "status"])


def get_subscription_ui_state(center: Center) -> dict | None:
    try:
        check_subscription_expiry(center)
        sub = get_active_subscription(center)
        if not sub:
            # Try to show any current/relevant sub for UI
            sub = CenterSubscription.objects.filter(center=center).order_by("-id").first()
            if not sub: return None
            
        days_left = sub.days_left()
        blocked = sub.is_blocked()
        in_grace_period = sub.in_grace_period()
        grace_hours_left = 0

        if in_grace_period:
            diff = (sub.hard_expires_at - timezone.now()).total_seconds()
            grace_hours_left = max(int(diff / 3600), 0)

        # Progress calculation
        progress = 100
        if sub.expires_at > timezone.now():
             total_span = (sub.expires_at - sub.started_at).total_seconds()
             if total_span > 0:
                 elapsed = (timezone.now() - sub.started_at).total_seconds()
                 progress = int((elapsed / total_span) * 100)
                 progress = max(0, min(100, progress))

        warn = (days_left <= 7 and not blocked and not in_grace_period)

        # STACK INFO (Paused subs)
        # Use center.subscriptions related manager
        paused_subs = center.subscriptions.filter(status=CenterSubscription.Status.PAUSED)
        stack_info = []
        for p in paused_subs:
            rem_days = int(p.remaining_seconds / 86400)
            stack_info.append({
                "plan": p.plan.title,
                "days": rem_days
            })

        return {
            "plan_code": sub.plan.code,
            "plan_title": sub.plan.title,
            "plan_tier": sub.plan.tier,
            "expires_at": sub.expires_at,
            "days_left": days_left,
            "blocked": blocked,
            "warn": warn,
            "progress": progress,
            "in_grace_period": in_grace_period,
            "grace_hours_left": grace_hours_left,
            "hard_expires_at": sub.hard_expires_at,
            "stack": stack_info # ✅ Show queued plans
        }
    except Exception as e:
        logging.error(f"get_subscription_ui_state error: {str(e)}")
        # Provide basic fallback to prevent 500
        return {
            "plan_code": "ERROR", 
            "plan_title": "System Error", 
            "days_left": 0, "blocked": True
        }
