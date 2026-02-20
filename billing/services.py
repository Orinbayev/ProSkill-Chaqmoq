# billing/services.py
from __future__ import annotations
from dataclasses import dataclass
from django.utils import timezone
from django.db import transaction
from django.db import models
from django.db.models import Q
import logging

from accounts.models import Center
from .models import SubscriptionPlan, CenterSubscription, PromoCode, SubscriptionOrder, PlanFeature


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
        # If explicitly not expired, calculate progress based on full duration
        # Since we might have multiple segments, relying on "started_at" of THIS segment is fine
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
