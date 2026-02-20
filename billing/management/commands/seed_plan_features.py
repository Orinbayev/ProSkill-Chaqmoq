"""
Management command: seed_plan_features

Barcha default PlanFeaturelarni yaratadi.
Mavjud bo'lsa update qiladi (idempotent).

Ishlatish:
    python manage.py seed_plan_features
"""
from django.core.management.base import BaseCommand
from billing.models import PlanFeature


FEATURES = [
    # ── ASOSIY ──────────────────────────────────────────────────────
    {
        "code": "dashboard",
        "name": "Dashboard",
        "description": "Asosiy boshqaruv paneli va statistika",
        "category": "core",
        "is_core": True,
        "order": 1,
    },
    {
        "code": "profile_settings",
        "name": "Profil & Sozlamalar",
        "description": "Markaz ma'lumotlarini tahrirlash",
        "category": "core",
        "is_core": True,
        "order": 2,
    },
    {
        "code": "notifications",
        "name": "Bildirishnomalar",
        "description": "Tizim ichki bildirishnomalari",
        "category": "core",
        "is_core": True,
        "order": 3,
    },

    # ── O'QUVCHILAR ──────────────────────────────────────────────────
    {
        "code": "students_list",
        "name": "O'quvchilar ro'yxati",
        "description": "Barcha talabalar bazasini ko'rish va boshqarish",
        "category": "students",
        "is_core": False,
        "order": 1,
    },
    {
        "code": "students_add",
        "name": "O'quvchi qo'shish",
        "description": "Yangi talaba qo'shish imkoniyati",
        "category": "students",
        "is_core": False,
        "order": 2,
    },
    {
        "code": "students_profile",
        "name": "Talaba profili",
        "description": "Batafsil talaba profili va ma'lumotlari",
        "category": "students",
        "is_core": False,
        "order": 3,
    },
    {
        "code": "students_archive",
        "name": "O'quvchini arxivlash",
        "description": "O'quvchini arxivlash va faolsizlantirish",
        "category": "students",
        "is_core": False,
        "order": 4,
    },

    # ── GURUHLAR ─────────────────────────────────────────────────────
    {
        "code": "groups_list",
        "name": "Guruhlar ro'yxati",
        "description": "Barcha guruhlarni ko'rish",
        "category": "groups",
        "is_core": False,
        "order": 1,
    },
    {
        "code": "groups_create",
        "name": "Guruh yaratish",
        "description": "Yangi guruh ochish va talabalar qo'shish",
        "category": "groups",
        "is_core": False,
        "order": 2,
    },
    {
        "code": "groups_manage",
        "name": "Guruhni boshqarish",
        "description": "Guruh ma'lumotlarini tahrirlash, o'qituvchi belgilash",
        "category": "groups",
        "is_core": False,
        "order": 3,
    },

    # ── MOLIYA / TO'LOV ──────────────────────────────────────────────
    {
        "code": "payments_receive",
        "name": "To'lov qabul qilish",
        "description": "O'quvchilardan to'lov qabul qilish",
        "category": "payments",
        "is_core": False,
        "order": 1,
    },
    {
        "code": "payments_history",
        "name": "To'lovlar tarixi",
        "description": "Barcha to'lovlar tarixi va filtrlash",
        "category": "payments",
        "is_core": False,
        "order": 2,
    },
    {
        "code": "expenses",
        "name": "Xarajatlar (Chiqimlar)",
        "description": "Ofis xarajatlarini kiritish va kuzatish",
        "category": "payments",
        "is_core": False,
        "order": 3,
    },
    {
        "code": "salary",
        "name": "Oylik ish haqi",
        "description": "Xodimlar va o'qituvchilar maoshini boshqarish",
        "category": "payments",
        "is_core": False,
        "order": 4,
    },
    {
        "code": "cashbox",
        "name": "Kassa boshqaruvi",
        "description": "Kassa holati va moliyaviy balans",
        "category": "payments",
        "is_core": False,
        "order": 5,
    },

    # ── QARZDORLAR ───────────────────────────────────────────────────
    {
        "code": "debtors_list",
        "name": "Qarzdorlar ro'yxati",
        "description": "Qarzdor o'quvchilarni kuzatish",
        "category": "debtors",
        "is_core": False,
        "order": 1,
    },
    {
        "code": "debtors_notify",
        "name": "Qarzdorlarga xabar",
        "description": "Qarzdorlarga SMS yoki bildirisnoma yuborish",
        "category": "debtors",
        "is_core": False,
        "order": 2,
    },

    # ── JADVAL / DAVOMAT ─────────────────────────────────────────────
    {
        "code": "attendance",
        "name": "Davomat belgisi",
        "description": "Kunlik davomatni belgilash (QR yoki Manual)",
        "category": "schedule",
        "is_core": False,
        "order": 1,
    },
    {
        "code": "schedule",
        "name": "Dars jadvali",
        "description": "Haftalik dars jadvalini tuzish",
        "category": "schedule",
        "is_core": False,
        "order": 2,
    },
    {
        "code": "qr_attendance",
        "name": "QR Davomat",
        "description": "QR kod orqali avtomatik davomat",
        "category": "schedule",
        "is_core": False,
        "order": 3,
    },

    # ── KURSLAR / DARSLAR ────────────────────────────────────────────
    {
        "code": "courses",
        "name": "Kurslar & Dasturlar",
        "description": "O'quv dasturlarini yaratish va boshqarish",
        "category": "courses",
        "is_core": False,
        "order": 1,
    },
    {
        "code": "tasks",
        "name": "Vazifalar (Uy ishi)",
        "description": "Talabaga vazifa berish va baholash",
        "category": "courses",
        "is_core": False,
        "order": 2,
    },
    {
        "code": "exams",
        "name": "Imtihonlar",
        "description": "Test sinovlari va natijalar",
        "category": "courses",
        "is_core": False,
        "order": 3,
    },
    {
        "code": "grades",
        "name": "Baholar",
        "description": "O'quvchilar baholash tizimi",
        "category": "courses",
        "is_core": False,
        "order": 4,
    },

    # ── XODIMLAR / ROLLAR ────────────────────────────────────────────
    {
        "code": "staff_list",
        "name": "Xodimlar ro'yxati",
        "description": "Xodimlar bazasini ko'rish va boshqarish",
        "category": "staff",
        "is_core": False,
        "order": 1,
    },
    {
        "code": "roles_manage",
        "name": "Rollar boshqaruvi",
        "description": "Xodimlarga rol va huquqlar berish",
        "category": "staff",
        "is_core": False,
        "order": 2,
    },
    {
        "code": "staff_salary",
        "name": "Xodim ish haqi",
        "description": "Xodimlarga oylik belgilash va to'lash",
        "category": "staff",
        "is_core": False,
        "order": 3,
    },

    # ── SMS / REKLAMA ────────────────────────────────────────────────
    {
        "code": "sms_broadcast",
        "name": "Ommaviy SMS",
        "description": "Barcha o'quvchilarga SMS xabar yuborish",
        "category": "broadcast",
        "is_core": False,
        "order": 1,
    },
    {
        "code": "sms_auto",
        "name": "Avtomatik SMS",
        "description": "Davomat, to'lov eslatmalari avtomatik SMS",
        "category": "broadcast",
        "is_core": False,
        "order": 2,
    },
    {
        "code": "telegram_bot",
        "name": "Telegram Bot",
        "description": "Markaz uchun alohida Telegram bot",
        "category": "broadcast",
        "is_core": False,
        "order": 3,
    },

    # ── HISOBOT / EXPORT ─────────────────────────────────────────────
    {
        "code": "reports_basic",
        "name": "Asosiy hisobotlar",
        "description": "Umumiy moliya va o'quvchi statistikasi",
        "category": "reports",
        "is_core": False,
        "order": 1,
    },
    {
        "code": "reports_advanced",
        "name": "Kengaytirilgan hisobotlar",
        "description": "Batafsil moliya va akademik tahlil hisobotlari",
        "category": "reports",
        "is_core": False,
        "order": 2,
    },
    {
        "code": "export_excel",
        "name": "Excel/PDF eksport",
        "description": "Ma'lumotlarni Excel yoki PDF formatida yuklab olish",
        "category": "reports",
        "is_core": False,
        "order": 3,
    },

    # ── CRM / ANALYTICS ──────────────────────────────────────────────
    {
        "code": "leads",
        "name": "Lidlar (CRM)",
        "description": "Yangi mijozlar bilan ishlash (Kanban board)",
        "category": "crm",
        "is_core": False,
        "order": 1,
    },
    {
        "code": "crm_pipeline",
        "name": "Savdo quvuri",
        "description": "Liddan o'quvchiga konversiyani kuzatish",
        "category": "crm",
        "is_core": False,
        "order": 2,
    },
    {
        "code": "analytics",
        "name": "Analytics panel",
        "description": "Kengaytirilgan ma'lumotlar tahlili va grafiklar",
        "category": "crm",
        "is_core": False,
        "order": 3,
    },
    {
        "code": "kpi",
        "name": "KPI Hisobot",
        "description": "Xodimlar va markaz KPI ko'rsatkichlari",
        "category": "crm",
        "is_core": False,
        "order": 4,
    },

    # ── SOZLAMALAR ───────────────────────────────────────────────────
    {
        "code": "store",
        "name": "Do'kon (Shop)",
        "description": "Kitoblar va o'quv qurollari savdosi",
        "category": "settings",
        "is_core": False,
        "order": 1,
    },
    {
        "code": "chaqmoq",
        "name": "Chaqmoq tizimi",
        "description": "Gamification: chaqmoq ball tizimi",
        "category": "settings",
        "is_core": False,
        "order": 2,
    },
    {
        "code": "donation",
        "name": "Xayriya / Donation",
        "description": "Xayriya to'lovlarini qabul qilish",
        "category": "settings",
        "is_core": False,
        "order": 3,
    },
    {
        "code": "api_access",
        "name": "API kirish",
        "description": "Tashqi integratsiyalar uchun API kalit",
        "category": "settings",
        "is_core": False,
        "order": 4,
    },
]


class Command(BaseCommand):
    help = "PlanFeature lar uchun boshlang'ich seed ma'lumotlarini yaratadi"

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for feature_data in FEATURES:
            obj, created = PlanFeature.objects.update_or_create(
                code=feature_data["code"],
                defaults={
                    "name": feature_data["name"],
                    "description": feature_data["description"],
                    "category": feature_data["category"],
                    "is_core": feature_data["is_core"],
                    "order": feature_data["order"],
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Seed bajarildi: {created_count} yangi, {updated_count} yangilangan"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                f"Jami {PlanFeature.objects.count()} ta feature bazada mavjud."
            )
        )
