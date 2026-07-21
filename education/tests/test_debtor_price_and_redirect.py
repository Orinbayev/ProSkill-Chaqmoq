import json
from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import Center, User
from core.test_utils import activate_center
from education.models import Group, Enrollment, TuitionMonth, Payment
from billing.models import SubscriptionPlan
from education.services.tuition import ensure_tuition_month, tuition_month_fee_field
from education.views import get_student_total_debt

class DebtorPriceAndRedirectTests(TestCase):
    def setUp(self):
        # Create billing plan required for operations
        self.plan = SubscriptionPlan.objects.create(
            code="START",
            title="Start Plan",
            monthly_price=0,
            active=True
        )

        # Setup tenant center
        self.center = Center.objects.create(
            name="Test Center", slug="test-center"
        )
        activate_center(self.center)
        self.director = User.objects.create_user(
            email="director@test.com", password="password",
            role="director", center=self.center,
            ism="Dir", familya="Test"
        )
        self.teacher = User.objects.create_user(
            email="teacher@test.com", password="password",
            role="teacher", center=self.center,
            ism="Teach", familya="Test"
        )
        self.student = User.objects.create_user(
            email="student@test.com", password="password",
            role="student", center=self.center,
            ism="Ali", familya="Valiyev"
        )

        # Setup group
        self.group = Group.objects.create(
            center=self.center, nom="Test Group",
            oqituvchi=self.teacher,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )

        # Setup enrollment starting in past month (2026-05-01)
        self.enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            kurs_narhi=500_000,
            student_payable_amount=400_000,  # override is set initially
            oqituvchi_foiz=40,
            is_active=True,
            joined_at=date(2026, 5, 1),
            monthly_lessons=12,
        )

        # Ensure tuition months exist
        self.tm_may = ensure_tuition_month(self.enrollment, date(2026, 5, 1))
        self.tm_june = ensure_tuition_month(self.enrollment, date(2026, 6, 1))

        self.client.force_login(self.director)

    def test_student_drawer_price_edit_syncs_and_clears_override(self):
        """
        Editing student price in the drawer:
        - updates kurs_narhi
        - clears student_payable_amount (sets to None)
        - syncs new price to all tuition months starting from joined_at
        """
        fee_field = tuition_month_fee_field()
        # Verify initial state
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.kurs_narhi, 500_000)
        self.assertEqual(self.enrollment.student_payable_amount, 400_000)
        
        self.tm_may.refresh_from_db()
        self.tm_june.refresh_from_db()
        self.assertEqual(getattr(self.tm_may, fee_field), 400_000)
        self.assertEqual(getattr(self.tm_june, fee_field), 400_000)

        # Make the AJAX request to update the enrollment price
        url = reverse("accounts:student_edit_ajax", args=[self.student.pk])
        payload = {
            "action": "enrollment_update",
            "enrollment_id": self.enrollment.id,
            "kurs_narhi": "350000",
            "joined_at": "2026-05-01",
            "lesson_pattern": "group",
        }
        tenant_url = f"/{self.center.slug}{url}"
        response = self.client.post(tenant_url, payload)
        self.assertEqual(response.status_code, 200)
        
        # Verify enrollment is updated
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.kurs_narhi, 350_000)
        self.assertIsNone(self.enrollment.student_payable_amount)

        # Verify both TuitionMonth objects are updated to 350000
        self.tm_may.refresh_from_db()
        self.tm_june.refresh_from_db()
        self.assertEqual(getattr(self.tm_may, fee_field), 350_000)
        self.assertEqual(getattr(self.tm_june, fee_field), 350_000)

    def test_payment_clearing_debt_stays_in_qarzdorlar(self):
        """
        Qarzdorlar bo'limidan to'lov qilinganda — qarz to'liq yopilsa ham —
        foydalanuvchi qarzdorlar sahifasida qoladi (tolovlar_home ga o'tmaydi).
        """
        total_debt_before = get_student_total_debt(self.student, self.center)
        self.assertGreater(total_debt_before, 0)

        url = reverse("education:create_payment")
        tenant_url = f"/{self.center.slug}{url}"
        qarzdorlar_url = f"/{self.center.slug}/talim/qarzdorlar/"

        # Qisman to'lov
        payload_partial = {
            "student_id": self.student.id,
            "enrollment_id": self.enrollment.id,
            "cash_amount": "200000",
            "card_amount": "0",
            "paid_date": "2026-06-08",
            "next": qarzdorlar_url,
        }
        response = self.client.post(tenant_url, payload_partial)
        self.assertRedirects(response, qarzdorlar_url, target_status_code=200)

        # To'liq to'lov — qarz 0 ga tushadi
        remaining = get_student_total_debt(self.student, self.center)
        self.assertGreater(remaining, 0)

        payload_full = {
            "student_id": self.student.id,
            "enrollment_id": self.enrollment.id,
            "cash_amount": str(remaining),
            "card_amount": "0",
            "paid_date": "2026-06-08",
            "next": qarzdorlar_url,
        }
        response = self.client.post(tenant_url, payload_full)
        # Qarzdorlardan kelgan bo'lsa — shu sahifada qoladi
        self.assertRedirects(response, qarzdorlar_url, target_status_code=200)

    def test_payment_from_tolovlar_redirects_to_tolovlar_when_debt_zero(self):
        """
        To'lovlar bo'limidan to'lov qilinib qarz 0 bo'lsa — tolovlar_home ga o'tadi.
        """
        total_debt_before = get_student_total_debt(self.student, self.center)
        self.assertGreater(total_debt_before, 0)

        url = reverse("education:create_payment")
        tenant_url = f"/{self.center.slug}{url}"
        tolovlar_url = f"/{self.center.slug}/talim/tolovlar/"

        # To'liq to'lov, to'lovlar bo'limidan
        payload_full = {
            "student_id": self.student.id,
            "enrollment_id": self.enrollment.id,
            "cash_amount": str(total_debt_before),
            "card_amount": "0",
            "paid_date": "2026-06-08",
            "next": tolovlar_url,
        }
        response = self.client.post(tenant_url, payload_full)
        # To'lovlardan kelgan bo'lsa — tolovlar_home ga o'tadi
        expected_redirect = reverse("education:tolovlar_home")
        self.assertRedirects(response, expected_redirect, fetch_redirect_response=False)

    def test_edit_student_month_debt_to_zero_redirects_via_total_debt(self):
        """
        Oy qarzi tahriri: fee 0 ga tushadi va API ok + total_debt qaytaradi.
        """
        fee_field = tuition_month_fee_field()
        may_fee = int(getattr(self.tm_may, fee_field) or 0)
        june_fee = int(getattr(self.tm_june, fee_field) or 0)
        self.assertEqual(may_fee, 400_000)
        self.assertEqual(june_fee, 400_000)

        url = reverse("education:edit_student_month_debt", args=[self.student.pk])
        tenant_url = f"/{self.center.slug}{url}"

        # June → 0
        response = self.client.post(tenant_url, {"month": "2026-06", "new_debt": "0"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIn("total_debt", data)
        self.assertGreaterEqual(int(data["total_debt"]), 0)

        self.tm_june.refresh_from_db()
        self.assertEqual(int(getattr(self.tm_june, fee_field) or 0), 0)

        # May → 0
        response = self.client.post(tenant_url, {"month": "2026-05", "new_debt": "0"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertGreaterEqual(int(data["total_debt"]), 0)

        self.tm_may.refresh_from_db()
        self.assertEqual(int(getattr(self.tm_may, fee_field) or 0), 0)
