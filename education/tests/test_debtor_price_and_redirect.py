import json
from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import Center, User
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

    def test_payment_clearing_debt_redirects(self):
        """
        Making a payment that brings total debt to 0 redirects to /talim/tolovlar/
        """
        # Calculate initial total debt
        total_debt_before = get_student_total_debt(self.student, self.center)
        self.assertGreater(total_debt_before, 0)

        # Create a partial payment
        url = reverse("education:create_payment")
        tenant_url = f"/{self.center.slug}{url}"
        
        payload_partial = {
            "student_id": self.student.id,
            "enrollment_id": self.enrollment.id,
            "cash_amount": "200000",
            "card_amount": "0",
            "paid_date": "2026-06-08",
            "next": f"/{self.center.slug}/talim/qarzdorlar/",
        }
        response = self.client.post(tenant_url, payload_partial)
        # Should redirect back to next URL specified in POST
        self.assertRedirects(response, f"/{self.center.slug}/talim/qarzdorlar/", target_status_code=302)

        # Pay remaining
        remaining = get_student_total_debt(self.student, self.center)
        self.assertGreater(remaining, 0)
        
        payload_full = {
            "student_id": self.student.id,
            "enrollment_id": self.enrollment.id,
            "cash_amount": str(remaining),
            "card_amount": "0",
            "paid_date": "2026-06-08",
            "next": f"/{self.center.slug}/talim/qarzdorlar/",
        }
        response = self.client.post(tenant_url, payload_full)
        # Should automatically redirect to tolovlar_home since total debt is 0
        expected_redirect = reverse("education:tolovlar_home")
        self.assertRedirects(response, expected_redirect, target_status_code=302)

    def test_edit_student_month_debt_to_zero_redirects_via_total_debt(self):
        """
        Editing monthly debt to a value that makes total debt 0 returns total_debt: 0
        """
        total_debt_before = get_student_total_debt(self.student, self.center)
        self.assertEqual(total_debt_before, 800_000)

        # Update June month debt to 0
        url = reverse("education:edit_student_month_debt", args=[self.student.pk])
        tenant_url = f"/{self.center.slug}{url}"
        
        payload_june = {
            "month": "2026-06",
            "new_debt": "0",
        }
        response = self.client.post(tenant_url, payload_june)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["total_debt"], 400_000)  # May debt still remains

        # Update May month debt to 0
        payload_may = {
            "month": "2026-05",
            "new_debt": "0",
        }
        response = self.client.post(tenant_url, payload_may)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["total_debt"], 0)  # Total debt is now 0
