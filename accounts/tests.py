from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from accounts.student_limit import check_student_limit
from billing.models import CenterSubscription, SubscriptionOrder, SubscriptionPlan


@override_settings(TIME_ZONE="Asia/Tashkent", USE_TZ=True)
class SuperadminPaymentHistoryApiTests(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_superuser(
            email="superadmin.payment@test.uz",
            password="strong-pass-123",
        )
        self.client.force_login(self.superadmin)

        self.center = Center.objects.create(name="Pay Center", slug="pay-center")
        self.plan = SubscriptionPlan.objects.create(
            code="PRO",
            title="PRO",
            name="PRO",
            monthly_price=100000,
            price=100000,
            duration_days=30,
            max_students=100,
            active=True,
        )

    def _create_paid_order(self, paid_at, *, amount=1000):
        return SubscriptionOrder.objects.create(
            center=self.center,
            plan=self.plan,
            duration_months=1,
            base_price=amount,
            discount_percent=0,
            final_price=amount,
            status=SubscriptionOrder.Status.PAID,
            paid_at=paid_at,
        )

    def test_payment_history_api_supports_pagination_and_page_size(self):
        now = timezone.now()
        for i in range(25):
            self._create_paid_order(now - timedelta(minutes=i), amount=1000 + i)

        response = self.client.get("/platform/api/finance/payments/?per_page=10&page=2")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("payments", payload)
        self.assertEqual(len(payload["payments"]), 10)
        self.assertIn("pagination", payload)
        self.assertEqual(payload["pagination"]["per_page"], 10)
        self.assertEqual(payload["pagination"]["page"], 2)
        self.assertEqual(payload["pagination"]["total_pages"], 3)
        self.assertEqual(payload["pagination"]["total_count"], 25)
        self.assertTrue(payload["pagination"]["has_previous"])
        self.assertTrue(payload["pagination"]["has_next"])

    def test_payment_history_api_returns_local_time_string(self):
        paid_at_utc = datetime(2026, 3, 24, 16, 55, tzinfo=dt_timezone.utc)
        order = self._create_paid_order(paid_at_utc, amount=1200)

        response = self.client.get("/platform/api/finance/payments/?per_page=10&page=1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["payments"])

        row = next((item for item in payload["payments"] if item["id"] == order.id), None)
        self.assertIsNotNone(row)

        expected_local = timezone.localtime(paid_at_utc).strftime("%d.%m.%Y %H:%M")
        self.assertEqual(row["paid_at"], expected_local)

    def test_superadmin_dashboard_shows_paginated_payment_history_and_local_time(self):
        now = timezone.now()
        for i in range(12):
            self._create_paid_order(now - timedelta(minutes=i), amount=2000 + i)

        paid_at_utc = datetime(2026, 3, 24, 16, 55, tzinfo=dt_timezone.utc)
        self._create_paid_order(paid_at_utc, amount=7777)

        response = self.client.get("/platform/?payments_per_page=50&payments_page=1")
        self.assertEqual(response.status_code, 200)

        html = response.content.decode("utf-8")
        self.assertIn("Sahifa 1 / 1", html)
        self.assertIn("50 ta", html)
        self.assertIn("To'lovlar Tarixi", html)

        expected_local = timezone.localtime(paid_at_utc).strftime("%d.%m.%Y %H:%M")
        self.assertIn(expected_local, html)


class StudentLimitResolutionTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(
            name="Limit Center",
            slug="limit-center",
            capacity_limit=200,
            max_students=2000,
        )
        self.director = User.objects.create_user(
            email="director.limit@test.uz",
            password="strong-pass-123",
            role="director",
            ism="Limit",
            familya="Director",
            center=self.center,
        )
        self.plan = SubscriptionPlan.objects.create(
            code="LIMIT_2000",
            title="Limit 2000",
            name="LIMIT_2000",
            monthly_price=500000,
            price=500000,
            duration_days=30,
            max_students=2000,
            active=True,
        )
        CenterSubscription.objects.create(
            center=self.center,
            plan=self.plan,
            status=CenterSubscription.Status.ACTIVE,
            expires_at=timezone.now() + timedelta(days=30),
        )

    def _bulk_students(self, count: int):
        User.objects.bulk_create([
            User(
                email=f"student-limit-{idx}@test.uz",
                role="student",
                ism=f"Student{idx}",
                familya="Limit",
                center=self.center,
            )
            for idx in range(count)
        ])

    def test_check_student_limit_allows_261_of_2000(self):
        self._bulk_students(261)

        state = check_student_limit(self.center, raise_error=False, actor=self.director)

        self.assertFalse(state["is_at_limit"])
        self.assertEqual(state["current_count"], 261)
        self.assertEqual(state["limit"], 2000)
        self.assertIn(
            state["limit_source"],
            {"active_center_subscription.plan.max_students", "center.max_students"},
        )

    def test_check_student_limit_blocks_after_2000(self):
        self._bulk_students(2000)

        with self.assertRaises(ValidationError):
            check_student_limit(self.center, raise_error=True, actor=self.director)


class TenantRedirectRegressionTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Redirect Center", slug="redirect-center")
        self.director = User.objects.create_user(
            email="director.redirect@test.uz",
            password="strong-pass-123",
            role="director",
            ism="Redirect",
            familya="Director",
            center=self.center,
        )
        self.client.force_login(self.director)

    def test_core_home_reverse_points_to_web_dashboard(self):
        self.assertEqual(reverse("core:home"), "/")
        self.assertEqual(reverse("core:notifications"), "/notifications/")

    def test_add_user_redirects_back_to_web_home_after_save(self):
        response = self.client.post(
            reverse("accounts:add_user"),
            {
                "ism": "Ali",
                "familya": "Teacher",
                "otchestvo": "",
                "telefon1": "",
                "telefon2": "",
                "center": str(self.center.id),
                "role": "teacher",
                "email": "ali.teacher@test.uz",
                "password": "strong-pass-123",
                "oqituvchi_foizi": "45",
                "birth_date": "",
                "gender": "",
                "passport_id": "",
                "jshr": "",
                "address": "",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("core:home"))
        self.assertFalse(response["Location"].startswith("/api/mobile/"))
        self.assertTrue(User.objects.filter(email="ali.teacher@test.uz", role="teacher").exists())

    def test_add_user_redirects_to_next_when_provided(self):
        response = self.client.post(
            reverse("accounts:add_user") + "?role=student&next=/redirect-center/stat/students/",
            {
                "next": "/redirect-center/stat/students/",
                "ism": "Vali",
                "familya": "Student",
                "otchestvo": "",
                "telefon1": "",
                "telefon2": "",
                "center": str(self.center.id),
                "role": "student",
                "email": "vali.student@test.uz",
                "password": "strong-pass-123",
                "oqituvchi_foizi": "",
                "birth_date": "2010-01-01",
                "gender": "male",
                "passport_id": "",
                "jshr": "",
                "address": "",
                "group": "",
                "kurs_narhi": "",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/redirect-center/stat/students/")
        self.assertTrue(User.objects.filter(email="vali.student@test.uz", role="student").exists())

    def test_director_can_open_tenant_add_user_page(self):
        response = self.client.get(reverse("accounts:add_user") + "?role=student")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student Anketasi")
