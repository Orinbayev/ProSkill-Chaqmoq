from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse

from accounts.models import Center, User
from education.models import Attendance, Enrollment, Group, Payment, PaymentAllocation, TeacherIncome, TuitionMonth
from education.services.tuition import (
    effective_student_payable_amount,
    ensure_tuition_month,
    full_course_amount,
)
from education.views import sync_tuition_fee


class StudentPayableAmountTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Payable Center", slug="payable-center")
        self.director = User.objects.create_user(
            email="director@payable.test",
            password="testpass123",
            role="director",
            center=self.center,
            ism="Payable",
            familya="Director",
        )
        self.teacher = User.objects.create_user(
            email="teacher@payable.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Payable",
            familya="Teacher",
            oqituvchi_foizi=40,
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="Payable Group",
            oqituvchi=self.teacher,
            kurs_narxi=550_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )

        self.regular_student = User.objects.create_user(
            email="regular@payable.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Regular",
            familya="Student",
            telefon1="+998901000001",
        )
        self.discounted_student = User.objects.create_user(
            email="discounted@payable.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Discounted",
            familya="Student",
            telefon1="+998901000002",
        )
        self.teacher_share_student = User.objects.create_user(
            email="teacher-share@payable.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Teacher",
            familya="Share Student",
            telefon1="+998901000004",
        )

        self.regular_enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.regular_student,
            kurs_narhi=550_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        self.discounted_enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.discounted_student,
            kurs_narhi=550_000,
            student_payable_amount=300_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        self.teacher_share_enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.teacher_share_student,
            kurs_narhi=550_000,
            student_payable_amount=220_000,
            oqituvchi_foiz=40,
            is_active=True,
        )

        self.client.force_login(self.director)
        self.qarzdorlar_url = f"/{self.center.slug}{reverse('education:qarzdorlar_home')}"

    def test_effective_payable_amount_falls_back_to_full_course_amount_when_null(self):
        self.assertEqual(full_course_amount(self.regular_enrollment), 550_000)
        self.assertEqual(effective_student_payable_amount(self.regular_enrollment), 550_000)

    def test_ensure_tuition_month_uses_student_payable_amount_for_debt(self):
        tm = ensure_tuition_month(self.discounted_enrollment, self.discounted_enrollment.created_at.date().replace(day=1))

        self.assertEqual(tm.fee_amount, 300_000)
        self.assertEqual(full_course_amount(self.discounted_enrollment), 550_000)
        self.assertEqual(effective_student_payable_amount(self.discounted_enrollment), 300_000)

    def test_qarzdorlar_home_shows_discounted_debt_amount(self):
        response = self.client.get(self.qarzdorlar_url)

        self.assertEqual(response.status_code, 200)
        rows = {row["student"].email: row for row in response.context["page_obj"].object_list}
        self.assertEqual(rows[self.regular_student.email]["debt"], 550_000)
        self.assertEqual(rows[self.discounted_student.email]["debt"], 300_000)

    def test_qarzdorlar_home_shows_teacher_share_and_full_price_hint(self):
        response = self.client.get(self.qarzdorlar_url)

        self.assertEqual(response.status_code, 200)
        rows = {row["student"].email: row for row in response.context["page_obj"].object_list}
        teacher_share_row = rows[self.teacher_share_student.email]
        self.assertEqual(teacher_share_row["debt"], 220_000)
        self.assertTrue(teacher_share_row["has_teacher_share_only"])
        self.assertEqual(teacher_share_row["teacher_share_only_debt"], 220_000)
        self.assertEqual(teacher_share_row["teacher_share_only_full_total"], 550_000)
        self.assertEqual(teacher_share_row["payment_amount"], 220_000)
        self.assertEqual(teacher_share_row["payment_scope"], "teacher_share_only")
        self.assertEqual(teacher_share_row["teacher_share_only_payment_enrollment_id"], self.teacher_share_enrollment.id)

        html = response.content.decode("utf-8")
        self.assertIn("O'qituvchi haqqi:", html)
        self.assertIn("Umumiy narxi:", html)
        self.assertIn(f'data-enrollment-id="{self.teacher_share_enrollment.id}"', html)

    def test_qarzdorlar_home_renders_payment_date_input_in_modal(self):
        response = self.client.get(self.qarzdorlar_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="paid_date"')
        self.assertContains(response, 'type="date"')

    def test_teacher_income_still_uses_full_course_amount(self):
        attendance = Attendance.objects.create(
            group=self.group,
            student=self.discounted_student,
            center=self.center,
            date=self.discounted_enrollment.created_at.date(),
            status="present",
        )

        teacher_income = TeacherIncome.objects.get(attendance=attendance)

        self.assertEqual(teacher_income.total_amount, round(550_000 / 12))
        self.assertEqual(teacher_income.amount, round((550_000 / 12) * 0.4))

    def test_student_payable_amount_cannot_exceed_full_course_amount(self):
        extra_student = User.objects.create_user(
            email="invalid@payable.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Invalid",
            familya="Student",
            telefon1="+998901000003",
        )
        enrollment = Enrollment(
            center=self.center,
            group=self.group,
            student=extra_student,
            kurs_narhi=550_000,
            student_payable_amount=600_000,
            oqituvchi_foiz=40,
        )

        with self.assertRaises(ValidationError):
            enrollment.full_clean()

    def test_sync_tuition_fee_reuses_soft_deleted_current_month_record(self):
        current_month = self.discounted_enrollment.created_at.date().replace(day=1)
        tm = ensure_tuition_month(self.discounted_enrollment, current_month)
        tm.delete()

        sync_tuition_fee(self.discounted_enrollment, 280_000)

        self.assertEqual(
            self.discounted_enrollment.tuition_months.filter(month=current_month).count(),
            1,
        )
        tm.refresh_from_db()
        self.assertFalse(tm.is_deleted)
        self.assertEqual(tm.fee_amount, 280_000)

    def test_enrollment_edit_accepts_teacher_share_checkbox_value_one(self):
        edit_url = f"/{self.center.slug}{reverse('education:enrollment_edit', args=[self.regular_enrollment.id])}"

        response = self.client.post(edit_url, data={
            "ism": self.regular_student.ism,
            "familya": self.regular_student.familya,
            "email": self.regular_student.email,
            "group_id": self.group.id,
            "kurs_narhi": "550000",
            "oqituvchi_foiz": "40",
            "teacher_share_only": "1",
            "next": self.qarzdorlar_url,
            "month": "",
        })

        self.assertEqual(response.status_code, 302)
        self.regular_enrollment.refresh_from_db()
        self.assertEqual(self.regular_enrollment.student_payable_amount, 220_000)

    def test_enrollment_edit_can_disable_teacher_share_only(self):
        edit_url = f"/{self.center.slug}{reverse('education:enrollment_edit', args=[self.teacher_share_enrollment.id])}"

        response = self.client.post(edit_url, data={
            "ism": self.teacher_share_student.ism,
            "familya": self.teacher_share_student.familya,
            "email": self.teacher_share_student.email,
            "group_id": self.group.id,
            "kurs_narhi": "550000",
            "oqituvchi_foiz": "40",
            "student_payable_amount": "",
            "next": self.qarzdorlar_url,
            "month": "",
        })

        self.assertEqual(response.status_code, 302)
        self.teacher_share_enrollment.refresh_from_db()
        self.assertIsNone(self.teacher_share_enrollment.student_payable_amount)

    def test_enrollment_edit_renders_saved_teacher_share_checkbox_state(self):
        edit_url = f"/{self.center.slug}{reverse('education:enrollment_edit', args=[self.teacher_share_enrollment.id])}"

        response = self.client.get(edit_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="teacherShareOnly"')
        self.assertContains(response, 'id="teacherShareOnly" name="teacher_share_only" checked', html=False)

    def test_create_payment_uses_teacher_share_scope_amount_for_student_flow(self):
        pay_url = f"/{self.center.slug}{reverse('education:create_payment')}"
        month = self.teacher_share_enrollment.created_at.date().replace(day=1)
        tm = ensure_tuition_month(self.teacher_share_enrollment, month)

        response = self.client.post(pay_url, data={
            "student_id": self.teacher_share_student.id,
            "payment_scope": "teacher_share_only",
            "cash_amount": "220000",
            "card_amount": "0",
            "next": self.qarzdorlar_url,
        })

        self.assertEqual(response.status_code, 302)
        paid_total = PaymentAllocation.objects.filter(tuition_month=tm).aggregate(total=Sum("amount"))["total"] or 0
        self.assertEqual(int(paid_total), 220_000)
        self.assertEqual(TuitionMonth.objects.filter(enrollment=self.teacher_share_enrollment, month=month).count(), 1)

    def test_create_payment_uses_selected_paid_date_for_student_flow(self):
        pay_url = f"/{self.center.slug}{reverse('education:create_payment')}"
        selected_date = self.regular_enrollment.created_at.date().replace(day=5)

        response = self.client.post(pay_url, data={
            "student_id": self.regular_student.id,
            "cash_amount": "100000",
            "card_amount": "0",
            "paid_date": selected_date.isoformat(),
            "next": self.qarzdorlar_url,
        })

        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.filter(student=self.regular_student).latest("id")
        self.assertEqual(payment.paid_date, selected_date)

    def test_create_payment_uses_selected_paid_date_for_enrollment_flow(self):
        pay_url = f"/{self.center.slug}{reverse('education:create_payment')}"
        selected_date = self.teacher_share_enrollment.created_at.date().replace(day=7)

        response = self.client.post(pay_url, data={
            "enrollment_id": self.teacher_share_enrollment.id,
            "cash_amount": "50000",
            "card_amount": "0",
            "paid_date": selected_date.isoformat(),
            "next": self.qarzdorlar_url,
        })

        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.filter(enrollment=self.teacher_share_enrollment).latest("id")
        self.assertEqual(payment.paid_date, selected_date)
