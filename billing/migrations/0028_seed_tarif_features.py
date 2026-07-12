"""Data-driven tariflar uchun seed — IDEMPOTENT va ADDITIV.

Muhim qoidalar (buzilmasin):
- Hech narsa O'CHIRILMAYDI. Faqat get_or_create + additiv .add() + update.
- M2M `plan_features` HECH QACHON tozalanmaydi — faqat qo'shiladi (teacherowski'ning
  mavjud extralari saqlanadi).
- CORE featurelar barcha tarifda ochiq (center_has_feature is_core orqali doim True).
- Center.features / CenterFeatureOverride'larga TEGILMAYDI.
"""
from django.db import migrations


# ── Feature ta'riflari: (code, name_uz, category, type) ──────────────────
CORE_FEATURES = [
    ("dashboard", "Boshqaruv paneli", "core"),
    ("students", "O'quvchilar", "core"),
    ("staff", "Xodimlar", "team"),
    ("leads_crm", "Leadlar (CRM)", "core"),
    ("salary_report", "Maosh hisoboti", "finance"),
    ("groups", "Guruhlar", "core"),
    ("debtors", "Qarzdorlar", "finance"),
    ("payments", "To'lovlar", "finance"),
    ("attendance", "Davomat", "core"),
    ("schedule", "Dars jadvali", "core"),
    ("parents", "Ota-onalar", "core"),
    ("shop", "Do'kon", "core"),
    ("shop_requests", "Do'kon so'rovlari", "core"),
    ("chaqmoq_points", "Chaqmoq ballari", "core"),
    ("chaqmoq_rating", "Chaqmoq reytingi", "core"),
    ("chaqmoq_rules", "Chaqmoq qoidalari", "core"),
    ("games", "O'yinlar", "core"),
    ("permissions", "Ruxsatlar", "team"),
    ("trash", "Savat (o'chirilganlar)", "core"),
    ("manual_notifications", "Qo'lda xabar yuborish", "marketing"),
    ("excel_export", "Excel yuklab olish", "core"),
    ("dark_mode", "Tungi rejim", "core"),
]

PREMIUM_FEATURES = [
    ("parent_telegram_portal", "Ota-ona Telegram portali", "marketing"),
    ("auto_debt_reminder", "Avto qarz eslatmasi", "marketing"),
    ("auto_lesson_reminder", "Avto dars eslatmasi", "marketing"),
    ("bulk_segmented_message", "Segmentli ommaviy xabar", "marketing"),
    ("scheduled_report", "Rejalashtirilgan hisobot", "finance"),
    ("advanced_analytics", "Chuqur analitika", "advanced"),
    ("teacher_mobile_web", "O'qituvchi mobil web", "advanced"),
]

# PRO featurelar: (code, name_uz, category, type)
PRO_FEATURES = [
    ("ai_assistant", "AI Yordamchi", "advanced", "QUOTA"),
    ("ai_churn_prediction", "AI ketish bashorati", "advanced", "BOOLEAN"),
    ("mobile_app_access", "Mobil ilova kirishi", "advanced", "BOOLEAN"),
    ("multi_branch", "Ko'p filial", "advanced", "BOOLEAN"),
    ("custom_roles", "Maxsus rollar", "team", "BOOLEAN"),
    ("api_access", "API kirish", "advanced", "BOOLEAN"),
    ("priority_support", "Ustuvor qo'llab-quvvatlash", "advanced", "BOOLEAN"),
]

AI_QUOTA_PER_MONTH = 500

# Kanonik tariflar: code -> (title, tier, max_students, landing_visible)
CANONICAL_PLANS = {
    "STANDART": ("Standart", 10, 200),
    "PREMIUM": ("Premium", 20, 450),
    "PRO": ("PRO", 30, 2000),
    "CUSTOM": ("Custom", 40, 1000000),  # cheksiz o'rniga katta son (0-handling'ga bog'liq emas)
}


def seed(apps, schema_editor):
    PlanFeature = apps.get_model("billing", "PlanFeature")
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    PlanFeatureRule = apps.get_model("billing", "PlanFeatureRule")
    CenterSubscription = apps.get_model("billing", "CenterSubscription")

    # 1) Featurelarni yaratish/yangilash (idempotent) ───────────────────────
    order = 0

    def upsert_feature(code, name_uz, category, ftype, is_core):
        nonlocal order
        order += 1
        obj, created = PlanFeature.objects.get_or_create(
            code=code,
            defaults={
                "name": name_uz, "name_uz": name_uz, "category": category,
                "type": ftype, "is_core": is_core, "is_active": True, "order": order,
            },
        )
        # Mavjud bo'lsa: faqat type/is_core to'g'rilaymiz (nom/tavsifga tegmaymiz).
        changed = False
        if obj.type != ftype:
            obj.type = ftype; changed = True
        if obj.is_core != is_core:
            obj.is_core = is_core; changed = True
        if not obj.name_uz:
            obj.name_uz = name_uz; changed = True
        if changed:
            obj.save(update_fields=["type", "is_core", "name_uz"])
        return obj

    feat = {}
    for code, name_uz, cat in CORE_FEATURES:
        feat[code] = upsert_feature(code, name_uz, cat, "CORE", True)
    for code, name_uz, cat in PREMIUM_FEATURES:
        feat[code] = upsert_feature(code, name_uz, cat, "BOOLEAN", False)
    for code, name_uz, cat, ftype in PRO_FEATURES:
        feat[code] = upsert_feature(code, name_uz, cat, ftype, False)

    # 2) Kanonik tariflar (idempotent) ──────────────────────────────────────
    plan_obj = {}
    for code, (title, tier, max_students) in CANONICAL_PLANS.items():
        p, _ = SubscriptionPlan.objects.get_or_create(
            code=code,
            defaults={
                "title": title, "name": title, "tier": tier,
                "max_students": max_students, "active": True, "landing_visible": True,
            },
        )
        # Mavjud kanonik tarif: limitni spec qiymatiga keltiramiz, ko'rinadigan qilamiz.
        fields = []
        if p.max_students != max_students:
            p.max_students = max_students; fields.append("max_students")
        if not p.landing_visible:
            p.landing_visible = True; fields.append("landing_visible")
        if not p.active:
            p.active = True; fields.append("active")
        if fields:
            p.save(update_fields=fields)
        plan_obj[code] = p

    # 3) PlanFeatureRule + M2M sync (ADDITIV) ────────────────────────────────
    def enable(plan, feature, limit_value=None):
        rule, _ = PlanFeatureRule.objects.get_or_create(
            plan=plan, feature=feature,
            defaults={"enabled": True, "limit_value": limit_value},
        )
        fields = []
        if not rule.enabled:
            rule.enabled = True; fields.append("enabled")
        if limit_value is not None and rule.limit_value != limit_value:
            rule.limit_value = limit_value; fields.append("limit_value")
        if fields:
            rule.save(update_fields=fields)
        # M2M — faqat qo'shamiz, hech qachon olib tashlamaymiz.
        plan.plan_features.add(feature)

    core_codes = [c for c, *_ in CORE_FEATURES]
    premium_codes = [c for c, *_ in PREMIUM_FEATURES]
    pro_codes = [c for c, *_ in PRO_FEATURES]

    # CORE — barcha kanonik tarifda ochiq
    for code in CANONICAL_PLANS:
        for fc in core_codes:
            enable(plan_obj[code], feat[fc])
    # PREMIUM featurelar — PREMIUM, PRO, CUSTOM
    for code in ("PREMIUM", "PRO", "CUSTOM"):
        for fc in premium_codes:
            enable(plan_obj[code], feat[fc])
    # PRO featurelar — PRO, CUSTOM (ai_assistant QUOTA=500)
    for code in ("PRO", "CUSTOM"):
        for fc in pro_codes:
            limit = AI_QUOTA_PER_MONTH if fc == "ai_assistant" else None
            enable(plan_obj[code], feat[fc], limit_value=limit)

    # 4) Ortiqcha/test tariflarni landingdan yashirish (o'chirmasdan) ─────────
    canonical = set(CANONICAL_PLANS.keys())
    for p in SubscriptionPlan.objects.exclude(code__in=canonical):
        if p.landing_visible:
            p.landing_visible = False
            p.save(update_fields=["landing_visible"])

    # 5) Mavjud aktiv obunalarni grandfather qilish (additiv) ────────────────
    CenterSubscription.objects.filter(status="ACTIVE", is_grandfathered=False).update(
        is_grandfathered=True
    )


def noop(apps, schema_editor):
    # Seed teskari qaytarilmaydi (ma'lumot o'chirilmaydi).
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0027_centersubscription_is_grandfathered_planfeature_type_and_more"),
    ]
    operations = [migrations.RunPython(seed, noop)]
