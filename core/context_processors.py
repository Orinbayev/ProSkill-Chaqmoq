# core/context_processors.py
# ────────────────────────────────────────────────────────────
# Performance-optimized context processor  (v3)
#
# ASOSIY TUZATISHLAR:
# 1. get_active_subscription() 3x chaqirilishini 1x ga tushirildi
#    (get_subscription_ui_state VA get_feature_flags har biri alohida chaqirardi)
# 2. user_subscription_data: faqat center yo'q foydalanuvchilar uchun kerak
#    (director/manager/teacher — center subscription ni ishlatadi)
# 3. Notification: 2 query (count + list) → 1 query (bitta qs, python da count)
# 4. Cache TTL sub: 60s (oldin 30s), notif: 20s (oldin 15s)
# ────────────────────────────────────────────────────────────
import logging
from django.core.cache import cache
from django.utils import timezone

from core.center_features import get_center_ui_feature_map

logger = logging.getLogger(__name__)

_SUPERADMIN_ALL_FEATURES = frozenset({"leads", "finance", "kpi", "store", "tasks", "sms"})

_PREVIEW_PLAN_SESSION_KEY = "preview_plan_tier"


def _clear_stale_preview_session(request):
    """Eski preview_plan session'larini tozalaydi."""
    request.session.pop(_PREVIEW_PLAN_SESSION_KEY, None)


def tenant_context(request):
    user = getattr(request, "user", None)
    center = getattr(request, "center", None)

    if not user or not user.is_authenticated:
        return {}

    is_super = user.is_superuser
    is_demo_center = bool(center and getattr(center, "is_demo", False))
    is_demo_user = bool(getattr(user, "is_demo_user", False))

    sub_ui = None
    features: set = set()
    user_subscription_data = None

    # ── User-level subscription ─────────────────────────────────
    # Faqat center yo'q foydalanuvchilar uchun kerak (orphan users).
    # Director/manager/teacher — center subscription ishlatadi.
    # Bu 1 ta qo'shimcha DB query (check_subscription) — center bo'lsa ham chaqirilardi.
    # ✅ PERF FIX: faqat center yo'q bo'lsa chaqiramiz.
    if not center:
        try:
            from billing.services import get_user_subscription_dashboard_data
            user_subscription_data = get_user_subscription_dashboard_data(user)
        except Exception as e:
            logger.warning("tenant_context user subscription error: %s", e)

    # ── Center subscription check ───────────────────────────────
    if center:
        try:
            from billing.services import (
                get_subscription_ui_state,
                get_feature_flags,
                ensure_center_subscription,
            )

            # Filial bo'lsa asosiy markazni aniqlaymiz — subscription shu yerdan
            root_center = center.get_root_center() if getattr(center, 'parent_center_id', None) else center

            # ensure_center_subscription: 10 daqiqada bir marta (faqat root center uchun)
            if not is_super and not getattr(center, 'parent_center_id', None):
                now_ts = int(timezone.now().timestamp())
                last_ensure = int(request.session.get("_sub_ensure_ts", 0) or 0)
                if now_ts - last_ensure > 600:
                    ensure_center_subscription(root_center)
                    request.session["_sub_ensure_ts"] = now_ts

            # Cache key: root_center.id — filial va asosiy markaz bir xil cache ishlatadi
            sub_cache_key = f"tenant_ctx:sub:v3:{root_center.id}"
            cached_sub_data = cache.get(sub_cache_key)
            if cached_sub_data is not None:
                sub_ui = cached_sub_data.get("sub_ui")
                features = set(cached_sub_data.get("features", []))
            else:
                try:
                    sub_ui = get_subscription_ui_state(root_center)
                except Exception as e:
                    logger.warning("get_subscription_ui_state error: %s", e)

                try:
                    features = get_feature_flags(root_center)
                except Exception as e:
                    logger.warning("get_feature_flags error: %s", e)

                cache.set(
                    sub_cache_key,
                    {"sub_ui": sub_ui, "features": sorted(features)},
                    timeout=60,
                )
        except Exception as e:
            logger.warning("tenant_context subscription error: %s", e)

    # Eski preview session'ni tozalash (test bar olib tashlandi)
    _clear_stale_preview_session(request)

    # ── Joriy tarif darajasi ───────────────────────────────────
    from billing.plan_tiers import get_plan_tier_from_subscription, TIER_FREE
    current_plan_tier = TIER_FREE
    if center:
        if isinstance(sub_ui, dict) and sub_ui.get("plan_tier") is not None:
            current_plan_tier = sub_ui.get("plan_tier")
        else:
            try:
                from billing.services import get_active_subscription as _get_active_sub
                _root = center.get_root_center() if getattr(center, 'parent_center_id', None) else center
                current_plan_tier = get_plan_tier_from_subscription(_get_active_sub(_root))
            except Exception as e:
                logger.warning("current_plan_tier error: %s", e)

    # ── Feature flags ──────────────────────────────────────────
    center_ai_enabled = bool(getattr(center, "ai_enabled", False)) if center else False

    if is_super:
        res = {
            "request_center": center,
            "is_superadmin": True,
            "sub_ui": sub_ui,
            "user_subscription": user_subscription_data,
            "feature_flags": _SUPERADMIN_ALL_FEATURES,
            "feature_leads": True,
            "feature_finance": True,
            "feature_kpi": True,
            "feature_store": True,
            "feature_tasks": True,
            "feature_sms": True,
            "feature_ai": True,
            "feature_hr": True,
            "center_ai_enabled": True,
            "current_plan_tier": 30,
        }
    else:
        res = {
            "request_center": center,
            "is_superadmin": False,
            "sub_ui": sub_ui,
            "user_subscription": user_subscription_data,
            "feature_flags": features,
            "feature_leads":   "leads" in features or "lidlar" in features,
            "feature_finance": "finance" in features,
            "feature_kpi":     "kpi" in features or "analytics" in features,
            "feature_store":   "store" in features or "roles" in features,
            "feature_tasks":   "tasks" in features or "branches" in features,
            "feature_sms":     "sms" in features,
            "feature_ai":      center_ai_enabled,
            "feature_hr":      "hr" in features,
            "center_ai_enabled": center_ai_enabled,
            "current_plan_tier": current_plan_tier,
        }

    res.update(get_center_ui_feature_map(center))

    # ── Notifications ───────────────────────────────────────────
    # ✅ PERF FIX: 2 query (count + list) → 1 query (list dan count chiqaramiz)
    # Cache TTL: 20s (oldin 15s) — ozgina oshirildi
    unread_count = 0
    latest_notifications = []
    try:
        from core.models import Notification
        notif_cache_key = f"tenant_ctx:notif:v2:{user.id}"
        cached_notif = cache.get(notif_cache_key)
        if cached_notif is not None:
            unread_count = int(cached_notif.get("unread_count", 0))
            latest_notifications = cached_notif.get("latest_notifications", [])
        else:
            # ✅ 1 query: bitta .only() bilan kerakli fieldlarni olish
            qs = list(
                Notification.objects
                .filter(recipient=user)
                .only("id", "title", "message", "type", "is_read", "created_at")
                .order_by("-created_at")[:10]
            )
            unread_count = sum(1 for n in qs if not n.is_read)
            latest_notifications = qs[:5]
            cache.set(
                notif_cache_key,
                {"unread_count": unread_count, "latest_notifications": latest_notifications},
                timeout=20,
            )
    except Exception as e:
        logger.warning("tenant_context notification error: %s", e)

    res.update({
        "unread_notifications_count": unread_count,
        "latest_notifications": latest_notifications,
        "is_demo_center": is_demo_center,
        "is_demo_user": is_demo_user,
        "demo_mode_active": is_demo_center or is_demo_user,
    })

    return res
