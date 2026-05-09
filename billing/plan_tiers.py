# billing/plan_tiers.py
"""
Sidebar xususiyatlari va ularning minimum talab qilinadigan tarif darajasi.
Tier: 1=FREE, 10=STANDARD, 20=PRO, 30=PREMIUM
"""

TIER_FREE = 1
TIER_STANDARD = 10
TIER_PRO = 20
TIER_PREMIUM = 30

TIER_LABELS = {
    TIER_FREE: "FREE",
    TIER_STANDARD: "STANDARD",
    TIER_PRO: "PRO",
    TIER_PREMIUM: "PREMIUM",
}

TIER_BADGE_CLASS = {
    TIER_FREE: "tier-free",
    TIER_STANDARD: "tier-standard",
    TIER_PRO: "tier-pro",
    TIER_PREMIUM: "tier-premium",
}

# Sidebar xususiyatlari → minimum talab qilinadigan tarif
SIDEBAR_FEATURE_GATES = {
    # ── FREE (hammaga ochiq) ──────────────────────────────────
    "dashboard":    {"tier": TIER_FREE,     "label": "Boshqaruv paneli",       "icon": "fa-table-columns"},
    "students":     {"tier": TIER_FREE,     "label": "O'quvchilar",             "icon": "fa-user-graduate"},
    "groups":       {"tier": TIER_FREE,     "label": "Guruhlar",                "icon": "fa-layer-group"},

    # ── STANDARD ─────────────────────────────────────────────
    "hr":           {"tier": TIER_STANDARD, "label": "Xodimlar",               "icon": "fa-id-badge"},
    "attendance":   {"tier": TIER_STANDARD, "label": "Davomat",                "icon": "fa-calendar-check"},
    "payments":     {"tier": TIER_STANDARD, "label": "To'lovlar",              "icon": "fa-sack-dollar"},
    "chaqmoq":      {"tier": TIER_STANDARD, "label": "Chaqmoq tizimi",         "icon": "fa-bolt"},
    "debtors":      {"tier": TIER_STANDARD, "label": "Qarzdorlar",             "icon": "fa-user-minus"},
    "notifications":{"tier": TIER_STANDARD, "label": "Xabar yuborish",         "icon": "fa-paper-plane"},

    # ── PRO ──────────────────────────────────────────────────
    "leads":        {"tier": TIER_PRO,      "label": "Leadlar (CRM)",           "icon": "fa-phone-volume"},
    "analytics":    {"tier": TIER_PRO,      "label": "Hisobot va Analitika",    "icon": "fa-chart-pie"},
    "store":        {"tier": TIER_PRO,      "label": "Do'kon (Mahsulotlar)",    "icon": "fa-store"},
    "exams":        {"tier": TIER_PRO,      "label": "Imtihon Sessiyalar",      "icon": "fa-pen-to-square"},
    "certificates": {"tier": TIER_PRO,      "label": "Sertifikatlar",           "icon": "fa-award"},
    "schedule":     {"tier": TIER_PRO,      "label": "Haftalik Jadval",         "icon": "fa-calendar-week"},
    "kpi":          {"tier": TIER_PRO,      "label": "KPI va Hisobotlar",       "icon": "fa-chart-line"},

    # ── PREMIUM ───────────────────────────────────────────────
    "sms":          {"tier": TIER_PREMIUM,  "label": "SMS Xabarnoma",           "icon": "fa-comment-sms"},
    "branches":     {"tier": TIER_PREMIUM,  "label": "Filiallar",               "icon": "fa-code-branch"},
    "ai":           {"tier": TIER_PREMIUM,  "label": "AI Yordamchi",            "icon": "fa-robot"},
}

PLAN_UPGRADE_INFO = {
    TIER_STANDARD: {
        "title": "STANDARD",
        "badge_class": "tier-standard",
        "price": "199,000 so'm/oy",
        "highlight": "Kichik va o'rta o'quv markazlar uchun",
        "features": [
            "Xodimlar boshqaruvi (HR)",
            "To'lovlar va qarzdorlar",
            "Davomat tizimi",
            "Chaqmoq gamifikatsiya",
            "Bildirishnoma yuborish",
        ],
    },
    TIER_PRO: {
        "title": "PRO",
        "badge_class": "tier-pro",
        "price": "399,000 so'm/oy",
        "highlight": "O'sib borayotgan markazlar uchun",
        "features": [
            "Leadlar va CRM tizimi",
            "Kengaytirilgan hisobotlar",
            "Mahsulotlar do'koni",
            "Imtihon sessiyalar",
            "Sertifikat tizimi",
            "Haftalik dars jadvali",
            "KPI va tahlil",
        ],
    },
    TIER_PREMIUM: {
        "title": "PREMIUM",
        "badge_class": "tier-premium",
        "price": "699,000 so'm/oy",
        "highlight": "Barcha imkoniyatlar bir joyda",
        "features": [
            "AI Yordamchi (ChatGPT)",
            "SMS Xabarnoma tizimi",
            "Cheksiz filiallar",
            "Ustuvorlik qo'llab-quvvatlash",
            "Barcha PRO xususiyatlar",
        ],
    },
}


def get_plan_tier_from_code(plan_code: str) -> int:
    code = (plan_code or "").upper()
    mapping = {
        "FREE": TIER_FREE,
        "STANDARD": TIER_STANDARD,
        "PRO": TIER_PRO,
        "PREMIUM": TIER_PREMIUM,
    }
    return mapping.get(code, TIER_FREE)


def get_plan_tier_from_subscription(subscription) -> int:
    if not subscription or not subscription.plan:
        return TIER_FREE
    tier = getattr(subscription.plan, "tier", None)
    if tier:
        return int(tier)
    return get_plan_tier_from_code(getattr(subscription.plan, "code", "FREE"))


def is_feature_locked(feature_code: str, current_tier: int) -> bool:
    gate = SIDEBAR_FEATURE_GATES.get(feature_code)
    if not gate:
        return False
    return current_tier < gate["tier"]


def get_required_tier(feature_code: str) -> int:
    gate = SIDEBAR_FEATURE_GATES.get(feature_code)
    return gate["tier"] if gate else TIER_FREE
