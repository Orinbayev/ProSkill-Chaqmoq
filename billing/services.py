# billing/services.py
from __future__ import annotations
from dataclasses import dataclass
from django.utils import timezone
from django.db import transaction
from django.db import models

from accounts.models import Center
from .models import SubscriptionPlan, CenterSubscription, PromoCode, SubscriptionOrder


DURATIONS = [1, 3, 6, 9, 12]


FEATURES_BY_PLAN = {
    "FREE": set(),
    "STANDARD": {"finance", "tasks"},
    "PREMIUM": {"finance", "tasks", "leads"},
    "PRO": {"finance", "tasks", "leads", "kpi", "store", "sms"},
    # Legacy fallbacks
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
    Center uchun subscription yo‘q bo‘lsa yaratib beradi.
    Planni center.plan ga qarab moslaydi.
    """
    try:
        # Check if already exists to avoid RelatedObjectDoesNotExist exception logic
        sub = getattr(center, "subscription", None)
        if sub:
            return sub

        # Fallback plan code
        allowed_plans = ["FREE", "STANDARD", "PREMIUM", "PRO", "START", "ENTERPRISE"]
        plan_code = center.plan if center.plan in allowed_plans else "FREE"
        
        plan = SubscriptionPlan.objects.filter(code=plan_code, active=True).first()
        if not plan:
            plan = SubscriptionPlan.objects.order_by("monthly_price").first()

        if not plan:
            return None

        # Use get_or_create to avoid IntegrityErrors in concurrent environments
        sub, created = CenterSubscription.objects.get_or_create(
            center=center, 
            defaults={"plan": plan}
        )
        return sub
    except Exception as e:
        import logging
        logging.error(f"ensure_center_subscription error for center {getattr(center, 'id', 'unknown')}: {str(e)}")
        return None


def get_feature_flags(center: Center) -> set[str]:
    """
    Center uchun mavjud feature'larni qaytaradi.
    1. Plan asosida default feature'lar
    2. Center.features orqali manual override
    """
    sub = getattr(center, "subscription", None)
    code = None
    if sub and sub.plan:
        code = sub.plan.code
    else:
        code = center.plan
    
    # Plan asosida default features
    features = FEATURES_BY_PLAN.get(code, set()).copy()
    
    # Manual overrides (Center.features JSON)
    manual_features = getattr(center, 'features', {}) or {}
    for feature_name, enabled in manual_features.items():
        if enabled:
            features.add(feature_name)
        elif feature_name in features:
            features.remove(feature_name)
    
    return features


def validate_promocode(code: str, plan: SubscriptionPlan, center: Center | None = None) -> PromoCode | None:
    code = (code or "").strip().upper()
    if not code:
        return None
    promo = PromoCode.objects.filter(code=code).first()
    if not promo or not promo.is_valid_now():
        return None
    
    # agar promo.plans bo‘sh bo‘lmasa — faqat shularga
    if promo.plans.exists() and not promo.plans.filter(id=plan.id).exists():
        return None

    # ✅ Yangi: Bir marta ishlata olishni tekshirish
    if center and promo.once_per_center:
        # Paid orderlarda shu promo ishlatilganmi?
        already_used = SubscriptionOrder.objects.filter(
            center=center, 
            promo=promo, 
            status=SubscriptionOrder.Status.PAID
        ).exists()
        if already_used:
            return None

    return promo


def calculate_price(plan: SubscriptionPlan, months: int, promo_code: str | None, center: Center | None = None) -> PricingResult:
    months = int(months or 1)
    if months not in DURATIONS:
        months = 1

    base_price = plan.monthly_price * months
    promo = validate_promocode(promo_code or "", plan, center=center)
    
    # Plan discount + Promo discount (capped at 100%)
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
    Order PAID bo‘lsa:
    - promo used_count++
    - CenterSubscription expires_at uzayadi (PRORATION logic bilan)
    - Center plan + limitlar yangilanadi
    """
    if order.status == SubscriptionOrder.Status.PAID:
        return

    now = timezone.now()
    order.status = SubscriptionOrder.Status.PAID
    order.paid_at = now
    order.save(update_fields=["status", "paid_at"])

    if order.promo:
        # Update promo usage safely
        PromoCode.objects.filter(id=order.promo.id).update(used_count=models.F("used_count") + 1)

    center = order.center
    sub = ensure_center_subscription(center)
    if not sub:
        return

    # --- PRORATION LOGIC ---
    # Agar plan o'zgarsa (Upgrade/Downgrade), eski plandagi qolgan kunlar qiymatini
    # yangi planga o'tkazamiz (konvertatsiya).
    
    current_plan = sub.plan
    new_plan = order.plan
    
    if current_plan.code == new_plan.code:
        # 1. Bir xil plan -> Shunchaki uzaytiramiz
        start_from = sub.expires_at if sub.expires_at and sub.expires_at > now else now
        sub.expires_at = start_from + timezone.timedelta(days=30 * int(order.duration_months))
    else:
        # 2. Plan o'zgaryapti -> Proration (Qayta hisoblash)
        remaining_days = 0
        if sub.expires_at and sub.expires_at > now:
            remaining_days = (sub.expires_at - now).days
        
        value_remaining = 0
        if remaining_days > 0 and current_plan.monthly_price > 0:
            daily_rate_old = current_plan.monthly_price / 30.0
            value_remaining = remaining_days * daily_rate_old
            
        # Eski qiymatni yangi planga kun qilib o'tkazamiz
        days_credit = 0
        if new_plan.monthly_price > 0:
            daily_rate_new = new_plan.monthly_price / 30.0
            days_credit = int(value_remaining / daily_rate_new)
        else:
            # Agar Free planga o'tayotgan bo'lsa, eski qiymat kuyadi (yoki cheksiz vaqt beriladi)
            days_credit = 0 

        # Yangi muddati = Hozir + Konvertatsiya qilingan kunlar + Sotib olingan kunlar
        total_new_days = days_credit + (30 * int(order.duration_months))
        sub.expires_at = now + timezone.timedelta(days=total_new_days)
        
        # Planni almashtiramiz
        sub.plan = new_plan

    # Common Updates
    sub.status = CenterSubscription.Status.ACTIVE
    sub.manual_block = False
    sub.save()

    # Sync Center Fields
    center.plan = new_plan.code
    center.max_users = new_plan.max_users
    center.max_groups = new_plan.max_groups
    center.max_students = new_plan.max_students
    center.status = Center.STATUS_ACTIVE
    center.expires_at = sub.expires_at
    center.monthly_price = new_plan.monthly_price
    center.save()


def get_subscription_ui_state(center: Center) -> dict | None:
    try:
        sub = ensure_center_subscription(center)
        if not sub:
            return None
            
        days_left = sub.days_left()
        blocked = sub.is_blocked()
        in_grace_period = sub.in_grace_period()
        grace_hours_left = 0

        if in_grace_period:
            diff = (sub.hard_expires_at - timezone.now()).total_seconds()
            grace_hours_left = max(int(diff / 3600), 0)

        # Progress calculation based on actual duration
        diff = (sub.expires_at - sub.started_at).days
        total_duration = max(diff, 30)
        
        progress = int(max(min(days_left / total_duration, 1), 0) * 100)
        percent_left = progress

        warn = (days_left <= 7 and not blocked and not in_grace_period)

        # Get proper plan title
        plan_title = sub.plan.title if sub.plan else center.plan
        plan_code = sub.plan.code if sub.plan else center.plan

        return {
            "plan_code": plan_code,
            "plan_title": plan_title,
            "expires_at": sub.expires_at,
            "days_left": days_left,
            "blocked": blocked,
            "warn": warn,
            "progress": progress, 
            # Grace Period Info for Modal/Lockout Warning
            "in_grace_period": in_grace_period,
            "grace_hours_left": grace_hours_left,
            "hard_expires_at": sub.hard_expires_at,
        }
    except Exception as e:
        import logging
        logging.error(f"get_subscription_ui_state error for center {getattr(center, 'id', 'unknown')}: {str(e)}")
        return None
