# billing/management/commands/migrate_tariff_v2.py
"""
Tarif v2 — Bosqich 2: Plan upsert + legacy deactivate + Center.features → CenterFeatureOverride backfill.

Hech qanday ma'lumot o'chmaydi:
  - Eski SubscriptionPlan rowlari faqat active=False & landing_visible=False qilinadi.
  - Center.features JSONField o'zgartirilmaydi (tozalash keyingi fazada).
  - CenterSubscription rowlari tegilmaydi.
"""
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import transaction

from billing.models import (
    PlanFeature,
    SubscriptionPlan,
    CenterSubscription,
    CenterFeatureOverride,
)
from accounts.models import Center


PLANS = [
    {
        "code": "START", "tier": 1, "title": "START", "name": "START",
        "monthly_price": 200_000, "price": 200_000, "duration_days": 30,
        "max_students": 100, "max_users": 5, "max_groups": 30, "max_branches": 1,
        "subtitle_uz": "Yangi va kichik o'quv markazlar uchun",
        "student_range_uz": "0-100 o'quvchi",
        "is_recommended": False, "landing_visible": True, "active": True,
        "feature_codes": [
            "dashboard", "oquvchi_crud", "davomat", "tolovlar", "rollar",
            "moliya_statistika", "telegram_bot",
        ],
    },
    {
        "code": "PRO", "tier": 2, "title": "PRO", "name": "PRO",
        "monthly_price": 400_000, "price": 400_000, "duration_days": 30,
        "max_students": 300, "max_users": 15, "max_groups": 100, "max_branches": 2,
        "subtitle_uz": "O'rta o'lcham markazlar uchun",
        "student_range_uz": "100-300 o'quvchi",
        "is_recommended": True, "landing_visible": True, "active": True,
        "feature_codes": [
            "dashboard", "oquvchi_crud", "davomat", "tolovlar", "rollar",
            "moliya_statistika", "excel_export", "chegirmali_narh",
            "filial_qoshish", "filial_crud",
            "telegram_bot", "lidlar",
        ],
    },
    {
        "code": "PREMIUM", "tier": 3, "title": "PREMIUM", "name": "PREMIUM",
        "monthly_price": 700_000, "price": 700_000, "duration_days": 30,
        "max_students": 0, "max_users": 0, "max_groups": 0, "max_branches": 0,  # 0 = cheksiz
        "subtitle_uz": "Yirik markazlar — barcha imkoniyatlar",
        "student_range_uz": "Cheksiz",
        "is_recommended": False, "landing_visible": True, "active": True,
        "feature_codes": [
            "dashboard", "oquvchi_crud", "davomat", "tolovlar", "rollar",
            "moliya_statistika", "excel_export", "chegirmali_narh",
            "filial_qoshish", "filial_crud",
            "telegram_bot", "lidlar",
            "ai_assistant", "gdrive_backup",
        ],
    },
]

NEW_PLAN_CODES = ["START", "PRO", "PREMIUM"]
EXPECTED_COUNTS = {"START": 7, "PRO": 12, "PREMIUM": 14}


class Command(BaseCommand):
    help = "Tarif v2 — Bosqich 2: planlarni upsert, legacy deactivate, Center.features → override backfill."

    def handle(self, *args, **options):
        # 0) Avval featurelarni seed qilamiz
        self.stdout.write(self.style.MIGRATE_HEADING("0) seed_features_v2 chaqirilmoqda..."))
        call_command("seed_features_v2")

        with transaction.atomic():
            # A) Plan upsert
            self.stdout.write(self.style.MIGRATE_HEADING("\nA) Planlarni upsert qilish..."))
            for plan_dict in PLANS:
                pd = dict(plan_dict)  # copy — global o'zgarmasin
                feature_codes = pd.pop("feature_codes")
                code = pd.pop("code")

                plan, created = SubscriptionPlan.objects.update_or_create(
                    code=code,
                    defaults=pd,
                )

                features = PlanFeature.objects.filter(code__in=feature_codes)
                if features.count() != len(feature_codes):
                    found = set(features.values_list("code", flat=True))
                    missing = set(feature_codes) - found
                    raise CommandError(
                        f"{code} uchun feature topilmadi: {missing}"
                    )

                plan.plan_features.set(features)
                marker = "✓" if created else "↻"
                action = "created" if created else "updated"
                self.stdout.write(
                    f"{marker} {code}: {action} with {features.count()} features"
                )

            # B) Legacy planlarni deactivate
            self.stdout.write(self.style.MIGRATE_HEADING("\nB) Legacy planlarni deactivate qilish..."))
            legacy_qs = SubscriptionPlan.objects.exclude(code__in=NEW_PLAN_CODES)
            legacy_count = legacy_qs.count()
            legacy_codes = list(legacy_qs.values_list("code", flat=True))
            legacy_qs.update(active=False, landing_visible=False)
            self.stdout.write(
                f"  {legacy_count} ta legacy plan deactivate qilindi: {legacy_codes}"
            )

            # C) Center.features JSONField → CenterFeatureOverride backfill
            self.stdout.write(self.style.MIGRATE_HEADING("\nC) Center.features → CenterFeatureOverride backfill..."))

            centers = Center.objects.filter(is_deleted=False)
            overrides_created = 0
            overrides_updated = 0
            skipped_legacy_keys = []  # (center_id, key) — featureda yo'q
            skipped_child = 0
            skipped_core = 0
            skipped_match_default = 0

            for center in centers:
                # Faqat root centerga override yoziladi
                if getattr(center, "parent_center_id", None):
                    skipped_child += 1
                    continue

                raw = getattr(center, "features", None) or {}
                if not isinstance(raw, dict):
                    continue

                sub = (
                    CenterSubscription.objects
                    .filter(center=center, status="ACTIVE")
                    .select_related("plan")
                    .first()
                )
                plan_codes = set()
                if sub and sub.plan:
                    plan_codes = set(
                        sub.plan.plan_features.values_list("code", flat=True)
                    )

                for key, value in raw.items():
                    if not isinstance(value, bool):
                        continue
                    feature = PlanFeature.objects.filter(code=key).first()
                    if not feature:
                        skipped_legacy_keys.append((center.id, key))
                        continue
                    plan_default = feature.code in plan_codes
                    if value == plan_default:
                        skipped_match_default += 1
                        continue
                    if feature.is_core:
                        skipped_core += 1
                        continue
                    _, created = CenterFeatureOverride.objects.update_or_create(
                        center=center,
                        feature=feature,
                        defaults={
                            "enabled": value,
                            "note": "Phase 2 backfill from Center.features",
                        },
                    )
                    if created:
                        overrides_created += 1
                    else:
                        overrides_updated += 1

            self.stdout.write(
                f"✓ {overrides_created} overrides created from Center.features JSONField"
            )
            self.stdout.write(
                f"  ({overrides_updated} mavjud override yangilandi, "
                f"{skipped_child} child branch o'tkazildi, "
                f"{skipped_core} CORE override rad etildi, "
                f"{skipped_match_default} default-ga mos JSON kalitlar o'tkazildi)"
            )
            if skipped_legacy_keys:
                # Unique kalitlarni ko'rsatamiz (markazlar bo'yicha emas)
                unique_keys = sorted({k for _, k in skipped_legacy_keys})
                self.stdout.write(self.style.WARNING(
                    f"  Featureda yo'q legacy kalitlar (jami {len(skipped_legacy_keys)} ta yozuv, "
                    f"unique kalitlar): {unique_keys}"
                ))

            # D) Verification
            self.stdout.write(self.style.MIGRATE_HEADING("\nD) Verifikatsiya..."))
            total_features = PlanFeature.objects.count()
            active_landing_plans = SubscriptionPlan.objects.filter(landing_visible=True).count()
            start_features = SubscriptionPlan.objects.get(code="START").plan_features.count()
            pro_features = SubscriptionPlan.objects.get(code="PRO").plan_features.count()
            premium_features = SubscriptionPlan.objects.get(code="PREMIUM").plan_features.count()
            override_count = CenterFeatureOverride.objects.count()
            centers_with_active_sub = (
                CenterSubscription.objects
                .filter(status="ACTIVE")
                .values("center")
                .distinct()
                .count()
            )

            self.stdout.write(f"- Total PlanFeatures: {total_features}     (must be ≥ 16)")
            self.stdout.write(f"- Active SubscriptionPlans (landing_visible=True): {active_landing_plans}     (must be exactly 3)")
            self.stdout.write(f"- START features count: {start_features}   (must be 7)")
            self.stdout.write(f"- PRO features count: {pro_features}     (must be 12)")
            self.stdout.write(f"- PREMIUM features count: {premium_features} (must be 14)")
            self.stdout.write(f"- CenterFeatureOverrides: {override_count}")
            self.stdout.write(f"- Centers with active subscription: {centers_with_active_sub}")

            assertions = [
                (total_features >= 16, f"PlanFeature soni 16 dan kam: {total_features}"),
                (active_landing_plans == 3, f"landing_visible plan soni 3 emas: {active_landing_plans}"),
                (start_features == EXPECTED_COUNTS["START"], f"START feature soni 7 emas: {start_features}"),
                (pro_features == EXPECTED_COUNTS["PRO"], f"PRO feature soni 12 emas: {pro_features}"),
                (premium_features == EXPECTED_COUNTS["PREMIUM"], f"PREMIUM feature soni 14 emas: {premium_features}"),
            ]
            for ok, msg in assertions:
                if not ok:
                    raise CommandError(msg)

            self.stdout.write(self.style.SUCCESS("\nBarcha tekshiruvlar muvaffaqiyatli o'tdi."))
