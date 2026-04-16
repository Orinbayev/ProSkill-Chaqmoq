from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import Center, User
from education.models import Enrollment, Group, Payment, PaymentAllocation, TuitionMonth
from education.services.reset_center_debt_service import verify_center_single_month_debt


class ResetCenterToAprilDebtCommandTests(TestCase):
    def setUp(self):
        self.target_month = date(2026, 4, 1)

        self.center = Center.objects.create(name="Test Center", slug="test")
        self.other_center = Center.objects.create(name="Other Center", slug="other")

        self.manager = User.objects.create_user(
            email="manager@test.local",
            password="testpass123",
            role="manager",
            center=self.center,
            ism="Reset",
            familya="Manager",
        )
        self.teacher = User.objects.create_user(
            email="teacher@test.local",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Reset",
            familya="Teacher",
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="Reset Group",
            oqituvchi=self.teacher,
            kurs_narxi=300_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )

        self.student_one = User.objects.create_user(
            email="student1@test.local",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Ali",
            familya="Reset",
            telefon1="+998901110001",
        )
        self.student_two = User.objects.create_user(
            email="student2@test.local",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Vali",
            familya="Reset",
            telefon1="+998901110002",
        )

        self.enrollment_one = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student_one,
            kurs_narhi=300_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        self.enrollment_two = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student_two,
            kurs_narhi=400_000,
            student_payable_amount=250_000,
            oqituvchi_foiz=40,
            is_active=True,
        )

        self.tm_one_march = TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.enrollment_one,
            month=date(2026, 3, 1),
            fee_amount=300_000,
        )
        self.tm_one_april = TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.enrollment_one,
            month=self.target_month,
            fee_amount=300_000,
        )
        self.tm_two_march = TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.enrollment_two,
            month=date(2026, 3, 1),
            fee_amount=250_000,
        )
        self.tm_two_may = TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.enrollment_two,
            month=date(2026, 5, 1),
            fee_amount=250_000,
        )

        self.payment_one = Payment.objects.create(
            enrollment=self.enrollment_one,
            center=self.center,
            student=self.student_one,
            group=self.group,
            payment_type="cash",
            cash_amount=300_000,
            paid_date=date(2026, 3, 5),
            created_by=self.manager,
        )
        self.payment_two = Payment.objects.create(
            enrollment=self.enrollment_two,
            center=self.center,
            student=self.student_two,
            group=self.group,
            payment_type="cash",
            cash_amount=100_000,
            paid_date=date(2026, 4, 10),
            created_by=self.manager,
        )

        self.allocation_one = PaymentAllocation.objects.create(
            center=self.center,
            payment=self.payment_one,
            tuition_month=self.tm_one_march,
            amount=300_000,
        )
        self.allocation_two = PaymentAllocation.objects.create(
            center=self.center,
            payment=self.payment_two,
            tuition_month=self.tm_two_march,
            amount=100_000,
        )

        # Legacy/noisy rows: center can be null, but they still belong to the current center.
        Payment.all_objects.filter(pk=self.payment_two.pk).update(center=None)
        PaymentAllocation.all_objects.filter(pk=self.allocation_two.pk).update(center=None)
        TuitionMonth.all_objects.filter(pk=self.tm_two_may.pk).update(center=None)

        other_manager = User.objects.create_user(
            email="manager@other.local",
            password="testpass123",
            role="manager",
            center=self.other_center,
            ism="Other",
            familya="Manager",
        )
        other_teacher = User.objects.create_user(
            email="teacher@other.local",
            password="testpass123",
            role="teacher",
            center=self.other_center,
            ism="Other",
            familya="Teacher",
        )
        other_group = Group.objects.create(
            center=self.other_center,
            nom="Other Group",
            oqituvchi=other_teacher,
            kurs_narxi=180_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        other_student = User.objects.create_user(
            email="student@other.local",
            password="testpass123",
            role="student",
            center=self.other_center,
            ism="Other",
            familya="Student",
            telefon1="+998901119999",
        )
        other_enrollment = Enrollment.objects.create(
            center=self.other_center,
            group=other_group,
            student=other_student,
            kurs_narhi=180_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        other_tm = TuitionMonth.objects.create(
            center=self.other_center,
            enrollment=other_enrollment,
            month=self.target_month,
            fee_amount=180_000,
        )
        other_payment = Payment.objects.create(
            enrollment=other_enrollment,
            center=self.other_center,
            student=other_student,
            group=other_group,
            payment_type="cash",
            cash_amount=180_000,
            paid_date=date(2026, 4, 8),
            created_by=other_manager,
        )
        PaymentAllocation.objects.create(
            center=self.other_center,
            payment=other_payment,
            tuition_month=other_tm,
            amount=180_000,
        )

        self.client.force_login(self.manager)
        self.qarzdorlar_url = f"/{self.center.slug}{reverse('education:qarzdorlar_home')}"
        self.tolovlar_url = f"/{self.center.slug}{reverse('education:tolovlar_home')}"
        self.april_range = {
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
        }

    def test_command_resets_only_target_center_to_april_debt(self):
        stdout = StringIO()

        call_command(
            "reset_center_to_april_debt",
            center_slug=self.center.slug,
            month="2026-04",
            stdout=stdout,
        )

        verification = verify_center_single_month_debt(self.center, self.target_month)

        self.assertEqual(verification.remaining_payments, 0)
        self.assertEqual(verification.remaining_allocations, 0)
        self.assertEqual(verification.active_enrollment_count, 2)
        self.assertEqual(verification.target_month_tuition_count, 2)
        self.assertEqual(verification.debtor_count, 2)
        self.assertEqual(verification.total_debt, 550_000)
        self.assertEqual(verification.expected_total_debt, 550_000)

        self.enrollment_one.refresh_from_db()
        self.enrollment_two.refresh_from_db()
        self.assertEqual(self.enrollment_one.jami_tolangan, 0)
        self.assertEqual(self.enrollment_two.jami_tolangan, 0)

        self.assertEqual(
            Payment.objects.filter(group__center=self.center).count(),
            0,
        )
        self.assertEqual(
            PaymentAllocation.objects.filter(payment__group__center=self.center).count(),
            0,
        )
        self.assertEqual(
            TuitionMonth.objects.filter(
                enrollment__in=[self.enrollment_one, self.enrollment_two],
                month=self.target_month,
            ).count(),
            2,
        )
        self.assertEqual(
            TuitionMonth.objects.filter(
                enrollment__in=[self.enrollment_one, self.enrollment_two],
            ).exclude(month=self.target_month).count(),
            0,
        )
        self.assertTrue(
            TuitionMonth.all_objects.filter(
                enrollment=self.enrollment_one,
                month=date(2026, 3, 1),
                is_deleted=True,
            ).exists()
        )
        self.assertTrue(
            TuitionMonth.all_objects.filter(
                enrollment=self.enrollment_two,
                month=date(2026, 5, 1),
                is_deleted=True,
            ).exists()
        )

        april_tm_two = TuitionMonth.objects.get(
            enrollment=self.enrollment_two,
            month=self.target_month,
        )
        self.assertEqual(april_tm_two.fee_amount, 250_000)
        self.assertEqual(april_tm_two.center, self.center)

        self.assertEqual(
            Payment.objects.filter(group__center=self.other_center).count(),
            1,
        )
        self.assertEqual(
            PaymentAllocation.objects.filter(payment__group__center=self.other_center).count(),
            1,
        )

        qarzdorlar_response = self.client.get(self.qarzdorlar_url, self.april_range)
        self.assertEqual(qarzdorlar_response.status_code, 200)
        self.assertEqual(qarzdorlar_response.context["stats_summary"]["debtors"], 2)
        self.assertEqual(qarzdorlar_response.context["page_obj"].paginator.count, 2)

        rows = {
            row["student"].email: row
            for row in qarzdorlar_response.context["page_obj"].object_list
        }
        self.assertEqual(rows[self.student_one.email]["debt"], 300_000)
        self.assertEqual(rows[self.student_two.email]["debt"], 250_000)

        tolovlar_response = self.client.get(self.tolovlar_url, self.april_range)
        self.assertEqual(tolovlar_response.status_code, 200)
        self.assertEqual(tolovlar_response.context["page_obj"].paginator.count, 0)
        self.assertEqual(tolovlar_response.context["payment_record_count"], 0)

        output = stdout.getvalue()
        self.assertIn("Reset muvaffaqiyatli yakunlandi", output)
        self.assertIn("/test/talim/qarzdorlar/", output)

    def test_command_dry_run_does_not_change_data(self):
        stdout = StringIO()

        call_command(
            "reset_center_to_april_debt",
            center_slug=self.center.slug,
            month="2026-04",
            dry_run=True,
            stdout=stdout,
        )

        self.assertEqual(
            Payment.objects.filter(group__center=self.center).count(),
            2,
        )
        self.assertEqual(
            PaymentAllocation.objects.filter(payment__group__center=self.center).count(),
            2,
        )
        self.assertEqual(
            TuitionMonth.objects.filter(enrollment__group__center=self.center).count(),
            4,
        )
        self.enrollment_one.refresh_from_db()
        self.enrollment_two.refresh_from_db()
        self.assertEqual(self.enrollment_one.jami_tolangan, 300_000)
        self.assertEqual(self.enrollment_two.jami_tolangan, 100_000)
        self.assertIn("DRY-RUN", stdout.getvalue())

    def test_command_allows_zero_fee_enrollments_to_remain_free(self):
        free_student = User.objects.create_user(
            email="free@test.local",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Free",
            familya="Student",
            telefon1="+998901110003",
        )
        free_enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=free_student,
            kurs_narhi=0,
            student_payable_amount=0,
            oqituvchi_foiz=40,
            is_active=True,
        )

        stdout = StringIO()
        call_command(
            "reset_center_to_april_debt",
            center_slug=self.center.slug,
            month="2026-04",
            stdout=stdout,
        )

        verification = verify_center_single_month_debt(self.center, self.target_month)
        self.assertEqual(verification.active_enrollment_count, 3)
        self.assertEqual(verification.expected_debtor_count, 2)
        self.assertEqual(verification.debtor_count, 2)
        self.assertEqual(verification.total_debt, 550_000)

        free_tm = TuitionMonth.objects.get(enrollment=free_enrollment, month=self.target_month)
        self.assertEqual(free_tm.fee_amount, 0)

        qarzdorlar_response = self.client.get(self.qarzdorlar_url, self.april_range)
        self.assertEqual(qarzdorlar_response.status_code, 200)
        self.assertEqual(qarzdorlar_response.context["stats_summary"]["debtors"], 2)
        debtor_emails = {
            row["student"].email
            for row in qarzdorlar_response.context["page_obj"].object_list
        }
        self.assertNotIn(free_student.email, debtor_emails)

        output = stdout.getvalue()
        self.assertIn("Fee=0 enrollmentlar topildi", output)
