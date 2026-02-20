# core/context_processors.py
# ────────────────────────────────────────────────────────────
# Performance-optimized context processor
# • ensure_center_subscription() faqat zarur hollarda chaqiriladi
# • Notification query — faqat authenticated user uchun, cache bilan
# • is_superadmin context flag — sidebar va template uchun
# ────────────────────────────────────────────────────────────
import logging
logger = logging.getLogger(__name__)


def tenant_context(request):
    user = getattr(request, "user", None)
    center = getattr(request, "center", None)

    if not user or not user.is_authenticated:
        return {}

    is_super = user.is_superuser

    sub_ui = None
    features = set()

    # ── Subscription check (faqat center mavjud bo'lsa) ────────
    # ensure_center_subscription() har requestda emas,
    # faqat center-specific URLlarda chaqiriladi.
    if center and not is_super:
        try:
            from billing.services import (
                get_subscription_ui_state,
                get_feature_flags,
                ensure_center_subscription,
            )
            ensure_center_subscription(center)
            sub_ui = get_subscription_ui_state(center)
            features = get_feature_flags(center)
        except Exception as e:
            logger.warning(f"tenant_context subscription error: {e}")

    # ── Feature flags ──────────────────────────────────────────
    if is_super:
        # Superadmin — barcha flaglar ochiq
        res = {
            "request_center": center,
            "is_superadmin": True,
            "sub_ui": sub_ui,
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
            "feature_flags": features,
            "feature_leads": "leads" in features,
            "feature_finance": "finance" in features,
            "feature_kpi": "kpi" in features,
            "feature_store": "store" in features,
            "feature_tasks": "tasks" in features,
            "feature_sms": "sms" in features,
        }

    # ── Notifications (bitta query, faqat authenticated) ───────
    unread_count = 0
    latest_notifications = []
    try:
        from core.models import Notification
        qs = Notification.objects.filter(recipient=user).order_by("-created_at")
        # values_list avoids full model hydration for count
        unread_count = qs.filter(is_read=False).count()
        latest_notifications = list(qs[:5])
    except Exception as e:
        logger.warning(f"tenant_context notification error: {e}")

    res.update({
        "unread_notifications_count": unread_count,
        "latest_notifications": latest_notifications,
    })

    return res
