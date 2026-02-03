# billing/services.py
from __future__ import annotations
from dataclasses import dataclass
from django.utils import timezone
from django.db import transaction
# billing/services.py tepasiga qo‘sh
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


def ensure_center_subscription(center: Center) -> CenterSubscription:
    """
    Center uchun subscription yo‘q bo‘lsa yaratib beradi.
    Planni center.plan ga qarab moslaydi.
    """
    sub = getattr(center, "subscription", None)
    if sub:
        return sub

    plan_code = center.plan if center.plan in ("START", "STANDARD", "PRO", "PREMIUM", "ENTERPRISE") else "START"
    plan = SubscriptionPlan.objects.filter(code=plan_code, active=True).first()
    if not plan:
        plan = SubscriptionPlan.objects.order_by("monthly_price").first()

    return CenterSubscription.objects.create(center=center, plan=plan)


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
    - CenterSubscription expires_at uzayadi
    - Center plan + limitlar yangilanadi
    """
    if order.status == SubscriptionOrder.Status.PAID:
        return

    now = timezone.now()
    order.status = SubscriptionOrder.Status.PAID
    order.paid_at = now
    order.save(update_fields=["status", "paid_at"])

    if order.promo_id:
        PromoCode.objects.filter(id=order.promo_id).update(used_count=models.F("used_count") + 1)

    center = order.center
    sub = ensure_center_subscription(center)

    # plan update
    sub.plan = order.plan
    sub.status = CenterSubscription.Status.ACTIVE
    sub.manual_block = False

    # expires extend: agar expired bo‘lsa, bugundan; bo‘lmasa, o‘sha expires_at’dan
    start_from = sub.expires_at if sub.expires_at > now else now
    sub.expires_at = start_from + timezone.timedelta(days=30 * int(order.duration_months))
    sub.save()

    # center limitlarni plan bo‘yicha update qilamiz
    center.plan = order.plan.code
    center.max_users = order.plan.max_users
    center.max_groups = order.plan.max_groups
    center.max_students = order.plan.max_students
    center.save(update_fields=["plan", "max_users", "max_groups", "max_students"])


def get_subscription_ui_state(center: Center) -> dict:
    sub = ensure_center_subscription(center)
    days_left = sub.days_left()
    blocked = sub.is_blocked()

    # Progress calculation based on actual duration
    total_duration = (sub.expires_at - sub.started_at).days
    if total_duration <= 0:
        total_duration = 30 # Fallback default
    
    progress = int(max(min(days_left / total_duration, 1), 0) * 100)
    percent_left = progress

    warn = (days_left <= 7 and not blocked)

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
        "progress": progress, # This is now percent LEFT
    }
