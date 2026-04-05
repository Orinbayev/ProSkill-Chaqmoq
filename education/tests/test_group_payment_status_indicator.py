from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import Center, User
from education.models import Enrollment, Group, Payment, PaymentAllocation, TuitionMonth


class GroupPaymentStatusIndicatorTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Status Center", slug="status-center")
        self.director = User.objects.create_user(
            email="director@status.test",
            password="testpass123",
            role="director",
            center=self.center,
            ism="Status",
            familya="Director",
        )
        self.teacher = User.objects.create_user(
            email="teacher@status.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Status",
            familya="Teacher",
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="Automation Group",
            oqituvchi=self.teacher,
            kurs_narxi=100_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.group_two = Group.objects.create(
            center=self.center,
            nom="Automation Group 2",
            oqituvchi=self.teacher,
            kurs_narxi=300_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.april_date = date(2026, 4, 5)
        self.april_month = date(2026, 4, 1)
        self.may_date = date(2026, 5, 5)

        self.full_student, self.full_enrollment = self._create_student_with_enrollment("full")
        self.partial_student, self.partial_enrollment = self._create_student_with_enrollment("partial")
        self.unpaid_student, self.unpaid_enrollment = self._create_student_with_enrollment("unpaid")
        self.multi_student, self.multi_primary_enrollment = self._create_student_with_enrollment("multi")
        self.multi_secondary_enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group_two,
            student=self.multi_student,
            kurs_narhi=300_000,
            oqituvchi_foiz=40,
            is_active=True,
        )

        self.full_tm = TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.full_enrollment,
            month=self.april_month,
            fee_amount=100_000,
        )
        self.partial_tm = TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.partial_enrollment,
            month=self.april_month,
            fee_amount=100_000,
        )
        self.unpaid_tm = TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.unpaid_enrollment,
            month=self.april_month,
            fee_amount=100_000,
        )
        self.multi_primary_tm = TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.multi_primary_enrollment,
            month=self.april_month,
            fee_amount=100_000,
        )
        self.multi_secondary_tm = TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.multi_secondary_enrollment,
            month=self.april_month,
            fee_amount=300_000,
        )

        full_payment = Payment.objects.create(
            center=self.center,
            enrollment=self.full_enrollment,
            student=self.full_student,
            group=self.group,
            payment_type="cash",
            cash_amount=100_000,
            paid_date=self.april_date,
            created_by=self.director,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=full_payment,
            tuition_month=self.full_tm,
            amount=100_000,
        )

        partial_payment = Payment.objects.create(
            center=self.center,
            enrollment=self.partial_enrollment,
            student=self.partial_student,
            group=self.group,
            payment_type="cash",
            cash_amount=40_000,
            paid_date=self.april_date,
            created_by=self.director,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=partial_payment,
            tuition_month=self.partial_tm,
            amount=40_000,
        )

        multi_payment = Payment.objects.create(
            center=self.center,
            enrollment=self.multi_primary_enrollment,
            student=self.multi_student,
            group=self.group,
            payment_type="cash",
            cash_amount=100_000,
            paid_date=self.april_date,
            created_by=self.director,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=multi_payment,
            tuition_month=self.multi_primary_tm,
            amount=100_000,
        )

        self.client.force_login(self.director)
        self.url = f"/{self.center.slug}{reverse('education:group_detail', args=[self.group.id])}"

    def _create_student_with_enrollment(self, key: str):
        student = User.objects.create_user(
            email=f"{key}@status.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism=key.capitalize(),
            familya="Student",
            telefon1=f"+99890123{len(key):04d}",
        )
        enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=student,
            kurs_narhi=100_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        return student, enrollment

    def test_group_detail_shows_paid_partial_and_unpaid_payment_statuses(self):
        response = self.client.get(self.url, {"date": self.april_date.isoformat()})

        self.assertEqual(response.status_code, 200)
        statuses = {e.student.email: e.payment_status for e in response.context["enrollments"]}

        self.assertEqual(statuses[self.full_student.email], "paid")
        self.assertEqual(statuses[self.partial_student.email], "partial")
        self.assertEqual(statuses[self.unpaid_student.email], "unpaid")
        self.assertEqual(statuses[self.multi_student.email], "partial")

        self.assertContains(response, "payment-dot is-paid")
        self.assertContains(response, "payment-dot is-partial")
        self.assertContains(response, "payment-dot is-unpaid")

    def test_group_detail_uses_selected_month_for_payment_status(self):
        response = self.client.get(self.url, {"date": self.may_date.isoformat()})

        self.assertEqual(response.status_code, 200)
        statuses = {e.student.email: e.payment_status for e in response.context["enrollments"]}

        self.assertEqual(statuses[self.full_student.email], "unpaid")
        self.assertEqual(statuses[self.partial_student.email], "unpaid")
        self.assertEqual(statuses[self.unpaid_student.email], "unpaid")
        self.assertEqual(statuses[self.multi_student.email], "unpaid")
