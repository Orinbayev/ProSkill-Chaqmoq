"""
billing/management/commands/setup_plans.py

Idempotent command: ChaqmoqApp uchun 3 ta tarif va barcha feature'larni
bazada to'liq sozlaydi. Xavfsiz — har safar ishga tushirsa ham mavjud
ma'lumotlarni buzib yubormaydi.

Ishlatish:
    python manage.py setup_plans
    python manage.py setup_plans --dry-run   # faqat tekshiradi, yozmaydi
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


# ─────────────────────────────────────────────────────────────
# FEATURE KATALOGI
# code         — kod (billing/services.py da ishlatiladi)
# name         — saytdagi bo'lim nomi bilan bir xil!
# category     — core / finance / marketing / team / advanced
# is_core      — True = bepul, barchaga ochiq (require_feature tekshirmaydi)
# impl_status  — READY / PARTIAL / PLANNED
# order        — tartib (kichik = yuqorida)
# icon         — emoji (admin panelda ko'rinadi)
# ─────────────────────────────────────────────────────────────
FEATURE_CATALOG = [
    # ── CORE (barchaga bepul) ──────────────────────────────
    dict(
        code="guruhlar",
        name="Guruhlar",
        category="core",
        is_core=True,
        impl_status="READY",
        order=1,
        icon="👥",
        description_uz="Guruhlar yaratish, tahrirlash, arxivlash",
    ),
    dict(
        code="davomat",
        name="Davomat",
        category="core",
        is_core=True,
        impl_status="READY",
        order=2,
        icon="✅",
        description_uz="Kundalik davomat belgilash va tarix",
    ),
    dict(
        code="tolovlar",
        name="To'lovlar",
        category="core",
        is_core=True,
        impl_status="READY",
        order=3,
        icon="💳",
        description_uz="To'lov kiritish, ko'rish, tarix",
    ),
    dict(
        code="oquvchilar",
        name="O'quvchilar",
        category="core",
        is_core=True,
        impl_status="READY",
        order=4,
        icon="🎓",
        description_uz="O'quvchi profillari, ro'yxat, arxiv",
    ),
    dict(
        code="asosiy_dashboard",
        name="Asosiy Dashboard",
        category="core",
        is_core=True,
        impl_status="READY",
        order=5,
        icon="📊",
        description_uz="Bugungi raqamlar: daromad, o'quvchilar, guruhlar",
    ),
    dict(
        code="ota_ona_boglash",
        name="Ota-Ona Bog'lash",
        category="core",
        is_core=True,
        impl_status="READY",
        order=6,
        icon="👨‍👧",
        description_uz="Ota-onani Telegram orqali bog'lash",
    ),
    dict(
        code="xabarnomalar",
        name="Xabarnomalar",
        category="core",
        is_core=True,
        impl_status="READY",
        order=7,
        icon="🔔",
        description_uz="Bildirishnomalar markazi",
    ),
    dict(
        code="jadval",
        name="Dars Jadvali",
        category="core",
        is_core=True,
        impl_status="READY",
        order=8,
        icon="📅",
        description_uz="Haftalik dars jadvali",
    ),

    # ── FINANCE (STANDART dan boshlab) ─────────────────────
    dict(
        code="finance",
        name="Moliyaviy Dashboard va O'qituvchi Maoshi",
        category="finance",
        is_core=False,
        impl_status="READY",
        order=10,
        icon="💰",
        description_uz=(
            "To'liq moliyaviy dashboard (daromad/xarajat/foyda), "
            "o'qituvchi maoshini avtomatik hisoblash, oyni yopish"
        ),
    ),
    dict(
        code="xarajatlar",
        name="Xarajatlar Bo'limi",
        category="finance",
        is_core=False,
        impl_status="READY",
        order=11,
        icon="🧾",
        description_uz="Ijara, kommunal, reklama, xodim xarajatlarini nazorat qilish",
    ),
    dict(
        code="excel_eksport",
        name="Excel Eksport",
        category="finance",
        is_core=False,
        impl_status="READY",
        order=12,
        icon="📤",
        description_uz="To'lovlar, maoshlar, davomatlarni Excel ga eksport qilish",
    ),

    # ── MARKETING (STANDART dan boshlab) ───────────────────
    dict(
        code="leads",
        name="CRM / Lidlar",
        category="marketing",
        is_core=False,
        impl_status="READY",
        order=20,
        icon="🎯",
        description_uz=(
            "Potensial o'quvchilarni kuzatish, sinov darslari, "
            "konversiya hunicha, manbalar tahlili"
        ),
    ),

    # ── TEAM (PREMIUM dan boshlab) ─────────────────────────
    dict(
        code="support_teacher_enabled",
        name="Support O'qituvchi",
        category="team",
        is_core=False,
        impl_status="READY",
        order=30,
        icon="🤝",
        description_uz="Guruhga qo'shimcha support o'qituvchi qo'shish va maosh ulashish",
    ),
    dict(
        code="filial_qoshish",
        name="Filial Qo'shish",
        category="team",
        is_core=False,
        impl_status="READY",
        order=31,
        icon="🏫",
        description_uz="Bir akkauntda bir nechta filial (branch) boshqarish",
    ),

    # ── ADVANCED (PREMIUM dan boshlab) ─────────────────────
    dict(
        code="store",
        name="Do'kon / Mahsulotlar",
        category="advanced",
        is_core=False,
        impl_status="READY",
        order=40,
        icon="🛍️",
        description_uz="Darslik, material va tovarlarni sotish; sotib olish so'rovlari",
    ),
    dict(
        code="imtihon",
        name="Imtihon Moduli",
        category="advanced",
        is_core=False,
        impl_status="PARTIAL",
        order=41,
        icon="📝",
        description_uz="Imtihon sessiyalari, natijalar, reytinglar, tavsiyalar",
    ),
    dict(
        code="sertifikat",
        name="Sertifikat / Diplom",
        category="advanced",
        is_core=False,
        impl_status="PARTIAL",
        order=42,
        icon="🏆",
        description_uz="Sertifikat shablonlari, chiqarish, PDF, tekshirish",
    ),
    dict(
        code="sms",
        name="SMS Xabarnomalar",
        category="marketing",
        is_core=False,
        impl_status="PLANNED",
        order=22,
        icon="📱",
        description_uz="To'lov eslatmalari, davomat habarlari ota-onalarga SMS orqali",
    ),

    # ── PRO only ───────────────────────────────────────────
    dict(
        code="chaqmoq_bonus",
        name="Chaqmoq Bonus Tizimi",
        category="advanced",
        is_core=False,
        impl_status="PLANNED",
        order=50,
        icon="⚡",
        description_uz="O'quvchilarni gamifikatsiya orqali ushlab turish, bonus ballar",
    ),
    dict(
        code="hr",
        name="HR Dashboard",
        category="team",
        is_core=False,
        impl_status="PARTIAL",
        order=33,
        icon="👔",
        description_uz="Xodimlar boshqaruvi, ish vaqti, bandlik jadvali",
    ),
    dict(
        code="analytics",
        name="Analytics Dashboard",
        category="advanced",
        is_core=False,
        impl_status="PLANNED",
        order=52,
        icon="📈",
        description_uz="Chuqur tahlil: tendensiyalar, solishtirmalar, prognozlar",
    ),
]

# ─────────────────────────────────────────────────────────────
# PLAN KATALOGI
# max_groups=0, max_users=0  →  CHEKSIZ (model logikasiga mos)
# max_branches=0             →  CHEKSIZ
# ─────────────────────────────────────────────────────────────
PLAN_CATALOG = [
    dict(
        code="STANDART",
        title="Standart",
        tier=10,
        price=400_000,
        max_students=200,
        max_branches=1,
        max_groups=0,
        max_users=0,
        is_popular=False,
        is_recommended=False,
        subtitle_uz="O'sib borayotgan o'quv markaz uchun",
        description_uz=(
            "CRM/Lidlar, Moliyaviy Dashboard, O'qituvchi Maoshi, "
            "Xarajatlar va Excel Eksport — asosiy qurollar."
        ),
        student_range_uz="200 gacha o'quvchi",
        features=[
            "leads",
            "finance",
            "xarajatlar",
            "excel_eksport",
        ],
    ),
    dict(
        code="PREMIUM",
        title="Premium",
        tier=20,
        price=600_000,
        max_students=450,
        max_branches=2,
        max_groups=0,
        max_users=0,
        is_popular=True,
        is_recommended=True,
        subtitle_uz="Professional o'quv markaz uchun",
        description_uz=(
            "Standartdagi hamma narsa + Filial, Do'kon, "
            "Imtihon, Sertifikat, SMS va Support O'qituvchi."
        ),
        student_range_uz="450 gacha o'quvchi",
        features=[
            "leads",
            "finance",
            "xarajatlar",
            "excel_eksport",
            "support_teacher_enabled",
            "filial_qoshish",
            "store",
            "imtihon",
            "sertifikat",
            "sms",
        ],
    ),
    dict(
        code="PRO",
        title="Pro",
        tier=30,
        price=0,
        max_students=0,
        max_branches=0,
        max_groups=0,
        max_users=0,
        is_popular=False,
        is_recommended=False,
        subtitle_uz="Yirik tarmoq markazlar uchun (individual narx)",
        description_uz=(
            "Hamma narsa + Chaqmoq Bonus, HR Dashboard, Analytics — "
            "cheksiz o'quvchilar, cheksiz filiallar."
        ),
        student_range_uz="Cheksiz o'quvchilar",
        features=[
            "leads",
            "finance",
            "xarajatlar",
            "excel_eksport",
            "support_teacher_enabled",
            "filial_qoshish",
            "store",
            "imtihon",
            "sertifikat",
            "sms",
            "chaqmoq_bonus",
            "hr",
            "analytics",
        ],
    ),
]


class Command(BaseCommand):
    help = (
        "ChaqmoqApp tarif tizimini sozlaydi: PlanFeature va SubscriptionPlan "
        "ob'ektlarini yaratadi/yangilaydi. Idempotent — xavfsiz qayta ishga tushiriladi."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Hech narsa yozmaydi, faqat nima bo'lishini ko'rsatadi.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN — hech narsa yozilmaydi ===\n"))

        try:
            with transaction.atomic():
                self._sync_features(dry_run)
                self._sync_plans(dry_run)
                if dry_run:
                    raise _DryRunRollback()
        except _DryRunRollback:
            self.stdout.write(self.style.WARNING("\nDRY RUN tugadi — barcha o'zgarishlar bekor qilindi."))
            return

        self.stdout.write(self.style.SUCCESS("\n✅ setup_plans muvaffaqiyatli bajarildi!"))

    # ─────────────────────────────────────────────────────
    def _sync_features(self, dry_run: bool):
        from billing.models import PlanFeature

        self.stdout.write(self.style.HTTP_INFO("\n── PlanFeature'larni sinxronlash ──"))
        for item in FEATURE_CATALOG:
            code = item["code"]
            obj, created = PlanFeature.objects.get_or_create(code=code)
            changed = []

            fields_map = {
                "name":                  item["name"],
                "category":              item["category"],
                "is_core":               item["is_core"],
                "implementation_status": item["impl_status"],
                "order":                 item["order"],
                "icon":                  item.get("icon", ""),
                "description_uz":        item.get("description_uz", ""),
                "is_active":             True,
                "show_on_landing":       not item["is_core"],
            }
            for field, value in fields_map.items():
                if getattr(obj, field) != value:
                    changed.append(f"{field}: {getattr(obj, field)!r} → {value!r}")
                    setattr(obj, field, value)

            if created:
                status = self.style.SUCCESS("  YANGI")
            elif changed:
                status = self.style.WARNING("  YANGILANDI")
            else:
                status = "  OK"

            detail = f" ({', '.join(changed[:2])})" if changed else ""
            self.stdout.write(f"{status}  [{item['category']:10}]  {code:35} {item['icon']} {item['name']}{detail}")

            if not dry_run and (created or changed):
                update_fields = list(fields_map.keys()) if not created else None
                obj.save(update_fields=update_fields)

        total = len(FEATURE_CATALOG)
        self.stdout.write(f"\n  Jami: {total} ta feature")

    # ─────────────────────────────────────────────────────
    def _sync_plans(self, dry_run: bool):
        from billing.models import SubscriptionPlan, PlanFeature

        self.stdout.write(self.style.HTTP_INFO("\n── SubscriptionPlan'larni sinxronlash ──"))

        for item in PLAN_CATALOG:
            code = item["code"]
            obj, created = SubscriptionPlan.objects.get_or_create(code=code)

            fields_map = {
                "title":            item["title"],
                "name":             item["title"],
                "tier":             item["tier"],
                "price":            item["price"],
                "monthly_price":    item["price"],
                "max_students":     item["max_students"],
                "max_branches":     item["max_branches"],
                "max_groups":       item["max_groups"],
                "max_users":        item["max_users"],
                "is_popular":       item["is_popular"],
                "is_recommended":   item["is_recommended"],
                "subtitle_uz":      item["subtitle_uz"],
                "description_uz":   item["description_uz"],
                "student_range_uz": item["student_range_uz"],
                "active":           True,
                "duration_days":    30,
                "landing_visible":  True,
            }
            changed = []
            for field, value in fields_map.items():
                if getattr(obj, field) != value:
                    changed.append(field)
                    setattr(obj, field, value)

            if not dry_run:
                obj.save()

            # M2M features
            desired_codes = set(item["features"])
            feature_qs = PlanFeature.objects.filter(code__in=desired_codes)
            found_codes = set(feature_qs.values_list("code", flat=True))
            missing = desired_codes - found_codes
            if missing:
                self.stdout.write(
                    self.style.ERROR(f"  ⚠️  {code}: topilmagan feature kodlar: {missing}")
                )

            if not dry_run:
                obj.plan_features.set(feature_qs)

            # Limit labellarini tayyorla
            students_label = "Cheksiz" if item["max_students"] == 0 else str(item["max_students"])
            branches_label = "Cheksiz" if item["max_branches"] == 0 else str(item["max_branches"])
            price_label    = "Custom"  if item["price"] == 0       else f"{item['price']:,} so'm"
            status_label   = self.style.SUCCESS("YANGI") if created else (self.style.WARNING("YANGILANDI") if changed else "OK")

            self.stdout.write(
                f"\n  {status_label}  {code} (tier={item['tier']})\n"
                f"         Narx: {price_label} | O'quvchi: {students_label} | "
                f"Filial: {branches_label} | Guruh: Cheksiz | Xodim: Cheksiz\n"
                f"         Features ({len(item['features'])} ta): {', '.join(item['features'])}"
            )

        self.stdout.write("")


class _DryRunRollback(Exception):
    """Dry-run rejimida transactionni qaytarish uchun."""
    pass
