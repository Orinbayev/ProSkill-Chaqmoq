from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse

from accounts.models import Center, User
from education.models import Attendance, Enrollment, Group, Payment, PaymentAllocation, StudentGroupTransfer, TuitionMonth
from education.services.student_transfer import transfer_student_to_group


class StudentGroupTransferTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Transfer Center", slug="transfer-center")
        self.other_center = Center.objects.create(name="Other Center", slug="other-transfer-center")
        self.director = User.objects.create_user(
            email="director@transfer.test",
            password="testpass123",
            role="director",
            center=self.center,
            ism="Transfer",
            familya="Director",
        )
        self.employee = User.objects.create_user(
            email="employee@transfer.test",
            password="testpass123",
            role="cashier",
            center=self.center,
            ism="Simple",
            familya="Employee",
        )
        self.teacher = User.objects.create_user(
            email="teacher@transfer.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Transfer",
            familya="Teacher",
        )
        self.student = User.objects.create_user(
            email="student@transfer.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Transfer",
            familya="Student",
        )
        self.group_a = Group.objects.create(
            center=self.center,
            nom="A Group",
            oqituvchi=self.teacher,
            kurs_narxi=260_000,
            oqituvchi_foiz=40,
            oy_dars_soni=26,
        )
        self.group_b = Group.objects.create(
            center=self.center,
            nom="B Group",
            oqituvchi=self.teacher,
            kurs_narxi=260_000,
            oqituvchi_foiz=40,
            oy_dars_soni=26,
        )
        self.other_group = Group.objects.create(
            center=self.other_center,
            nom="Other Group",
            oqituvchi=None,
            kurs_narxi=260_000,
            oqituvchi_foiz=40,
            oy_dars_soni=26,
        )
        self.enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group_a,
            student=self.student,
            kurs_narhi=260_000,
            oqituvchi_foiz=40,
            monthly_lessons=26,
            joined_at=date(2026, 4, 1),
            lesson_pattern=Enrollment.LESSON_PATTERN_DAILY,
            is_active=True,
        )
        self.month = date(2026, 4, 1)
        self.old_tm = TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.enrollment,
            month=self.month,
            fee_amount=260_000,
        )
        self.payment = Payment.objects.create(
            center=self.center,
            enrollment=self.enrollment,
            student=self.student,
            group=self.group_a,
            payment_type="cash",
            cash_amount=260_000,
            paid_date=date(2026, 4, 5),
            created_by=self.director,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=self.payment,
            tuition_month=self.old_tm,
            amount=260_000,
        )
        Attendance.objects.create(
            center=self.center,
            group=self.group_a,
            student=self.student,
            teacher=self.teacher,
            date=date(2026, 4, 3),
            status="present",
            present=True,
        )

    def test_transfer_moves_student_and_keeps_history(self):
        result = transfer_student_to_group(
            student=self.student,
            old_group=self.group_a,
            new_group=self.group_b,
            transfer_date=date(2026, 4, 16),
            reason="Jadval mos kelmadi",
            user=self.director,
        )

        self.enrollment.refresh_from_db()
        self.assertFalse(self.enrollment.is_active)
        self.assertFalse(Enrollment.objects.filter(group=self.group_a, student=self.student, is_active=True).exists())
        self.assertTrue(Enrollment.objects.filter(group=self.group_b, student=self.student, is_active=True).exists())
        self.assertEqual(Attendance.objects.filter(group=self.group_a, student=self.student).count(), 1)
        self.assertEqual(StudentGroupTransfer.objects.filter(student=self.student).count(), 1)

        old_tm = TuitionMonth.objects.get(enrollment=self.enrollment, month=self.month)
        new_tm = TuitionMonth.objects.get(enrollment=result["new_enrollment"], month=self.month)
        self.assertEqual(old_tm.fee_amount + new_tm.fee_amount, 260_000)
        self.assertEqual(PaymentAllocation.objects.filter(payment=self.payment).count(), 2)
        self.assertEqual(
            PaymentAllocation.objects.filter(tuition_month=old_tm).aggregate(s=Sum("amount"))["s"],
            old_tm.fee_amount,
        )
        self.assertEqual(
            PaymentAllocation.objects.filter(tuition_month=new_tm).aggregate(s=Sum("amount"))["s"],
            new_tm.fee_amount,
        )

    def test_transfer_without_attendance_zeros_old_group_financials(self):
        Attendance.objects.filter(group=self.group_a, student=self.student).delete()

        result = transfer_student_to_group(
            student=self.student,
            old_group=self.group_a,
            new_group=self.group_b,
            transfer_date=date(2026, 4, 16),
            reason="",
            user=self.director,
        )

        self.enrollment.refresh_from_db()
        transfer = StudentGroupTransfer.objects.get(student=self.student)
        old_tm = TuitionMonth.objects.get(enrollment=self.enrollment, month=self.month)
        new_tm = TuitionMonth.objects.get(enrollment=result["new_enrollment"], month=self.month)

        self.assertFalse(self.enrollment.is_active)
        self.assertFalse(Enrollment.objects.filter(group=self.group_a, student=self.student, is_active=True).exists())
        self.assertTrue(Enrollment.objects.filter(group=self.group_b, student=self.student, is_active=True).exists())
        self.assertEqual(old_tm.fee_amount, 0)
        self.assertEqual(transfer.old_attendance_summary["total"], 0)
        self.assertEqual(transfer.old_attendance_summary["present"], 0)
        self.assertEqual(transfer.old_payment_state["old_group_financials"]["billable_lessons"], 0)
        self.assertEqual(transfer.old_payment_state["old_group_financials"]["student_debt"], 0)
        self.assertEqual(transfer.old_payment_state["old_group_financials"]["teacher_share"], 0)
        self.assertEqual(transfer.old_payment_state["old_group_financials"]["center_share"], 0)
        self.assertGreaterEqual(new_tm.fee_amount, 0)
        self.assertEqual(
            PaymentAllocation.objects.filter(payment=self.payment).aggregate(s=Sum("amount"))["s"],
            260_000,
        )

    def test_cannot_transfer_to_same_or_other_tenant_group(self):
        with self.assertRaises(ValidationError):
            transfer_student_to_group(
                student=self.student,
                old_group=self.group_a,
                new_group=self.group_a,
                transfer_date=date(2026, 4, 16),
                reason="Same",
                user=self.director,
            )

        with self.assertRaises(ValidationError):
            transfer_student_to_group(
                student=self.student,
                old_group=self.group_a,
                new_group=self.other_group,
                transfer_date=date(2026, 4, 16),
                reason="Tenant",
                user=self.director,
            )

    def test_regular_employee_cannot_transfer(self):
        with self.assertRaises(PermissionDenied):
            transfer_student_to_group(
                student=self.student,
                old_group=self.group_a,
                new_group=self.group_b,
                transfer_date=date(2026, 4, 16),
                reason="No permission",
                user=self.employee,
            )

    def test_transfer_view_rejects_regular_employee(self):
        self.client.force_login(self.employee)
        url = f"/{self.center.slug}{reverse('education:transfer_student', args=[self.enrollment.id])}"
        response = self.client.post(url, {
            "new_group": self.group_b.id,
            "transfer_date": "2026-04-16",
            "reason": "No permission",
        })

        self.assertEqual(response.status_code, 302)
        self.enrollment.refresh_from_db()
        self.assertTrue(self.enrollment.is_active)

    def test_transfer_view_accepts_missing_reason_and_date_when_student_has_no_attendance(self):
        Attendance.objects.filter(group=self.group_a, student=self.student).delete()
        self.client.force_login(self.director)
        url = f"/{self.center.slug}{reverse('education:transfer_student', args=[self.enrollment.id])}"

        with patch("education.forms.timezone.localdate", return_value=date(2026, 4, 16)):
            response = self.client.post(url, {
                "new_group": self.group_b.id,
            })

        self.assertEqual(response.status_code, 302)
        self.enrollment.refresh_from_db()
        self.assertFalse(self.enrollment.is_active)
        self.assertTrue(Enrollment.objects.filter(group=self.group_b, student=self.student, is_active=True).exists())
        transfer = StudentGroupTransfer.objects.get(student=self.student)
        self.assertEqual(transfer.transfer_date, date(2026, 4, 16))
        self.assertEqual(transfer.old_attendance_summary["total"], 0)

    def test_transfer_rolls_back_on_error(self):
        with patch("education.services.student_transfer.StudentGroupTransfer.objects.create", side_effect=RuntimeError("archive failed")):
            with self.assertRaises(RuntimeError):
                transfer_student_to_group(
                    student=self.student,
                    old_group=self.group_a,
                    new_group=self.group_b,
                    transfer_date=date(2026, 4, 16),
                    reason="Rollback",
                    user=self.director,
                )

        self.enrollment.refresh_from_db()
        self.old_tm.refresh_from_db()
        self.assertTrue(self.enrollment.is_active)
        self.assertEqual(self.old_tm.fee_amount, 260_000)
        self.assertFalse(Enrollment.objects.filter(group=self.group_b, student=self.student, is_active=True).exists())
        self.assertEqual(PaymentAllocation.objects.filter(payment=self.payment).count(), 1)
