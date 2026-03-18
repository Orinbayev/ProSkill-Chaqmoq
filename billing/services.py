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
    sub = center.active_subscription or center.subscription
    if sub and sub.plan:
        return sub.plan.plan_features.filter(code=feature_code).exists()

    return False




DURATIONS = [1, 3, 6, 9, 12]

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
    sub = getattr(center, "active_subscription", None) or getattr(center, "subscription", None)
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
        sub = center.subscription
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
    sub = center.active_subscription or center.subscription # Prioritize active
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
def mark_order_paid(order: SubscriptionOrder) -> None:
    """
    PAID Logic with PAUSE/RESUME support.
    """
    if order.status == SubscriptionOrder.Status.PAID:
        return

    now = timezone.now()
    order.status = SubscriptionOrder.Status.PAID
    order.paid_at = now
    order.save(update_fields=["status", "paid_at"])

    if order.promo:
        PromoCode.objects.filter(id=order.promo.id).update(used_count=models.F("used_count") + 1)

    center = order.center
    
    # ensure active sub
    ensure_center_subscription(center)

    # 1. Get currently ACTIVE subscription
    active_sub = center.active_subscription
    new_plan = order.plan
    duration_days = 30 * int(order.duration_months)

    if not active_sub:
        # No active sub -> Create new immediate one
        CenterSubscription.objects.create(
            center=center,
            plan=new_plan,
            status=CenterSubscription.Status.ACTIVE,
            started_at=now,
            expires_at=now + timezone.timedelta(days=duration_days)
        )
    else:
        # Check TIER
        current_tier = active_sub.plan.tier
        new_tier = new_plan.tier

        if new_tier > current_tier:
            # === UPGRADE: PAUSE CURRENT ===
            remaining_seconds = 0
            if active_sub.expires_at > now:
                remaining = (active_sub.expires_at - now).total_seconds()
                remaining_seconds = int(remaining)
            
            if remaining_seconds > 0:
                active_sub.remaining_seconds = remaining_seconds
                active_sub.paused_at = now
                active_sub.status = CenterSubscription.Status.PAUSED
                active_sub.save()
            else:
                # Already expired logically
                active_sub.status = CenterSubscription.Status.EXPIRED
                active_sub.save()

            # Create NEW active subscription
            CenterSubscription.objects.create(
                center=center,
                plan=new_plan,
                status=CenterSubscription.Status.ACTIVE,
                started_at=now,
                expires_at=now + timezone.timedelta(days=duration_days)
            )

        elif new_tier == current_tier:
            # === EXTEND: SAME PLAN ===
            # Just add time
            if active_sub.expires_at > now:
                active_sub.expires_at += timezone.timedelta(days=duration_days)
            else:
                active_sub.expires_at = now + timezone.timedelta(days=duration_days)
            active_sub.save()

        else:
            # === DOWNGRADE: QUEUE IT ===
            # New Plan is LOWER tier (e.g. Standard bought while Pro active)
            # Create as PAUSED/QUEUED with full duration
            # Only logical if user wants to use it AFTER current high tier finishes.
            # We treat it as a "Paused" subscription with full duration remaining.
            CenterSubscription.objects.create(
                center=center,
                plan=new_plan,
                status=CenterSubscription.Status.PAUSED,
                remaining_seconds=duration_days * 86400, # Full duration saved in seconds
                started_at=now, 
                expires_at=now # Irrelevant until activated
            )

    # Sync Center fields to ACTIVE sub's plan
    # (re-fetch to be sure)
    final_active = center.active_subscription
    if final_active:
        center.plan = final_active.plan.code
        center.max_users = final_active.plan.max_users
        center.max_groups = final_active.plan.max_groups
        center.max_students = final_active.plan.max_students
        center.status = Center.STATUS_ACTIVE
        center.expires_at = final_active.expires_at
        center.monthly_price = final_active.plan.monthly_price
        center.save()


def check_subscription_expiry(center: Center):
    """
    Checks if active subscription expired. 
    If yes -> Resume a PAUSED one if exists.
    Call this periodically or in middleware.
    """
    now = timezone.now()
    active = center.active_subscription
    
    if active and active.is_expired():
        # 1. Mark current as EXPIRED
        active.status = CenterSubscription.Status.EXPIRED
        active.save()
        
    # If no active subscription (or just expired one), check for resumable
    if not center.active_subscription:
        # 2. Find PAUSED subscriptions
        # Prioritize: Highest Tier first, then created_earliest?
        # Logic: If I have Pro (Paused) and Standard (Paused), which one first?
        # Usually higher tier first.
        paused_sub = center.subscriptions.filter(
            status=CenterSubscription.Status.PAUSED,
            remaining_seconds__gt=0
        ).order_by('-plan__tier', 'started_at').first()
        
        if paused_sub:
            # RESUME IT
            paused_sub.status = CenterSubscription.Status.ACTIVE
            paused_sub.paused_at = None
            # New expiry = Now + Remaining
            paused_sub.expires_at = now + timezone.timedelta(seconds=paused_sub.remaining_seconds)
            # Reset remaining (it's consumed now)
            paused_sub.remaining_seconds = 0
            paused_sub.save()
            
            # Sync Center
            center.plan = paused_sub.plan.code
            center.expires_at = paused_sub.expires_at
            center.status = Center.STATUS_ACTIVE
            center.save()


def get_subscription_ui_state(center: Center) -> dict | None:
    try:
        # Check active sub validity first
        check_subscription_expiry(center) # 🔥 Auto-check logic

        sub = center.active_subscription
        if not sub:
            # Fallback to any prop
            sub = center.subscription
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
