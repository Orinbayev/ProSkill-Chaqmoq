# core/context_processors.py
from billing.services import get_subscription_ui_state, get_feature_flags, ensure_center_subscription

def tenant_context(request):
    user = getattr(request, "user", None)
    center = getattr(request, "center", None)
    is_super = bool(user and user.is_authenticated and user.is_superuser)

    sub_ui = None
    features = set()

    # 1. Obunani aniqlash (faqat center tanlangan bo'lsa)
    try:
        if user and user.is_authenticated and center:
            # Superadmin uchun ham sub_ui kerak bo'lishi mumkin (infobar uchun)
            ensure_center_subscription(center)
            sub_ui = get_subscription_ui_state(center)
            features = get_feature_flags(center)
    except Exception as e:
        import logging
        logging.error(f"tenant_context error: {str(e)}")
        # Continue with defaults

    # 2. Flaglarni shakllantirish
    if is_super:
        # ✅ Superadmin uchun HAMMA bo'limlar ochiq bo'lishi shart
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
        # Oddiy foydalanuvchilar (Director/Manager) uchun planga qarab
        # Agar sub_ui None bo'lsa (yangi center), default flaglar bo'sh bo'ladi
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
    return res
