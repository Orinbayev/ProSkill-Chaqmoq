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

# ──────────────────────────────────────────────────────────────────────────────
# Request-scope in-process cache for center_has_feature.
# center_has_feature is called once per (enrollment × month) in debt snapshot
# loops — potentially thousands of times per request. Caching the result for
# (center_id, feature_code) eliminates ~4 DB queries per repeat call.
# Thread-local is used so the cache is isolated per worker thread / request.
# ──────────────────────────────────────────────────────────────────────────────
import threading as _thr
_chf_local = _thr.local()


def _chf_cache() -> dict:
    if not hasattr(_chf_local, 'd'):
        _chf_local.d = {}
    return _chf_local.d


def clear_feature_request_cache() -> None:
    """Call at the start of a long-running view to flush stale entries."""
    _chf_local.d = {}


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
    # Legacy JSONField sync — kept for backward compat.
    enabled_codes = set(plan.plan_features.values_list("code", flat=True))
    current_overrides = center.features or {}

    # Rebuild center.features: plan features = True, missing = False (unless manually overridden)
    all_features = list(PlanFeature.objects.all())
    known_feature_codes = {feature.code for feature in all_features}
    new_features = {
        key: value
        for key, value in current_overrides.items()
        if key not in known_feature_codes
    }
    for f in all_features:
        if f.code in current_overrides:
            # Manual override preserved
            new_features[f.code] = current_overrides[f.code]
        else:
            new_features[f.code] = f.code in enabled_codes

    center.features = new_features
    center.save(update_fields=["features"])
    invalidate_center_limit_cache(center)


LEGACY_CODE_MAP = {
    # legacy PlanFeature.code → v2 PlanFeature.code
    "leads": "lidlar",
    "branches": "filial_qoshish",
    "roles": "rollar",
    # "sms" maps to itself but we keep it explicit for safety
    "sms": "sms",
    # UI-only flags (kept untouched, unmapped)
    # "ui_weekly_schedule", "ui_certificates", "ui_exam_sessions",
    # "ui_failed_students", "tasks", "kpi", "store",
    # "support_teacher_enabled" — these stay as JSONField overrides only
}


def _resolve_feature_code(code: str) -> str:
    """Map legacy feature codes to v2 codes. Returns input if no mapping."""
    return LEGACY_CODE_MAP.get(code, code)


def center_has_feature(center, slug: str) -> bool:
    """
    Single source of truth for ChaqmoqApp feature gating (v2).

    Resolution order:
      1. Resolve any legacy code to its v2 equivalent.
      2. If the (root) center has a CenterFeatureOverride for this feature,
         that wins absolutely.
      3. CORE features (PlanFeature.is_core=True) are always enabled.
      4. Otherwise, check the active subscription's plan.plan_features M2M.
      5. As a final compatibility layer, fall back to legacy Center.features
         JSONField for keys that have no v2 PlanFeature row yet.

    Results are cached in thread-local storage for the duration of a request
    to avoid hammering the DB from tight loops (debt snapshot calculations).
    """
    from billing.models import PlanFeature, CenterFeatureOverride
    code = _resolve_feature_code(slug)

    # Resolve to root center
    root = center.get_root_center() if getattr(center, 'parent_center_id', None) else center
    root_id = getattr(root, 'id', None)

    # ── Request-scope cache ────────────────────────────────────────────────
    if root_id is not None:
        ck = (root_id, code)
        _cache = _chf_cache()
        if ck in _cache:
            return _cache[ck]

    # ── Actual DB resolution ───────────────────────────────────────────────

    # 1. Override wins
    override = (
        CenterFeatureOverride.objects
        .filter(center=root, feature__code=code)
        .first()
    )
    if override:
        result = override.enabled
        if root_id is not None:
            _chf_cache()[(root_id, code)] = result
        return result

    # 2. Look up the feature
    feature = PlanFeature.objects.filter(code=code, is_active=True).first()

    # CORE always on
    if feature and feature.is_core:
        if root_id is not None:
            _chf_cache()[(root_id, code)] = True
        return True

    # 3. Active subscription plan
    sub = get_active_subscription(root)
    if sub and not sub.is_blocked() and sub.plan and feature:
        if sub.plan.plan_features.filter(code=code).exists():
            if root_id is not None:
                _chf_cache()[(root_id, code)] = True
            return True

    # 4. Legacy JSONField fallback (for UI flags not yet migrated)
    raw = getattr(root, 'features', None) or {}
    if isinstance(raw, dict) and code in raw and isinstance(raw[code], bool):
        result = raw[code]
        if root_id is not None:
            _chf_cache()[(root_id, code)] = result
        return result

    # If we reached here with no feature row at all, default to False (closed)
    if root_id is not None:
        _chf_cache()[(root_id, code)] = False
    return False


def get_center_feature_limit(center, slug: str):
    """LIMIT/QUOTA feature uchun aktiv tarifdagi limit_value (None = cheksiz).

    `students`/`max_students` uchun mavjud resolve_center_student_limit ishlatiladi.
    """
    from billing.models import PlanFeatureRule, CenterSubscription
    code = _resolve_feature_code(slug)
    if code in ("students", "student_limit", "max_students"):
        return resolve_center_student_limit(center).get("limit")

    root = center.get_root_center() if getattr(center, "parent_center_id", None) else center
    sub = (
        CenterSubscription.objects.filter(center=root, status="ACTIVE")
        .select_related("plan")
        .order_by("-plan__tier")
        .first()
    )
    if not sub:
        return None
    rule = PlanFeatureRule.objects.filter(plan=sub.plan, feature__code=code).first()
    return rule.limit_value if rule else None


def get_center_quota_usage(center, slug: str):
    """QUOTA feature — joriy oy uchun (used_count, limit). limit None = cheksiz."""
    from billing.models import FeatureUsage, PlanFeature
    from django.utils import timezone
    code = _resolve_feature_code(slug)
    root = center.get_root_center() if getattr(center, "parent_center_id", None) else center
    feat = PlanFeature.objects.filter(code=code).first()
    if feat is None:
        return (0, None)
    period = timezone.now().strftime("%Y-%m")
    usage = FeatureUsage.objects.filter(center=root, feature=feat, period=period).first()
    used = usage.used_count if usage else 0
    return (used, get_center_feature_limit(center, code))


def consume_center_quota(center, slug: str, n: int = 1) -> bool:
    """QUOTA feature ishlatilganda joriy oy hisobini oshiradi.

    Feature ochiq bo'lmasa yoki limit oshsa `False` qaytaradi (va oshirmaydi).
    Cheksiz (limit None) bo'lsa doim `True`.
    """
    from billing.models import FeatureUsage, PlanFeature
    from django.db.models import F
    from django.utils import timezone

    if not center_has_feature(center, slug):
        return False
    code = _resolve_feature_code(slug)
    root = center.get_root_center() if getattr(center, "parent_center_id", None) else center
    feat = PlanFeature.objects.filter(code=code).first()
    if feat is None:
        return False
    limit = get_center_feature_limit(center, code)
    period = timezone.now().strftime("%Y-%m")
    usage, _ = FeatureUsage.objects.get_or_create(center=root, feature=feat, period=period)
    if limit is not None and (usage.used_count + n) > limit:
        return False
    FeatureUsage.objects.filter(pk=usage.pk).update(used_count=F("used_count") + n)
    return True


def can_center_use_feature(center, feature_code):
    return center_has_feature(center, feature_code)


# ============================================================
# SUBSCRIPTION HELPERS (No cached_property)
# ============================================================

def get_active_subscription(center: Center) -> CenterSubscription | None:
    """
    Returns the currently ACTIVE center subscription from DB.
    Agar bu markaz filial bo'lsa (parent_center mavjud) — asosiy markazning
    subscriptionini ishlatadi. Shunday qilib 1 ta tarif barcha filiallarni qoplaydi.
    """
    # Filial bo'lsa — root (asosiy) markazning subscriptionini ishlatamiz
    if getattr(center, 'parent_center_id', None):
        root = center.get_root_center()
        return CenterSubscription.objects.filter(
            center=root,
            status=CenterSubscription.Status.ACTIVE
        ).select_related("plan").order_by("-expires_at", "-id").first()

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

    cache.delete_many([
        f"tenant_ctx:sub:v3:{center_id}",
        f"billing:features:v4:{center_id}",
    ])


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

# DEPRECATED 2026-05-06 — replaced by PlanFeature/Plan.plan_features M2M.
# Kept for emergency rollback only. Will be removed after 2026-06-15
# (after the new paying tenant is onboarded and verified on v2).
# DO NOT add new entries here.
FEATURES_BY_PLAN = {
    "FREE":      set(),
    # Legacy plan codes (backward compat — DO NOT remove)
    "STANDARD":  {"finance", "tasks"},
    "PREMIUM":   {"finance", "tasks", "leads"},
    "PRO":       {"finance", "tasks", "leads", "kpi", "store", "sms"},
    "START":     set(),
    "ENTERPRISE": {"finance", "tasks", "leads", "kpi", "store", "sms"},
    # v2 plan codes (active)
    "STANDART":  {"leads", "finance", "xarajatlar", "excel_eksport"},
    "PREMIUM_V2": {
        "leads", "finance", "xarajatlar", "excel_eksport",
        "support_teacher_enabled", "filial_qoshish", "store",
        "imtihon", "sertifikat", "sms",
    },
    "PRO_V2": {
        "leads", "finance", "xarajatlar", "excel_eksport",
        "support_teacher_enabled", "filial_qoshish", "store",
        "imtihon", "sertifikat", "sms",
        "chaqmoq_bonus", "hr", "analytics",
    },
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
    Filial (branch) bo'lsa — alohida subscription YARATMAYDI va mavjudini O'CHIRADI.
    Filiallar faqat asosiy (root) markazning subscriptionidan foydalanadi.
    """
    try:
        # Filial bo'lsa — o'z subscriptionlarini o'chirib, parent dan olamiz
        if getattr(center, 'parent_center_id', None):
            # Agar filialda avval yaratilgan subscription bo'lsa — o'chiramiz
            own = CenterSubscription.objects.filter(center=center)
            if own.exists():
                own.delete()
            return get_active_subscription(center)

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


def get_feature_flags(center):
    """Return set of enabled feature codes for the center (effective state)."""
    from billing.models import CenterFeatureOverride, PlanFeature
    root = center.get_root_center() if getattr(center, 'parent_center_id', None) else center

    cache_key = f"billing:features:v4:{root.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return set(cached)

    enabled = set()

    active_features = list(
        PlanFeature.objects
        .filter(is_active=True)
        .values("id", "code", "is_core")
    )
    feature_id_to_code = {feature["id"]: feature["code"] for feature in active_features}

    overrides = {
        feature_id_to_code[feature_id]: is_enabled
        for feature_id, is_enabled in CenterFeatureOverride.objects
        .filter(center=root, feature_id__in=feature_id_to_code)
        .values_list("feature_id", "enabled")
    }

    plan_codes = set()
    sub = get_active_subscription(root)
    if sub and not sub.is_blocked() and sub.plan_id:
        plan_codes = set(
            sub.plan.plan_features
            .filter(is_active=True)
            .values_list("code", flat=True)
        )

    for feature in active_features:
        code = feature["code"]
        if code in overrides:
            if overrides[code]:
                enabled.add(code)
            continue
        if feature["is_core"] or code in plan_codes:
            enabled.add(code)

    # Also include legacy JSONField truthy keys that have no PlanFeature row,
    # so existing UI flags keep working
    raw = getattr(root, 'features', None) or {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, bool) and v:
                enabled.add(k)

    cache.set(cache_key, sorted(enabled), timeout=60)
    return enabled


def can_add_branch(center: Center) -> tuple[bool, str]:
    """
    Director yangi filial ocha oladimi yoki yo'qligini tekshiradi.
    Qaytaradi: (True, "OK") yoki (False, "sabab")

    Qoidalar:
      - Faqat root (asosiy) markaz uchun chaqirilishi kerak
      - max_branches=0 → cheksiz
      - max_branches=1 → faqat asosiy (filial qo'shib bo'lmaydi)
      - max_branches=N → N-1 ta filial qo'shish mumkin (asosiy + N-1 filial)
    """
    root = center.get_root_center() if getattr(center, 'parent_center_id', None) else center
    sub = get_active_subscription(root)
    if not sub:
        return False, "Aktiv tarif topilmadi. Avval tarif sotib oling."

    # NEW: feature gate
    if not center_has_feature(root, "filial_qoshish"):
        return (
            False,
            f"Tarifingiz ({sub.plan.title if sub.plan else '—'}) "
            f"filial qo'shishga ruxsat bermaydi. PRO yoki PREMIUM tarifga o'ting."
        )

    plan = sub.plan
    max_b = plan.max_branches if plan else 1
    if max_b == 0:
        return True, "OK"
    if max_b == 1:
        return (
            False,
            f"Tarifingiz ({plan.title}) faqat asosiy markazni qo'llab-quvvatlaydi. "
            f"Filial uchun PRO yoki PREMIUM tarif kerak."
        )

    from accounts.models import Center
    current_branches = Center.objects.filter(
        parent_center=root, is_deleted=False, status=Center.STATUS_ACTIVE
    ).count()
    if current_branches >= (max_b - 1):
        return (
            False,
            f"Tarifingizda {max_b - 1} ta filial limiti bor "
            f"({current_branches} ta ishlatilgan). PREMIUM tarifga o'ting."
        )
    return True, "OK"


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
    # Filial → root (subscription source of truth)
    if getattr(center, "parent_center_id", None) and hasattr(center, "get_root_center"):
        center = center.get_root_center()

    active = get_active_subscription(center)
    changed = False

    if active and active.expires_at <= now:
        active.status = CenterSubscription.Status.EXPIRED
        active.save(update_fields=["status"])
        changed = True
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
            changed = True

    if changed:
        try:
            from core.middleware import invalidate_center_tree_cache
            invalidate_center_tree_cache(center)
        except Exception:
            pass


def get_subscription_ui_state(center: Center) -> dict | None:
    try:
        # Filial bo'lsa — asosiy markazda ishlashimiz kerak
        root = center.get_root_center() if getattr(center, 'parent_center_id', None) else center
        check_subscription_expiry(root)
        sub = get_active_subscription(root)
        if not sub:
            # Try to show any current/relevant sub for UI
            sub = CenterSubscription.objects.filter(center=root).order_by("-id").first()
            if not sub: return None
            
        days_left = sub.days_left()
        blocked = sub.is_blocked()
        in_grace_period = sub.in_grace_period()
        grace_hours_left = 0

        if in_grace_period:
            diff = (sub.hard_expires_at - timezone.now()).total_seconds()
            grace_hours_left = max(int(diff / 3600), 0)

        # Progress = qolgan foiz (0 = tugagan, 100 = to'liq muddat)
        progress = 0
        now = timezone.now()
        started = getattr(sub, "started_at", None) or getattr(sub, "created_at", None)
        if sub.expires_at and started and sub.expires_at > now:
            total_span = (sub.expires_at - started).total_seconds()
            remaining = (sub.expires_at - now).total_seconds()
            if total_span > 0:
                progress = int(round((remaining / total_span) * 100))
                progress = max(0, min(100, progress))
            else:
                progress = 100 if remaining > 0 else 0
        elif sub.expires_at and sub.expires_at > now:
            # started_at yo'q bo'lsa ham qolgan kun asosida taxmin
            progress = 100 if days_left > 30 else max(5, min(100, int(days_left * 3)))

        warn = (days_left <= 7 and not blocked and not in_grace_period)
        critical = days_left <= 3 and not blocked

        # STACK INFO (Paused subs) — root markaz bo'yicha
        paused_subs = root.subscriptions.filter(status=CenterSubscription.Status.PAUSED)
        stack_info = []
        for p in paused_subs:
            rem_days = int(p.remaining_seconds / 86400)
            stack_info.append({
                "plan": p.plan.title,
                "days": rem_days
            })

        if blocked:
            status_label = "Bloklangan"
            status_tone = "danger"
        elif in_grace_period:
            status_label = "Grace period"
            status_tone = "warn"
        elif critical:
            status_label = "Kritik"
            status_tone = "danger"
        elif warn:
            status_label = "Tez tugaydi"
            status_tone = "warn"
        else:
            status_label = "Faol"
            status_tone = "ok"

        return {
            "plan_code": sub.plan.code,
            "plan_title": sub.plan.title,
            "plan_tier": sub.plan.tier,
            "expires_at": sub.expires_at,
            "days_left": days_left,
            "blocked": blocked,
            "warn": warn,
            "critical": critical,
            "progress": progress,
            "in_grace_period": in_grace_period,
            "grace_hours_left": grace_hours_left,
            "hard_expires_at": sub.hard_expires_at,
            "stack": stack_info,
            "status_label": status_label,
            "status_tone": status_tone,
        }
    except Exception as e:
        logging.error(f"get_subscription_ui_state error: {str(e)}")
        # Provide basic fallback to prevent 500
        return {
            "plan_code": "ERROR", 
            "plan_title": "System Error", 
            "days_left": 0, "blocked": True
        }
