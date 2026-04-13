from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Center, User
from chaqmoq.models import Ledger, Rule
from chaqmoq.services import apply_payment_discipline_penalties
from education.models import Enrollment, Group, Payment, PaymentAllocation, TuitionMonth


class PaymentDisciplineRuleTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Discipline Center", slug="discipline-center")
        self.director = User.objects.create_user(
            email="director@discipline.test",
            password="testpass123",
            role="director",
            center=self.center,
            ism="Discipline",
            familya="Director",
        )
        self.teacher = User.objects.create_user(
            email="teacher@discipline.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Discipline",
            familya="Teacher",
        )
        self.student = User.objects.create_user(
            email="student@discipline.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Discipline",
            familya="Student",
            telefon1="+998901110000",
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="Discipline Group",
            oqituvchi=self.teacher,
            kurs_narxi=100_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            kurs_narhi=100_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        self.rule = Rule.objects.create(
            center=self.center,
            nom="To'lov intizomi",
            tur=Rule.PAYMENT_DISCIPLINE,
            discipline_active=True,
            discipline_deadline_day=10,
            discipline_bonus_score=20,
            discipline_penalty_score=-20,
        )
        self.month = date(2026, 4, 1)

    def _create_tuition_month(self, enrollment=None):
        enrollment = enrollment or self.enrollment
        return TuitionMonth.objects.create(
            center=self.center,
            enrollment=enrollment,
            month=self.month,
            fee_amount=100_000,
        )

    def _create_payment(self, enrollment=None, amount=100_000):
        enrollment = enrollment or self.enrollment
        return Payment.objects.create(
            center=self.center,
            enrollment=enrollment,
            student=enrollment.student,
            group=enrollment.group,
            payment_type="cash",
            cash_amount=amount,
            paid_date=date(2026, 4, 10),
            created_by=self.director,
        )

    def test_full_payment_before_deadline_adds_discipline_bonus(self):
        tuition_month = self._create_tuition_month()

        with patch("chaqmoq.services.timezone.localdate", return_value=date(2026, 4, 10)):
            payment = self._create_payment()
            PaymentAllocation.objects.create(
                center=self.center,
                payment=payment,
                tuition_month=tuition_month,
                amount=100_000,
            )

        ledger = Ledger.objects.get(student=self.student, rule=self.rule, related_month=self.month)
        self.assertEqual(ledger.ball, 20)

    def test_unpaid_student_after_deadline_gets_penalty_once(self):
        self._create_tuition_month()

        with patch("chaqmoq.services.timezone.localdate", return_value=date(2026, 4, 11)):
            count = apply_payment_discipline_penalties(center=self.center)
            second_count = apply_payment_discipline_penalties(center=self.center)

        self.assertEqual(count, 1)
        self.assertEqual(second_count, 0)
        self.assertEqual(
            list(Ledger.objects.filter(student=self.student, rule=self.rule).values_list("ball", flat=True)),
            [-20],
        )

    def test_penalty_command_processes_all_centers(self):
        self._create_tuition_month()
        out = StringIO()

        with patch("chaqmoq.services.timezone.localdate", return_value=date(2026, 4, 11)):
            call_command("process_lightning_rules", stdout=out)

        self.assertIn("Applied 1 payment discipline penalties.", out.getvalue())
        self.assertTrue(
            Ledger.objects.filter(
                student=self.student,
                rule=self.rule,
                related_month=self.month,
                ball=-20,
            ).exists()
        )

    def test_student_with_multiple_unpaid_enrollments_gets_one_monthly_penalty(self):
        self._create_tuition_month()
        second_group = Group.objects.create(
            center=self.center,
            nom="Second Discipline Group",
            oqituvchi=self.teacher,
            kurs_narxi=100_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        second_enrollment = Enrollment.objects.create(
            center=self.center,
            group=second_group,
            student=self.student,
            kurs_narhi=100_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        self._create_tuition_month(second_enrollment)

        with patch("chaqmoq.services.timezone.localdate", return_value=date(2026, 4, 11)):
            count = apply_payment_discipline_penalties(center=self.center)

        self.assertEqual(count, 1)
        self.assertEqual(Ledger.objects.filter(student=self.student, rule=self.rule).count(), 1)
