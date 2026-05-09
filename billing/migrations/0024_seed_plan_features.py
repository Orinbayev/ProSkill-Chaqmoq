# billing/migrations/0024_seed_plan_features.py
#
# Data migration: PlanFeature jadvali uchun barcha standart modullarni seed qiladi.
# Idempotent — xavfsiz ko'p marta ishlatilishi mumkin (update_or_create).
# Render serverida `python manage.py migrate` bilan avtomatik ishlaydi.

from django.db import migrations

FEATURES = [
    # ── CORE ─────────────────────────────────────────────────────────────────
    # is_core=True: barcha tariflarda avtomatik yoqiq
    {
        "code": "students",
        "name": "O'quvchilar boshqaruvi",
        "name_uz": "O'quvchilar boshqaruvi",
        "description": "O'quvchilarni qo'shish, tahrirlash, kuzatish",
        "description_uz": "O'quvchilarni qo'shish, tahrirlash, kuzatish",
        "category": "core",
        "icon": "👨‍🎓",
        "is_core": True,
        "order": 1,
        "implementation_status": "READY",
    },
    {
        "code": "groups",
        "name": "Guruhlar boshqaruvi",
        "name_uz": "Guruhlar boshqaruvi",
        "description": "Guruh yaratish, dars jadvali, ro'yxat",
        "description_uz": "Guruh yaratish, dars jadvali, ro'yxat",
        "category": "core",
        "icon": "📚",
        "is_core": True,
        "order": 2,
        "implementation_status": "READY",
    },
    {
        "code": "teachers",
        "name": "O'qituvchilar",
        "name_uz": "O'qituvchilar ro'yxati",
        "description": "O'qituvchilar boshqaruvi",
        "description_uz": "O'qituvchilar boshqaruvi",
        "category": "core",
        "icon": "👩‍🏫",
        "is_core": True,
        "order": 3,
        "implementation_status": "READY",
    },
    {
        "code": "davomat",
        "name": "Davomat",
        "name_uz": "Davomat tizimi",
        "description": "Kunlik davomat belgilash va kuzatish",
        "description_uz": "Kunlik davomat belgilash va kuzatish",
        "category": "core",
        "icon": "✅",
        "is_core": True,
        "order": 4,
        "implementation_status": "READY",
    },
    {
        "code": "payments",
        "name": "To'lovlar",
        "name_uz": "To'lovlar tizimi",
        "description": "O'quvchilar to'lovini qabul qilish va kuzatish",
        "description_uz": "O'quvchilar to'lovini qabul qilish va kuzatish",
        "category": "core",
        "icon": "💳",
        "is_core": True,
        "order": 5,
        "implementation_status": "READY",
    },
    {
        "code": "gamification",
        "name": "Gamifikatsiya (Chaqmoq)",
        "name_uz": "Chaqmoq gamifikatsiya",
        "description": "O'quvchilarni rag'batlantirish, ball tizimi",
        "description_uz": "O'quvchilarni rag'batlantirish, ball tizimi",
        "category": "core",
        "icon": "⚡",
        "is_core": True,
        "order": 6,
        "implementation_status": "READY",
    },

    # ── FINANCE ──────────────────────────────────────────────────────────────
    {
        "code": "finance",
        "name": "Moliya boshqaruvi",
        "name_uz": "Moliya va hisobot",
        "description": "Daromad, xarajat, balans nazorati",
        "description_uz": "Daromad, xarajat, balans nazorati",
        "category": "finance",
        "icon": "💰",
        "is_core": False,
        "order": 1,
        "implementation_status": "READY",
    },
    {
        "code": "xarajatlar",
        "name": "Xarajatlar",
        "name_uz": "Xarajatlar moduli",
        "description": "Oylik xarajatlarni kiritish va hisobot",
        "description_uz": "Oylik xarajatlarni kiritish va hisobot",
        "category": "finance",
        "icon": "📊",
        "is_core": False,
        "order": 2,
        "implementation_status": "READY",
    },
    {
        "code": "excel_eksport",
        "name": "Excel eksport",
        "name_uz": "Excel eksport",
        "description": "Ma'lumotlarni Excel'ga eksport qilish",
        "description_uz": "Ma'lumotlarni Excel'ga eksport qilish",
        "category": "finance",
        "icon": "📥",
        "is_core": False,
        "order": 3,
        "implementation_status": "READY",
    },
    {
        "code": "analytics",
        "name": "Analitika va Hisobotlar",
        "name_uz": "Kengaytirilgan analitika",
        "description": "Daromad, o'quvchi dinamikasi, prognoz hisobotlari",
        "description_uz": "Daromad, o'quvchi dinamikasi, prognoz hisobotlari",
        "category": "finance",
        "icon": "📈",
        "is_core": False,
        "order": 4,
        "implementation_status": "READY",
    },
    {
        "code": "store",
        "name": "Qarzdorlar tizimi",
        "name_uz": "Qarzdorlar va eslatmalar",
        "description": "To'lamaganlarni kuzatish va eslatma yuborish",
        "description_uz": "To'lamaganlarni kuzatish va eslatma yuborish",
        "category": "finance",
        "icon": "🔔",
        "is_core": False,
        "order": 5,
        "implementation_status": "READY",
    },
    {
        "code": "kpi",
        "name": "KPI va Samaradorlik",
        "name_uz": "KPI va samaradorlik ko'rsatkichlari",
        "description": "O'qituvchi va markaz KPI hisoboti",
        "description_uz": "O'qituvchi va markaz KPI hisoboti",
        "category": "finance",
        "icon": "🎯",
        "is_core": False,
        "order": 6,
        "implementation_status": "READY",
    },

    # ── MARKETING ────────────────────────────────────────────────────────────
    {
        "code": "leads",
        "name": "Leadlar va CRM",
        "name_uz": "Leadlar va CRM tizimi",
        "description": "Potensial o'quvchilarni sistemali kuzatish",
        "description_uz": "Potensial o'quvchilarni sistemali kuzatish",
        "category": "marketing",
        "icon": "📞",
        "is_core": False,
        "order": 1,
        "implementation_status": "READY",
    },
    {
        "code": "sms",
        "name": "SMS Xabarnoma",
        "name_uz": "SMS avtomatik xabarlar",
        "description": "To'lov, davomat, eslatma SMS avtomatik yuborish",
        "description_uz": "To'lov, davomat, eslatma SMS avtomatik yuborish",
        "category": "marketing",
        "icon": "💬",
        "is_core": False,
        "order": 2,
        "implementation_status": "READY",
    },
    {
        "code": "imtihon",
        "name": "Imtihon Sessiyalar",
        "name_uz": "Imtihon sessiyalari",
        "description": "Professional imtihon tizimi — natijalar avtomatik hisoblanadi",
        "description_uz": "Professional imtihon tizimi — natijalar avtomatik hisoblanadi",
        "category": "marketing",
        "icon": "📝",
        "is_core": False,
        "order": 3,
        "implementation_status": "READY",
    },
    {
        "code": "sertifikat",
        "name": "Sertifikatlar",
        "name_uz": "Sertifikat tizimi",
        "description": "Professional sertifikat chiqarish va PDF eksport",
        "description_uz": "Professional sertifikat chiqarish va PDF eksport",
        "category": "marketing",
        "icon": "🏆",
        "is_core": False,
        "order": 4,
        "implementation_status": "READY",
    },

    # ── TEAM ─────────────────────────────────────────────────────────────────
    {
        "code": "hr",
        "name": "Xodimlar boshqaruvi (HR)",
        "name_uz": "HR — Xodimlar va maosh",
        "description": "Xodimlar, oylik maosh, KPI hisoblash",
        "description_uz": "Xodimlar, oylik maosh, KPI hisoblash",
        "category": "team",
        "icon": "👥",
        "is_core": False,
        "order": 1,
        "implementation_status": "READY",
    },
    {
        "code": "filial_qoshish",
        "name": "Filiallar boshqaruvi",
        "name_uz": "Ko'p filial — bir panel",
        "description": "Bir nechta filialni bitta paneldan boshqarish",
        "description_uz": "Bir nechta filialni bitta paneldan boshqarish",
        "category": "team",
        "icon": "🏫",
        "is_core": False,
        "order": 2,
        "implementation_status": "READY",
    },
    {
        "code": "support_teacher_enabled",
        "name": "Qo'shimcha o'qituvchi",
        "name_uz": "Qo'shimcha o'qituvchi profili",
        "description": "Yordamchi o'qituvchi akkauntini qo'shish imkoni",
        "description_uz": "Yordamchi o'qituvchi akkauntini qo'shish imkoni",
        "category": "team",
        "icon": "🧑‍🏫",
        "is_core": False,
        "order": 3,
        "implementation_status": "READY",
    },
    {
        "code": "roles",
        "name": "Rol tizimi",
        "name_uz": "Foydalanuvchi rollari",
        "description": "Menejer, admin, o'qituvchi rollarini boshqarish",
        "description_uz": "Menejer, admin, o'qituvchi rollarini boshqarish",
        "category": "team",
        "icon": "🔑",
        "is_core": False,
        "order": 4,
        "implementation_status": "READY",
    },
    {
        "code": "tasks",
        "name": "Vazifalar tizimi",
        "name_uz": "Vazifalar va topshiriqlar",
        "description": "Xodimlar uchun vazifa va topshiriqlar boshqaruvi",
        "description_uz": "Xodimlar uchun vazifa va topshiriqlar boshqaruvi",
        "category": "team",
        "icon": "📋",
        "is_core": False,
        "order": 5,
        "implementation_status": "READY",
    },

    # ── ADVANCED ─────────────────────────────────────────────────────────────
    {
        "code": "ai_assistant",
        "name": "AI Yordamchi",
        "name_uz": "ChatGPT texnologiyali AI yordamchi",
        "description": "7/24 AI savol-javob, markaz ma'lumotlari asosida",
        "description_uz": "7/24 AI savol-javob, markaz ma'lumotlari asosida",
        "category": "advanced",
        "icon": "🤖",
        "is_core": False,
        "order": 1,
        "implementation_status": "READY",
    },
    {
        "code": "chaqmoq_bonus",
        "name": "Chaqmoq Bonus tizimi",
        "name_uz": "Mukofot va bonus tizimi",
        "description": "O'quvchilarga ball va mukofot berish tizimi",
        "description_uz": "O'quvchilarga ball va mukofot berish tizimi",
        "category": "advanced",
        "icon": "⚡",
        "is_core": False,
        "order": 2,
        "implementation_status": "READY",
    },
    {
        "code": "schedule",
        "name": "Haftalik Dars Jadvali",
        "name_uz": "Drag&drop dars jadvali",
        "description": "Haftalik jadval — konflikt aniqlash va eksport",
        "description_uz": "Haftalik jadval — konflikt aniqlash va eksport",
        "category": "advanced",
        "icon": "🗓️",
        "is_core": False,
        "order": 3,
        "implementation_status": "PLANNED",
    },
]


def seed_features(apps, schema_editor):
    PlanFeature = apps.get_model("billing", "PlanFeature")
    for f in FEATURES:
        obj, created = PlanFeature.objects.get_or_create(
            code=f["code"],
            defaults={
                "name": f["name"],
                "name_uz": f.get("name_uz", ""),
                "description": f.get("description", ""),
                "description_uz": f.get("description_uz", ""),
                "category": f["category"],
                "icon": f["icon"],
                "is_core": f.get("is_core", False),
                "order": f.get("order", 0),
                "is_active": True,
                "implementation_status": f.get("implementation_status", "READY"),
                "show_on_landing": True,
            },
        )
        if not created:
            # Mavjud bo'lsa icon va metani yangilaymiz (is_core, category o'zgarmaydi)
            update_fields = []
            if not obj.icon:
                obj.icon = f["icon"]
                update_fields.append("icon")
            if not obj.name_uz:
                obj.name_uz = f.get("name_uz", "")
                update_fields.append("name_uz")
            if not obj.description_uz:
                obj.description_uz = f.get("description_uz", "")
                update_fields.append("description_uz")
            if not obj.is_active:
                obj.is_active = True
                update_fields.append("is_active")
            if update_fields:
                obj.save(update_fields=update_fields)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0023_planfeature_implementation_status_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_features, noop),
    ]
