# billing/services.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.core.cache import cache
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

logger = logging.getLogger(__name__)
DEFAULT_CENTER_STUDENT_FALLBACK_LIMIT = 50
_DASHBOARD_CACHE_PERIODS = (
    "this_month",
    "last_month",
    "3_months",
    "this_year",
    "last_year",
    "all",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
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
    invalidate_center_limit_cache(center)


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


def invalidate_center_limit_cache(center: Center | None) -> None:
    """
    Clear short-lived caches that may continue showing stale limit/subscription data.
    """
    center_id = getattr(center, "id", None)
    if not center_id:
        return

    cache_keys = [f"tenant_ctx:sub:v3:{center_id}"]
    cache_keys.extend(
        f"director_dashboard:v2:center:{center_id}:period:{period}"
        for period in _DASHBOARD_CACHE_PERIODS
    )
    cache.delete_many(cache_keys)


def _get_center_active_subscription_cached(center: Center) -> CenterSubscription | None:
    prefetched_active = getattr(center, "active_subs_list", None)
    if prefetched_active is not None:
        return prefetched_active[0] if prefetched_active else None

    prefetched_subs = getattr(center, "_prefetched_objects_cache", {}).get("subscriptions")
    if prefetched_subs is not None:
        active_subs = [s for s in prefetched_subs if s.status == CenterSubscription.Status.ACTIVE]
        if not active_subs:
            return None
        active_subs.sort(key=lambda s: (s.plan.tier, s.expires_at), reverse=True)
        return active_subs[0]

    return get_active_subscription(center)




DURATIONS = [1, 3, 6, 9, 12]


# ============================================================
# PLAN PRICING HELPERS
# ============================================================

from decimal import Decimal, ROUND_DOWN

# Period-specific price field mapping: months → model field name
_PERIOD_PRICE_FIELDS: dict[int, str] = {
    3:  "price_3m",
    6:  "price_6m",
    9:  "price_9m",
    12: "price_12m",
}


def get_plan_period_base_price(plan: "SubscriptionPlan", months: int) -> int:
    """
    Tarif uchun berilgan oy soniga mos umumiy narxni qaytaradi.
    Agar maxsus period narxi (price_3m, price_6m ...) belgilangan bo'lsa, shuni ishlatadi.
    Aks holda: monthly_price × months.

    Bu funksiya calculate_price() va calculate_plan_switch_days() da
    yangi to'lov asosini aniqlash uchun ishlatiladi.
    """
    months = int(months or 1)
    field = _PERIOD_PRICE_FIELDS.get(months)
    if field:
        period_price = getattr(plan, field, None)
        if period_price and int(period_price) > 0:
            return int(period_price)
    # Fallback: monthly_price × months
    return int((plan.monthly_price or 0) * months)


# ============================================================
# UNIVERSAL PLAN SWITCH CALCULATOR
# ============================================================

def calculate_plan_switch_days(
    active_sub: "CenterSubscription | None",
    new_plan: "SubscriptionPlan",
    paid_days: int = 0,
) -> dict:
    """
    Universal tarif almashtirish kalkulyatori. Uch holat:

    MODE "new":
      Faol obuna yo'q yoki tugagan → paid_days dan boshlanadi.

    MODE "extend":
      Xuddi shu tarif qayta sotib olindi → mavjud expires_at ga paid_days qo'shiladi.
      (Foydalanuvchi kredit konvertatsiyasiga yo'l qo'yilmaydi.)

    MODE "convert":
      Boshqa tarifga o'tish (arzonroqmi, qimmatroqmi farqi yo'q):
        old_daily     = old_monthly_price / 30
        credit        = old_daily × remaining_days          (floor, so'm)
        new_daily     = new_monthly_price / 30
        credit_days   = floor(credit / new_daily)            (floor, kun)
        total_days    = paid_days + credit_days

      Eski obuna EXPIRE bo'ladi, yangi obuna total_days bilan yaratiladi.

    Returns dict:
      {
        "mode":              "new" | "extend" | "convert",
        "is_same_plan":      bool,
        "remaining_days":    int,        # eski obunada qolgan kun
        "remaining_credit":  Decimal,    # eski obunada qolgan so'm qiymati
        "credit_days":       int,        # shu qiymat yangi tarifda necha kun
        "paid_days":         int,        # yangi to'lov uchun kunlar
        "total_new_days":    int,        # credit_days + paid_days
        "old_plan_title":    str,
        "old_monthly_price": int,
        "old_daily_price":   Decimal,
        "new_plan_title":    str,
        "new_monthly_price": int,
        "new_daily_price":   Decimal,
        "new_expires_at":    datetime,   # now + total_new_days
      }
    """
    now = timezone.now()

    # ── MODE: new ──────────────────────────────────────────────────────────
    # Faol obuna yo'q yoki allaqachon tugagan
    has_active_time = (
        active_sub is not None
        and active_sub.expires_at is not None
        and active_sub.expires_at > now
    )

    if not has_active_time:
        total = max(paid_days, 1)
        return {
            "mode": "new",
            "is_same_plan": False,
            "remaining_days": 0,
            "remaining_credit": Decimal(0),
            "credit_days": 0,
            "paid_days": paid_days,
            "total_new_days": total,
            "old_plan_title": "",
            "old_monthly_price": 0,
            "old_daily_price": Decimal(0),
            "new_plan_title": new_plan.title,
            "new_monthly_price": int(new_plan.monthly_price or 0),
            "new_daily_price": (Decimal(new_plan.monthly_price or 0) / 30).quantize(Decimal("0.01")),
            "new_expires_at": now + timezone.timedelta(days=total),
        }

    # ── MODE: extend ───────────────────────────────────────────────────────
    # Xuddi shu tarif (plan.id == active_sub.plan.id) → vaqt ustiga qo'shiladi
    is_same_plan = (active_sub.plan_id == new_plan.pk)

    if is_same_plan:
        # Extend from current expiry
        base_date = active_sub.expires_at  # already > now (checked above)
        new_expires_at = base_date + timezone.timedelta(days=paid_days)
        remaining_days = max(0, (active_sub.expires_at.date() - now.date()).days)
        new_monthly = Decimal(new_plan.monthly_price or 0)
        new_daily = (new_monthly / 30).quantize(Decimal("0.01")) if new_monthly > 0 else Decimal(0)
        return {
            "mode": "extend",
            "is_same_plan": True,
            "remaining_days": remaining_days,
            "remaining_credit": Decimal(0),
            "credit_days": 0,
            "paid_days": paid_days,
            "total_new_days": paid_days,   # faqat yangi to'lov kunlari qo'shiladi
            "old_plan_title": active_sub.plan.title,
            "old_monthly_price": int(active_sub.plan.monthly_price or 0),
            "old_daily_price": (Decimal(active_sub.plan.monthly_price or 0) / 30).quantize(Decimal("0.01")),
            "new_plan_title": new_plan.title,
            "new_monthly_price": int(new_monthly),
            "new_daily_price": new_daily,
            "new_expires_at": new_expires_at,
        }

    # ── MODE: convert ──────────────────────────────────────────────────────
    # Boshqa tarifga o'tish → kredit konvertatsiyasi
    old_monthly = Decimal(active_sub.plan.monthly_price or 0)
    new_monthly = Decimal(new_plan.monthly_price or 0)

    remaining_days = max(0, (active_sub.expires_at.date() - now.date()).days)

    # Narx nolga teng bo'lsa yoki qolgan kun yo'q bo'lsa → oddiy yangi obuna
    if old_monthly <= 0 or new_monthly <= 0 or remaining_days <= 0:
        total = max(paid_days, 1)
        new_monthly_safe = new_monthly if new_monthly > 0 else Decimal(0)
        new_daily = (new_monthly_safe / 30).quantize(Decimal("0.01")) if new_monthly_safe > 0 else Decimal(0)
        return {
            "mode": "new",
            "is_same_plan": False,
            "remaining_days": remaining_days,
            "remaining_credit": Decimal(0),
            "credit_days": 0,
            "paid_days": paid_days,
            "total_new_days": total,
            "old_plan_title": active_sub.plan.title,
            "old_monthly_price": int(old_monthly),
            "old_daily_price": (old_monthly / 30).quantize(Decimal("0.01")) if old_monthly > 0 else Decimal(0),
            "new_plan_title": new_plan.title,
            "new_monthly_price": int(new_monthly),
            "new_daily_price": new_daily,
            "new_expires_at": now + timezone.timedelta(days=total),
        }

    # Kredit hisoblash:
    #   old_daily   = old_monthly_price / 30
    #   credit      = old_daily × remaining_days       (so'm, floor)
    #   credit_days = floor(credit / new_daily)         (kun, floor)
    #   total       = paid_days + credit_days           (min 1)
    old_daily = old_monthly / Decimal(30)
    new_daily = new_monthly / Decimal(30)

    # Floor kreditni hisoblaymiz (foydalanuvchi to'lamagan qismni bermaymiz)
    remaining_credit = (old_daily * Decimal(remaining_days)).quantize(Decimal("1"), rounding=ROUND_DOWN)
    credit_days_exact = remaining_credit / new_daily
    credit_days = int(credit_days_exact.to_integral_value(rounding=ROUND_DOWN))

    total_new_days = max(paid_days + credit_days, 1)
    new_expires_at = now + timezone.timedelta(days=total_new_days)

    return {
        "mode": "convert",
        "is_same_plan": False,
        "remaining_days": remaining_days,
        "remaining_credit": remaining_credit,
        "credit_days": credit_days,
        "paid_days": paid_days,
        "total_new_days": total_new_days,
        "old_plan_title": active_sub.plan.title,
        "old_monthly_price": int(old_monthly),
        "old_daily_price": old_daily.quantize(Decimal("0.01")),
        "new_plan_title": new_plan.title,
        "new_monthly_price": int(new_monthly),
        "new_daily_price": new_daily.quantize(Decimal("0.01")),
        "new_expires_at": new_expires_at,
    }


def calculate_upgrade_preview(
    active_sub: "CenterSubscription | None",
    new_plan: "SubscriptionPlan",
    paid_days: int = 0,
) -> dict:
    """
    Backward-compatible wrapper for the upgrade preview API/modal.
    Delegates to calculate_plan_switch_days() and adds legacy keys.

    Returns all keys from calculate_plan_switch_days() plus:
      "is_upgrade": bool  — True if new plan tier > old plan tier and credit conversion happened
    """
    result = calculate_plan_switch_days(active_sub, new_plan, paid_days=paid_days)
    is_upgrade = (
        result["mode"] == "convert"
        and active_sub is not None
        and new_plan.tier > active_sub.plan.tier
    )
    result["is_upgrade"] = is_upgrade
    return result

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


def resolve_center_student_limit(
    center: Center | None,
    actor=None,
    fallback_limit: int = DEFAULT_CENTER_STUDENT_FALLBACK_LIMIT,
    include_usage: bool = False,
) -> dict:
    """
    Resolve a single source of truth for center student limit.

    Priority:
    1. Center-level sources (highest of capacity_limit, max_students,
       active CenterSubscription.plan.max_students)
    2. Legacy owner Subscription.plan.max_students (fallback only)
    3. Final fallback limit
    """
    resolved_fallback = max(int(fallback_limit or DEFAULT_CENTER_STUDENT_FALLBACK_LIMIT), 1)
    state = {
        "limit": resolved_fallback,
        "source": "fallback.default_limit",
        "source_label": "Fallback default limit",
        "plan_code": None,
        "plan_name": None,
        "candidates": [],
    }

    if not center:
        if include_usage:
            state.update({
                "current_count": 0,
                "remaining": resolved_fallback,
                "is_at_limit": False,
            })
        return state

    active_sub = _get_center_active_subscription_cached(center)
    center_candidates: list[dict] = []

    if active_sub and getattr(active_sub, "plan", None):
        active_limit = int(getattr(active_sub.plan, "max_students", 0) or 0)
        if active_limit > 0:
            center_candidates.append({
                "limit": active_limit,
                "source": "active_center_subscription.plan.max_students",
                "source_label": "Active center subscription plan",
            })
            state["plan_code"] = active_sub.plan.code
            state["plan_name"] = active_sub.plan.name or active_sub.plan.title or active_sub.plan.code

    center_max_students = int(getattr(center, "max_students", 0) or 0)
    if center_max_students > 0:
        center_candidates.append({
            "limit": center_max_students,
            "source": "center.max_students",
            "source_label": "Center.max_students",
        })

    center_capacity_limit = int(getattr(center, "capacity_limit", 0) or 0)
    if center_capacity_limit > 0:
        center_candidates.append({
            "limit": center_capacity_limit,
            "source": "center.capacity_limit",
            "source_label": "Center.capacity_limit",
        })

    if not state["plan_code"]:
        state["plan_code"] = getattr(center, "plan", None) or None
        state["plan_name"] = getattr(center, "plan", None) or None

    if center_candidates:
        selected = max(center_candidates, key=lambda item: int(item["limit"] or 0))
        state.update(selected)
        state["candidates"] = center_candidates
    else:
        owner = get_subscription_owner_for_center(center=center, actor=actor)
        owner_sub = check_subscription(owner) if owner else None
        if owner_sub and getattr(owner_sub, "plan", None):
            owner_limit = int(getattr(owner_sub.plan, "max_students", 0) or 0)
            if owner_limit > 0:
                state.update({
                    "limit": owner_limit,
                    "source": "legacy_owner_subscription.plan.max_students",
                    "source_label": "Legacy owner subscription plan",
                    "plan_code": owner_sub.plan.code,
                    "plan_name": owner_sub.plan.name or owner_sub.plan.title or owner_sub.plan.code,
                })

    if include_usage:
        from accounts.models import User

        current_count = User.objects.filter(
            center=center,
            role="student",
            is_archived=False,
        ).count()
        state.update({
            "current_count": current_count,
            "remaining": max(0, int(state["limit"] or 0) - current_count),
            "is_at_limit": current_count >= int(state["limit"] or 0),
        })

    return state


def get_center_student_limit(
    center: Center,
    actor=None,
    free_limit: int = DEFAULT_CENTER_STUDENT_FALLBACK_LIMIT,
) -> int:
    """
    Backward-compatible integer-only accessor for center student limit.
    """
    return int(
        resolve_center_student_limit(
            center=center,
            actor=actor,
            fallback_limit=free_limit,
            include_usage=False,
        )["limit"]
    )


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

    # Period-specific narxni ishlatamiz (price_3m, price_6m, price_9m, price_12m)
    # Agar belgilangan bo'lsa shuni olamiz, aks holda monthly_price × months
    base_price = get_plan_period_base_price(plan, months)

    promo = validate_promocode(promo_code or "", plan, center=center)

    # Tarif o'z chegirmasiga ega bo'lishi mumkin (plan.discount_percent)
    # Lekin period narxlari allaqachon chegirma bilan belgilanishi mumkin.
    # Shuning uchun: agar period narxi foydalanilsa va plan.discount_percent > 0
    # bo'lsa, ularning qo'shilishidan ehtiyot bo'lish kerak.
    # Biz faqat promo discount ni qo'shamiz (plan discount period narxiga kiritilgan deb hisoblaymiz).
    field = _PERIOD_PRICE_FIELDS.get(months)
    period_price_used = bool(field and getattr(plan, field, None) and int(getattr(plan, field, 0) or 0) > 0)

    if period_price_used:
        # Period narxi allaqachon chegirma bilan belgilangan → faqat promo discount qo'shamiz
        plan_discount = 0
    else:
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

    # ── Universal plan switch logic ────────────────────────────────────────
    # calculate_plan_switch_days handles three modes:
    #   "new"     → no active sub or expired → fresh start with paid_days
    #   "extend"  → same plan → extend existing expiry by paid_days
    #   "convert" → different plan → convert remaining credit to new plan days
    switch = calculate_plan_switch_days(
        active_sub=active_sub,
        new_plan=plan,
        paid_days=total_days,
    )

    logger.info(
        "Click plan switch: center=%s mode=%s old_plan=%s→new_plan=%s "
        "remaining_days=%s credit=%s credit_days=%s paid_days=%s total=%s",
        center.id,
        switch["mode"],
        active_sub.plan.code if active_sub else "—",
        plan.code,
        switch["remaining_days"],
        switch["remaining_credit"],
        switch["credit_days"],
        total_days,
        switch["total_new_days"],
    )

    new_end_date = switch["new_expires_at"]

    if switch["mode"] == "extend":
        # Xuddi shu tarif: extends_at ni yangilang, boshqa hech narsa o'zgarmaydi
        active_sub.expires_at = new_end_date
        active_sub.status = CenterSubscription.Status.ACTIVE
        active_sub.paused_at = None
        active_sub.remaining_seconds = 0
        active_sub.manual_block = False
        active_sub.save(update_fields=[
            "status", "expires_at", "paused_at", "remaining_seconds", "manual_block",
        ])
        target_sub = active_sub

    elif switch["mode"] == "convert":
        # Boshqa tarifga o'tish: eski obuna EXPIRE, yangi obuna yaratiladi
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

    else:
        # mode == "new": yangi obuna (eski yo'q yoki tugagan)
        if active_sub:
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

    center.plan = plan.code
    center.max_users = plan.max_users
    center.max_groups = plan.max_groups
    center.max_students = plan.max_students
    center.capacity_limit = max(int(center.capacity_limit or 0), int(plan.max_students or 0))
    center.status = Center.STATUS_ACTIVE
    center.expires_at = new_end_date
    center.monthly_price = plan.monthly_price
    center.save(
        update_fields=[
            "plan",
            "max_users",
            "max_groups",
            "max_students",
            "capacity_limit",
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

        # 4. Universal plan switch logic (extend / convert / new)
        active_sub = get_active_subscription(center)
        print(f"👉 Active Sub found in DB: {active_sub}")

        # calculate_plan_switch_days handles all three cases:
        #   "extend"  → same plan_id  → add paid days to existing expiry
        #   "convert" → different plan → convert remaining credit + add paid days
        #   "new"     → no active sub / expired → fresh start
        switch = calculate_plan_switch_days(
            active_sub=active_sub,
            new_plan=new_plan,
            paid_days=duration_days,
        )
        print(
            f"👉 Switch mode={switch['mode']} "
            f"remaining_days={switch['remaining_days']} "
            f"credit={switch['remaining_credit']} "
            f"credit_days={switch['credit_days']} "
            f"paid_days={switch['paid_days']} "
            f"total={switch['total_new_days']}"
        )

        if switch["mode"] == "extend":
            # Xuddi shu tarif → mavjud obuna muddatini uzaytirish
            print("➕ EXTEND: Same plan, adding paid days to current expiry")
            active_sub.expires_at = switch["new_expires_at"]
            active_sub.status = CenterSubscription.Status.ACTIVE
            active_sub.paused_at = None
            active_sub.remaining_seconds = 0
            active_sub.save(update_fields=["status", "expires_at", "paused_at", "remaining_seconds"])

        elif switch["mode"] == "convert":
            # Boshqa tarif → kredit konvertatsiyasi
            print(
                f"🔄 CONVERT: {active_sub.plan.code}→{new_plan.code} "
                f"credit_days={switch['credit_days']} paid_days={switch['paid_days']} "
                f"total={switch['total_new_days']}"
            )
            # Eski obunani EXPIRE qilamiz (kredit allaqachon konvert qilindi)
            active_sub.status = CenterSubscription.Status.EXPIRED
            active_sub.save(update_fields=["status"])

            CenterSubscription.objects.create(
                center=center,
                plan=new_plan,
                status=CenterSubscription.Status.ACTIVE,
                started_at=now,
                expires_at=switch["new_expires_at"],
                paused_at=None,
                remaining_seconds=0,
                manual_block=False,
            )

        else:
            # mode == "new": faol obuna yo'q yoki tugagan
            print("🆕 NEW: No active subscription, creating fresh one")
            if active_sub:
                active_sub.status = CenterSubscription.Status.EXPIRED
                active_sub.save(update_fields=["status"])

            CenterSubscription.objects.create(
                center=center,
                plan=new_plan,
                status=CenterSubscription.Status.ACTIVE,
                started_at=now,
                expires_at=switch["new_expires_at"],
                paused_at=None,
                remaining_seconds=0,
                manual_block=False,
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
            center.capacity_limit = max(int(center.capacity_limit or 0), int(final_active.plan.max_students or 0))
            center.status = Center.STATUS_ACTIVE
            center.expires_at = final_active.expires_at
            center.monthly_price = final_active.plan.monthly_price
            center.save(update_fields=[
                "plan", "max_users", "max_groups", "max_students",
                "capacity_limit",
                "status", "expires_at", "monthly_price"
            ])
            print("✅ Center fields updated")

        # 6. Sync User-Level Subscription for Director
        owner = get_subscription_owner_for_center(center)
        if owner:
            print(f"👉 Syncing Director: {owner.email}")
            give_subscription(owner, new_plan, duration_months=duration_months)

        invalidate_center_limit_cache(center)
        print(f"✅ PAID DONE")

    except Exception as e:
        import traceback
        logger.error("mark_order_paid error: %s", traceback.format_exc())
        raise e


@transaction.atomic
def sync_center_from_active_subscription(center: Center) -> bool:
    """
    CenterSubscription (source of truth) → Center modeli fieldlarini sinxronlaydi.

    Bu funksiya **yagona** sync nuqtasi bo'lib, quyidagi hollarda chaqirilishi kerak:
      - payment muvaffaqiyatli bo'lgandan keyin
      - superadmin tarif/muddat o'zgartirganidan keyin
      - manual subscription edit bo'lgandan keyin

    Maqsad: Center.plan, Center.expires_at, Center.monthly_price,
    Center.max_students kabilar ACTIVE CenterSubscription dan olinsin,
    ikki joyda alohida-alohida hisob bo'lmasin.

    Returns:
      True  — sinxronizatsiya muvaffaqiyatli
      False — faol obuna yo'q, Center o'zgartirilmaydi
    """
    active_sub = get_active_subscription(center)
    if not active_sub:
        return False

    plan = active_sub.plan
    center.plan          = plan.code
    center.expires_at    = active_sub.expires_at
    center.monthly_price = plan.monthly_price
    center.max_students  = plan.max_students
    center.capacity_limit = max(int(center.capacity_limit or 0), int(plan.max_students or 0))
    center.max_groups    = plan.max_groups
    center.max_users     = plan.max_users
    center.save(update_fields=[
        "plan", "expires_at", "monthly_price",
        "max_students", "capacity_limit", "max_groups", "max_users",
    ])
    # Feature flaglarni ham sinxronlaymiz
    apply_plan_to_center(center, plan)
    return True


@transaction.atomic
def superadmin_apply_subscription(
    center: Center,
    new_plan: "SubscriptionPlan",
    expires_at,
    actor=None,
) -> "CenterSubscription":
    """
    Superadmin tomonidan markazga tarif qo'lda belgilash yoki o'zgartirish.

    Mantiq:
      1. Mavjud ACTIVE obunani EXPIRED qilamiz
      2. Yangi ACTIVE obuna yaratamiz
      3. Center fieldlarini yangi obunadan sinxronlaymiz

    expires_at — datetime yoki date (string emas)
    """
    from django.utils import timezone as tz
    import datetime

    now = tz.now()

    # Agar string kelsa parse qilamiz
    if isinstance(expires_at, str):
        from django.utils.dateparse import parse_datetime, parse_date
        dt = parse_datetime(expires_at)
        if not dt:
            d = parse_date(expires_at)
            if d:
                dt = tz.make_aware(datetime.datetime.combine(d, datetime.time.min))
        expires_at = dt

    if expires_at is None:
        raise ValueError("expires_at required for superadmin_apply_subscription")

    if tz.is_naive(expires_at):
        expires_at = tz.make_aware(expires_at)

    # 1. Expire all active subscriptions for this center
    CenterSubscription.objects.filter(
        center=center,
        status=CenterSubscription.Status.ACTIVE,
    ).update(status=CenterSubscription.Status.EXPIRED)

    # 2. Create new ACTIVE subscription
    new_sub = CenterSubscription.objects.create(
        center=center,
        plan=new_plan,
        status=CenterSubscription.Status.ACTIVE,
        started_at=now,
        expires_at=expires_at,
        paused_at=None,
        remaining_seconds=0,
        manual_block=False,
    )

    # 3. Sync Center fields from new subscription
    center.plan          = new_plan.code
    center.expires_at    = expires_at
    center.monthly_price = new_plan.monthly_price
    center.max_students  = new_plan.max_students
    center.capacity_limit = max(int(center.capacity_limit or 0), int(new_plan.max_students or 0))
    center.max_groups    = new_plan.max_groups
    center.max_users     = new_plan.max_users
    center.status        = Center.STATUS_ACTIVE
    center.save(update_fields=[
        "plan", "expires_at", "monthly_price",
        "max_students", "capacity_limit", "max_groups", "max_users", "status",
    ])

    # 4. Feature sync
    apply_plan_to_center(center, new_plan)

    logging.getLogger(__name__).info(
        "superadmin_apply_subscription: center=%s plan=%s expires=%s actor=%s sub_id=%s",
        center.id, new_plan.code, expires_at.date(), getattr(actor, "id", None), new_sub.id,
    )
    return new_sub


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
            center.max_students = paused.plan.max_students
            center.status = Center.STATUS_ACTIVE
            center.capacity_limit = max(int(center.capacity_limit or 0), int(paused.plan.max_students or 0))
            center.save(update_fields=["plan", "expires_at", "max_students", "status", "capacity_limit"])
            invalidate_center_limit_cache(center)


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
