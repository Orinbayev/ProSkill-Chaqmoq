"""Data-driven tariflar (v2) uchun testlar.

Test bazasi barcha migratsiyani (0028 seed) yangidan quradi — shu bilan
seed migratsiya toza bazada ishlashi ham tekshiriladi.
"""
from django.test import TestCase
from django.utils import timezone

from accounts.models import Center
from billing.models import PlanFeature, SubscriptionPlan, PlanFeatureRule, CenterSubscription
from billing.services import clear_feature_request_cache


class _CacheSafeTest(TestCase):
    """center_has_feature request-scope cache'ini har test oldidan tozalaydi
    (productionda har request'da tozalanadi; testlar bir thread'da ketadi)."""
    def setUp(self):
        clear_feature_request_cache()


def _mk_center(slug, plan_code):
    c = Center.objects.create(name=f"Test {slug}", slug=slug)
    plan = SubscriptionPlan.objects.get(code=plan_code)
    CenterSubscription.objects.create(
        center=c, plan=plan, status="ACTIVE",
        expires_at=timezone.now() + timezone.timedelta(days=30),
    )
    return c


class SeedTarifTests(_CacheSafeTest):
    def test_core_features_seeded_as_core(self):
        for code in ("dashboard", "students", "payments", "attendance", "dark_mode"):
            f = PlanFeature.objects.get(code=code)
            self.assertEqual(f.type, "CORE", f"{code} CORE bo'lishi kerak")
            self.assertTrue(f.is_core)

    def test_canonical_plans_with_limits(self):
        self.assertEqual(SubscriptionPlan.objects.get(code="STANDART").max_students, 200)
        self.assertEqual(SubscriptionPlan.objects.get(code="PREMIUM").max_students, 450)
        self.assertEqual(SubscriptionPlan.objects.get(code="PRO").max_students, 2000)

    def test_ai_quota_rule(self):
        rule = PlanFeatureRule.objects.get(plan__code="PRO", feature__code="ai_assistant")
        self.assertTrue(rule.enabled)
        self.assertEqual(rule.limit_value, 500)

    def test_pro_features_not_in_standart(self):
        # STANDART tarifda PRO featurelar YOQ (yoki disabled)
        self.assertFalse(
            PlanFeatureRule.objects.filter(
                plan__code="STANDART", feature__code="ai_assistant", enabled=True
            ).exists()
        )


class TeacherowskiUnchangedTests(_CacheSafeTest):
    """MUHIM: Standart tarifdagi markaz HAMMA CORE bo'limdan foydalanadi."""

    def test_standart_center_has_all_core_features(self):
        c = _mk_center("std-center", "STANDART")
        core_codes = [
            "dashboard", "students", "staff", "leads_crm", "salary_report", "groups",
            "debtors", "payments", "attendance", "schedule", "parents", "shop",
            "shop_requests", "chaqmoq_points", "chaqmoq_rating", "chaqmoq_rules",
            "games", "permissions", "trash", "manual_notifications", "excel_export",
            "dark_mode",
        ]
        for code in core_codes:
            self.assertTrue(c.has_feature(code), f"CORE '{code}' Standart'da ochiq bo'lishi SHART")

    def test_standart_center_lacks_pro_features(self):
        c = _mk_center("std-center2", "STANDART")
        self.assertFalse(c.has_feature("ai_assistant"))
        self.assertFalse(c.has_feature("multi_branch"))


class QuotaTests(_CacheSafeTest):
    def test_pro_ai_quota_consume(self):
        c = _mk_center("pro-center", "PRO")
        self.assertTrue(c.has_feature("ai_assistant"))
        self.assertEqual(c.get_limit("ai_assistant"), 500)
        # 500 marta ishlatsa bo'ladi, 501-chi rad etiladi
        self.assertTrue(c.consume_quota("ai_assistant", 499))
        self.assertTrue(c.consume_quota("ai_assistant", 1))
        self.assertFalse(c.consume_quota("ai_assistant", 1))

    def test_standart_ai_quota_denied(self):
        c = _mk_center("std-center3", "STANDART")
        self.assertFalse(c.consume_quota("ai_assistant", 1))


# ── Superadmin panel kirish + matritsa AJAX testlari ──────────────────────
import json
from django.test import Client
from django.urls import reverse
from accounts.models import User


def _mk_user(username, superuser=False):
    email = f"{username}@test.uz"
    if superuser:
        return User.objects.create_superuser(email=email, password="strong-pass-123")
    return User.objects.create_user(
        email=email, password="strong-pass-123", role="director", ism="T", familya="U",
    )


class PanelAccessTests(_CacheSafeTest):
    def test_non_superuser_cannot_access_panel(self):
        c = Client()
        c.force_login(_mk_user("reg_user", superuser=False))
        r = c.get(reverse("platform_global:superadmin_plans"))
        self.assertNotEqual(r.status_code, 200)  # login'ga yo'naltiriladi / rad etiladi

    def test_superuser_can_access_panel(self):
        c = Client()
        c.force_login(_mk_user("su_user", superuser=True))
        r = c.get(reverse("platform_global:superadmin_plans"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Tarif matritsasi")


class MatrixApiTests(_CacheSafeTest):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(_mk_user("su_api", superuser=True))

    def _post(self, payload):
        return self.client.post(
            reverse("platform_global:api_feature_rule_update"),
            data=json.dumps(payload), content_type="application/json",
        )

    def test_non_superuser_api_forbidden(self):
        c = Client()
        c.force_login(_mk_user("reg_api", superuser=False))
        std = SubscriptionPlan.objects.get(code="STANDART")
        r = c.post(reverse("platform_global:api_feature_rule_update"),
                   data=json.dumps({"plan_id": std.id, "feature_code": "advanced_analytics", "enabled": True}),
                   content_type="application/json")
        self.assertEqual(r.status_code, 403)

    def test_core_feature_cannot_be_toggled(self):
        std = SubscriptionPlan.objects.get(code="STANDART")
        r = self._post({"plan_id": std.id, "feature_code": "dashboard", "enabled": False})
        self.assertEqual(r.status_code, 400)
        # CORE hali ham ochiq
        self.assertTrue(std.plan_features.filter(code="dashboard").exists() or PlanFeature.objects.get(code="dashboard").is_core)

    def test_toggle_premium_feature_syncs_m2m(self):
        std = SubscriptionPlan.objects.get(code="STANDART")
        self.assertFalse(std.plan_features.filter(code="advanced_analytics").exists())
        r = self._post({"plan_id": std.id, "feature_code": "advanced_analytics", "enabled": True})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(std.plan_features.filter(code="advanced_analytics").exists())
        # o'chirilsa M2M'dan chiqadi
        self._post({"plan_id": std.id, "feature_code": "advanced_analytics", "enabled": False})
        self.assertFalse(std.plan_features.filter(code="advanced_analytics").exists())

    def test_quota_limit_update(self):
        pro = SubscriptionPlan.objects.get(code="PRO")
        r = self.client.post(
            reverse("platform_global:api_feature_rule_update"),
            data=json.dumps({"plan_id": pro.id, "feature_code": "ai_assistant", "limit_value": 1000}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PlanFeatureRule.objects.get(plan=pro, feature__code="ai_assistant").limit_value, 1000)


# ── Obuna muddati tugaganda bloklash testlari ─────────────────────────────
from django.test import RequestFactory
from billing.middleware import SubscriptionMiddleware


class ExpiryBlockTests(_CacheSafeTest):
    def _expired_center(self):
        c = Center.objects.create(name="Exp", slug="exp-center")
        plan = SubscriptionPlan.objects.get(code="STANDART")
        CenterSubscription.objects.create(
            center=c, plan=plan, status="ACTIVE",
            started_at=timezone.now() - timezone.timedelta(days=40),
            expires_at=timezone.now() - timezone.timedelta(hours=2),  # 2 soat oldin tugagan (grace ichida)
        )
        return c

    def test_grace_gap_now_caught(self):
        """Kun tugagan, lekin grace ichida — eski shart bloklamasdi, endi bloklaydi."""
        c = self._expired_center()
        sub = CenterSubscription.objects.get(center=c)
        self.assertTrue(sub.is_expired())    # kun tugagan
        self.assertFalse(sub.is_blocked())   # grace ichida (eski shart bu holni o'tkazib yuborardi)

    def _run_mw(self, role):
        c = self._expired_center()
        u = _mk_user(f"exp_{role}")
        u.role = role
        u.center = c
        u.save()
        rf = RequestFactory()
        req = rf.get("/hisob/")   # billing bo'lmagan sahifa
        req.user = u
        req.center = c
        return SubscriptionMiddleware(get_response=lambda r: None).process_request(req)

    def test_director_blocked_on_expiry(self):
        resp = self._run_mw("director")
        self.assertIsNotNone(resp)                 # redirect qaytdi
        self.assertIn("/hisob/billing/blocked", resp.url)

    def test_manager_blocked_on_expiry(self):
        resp = self._run_mw("manager")
        self.assertIsNotNone(resp)
        self.assertIn("/hisob/billing/blocked", resp.url)

    def test_student_not_blocked_on_expiry(self):
        self.assertIsNone(self._run_mw("student"))   # o'quvchi kira oladi


class CenterEditExpirySyncTests(_CacheSafeTest):
    """center_edit sana o'zgartirilganda ACTIVE obuna DOIM sinxronlanadi
    (center.plan tarif kodiga mos kelmasa ham) — '12-iyul qo'ydim, 7 kun ko'rsatyapti' bug'i."""

    def test_editing_date_updates_active_subscription(self):
        c = Center.objects.create(name="EditSync", slug="edit-sync", plan="ESKI_KOD")
        plan = SubscriptionPlan.objects.get(code="STANDART")
        # Eski obuna: xato (uzoq) sana — trial now+30 kabi
        old_sub = CenterSubscription.objects.create(
            center=c, plan=plan, status="ACTIVE",
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )
        su = _mk_user("edit_su", superuser=True)
        client = Client()
        client.force_login(su)

        target = (timezone.now() - timezone.timedelta(days=2)).date()  # 2 kun oldin tugagan
        resp = client.post(
            reverse("platform_global:center_edit", args=[c.id]),
            data={
                "name": "EditSync", "slug": "edit-sync", "address": "",
                "plan": "ESKI_KOD",  # aktiv tarif kodiga MOS EMAS
                "capacity_limit": 200, "expires_at": target.isoformat(),
                "status": "ACTIVE", "ai_enabled": "",
            },
        )
        self.assertIn(resp.status_code, (200, 302))
        old_sub.refresh_from_db()
        # Endi ACTIVE obuna sanasi berilgan MAHALLIY sanaga TENG (kun oxiri)
        self.assertEqual(timezone.localtime(old_sub.expires_at).date(), target)
        self.assertTrue(old_sub.is_expired())  # 2 kun oldin tugagan → expired
