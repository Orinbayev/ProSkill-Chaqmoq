# core/context_processors.py
# ────────────────────────────────────────────────────────────
# Performance-optimized context processor
# • ensure_center_subscription() faqat zarur hollarda chaqiriladi
# • Notification query — faqat authenticated user uchun, cache bilan
# • is_superadmin context flag — sidebar va template uchun
# ────────────────────────────────────────────────────────────
import logging
from django.core.cache import cache
from django.utils import timezone
logger = logging.getLogger(__name__)


def tenant_context(request):
    user = getattr(request, "user", None)
    center = getattr(request, "center", None)

    if not user or not user.is_authenticated:
        return {}

    is_super = user.is_superuser
    is_demo_center = bool(center and getattr(center, "is_demo", False))
    is_demo_user = bool(getattr(user, "is_demo_user", False))

    sub_ui = None
    features = set()
    user_subscription_data = None

    # User-level subscription (auto-expire check)
    try:
        from billing.services import get_user_subscription_dashboard_data
        user_subscription_data = get_user_subscription_dashboard_data(user)
    except Exception as e:
        logger.warning(f"tenant_context user subscription error: {e}")

    # ── Subscription check (faqat center mavjud bo'lsa) ────────
    # ensure_center_subscription() har requestda emas,
    # faqat center-specific URLlarda chaqiriladi.
    if center:
        try:
            from billing.services import (
                get_subscription_ui_state,
                get_feature_flags,
                ensure_center_subscription,
            )
            # Only ensure/refresh if not superadmin (superadmins just view).
            # Throttle to avoid repeating heavy checks on every request.
            if not is_super:
                now_ts = int(timezone.now().timestamp())
                last_ensure = int(request.session.get("_sub_ensure_ts", 0) or 0)
                if now_ts - last_ensure > 600:
                    ensure_center_subscription(center)
                    request.session["_sub_ensure_ts"] = now_ts

            sub_cache_key = f"tenant_ctx:sub:{center.id}"
            cached_sub_data = cache.get(sub_cache_key)
            if cached_sub_data:
                sub_ui = cached_sub_data.get("sub_ui")
                features = set(cached_sub_data.get("features", []))
            else:
                sub_ui = get_subscription_ui_state(center)
                features = get_feature_flags(center)
                cache.set(
                    sub_cache_key,
                    {
                        "sub_ui": sub_ui,
                        "features": sorted(features),
                    },
                    timeout=30,
                )
        except Exception as e:
            logger.warning(f"tenant_context subscription error: {e}")

    # ── Feature flags ──────────────────────────────────────────
    if is_super:
        # Superadmin — barcha flaglar ochiq
        res = {
            "request_center": center,
            "is_superadmin": True,
            "sub_ui": sub_ui,
            "user_subscription": user_subscription_data,
            "feature_flags": {"leads", "finance", "kpi", "store", "tasks", "sms"},
            "feature_leads": True,
            "feature_finance": True,
            "feature_kpi": True,
            "feature_store": True,
            "feature_tasks": True,
            "feature_sms": True,
        }
    else:
        res = {
            "request_center": center,
            "is_superadmin": False,
            "sub_ui": sub_ui,
            "user_subscription": user_subscription_data,
            "feature_flags": features,
            "feature_leads": "leads" in features,
            "feature_finance": "finance" in features,
            "feature_kpi": "kpi" in features or "analytics" in features,
            "feature_store": "store" in features or "roles" in features,
            "feature_tasks": "tasks" in features or "branches" in features,
            "feature_sms": "sms" in features,
        }

    # ── Notifications (bitta query, faqat authenticated) ───────
    unread_count = 0
    latest_notifications = []
    try:
        from core.models import Notification
        notif_cache_key = f"tenant_ctx:notif:{user.id}"
        cached_notif = cache.get(notif_cache_key)
        if cached_notif:
            unread_count = int(cached_notif.get("unread_count", 0))
            latest_notifications = cached_notif.get("latest_notifications", [])
        else:
            qs = Notification.objects.filter(recipient=user).order_by("-created_at")
            unread_count = qs.filter(is_read=False).count()
            latest_notifications = list(qs[:5])
            cache.set(
                notif_cache_key,
                {
                    "unread_count": unread_count,
                    "latest_notifications": latest_notifications,
                },
                timeout=15,
            )
    except Exception as e:
        logger.warning(f"tenant_context notification error: {e}")

    res.update({
        "unread_notifications_count": unread_count,
        "latest_notifications": latest_notifications,
        "is_demo_center": is_demo_center,
        "is_demo_user": is_demo_user,
        "demo_mode_active": is_demo_center or is_demo_user,
    })

    return res
