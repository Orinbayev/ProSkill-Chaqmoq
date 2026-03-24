from datetime import datetime, timedelta, timezone as dt_timezone

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Center, User
from billing.models import SubscriptionOrder, SubscriptionPlan


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
