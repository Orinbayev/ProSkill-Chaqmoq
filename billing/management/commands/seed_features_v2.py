# billing/management/commands/seed_features_v2.py
"""
Tarif v2 — Bosqich 2/7: PlanFeature seed (idempotent).

Aniq 16 ta featureni `PlanFeature.objects.update_or_create(code=...)` orqali yaratadi/yangilaydi.
Qayta-qayta xavfsiz ishga tushirilishi mumkin.

Bosqich 7 audit (2026-05-06): har bir feature uchun `implementation_status`,
`show_on_landing` va `is_highlight` aniq belgilandi. PLANNED featurelar
landing'da yashirin va `is_active=False` (DB'da qoladi, saqlanadi).
"""
from django.core.management.base import BaseCommand

from billing.models import PlanFeature


# Tuple format:
# (code, name_uz, category, is_core, order, icon, description_uz,
#  impl_status, show_on_landing, is_highlight)
FEATURES = [
    # ────────────────────── CORE ──────────────────────
    ("dashboard", "Boshqaruv paneli (Dashboard)", "CORE", True, 5, "📊",
     "Director, Manager, Teacher, Student va Ota-ona uchun alohida boshqaruv panellari. "
     "Sayt'ning asosiy boshqaruv markazi.",
     "READY", True, True),
    ("oquvchi_crud", "O'quvchilar va guruhlar", "CORE", True, 10, "👥",
     "O'quvchi qo'shish, tahrirlash, o'chirish, guruhga biriktirish.",
     "READY", True, True),
    ("davomat", "Davomat (sababli / sababsiz)", "CORE", True, 20, "✓",
     "Sababli/sababsiz davomat, kunlik va oylik hisobot.",
     "READY", True, True),
    ("tolovlar", "To'lovlar va qarzdorlar", "CORE", True, 30, "💰",
     "To'lov qabul qilish, qarzdorlar ro'yxati, oylik hisob-kitob.",
     "READY", True, True),
    ("rollar", "Rollar (Director/Manager/Teacher/Student/Parent)", "CORE", True, 40, "🔑",
     "5 ta alohida rol uchun ajratilgan panellar va ruxsatlar.",
     "READY", False, False),

    # ────────────────────── FINANCE ──────────────────────
    ("moliya_statistika", "Moliya statistikasi va Excel hisobotlar", "FINANCE", False, 50, "📊",
     "Daromad, sof foyda, qarzdorlik diagrammalari + Excel formatida yuklab olish.",
     "READY", True, True),
    ("excel_export", "Excel export", "FINANCE", False, 60, "📥",
     "Qarzdorlar, xarajatlar va to'lovlar Excel formatida yuklab olish.",
     "READY", False, False),
    ("chegirmali_narh", "Chegirmali narh formulasi", "FINANCE", False, 70, "🏷",
     "Tekin o'quvchi, chegirmali narh va o'qtuvchi 40% ulushini avtomatik hisoblash.",
     "READY", False, False),

    # ────────────────────── TEAM ──────────────────────
    ("filial_qoshish", "Filiallar boshqaruvi", "TEAM", False, 80, "🏢",
     "Asosiy markazga qo'shimcha filiallar qo'shish, tahrirlash va boshqarish.",
     "READY", True, True),
    ("filial_crud", "Filial CRUD (tahrir/o'chir)", "TEAM", False, 90, "✏️",
     "Director paneldan filiallarni boshqarish, tahrirlash va o'chirish.",
     "READY", False, False),

    # ────────────────────── MARKETING ──────────────────────
    ("telegram_bot", "Telegram bot va lidlar (CRM)", "MARKETING", False, 100, "🤖",
     "O'qtuvchi, o'quvchi va ota-ona uchun Telegram bot integratsiyasi + demo so'ragan lidlar boshqaruvi.",
     "READY", True, True),
    ("lidlar", "Lidlar (Leads)", "MARKETING", False, 110, "📞",
     "Demo so'ragan mijozlar va lid menejmenti.",
     "READY", False, False),

    # ────────────────────── ADVANCED ──────────────────────
    ("ai_assistant", "AI yordamchi (Gemini)", "ADVANCED", False, 120, "🧠",
     "Markaz haqidagi savollarga javob beruvchi sun'iy intellekt.",
     "READY", True, True),
    ("bashorat", "Bashorat (Forecast)", "ADVANCED", False, 130, "🔮",
     "O'quvchi o'sishi va daromad bashorati AI yordamida.",
     # PARTIAL: backend bor (core/services/ai_insights.py:_forecast_bundle),
     # alohida UI sifatida hozircha AI assistant ichida ko'rinadi.
     "PARTIAL", False, False),
    ("kpi_tracker", "KPI Tracker", "ADVANCED", False, 140, "🎯",
     "O'qtuvchilar va managerlar samaradorligini kuzatish.",
     # PARTIAL: feature_kpi flag bor, lekin alohida KPI dashboard yo'q —
     # faqat teacher_salary_summary linki sifatida ko'rinadi.
     "PARTIAL", False, False),
    ("gdrive_backup", "Google Drive backup (avtomatik)", "ADVANCED", False, 150, "💾",
     "Avtomatik kunlik bazani Google Drive'ga zaxiralash.",
     "READY", True, True),
    ("sms", "SMS yuborish", "ADVANCED", False, 160, "✉️",
     "O'quvchilar va ota-onalarga ommaviy SMS yuborish.",
     # PLANNED: hozircha implementatsiya yo'q (faqat marketing matnlarda).
     "PLANNED", False, False),
]


# Model `category` choices'dagi qiymatlar lower-case ("core", "finance", ...).
CATEGORY_MAP = {
    "CORE": "core",
    "FINANCE": "finance",
    "MARKETING": "marketing",
    "TEAM": "team",
    "ADVANCED": "advanced",
}

# Tarif v1 dan qolgan legacy PlanFeature kodlari — DB'da qoldiriladi (gating uchun),
# lekin v2 landing'da ko'rinmaydi.
LEGACY_V1_CODES = [
    "students", "attendance", "finance", "salaries", "analytics",
    "leads", "branches", "roles", "chaqmoq_store",
]


class Command(BaseCommand):
    help = "Tarif v2 — Bosqich 7: 16 ta PlanFeature ni audit asosida idempotent seed qiladi."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for (code, name_uz, category, is_core, order, icon, description_uz,
             impl_status, show_on_landing, is_highlight) in FEATURES:
            cat_value = CATEGORY_MAP[category]
            # PLANNED features: is_active=False (admin/landing'da yashirin)
            is_active = (impl_status != "PLANNED")
            obj, created = PlanFeature.objects.update_or_create(
                code=code,
                defaults={
                    "name": name_uz,            # backward compat
                    "name_uz": name_uz,
                    "description": description_uz,  # backward compat
                    "description_uz": description_uz,
                    "category": cat_value,
                    "is_core": is_core,
                    "order": order,
                    "icon": icon,
                    "is_active": is_active,
                    "implementation_status": impl_status,
                    "show_on_landing": show_on_landing,
                    "is_highlight": is_highlight,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(f"✓ {code} [{impl_status}]: created")
            else:
                updated_count += 1
                self.stdout.write(f"↻ {code} [{impl_status}]: updated")

        # Legacy v1 PlanFeaturelarini landing'dan yashirish
        # (DB'da qoladi, gating ishlaydi, faqat marketing/pricing'da chiqmaydi).
        legacy_qs = PlanFeature.objects.filter(code__in=LEGACY_V1_CODES)
        legacy_hidden = legacy_qs.filter(show_on_landing=True).update(
            show_on_landing=False, is_highlight=False
        )
        if legacy_hidden:
            self.stdout.write(
                f"⌫ {legacy_hidden} ta legacy v1 feature landing'dan yashirildi "
                f"(DB'da qoladi)."
            )

        # Yakuniy hisobot
        ready = sum(1 for f in FEATURES if f[7] == "READY")
        partial = sum(1 for f in FEATURES if f[7] == "PARTIAL")
        planned = sum(1 for f in FEATURES if f[7] == "PLANNED")
        landing = sum(1 for f in FEATURES if f[8])
        highlights = sum(1 for f in FEATURES if f[9])

        self.stdout.write(self.style.SUCCESS(
            f"Yakun: {created_count} yaratildi, {updated_count} yangilandi (jami {len(FEATURES)})."
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Holat: READY={ready}, PARTIAL={partial}, PLANNED={planned} | "
            f"landing'da={landing}, highlight={highlights}."
        ))
