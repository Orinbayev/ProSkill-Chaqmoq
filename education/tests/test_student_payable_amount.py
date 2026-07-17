import calendar
import json

from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from freezegun import freeze_time

from datetime import date, timedelta

from accounts.models import Center, User
from education.models import (
    Attendance,
    Category,
    Enrollment,
    Group,
    GroupSchedule,
    Payment,
    PaymentAllocation,
    StudentGroupHistory,
    TeacherIncome,
    TuitionMonth,
)
from education.services.historical_finance_service import HistoricalFinanceService
from education.services.lesson_planning import calculate_lessons
from education.services.tuition import (
    effective_student_payable_amount,
    ensure_tuition_month,
    format_money,
    full_course_amount,
    pattern_lessons_between,
    round_money_to_thousand,
    tuition_month_preview,
)
from education.views import sync_tuition_fee

from core.test_utils import activate_center


class StudentPayableAmountTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Payable Center", slug="payable-center")
        activate_center(self.center)
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
        history_start = self.regular_enrollment.created_at.date().replace(day=1) - timedelta(days=30)
        for student in (
            self.regular_student,
            self.discounted_student,
            self.teacher_share_student,
        ):
            StudentGroupHistory.objects.create(
                student=student,
                group=self.group,
                center=self.center,
                start_date=history_start,
                kurs_narxi=550_000,
                oqituvchi_foiz=40,
            )

        self.client.force_login(self.director)
        self.qarzdorlar_url = f"/{self.center.slug}{reverse('education:qarzdorlar_home')}"
        self.month_preview_url = f"/{self.center.slug}{reverse('education:month_preview')}"

    def test_effective_payable_amount_falls_back_to_full_course_amount_when_null(self):
        self.assertEqual(full_course_amount(self.regular_enrollment), 550_000)
        self.assertEqual(effective_student_payable_amount(self.regular_enrollment), 550_000)

    def test_ensure_tuition_month_uses_student_payable_amount_for_debt(self):
        # Prorated tuition yangilanishidan so'ng: ensure_tuition_month partial oylar uchun
        # fee ni expected_lessons × per_lesson qilib qo'yadi. Bu test chegirma
        # effective_student_payable_amount dan olinishini tekshiradi, shuning uchun
        # o'quvchini "to'liq oy" holatiga keltirish uchun StudentGroupHistory'ni
        # o'tmishdagi sanaga qo'yamiz.
        month = self.discounted_enrollment.created_at.date().replace(day=1)
        StudentGroupHistory.objects.create(
            student=self.discounted_student,
            group=self.group,
            center=self.center,
            start_date=month - timedelta(days=30),
            kurs_narxi=550_000,
            oqituvchi_foiz=40,
        )

        tm = ensure_tuition_month(self.discounted_enrollment, month)

        self.assertEqual(tm.fee_amount, 300_000)
        self.assertEqual(full_course_amount(self.discounted_enrollment), 550_000)
        self.assertEqual(effective_student_payable_amount(self.discounted_enrollment), 300_000)

    def test_qarzdorlar_home_shows_discounted_debt_amount(self):
        response = self.client.get(self.qarzdorlar_url)

        self.assertEqual(response.status_code, 200)
        rows = {row["student"].email: row for row in response.context["page_obj"].object_list}
        self.assertEqual(rows[self.regular_student.email]["debt"], 550_000)
        self.assertEqual(rows[self.discounted_student.email]["debt"], 300_000)

    def test_qarzdorlar_home_hides_free_student_from_debtors(self):
        free_student = User.objects.create_user(
            email="free@payable.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Free",
            familya="Student",
            telefon1="+998901000099",
        )
        free_enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=free_student,
            kurs_narhi=550_000,
            student_payable_amount=0,
            oqituvchi_foiz=40,
            is_active=True,
        )
        ensure_tuition_month(
            free_enrollment,
            free_enrollment.created_at.date().replace(day=1),
        )

        response = self.client.get(self.qarzdorlar_url)

        self.assertEqual(response.status_code, 200)
        rows = {row["student"].email: row for row in response.context["page_obj"].object_list}
        self.assertNotIn(free_student.email, rows)

    def test_partial_payment_creates_only_real_remaining_debt(self):
        month = self.regular_enrollment.created_at.date().replace(day=1)
        tm = ensure_tuition_month(self.regular_enrollment, month)
        payment = Payment.objects.create(
            center=self.center,
            enrollment=self.regular_enrollment,
            student=self.regular_student,
            group=self.group,
            payment_type="cash",
            cash_amount=200_000,
            paid_date=month.replace(day=5),
            created_by=self.director,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=payment,
            tuition_month=tm,
            amount=200_000,
        )

        response = self.client.get(self.qarzdorlar_url)

        self.assertEqual(response.status_code, 200)
        rows = {row["student"].email: row for row in response.context["page_obj"].object_list}
        self.assertEqual(rows[self.regular_student.email]["debt"], 350_000)

    def test_discount_fully_paid_student_is_not_listed_as_debtor(self):
        month = self.discounted_enrollment.created_at.date().replace(day=1)
        tm = ensure_tuition_month(self.discounted_enrollment, month)
        payment = Payment.objects.create(
            center=self.center,
            enrollment=self.discounted_enrollment,
            student=self.discounted_student,
            group=self.group,
            payment_type="cash",
            cash_amount=300_000,
            paid_date=month.replace(day=6),
            created_by=self.director,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=payment,
            tuition_month=tm,
            amount=300_000,
        )

        response = self.client.get(self.qarzdorlar_url)

        self.assertEqual(response.status_code, 200)
        rows = {row["student"].email: row for row in response.context["page_obj"].object_list}
        self.assertNotIn(self.discounted_student.email, rows)

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
        self.assertIn("Umumiy:", html)
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
        StudentGroupHistory.objects.create(
            student=self.discounted_student,
            group=self.group,
            center=self.center,
            start_date=current_month - timedelta(days=30),
            kurs_narxi=550_000,
            oqituvchi_foiz=40,
        )
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

    def test_enrollment_edit_renders_start_date_pattern_and_preview_controls(self):
        edit_url = f"/{self.center.slug}{reverse('education:enrollment_edit', args=[self.regular_enrollment.id])}"

        response = self.client.get(edit_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="date"')
        self.assertContains(response, 'name="lesson_pattern"')
        self.assertContains(response, 'id="billingPreview"')
        self.assertContains(response, 'id="groupSelect"')
        self.assertNotContains(response, 'id="subjectSelect"')
        self.assertContains(response, 'id="remainingLessonsInput"')
        self.assertContains(response, "O'qish davri")
        self.assertContains(response, "Tugash sanasi")
        self.assertContains(response, "Oxirgi dars sanasi")
        self.assertContains(response, "Kurs narxi")
        self.assertContains(response, "Seshanba")
        self.assertContains(response, "Dushanba")
        self.assertNotContains(response, "Guruh jadvali")
        self.assertNotContains(response, "Guruhning real dars jadvali")
        self.assertContains(response, "Toq kunlari")
        self.assertContains(response, "Juft kunlari")

    @freeze_time("2026-04-01")
    def test_enrollment_edit_preview_endpoint_respects_selected_pattern_and_returns_lesson_plan(self):
        current_month = date(2026, 4, 1)
        start_date = date(2026, 4, 24)
        self.regular_enrollment.joined_at = start_date
        self.regular_enrollment.lesson_pattern = Enrollment.LESSON_PATTERN_GROUP
        self.regular_enrollment.monthly_lessons = self.group.oy_dars_soni
        self.regular_enrollment.save(update_fields=["joined_at", "lesson_pattern", "monthly_lessons"])

        edit_url = f"/{self.center.slug}{reverse('education:enrollment_edit', args=[self.regular_enrollment.id])}"
        page_response = self.client.get(edit_url)
        self.assertEqual(page_response.status_code, 200)
        self.assertEqual(page_response.context["selected_lesson_pattern"], Enrollment.LESSON_PATTERN_ODD)
        self.assertNotContains(page_response, 'value="group"', html=False)

        preview_response = self.client.get(
            edit_url,
            {
                "preview": "1",
                "joined_at": start_date.isoformat(),
                "lesson_pattern": "even",
                "group_id": self.group.id,
                "monthly_lessons": self.group.oy_dars_soni,
                "kurs_narhi": self.regular_enrollment.kurs_narhi,
                "oqituvchi_foiz": self.regular_enrollment.oqituvchi_foiz,
                "student_payable_amount": "",
                "teacher_share_only": "0",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(preview_response.status_code, 200)
        preview_payload = preview_response.json()["preview"]
        lesson_plan_payload = preview_response.json()["lesson_plan"]
        month_end = current_month.replace(
            day=calendar.monthrange(current_month.year, current_month.month)[1]
        )
        self.assertEqual(preview_payload["lesson_pattern"], "even")
        self.assertEqual(preview_payload["lesson_pattern_label"], "Juft kunlari")
        self.assertEqual(preview_payload["lesson_pattern_hint"], "Seshanba • Payshanba • Shanba")
        self.assertEqual(preview_payload["counted_days_summary"], "Hisoblangan kunlar: Sesh, Pay, Shan")
        self.assertEqual(
            preview_payload["lesson_count"],
            pattern_lessons_between(start_date, month_end, "even"),
        )
        self.assertEqual(lesson_plan_payload["remaining_lessons"], preview_payload["lesson_count"])
        self.assertTrue(lesson_plan_payload["last_lesson_date"])

    def test_enrollment_edit_only_lists_student_groups(self):
        math = Category.objects.create(name="Matematika", center=self.center)
        english = Category.objects.create(name="English", center=self.center)
        self.group.category_obj = math
        self.group.save(update_fields=["category_obj"])

        second_group = Group.objects.create(
            center=self.center,
            category_obj=english,
            nom="English A1",
            oqituvchi=self.teacher,
            kurs_narxi=480_000,
            oqituvchi_foiz=35,
            oy_dars_soni=12,
        )
        Group.objects.create(
            center=self.center,
            category_obj=math,
            nom="Matematika Tashqi",
            oqituvchi=self.teacher,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        Enrollment.objects.create(
            center=self.center,
            group=second_group,
            student=self.regular_student,
            kurs_narhi=480_000,
            oqituvchi_foiz=35,
            is_active=True,
        )

        edit_url = f"/{self.center.slug}{reverse('education:enrollment_edit', args=[self.regular_enrollment.id])}"
        response = self.client.get(edit_url)

        self.assertEqual(response.status_code, 200)
        group_ids = {item["group_id"] for item in response.context["groups"]}
        self.assertEqual(group_ids, {self.group.id, second_group.id})
        self.assertNotContains(response, 'id="subjectSelect"')
        self.assertContains(response, "English A1")
        self.assertNotContains(response, "Matematika Tashqi")

    def test_calculate_lessons_api_returns_manual_last_lesson_date(self):
        start_date = timezone.localdate()
        self.regular_enrollment.joined_at = start_date
        self.regular_enrollment.lesson_pattern = Enrollment.LESSON_PATTERN_ODD
        self.regular_enrollment.monthly_lessons = self.group.oy_dars_soni
        self.regular_enrollment.save(update_fields=["joined_at", "lesson_pattern", "monthly_lessons"])

        response = self.client.post(
            f"/{self.center.slug}{reverse('education:calculate_lessons_api')}",
            data=json.dumps(
                {
                    "enrollment_id": self.regular_enrollment.id,
                    "group_id": self.group.id,
                    "joined_at": start_date.isoformat(),
                    "lesson_pattern": "odd",
                    "remaining_lessons": 5,
                    "monthly_lessons": self.group.oy_dars_soni,
                    "kurs_narhi": self.regular_enrollment.kurs_narhi,
                    "oqituvchi_foiz": self.regular_enrollment.oqituvchi_foiz,
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertIn("data", payload)
        expected_plan = calculate_lessons(
            start_date=start_date,
            remaining_lessons=5,
            pattern="odd",
            from_date=timezone.localdate(),
            group=self.group,
        )
        self.assertEqual(payload["lesson_plan"]["remaining_lessons"], 5)
        self.assertEqual(payload["lesson_plan"]["last_lesson_date"], expected_plan["last_lesson_date"].isoformat())
        self.assertEqual(payload["preview"]["lesson_pattern"], "odd")
        self.assertEqual(payload["preview"]["lesson_count"], 5)
        expected_lesson_price = round(550_000 / self.group.oy_dars_soni)
        expected_debt = round(5 * (550_000 / self.group.oy_dars_soni))
        self.assertEqual(payload["preview"]["per_lesson_amount"], expected_lesson_price)
        self.assertEqual(payload["preview"]["fee_amount"], expected_debt)
        expected_teacher = ((550_000 * 40 // 100) // self.group.oy_dars_soni) * 5
        self.assertEqual(payload["preview"]["teacher_share"], expected_teacher)
        self.assertEqual(
            payload["preview"]["center_share"],
            payload["preview"]["fee_amount"] - payload["preview"]["teacher_share"],
        )
        self.assertEqual(payload["data"]["total_lessons"], payload["preview"]["lesson_count"])
        self.assertEqual(payload["data"]["lesson_price"], payload["preview"]["per_lesson_amount"])
        self.assertEqual(payload["data"]["total_debt"], payload["preview"]["fee_amount"])
        self.assertEqual(payload["data"]["teacher_share"], payload["preview"]["teacher_share"])
        self.assertEqual(payload["data"]["center_share"], payload["preview"]["center_share"])
        self.assertEqual(payload["data"]["end_date"], payload["preview"]["period_end_date"])

    def test_calculate_lessons_api_returns_json_error_for_invalid_input(self):
        response = self.client.post(
            f"/{self.center.slug}{reverse('education:calculate_lessons_api')}",
            data=json.dumps(
                {
                    "enrollment_id": self.regular_enrollment.id,
                    "group_id": "",
                    "joined_at": timezone.localdate().isoformat(),
                    "lesson_pattern": "not-a-pattern",
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("application/json", response["Content-Type"])
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertIn("error", payload)
        self.assertNotIn("<!doctype", response.content.decode().lower())

    @freeze_time("2026-03-01")
    def test_calculate_lessons_api_preserves_selected_start_date_with_period_end(self):
        start_date = date(2026, 3, 14)
        response = self.client.post(
            f"/{self.center.slug}{reverse('education:calculate_lessons_api')}",
            data=json.dumps(
                {
                    "enrollment_id": self.regular_enrollment.id,
                    "group_id": self.group.id,
                    "joined_at": start_date.isoformat(),
                    "period_end_date": "2026-03-31",
                    "lesson_pattern": "odd",
                    "monthly_lessons": self.group.oy_dars_soni,
                    "kurs_narhi": self.regular_enrollment.kurs_narhi,
                    "oqituvchi_foiz": self.regular_enrollment.oqituvchi_foiz,
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["preview"]["start_date"], "2026-03-14")
        self.assertEqual(payload["data"]["end_date"], "2026-03-31")
        self.assertEqual(payload["data"]["lesson_dates"], [16, 18, 20, 23, 25, 27, 30])

    def test_calculate_lessons_api_root_url_returns_success_data_contract(self):
        start_date = timezone.localdate()
        response = self.client.post(
            "/api/calculate-lessons/",
            data=json.dumps(
                {
                    "enrollment_id": self.regular_enrollment.id,
                    "group_id": self.group.id,
                    "joined_at": start_date.isoformat(),
                    "lesson_pattern": "daily",
                    "remaining_lessons": 3,
                    "monthly_lessons": self.group.oy_dars_soni,
                    "kurs_narhi": self.regular_enrollment.kurs_narhi,
                    "oqituvchi_foiz": self.regular_enrollment.oqituvchi_foiz,
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["total_lessons"], 3)
        expected_lesson_price = round(550_000 / self.group.oy_dars_soni)
        self.assertEqual(payload["data"]["lesson_price"], expected_lesson_price)
        self.assertEqual(payload["data"]["total_debt"], round(3 * (550_000 / self.group.oy_dars_soni)))

    def test_calculate_lessons_api_caps_student_debt_and_pays_teacher_by_real_lessons(self):
        start_date = timezone.localdate()
        response = self.client.post(
            f"/{self.center.slug}{reverse('education:calculate_lessons_api')}",
            data=json.dumps(
                {
                    "enrollment_id": self.regular_enrollment.id,
                    "group_id": self.group.id,
                    "joined_at": start_date.isoformat(),
                    "lesson_pattern": "daily",
                    "remaining_lessons": 13,
                    "monthly_lessons": 12,
                    "kurs_narhi": 500_000,
                    "oqituvchi_foiz": 50,
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total_lessons"], 13)
        self.assertEqual(data["lesson_price"], 41_667)
        self.assertEqual(data["total_debt"], 500_000)
        self.assertEqual(data["teacher_share"], 270_829)
        self.assertEqual(data["center_share"], 229_171)

    def test_qarzdorlar_debt_uses_same_capped_billing_as_profile(self):
        current_month = timezone.localdate().replace(day=1)
        self.regular_enrollment.joined_at = current_month
        self.regular_enrollment.lesson_pattern = Enrollment.LESSON_PATTERN_DAILY
        self.regular_enrollment.monthly_lessons = 12
        self.regular_enrollment.kurs_narhi = 500_000
        self.regular_enrollment.oqituvchi_foiz = 50
        self.regular_enrollment.save(
            update_fields=["joined_at", "lesson_pattern", "monthly_lessons", "kurs_narhi", "oqituvchi_foiz"]
        )
        StudentGroupHistory.objects.update_or_create(
            student=self.regular_student,
            group=self.group,
            end_date__isnull=True,
            defaults={
                "center": self.center,
                "start_date": current_month,
                "kurs_narxi": 500_000,
                "oqituvchi_foiz": 50,
            },
        )
        ensure_tuition_month(self.regular_enrollment, current_month)

        profile_response = self.client.post(
            f"/{self.center.slug}{reverse('education:calculate_lessons_api')}",
            data=json.dumps(
                {
                    "enrollment_id": self.regular_enrollment.id,
                    "group_id": self.group.id,
                    "joined_at": current_month.isoformat(),
                    "lesson_pattern": "daily",
                    "monthly_lessons": 12,
                    "kurs_narhi": 500_000,
                    "oqituvchi_foiz": 50,
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        qarzdorlar_response = self.client.get(self.qarzdorlar_url)

        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(qarzdorlar_response.status_code, 200)
        profile_debt = profile_response.json()["data"]["total_debt"]
        rows = {row["student"].email: row for row in qarzdorlar_response.context["page_obj"].object_list}
        self.assertEqual(profile_debt, 500_000)
        self.assertEqual(rows[self.regular_student.email]["debt"], profile_debt)

    def test_calculate_lessons_api_debt_uses_full_course_price_not_teacher_share_only_amount(self):
        start_date = timezone.localdate()
        self.teacher_share_enrollment.joined_at = start_date
        self.teacher_share_enrollment.lesson_pattern = Enrollment.LESSON_PATTERN_ODD
        self.teacher_share_enrollment.monthly_lessons = self.group.oy_dars_soni
        self.teacher_share_enrollment.save(update_fields=["joined_at", "lesson_pattern", "monthly_lessons"])

        response = self.client.post(
            f"/{self.center.slug}{reverse('education:calculate_lessons_api')}",
            data=json.dumps(
                {
                    "enrollment_id": self.teacher_share_enrollment.id,
                    "group_id": self.group.id,
                    "joined_at": start_date.isoformat(),
                    "lesson_pattern": "odd",
                    "remaining_lessons": 6,
                    "monthly_lessons": self.group.oy_dars_soni,
                    "kurs_narhi": self.teacher_share_enrollment.kurs_narhi,
                    "oqituvchi_foiz": self.teacher_share_enrollment.oqituvchi_foiz,
                    "student_payable_amount": self.teacher_share_enrollment.student_payable_amount,
                    "teacher_share_only": "1",
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        preview = response.json()["preview"]
        expected_debt = round(6 * (550_000 / self.group.oy_dars_soni))
        self.assertEqual(preview["lesson_count"], 6)
        self.assertEqual(preview["fee_amount"], expected_debt)
        self.assertNotEqual(preview["fee_amount"], self.teacher_share_enrollment.student_payable_amount)
        expected_teacher = ((550_000 * 40 // 100) // self.group.oy_dars_soni) * 6
        self.assertEqual(preview["teacher_share"], expected_teacher)
        self.assertEqual(preview["center_share"], expected_debt - preview["teacher_share"])

    def test_enrollment_edit_post_saves_manual_remaining_lessons_and_last_date(self):
        start_date = timezone.localdate()
        edit_url = f"/{self.center.slug}{reverse('education:enrollment_edit', args=[self.regular_enrollment.id])}"

        response = self.client.post(
            edit_url,
            data={
                "ism": self.regular_student.ism,
                "familya": self.regular_student.familya,
                "email": self.regular_student.email,
                "active_enrollment_id": self.regular_enrollment.id,
                "group_id": self.group.id,
                "joined_at": start_date.isoformat(),
                "lesson_pattern": "odd",
                "remaining_lessons_override": "5",
                "monthly_lessons": str(self.group.oy_dars_soni),
                "kurs_narhi": "550000",
                "oqituvchi_foiz": "40",
                "next": self.qarzdorlar_url,
                "month": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.regular_enrollment.refresh_from_db()
        expected_plan = calculate_lessons(
            start_date=self.regular_enrollment.joined_at,
            remaining_lessons=5,
            pattern=self.regular_enrollment.lesson_pattern,
            from_date=timezone.localdate(),
            group=self.group,
        )
        self.assertEqual(self.regular_enrollment.remaining_lessons_override, 5)
        self.assertEqual(self.regular_enrollment.last_lesson_date, expected_plan["last_lesson_date"])
        tm = TuitionMonth.objects.get(
            enrollment=self.regular_enrollment,
            month=start_date.replace(day=1),
        )
        self.assertEqual(tm.fee_amount, round(5 * (550_000 / self.group.oy_dars_soni)))

    def test_add_student_to_group_uses_start_date_pattern_and_creates_prorated_snapshot(self):
        add_url = f"/{self.center.slug}{reverse('education:add_student_to_group', args=[self.group.id])}"
        page_response = self.client.get(add_url)
        self.assertEqual(page_response.status_code, 200)
        # Redesigned search-and-add dashboard layout GET loads successfully
        pass

        student = User.objects.create_user(
            email="ajax-pattern@payable.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Ajax",
            familya="Pattern",
            telefon1="+998901000088",
        )
        current_month = date(2026, 4, 1)
        start_date = date(2026, 4, 25)
        month_end = current_month.replace(
            day=calendar.monthrange(current_month.year, current_month.month)[1]
        )
        expected_lessons = pattern_lessons_between(start_date, month_end, "odd")
        expected_fee = round((self.group.kurs_narxi * expected_lessons) / self.group.oy_dars_soni)

        preview_response = self.client.post(
            f"/{self.center.slug}{reverse('education:calculate_lessons_api')}",
            data=json.dumps(
                {
                    "group_id": self.group.id,
                    "joined_at": start_date.isoformat(),
                    "lesson_pattern": "odd",
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(preview_response.status_code, 200)
        preview_payload = preview_response.json()["preview"]
        self.assertEqual(preview_payload["lesson_count"], expected_lessons)
        self.assertEqual(preview_payload["fee_amount"], expected_fee)
        self.assertEqual(preview_payload["lesson_pattern_label"], "Toq kunlari")
        self.assertEqual(preview_payload["lesson_pattern_hint"], "Dushanba • Chorshanba • Juma")
        self.assertEqual(preview_payload["counted_days_summary"], "Hisoblangan kunlar: Dush, Chor, Jum")

        response = self.client.post(
            add_url,
            data=json.dumps({
                "student_id": student.id,
                "start_date": start_date.isoformat(),
                "lesson_pattern": "odd",
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        enrollment = Enrollment.objects.get(student=student, group=self.group)
        self.assertEqual(enrollment.joined_at, start_date)
        self.assertEqual(enrollment.lesson_pattern, "odd")
        self.assertEqual(payload["preview"]["lesson_count"], preview_payload["lesson_count"])
        self.assertEqual(payload["preview"]["fee_amount"], preview_payload["fee_amount"])
        self.assertEqual(payload["preview"]["lesson_pattern_label"], preview_payload["lesson_pattern_label"])
        self.assertEqual(payload["preview"]["counted_days_summary"], preview_payload["counted_days_summary"])
        tm = TuitionMonth.objects.get(enrollment=enrollment, month=current_month)
        self.assertEqual(tm.fee_amount, expected_fee)


    def test_qarzdorlar_rows_reuse_same_preview_lesson_count_and_label(self):
        current_month = self.regular_enrollment.created_at.date().replace(day=1)
        self.regular_enrollment.joined_at = current_month
        self.regular_enrollment.lesson_pattern = "odd"
        self.regular_enrollment.monthly_lessons = self.group.oy_dars_soni
        self.regular_enrollment.save(update_fields=["joined_at", "lesson_pattern", "monthly_lessons"])
        ensure_tuition_month(self.regular_enrollment, current_month)

        response = self.client.get(self.qarzdorlar_url)

        self.assertEqual(response.status_code, 200)
        rows = {row["student"].email: row for row in response.context["page_obj"].object_list}
        preview = tuition_month_preview(self.regular_enrollment, current_month)
        self.assertEqual(rows[self.regular_student.email]["lesson_count"], preview["lesson_count"])
        self.assertEqual(rows[self.regular_student.email]["lesson_pattern_label"], preview["lesson_pattern_label"])

    def test_qarzdorlar_filter_uses_auto_detected_lesson_pattern_counts(self):
        odd_student = User.objects.create_user(
            email="odd-filter@payable.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Pattern",
            familya="Filter Odd",
            telefon1="+998901000065",
        )
        even_student = User.objects.create_user(
            email="even-filter@payable.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Pattern",
            familya="Filter Even",
            telefon1="+998901000066",
        )
        odd_enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=odd_student,
            kurs_narhi=550_000,
            oqituvchi_foiz=40,
            joined_at=date(2026, 4, 24),
            lesson_pattern=Enrollment.LESSON_PATTERN_GROUP,
            is_active=True,
        )
        even_enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=even_student,
            kurs_narhi=550_000,
            oqituvchi_foiz=40,
            joined_at=date(2026, 4, 25),
            lesson_pattern=Enrollment.LESSON_PATTERN_GROUP,
            is_active=True,
        )
        odd_enrollment.monthly_lessons = self.group.oy_dars_soni
        odd_enrollment.save(update_fields=["monthly_lessons"])
        even_enrollment.monthly_lessons = self.group.oy_dars_soni
        even_enrollment.save(update_fields=["monthly_lessons"])
        ensure_tuition_month(odd_enrollment, date(2026, 4, 1))
        ensure_tuition_month(even_enrollment, date(2026, 4, 1))

        response = self.client.get(self.qarzdorlar_url, {"lesson_pattern_filter": "odd", "q": "Pattern"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_lesson_pattern_filter"], "odd")
        self.assertEqual(response.context["lesson_pattern_filter_counts"]["all"], 2)
        self.assertEqual(response.context["lesson_pattern_filter_counts"]["odd"], 1)
        self.assertEqual(response.context["lesson_pattern_filter_counts"]["even"], 1)
        rows = {row["student"].email: row for row in response.context["page_obj"].object_list}
        self.assertIn(odd_student.email, rows)
        self.assertNotIn(even_student.email, rows)

    def test_qarzdorlar_filter_keeps_multi_group_student_visible_in_both_odd_and_even_filters(self):
        second_group = Group.objects.create(
            center=self.center,
            nom="Pattern Second Group",
            oqituvchi=self.teacher,
            kurs_narxi=600_000,
            oqituvchi_foiz=35,
            oy_dars_soni=12,
        )
        dual_student = User.objects.create_user(
            email="dual-pattern@payable.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Dual",
            familya="Pattern",
            telefon1="+998901000067",
        )
        odd_enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=dual_student,
            kurs_narhi=550_000,
            oqituvchi_foiz=40,
            joined_at=date(2026, 4, 24),
            lesson_pattern=Enrollment.LESSON_PATTERN_GROUP,
            is_active=True,
        )
        even_enrollment = Enrollment.objects.create(
            center=self.center,
            group=second_group,
            student=dual_student,
            kurs_narhi=600_000,
            oqituvchi_foiz=35,
            joined_at=date(2026, 4, 25),
            lesson_pattern=Enrollment.LESSON_PATTERN_GROUP,
            is_active=True,
        )
        odd_enrollment.monthly_lessons = self.group.oy_dars_soni
        odd_enrollment.save(update_fields=["monthly_lessons"])
        even_enrollment.monthly_lessons = second_group.oy_dars_soni
        even_enrollment.save(update_fields=["monthly_lessons"])
        ensure_tuition_month(odd_enrollment, date(2026, 4, 1))
        ensure_tuition_month(even_enrollment, date(2026, 4, 1))

        odd_response = self.client.get(self.qarzdorlar_url, {"lesson_pattern_filter": "odd", "q": "Dual"})
        even_response = self.client.get(self.qarzdorlar_url, {"lesson_pattern_filter": "even", "q": "Dual"})

        self.assertEqual(odd_response.status_code, 200)
        self.assertEqual(even_response.status_code, 200)
        odd_rows = {row["student"].email: row for row in odd_response.context["page_obj"].object_list}
        even_rows = {row["student"].email: row for row in even_response.context["page_obj"].object_list}
        self.assertIn(dual_student.email, odd_rows)
        self.assertIn(dual_student.email, even_rows)

    def test_student_detail_context_contains_group_financial_cards_and_totals(self):
        second_group = Group.objects.create(
            center=self.center,
            nom="Student Detail Group",
            oqituvchi=self.teacher,
            kurs_narxi=640_000,
            oqituvchi_foiz=35,
            oy_dars_soni=12,
        )
        second_enrollment = Enrollment.objects.create(
            center=self.center,
            group=second_group,
            student=self.regular_student,
            kurs_narhi=620_000,
            oqituvchi_foiz=35,
            joined_at=date(2026, 4, 25),
            lesson_pattern=Enrollment.LESSON_PATTERN_GROUP,
            is_active=True,
        )
        self.regular_enrollment.joined_at = date(2026, 4, 24)
        self.regular_enrollment.lesson_pattern = Enrollment.LESSON_PATTERN_GROUP
        self.regular_enrollment.monthly_lessons = 12
        self.regular_enrollment.save(update_fields=["joined_at", "lesson_pattern", "monthly_lessons"])
        StudentGroupHistory.objects.filter(
            student=self.regular_student,
            group=self.group,
            end_date__isnull=True,
        ).update(start_date=date(2026, 4, 24))
        second_enrollment.monthly_lessons = 12
        second_enrollment.save(update_fields=["monthly_lessons"])
        ensure_tuition_month(self.regular_enrollment, date(2026, 4, 1))
        ensure_tuition_month(second_enrollment, date(2026, 4, 1))

        response = self.client.get(
            f"/{self.center.slug}{reverse('education:student_detail', args=[self.regular_student.id])}",
            {"month": "2026-04"},
        )

        self.assertEqual(response.status_code, 200)
        financials = response.context["student_group_financials"]
        self.assertEqual(len(financials["cards"]), 2)
        self.assertEqual(financials["cards"][0]["lesson_pattern_label"], "Toq kunlari")
        self.assertEqual(financials["cards"][1]["lesson_pattern_label"], "Juft kunlari")
        self.assertGreater(financials["totals"]["debt_amount"], 0)
        self.assertContains(response, "O'quvchi guruhlari")
        self.assertContains(response, "Student Detail Group")

    def test_student_detail_hides_group_financials_for_teacher(self):
        self.client.force_login(self.teacher)

        response = self.client.get(
            f"/{self.center.slug}{reverse('education:student_detail', args=[self.regular_student.id])}",
            {"month": "2026-04"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_view_student_group_financials"])
        self.assertIsNone(response.context["student_group_financials"])
        self.assertNotContains(response, "O'quvchi guruhlari")
        self.assertNotContains(response, "Jami hisob-kitob")
        self.assertContains(response, "Davomat va Chaqmoqlar")

    def test_money_helpers_round_to_thousand_for_ui(self):
        self.assertEqual(round_money_to_thousand(126667), 127000)
        self.assertEqual(round_money_to_thousand(206666), 207000)
        self.assertEqual(format_money(41667), "42 000 so'm")

    @freeze_time("2026-04-01")
    def test_month_preview_is_read_only_and_shows_reconciled_delta(self):
        preview_month = date(2026, 4, 1)
        for weekday in (1, 3, 5):
            GroupSchedule.objects.get_or_create(
                center=self.center,
                group=self.group,
                weekday=weekday,
                start_time="10:00",
            )

        preview_student = User.objects.create_user(
            email="preview@payable.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Preview",
            familya="Student",
            telefon1="+998901000077",
        )
        preview_enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=preview_student,
            kurs_narhi=550_000,
            student_payable_amount=330_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        StudentGroupHistory.objects.create(
            student=preview_student,
            group=self.group,
            center=self.center,
            start_date=date(2026, 4, 18),
            kurs_narxi=550_000,
            oqituvchi_foiz=40,
        )
        tm = TuitionMonth.objects.create(
            center=self.center,
            enrollment=preview_enrollment,
            month=preview_month,
            fee_amount=330_000,
        )
        for day, status in ((20, "present"), (22, "present"), (24, "present"), (27, "present"), (29, "absent_unexcused")):
            Attendance.objects.create(
                center=self.center,
                group=self.group,
                student=preview_student,
                teacher=self.teacher,
                date=date(2026, 4, day),
                status=status,
            )

        response = self.client.get(
            self.month_preview_url,
            {"month": "2026-04", "group": self.group.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TuitionMonth.objects.filter(pk=tm.pk).count(), 1)
        tm.refresh_from_db()
        self.assertEqual(tm.fee_amount, 330_000)

        preview_row = next(
            row
            for row in response.context["rows"]
            if row["student"].email == preview_student.email
        )
        self.assertEqual(preview_row["expected_lessons"], 6)
        self.assertEqual(preview_row["billable_lessons"], 5)
        self.assertEqual(preview_row["prorated_fee"], round(6 * (330_000 / 12)))
        self.assertEqual(preview_row["reconciled_fee"], round(5 * (330_000 / 12)))
        self.assertEqual(preview_row["current_fee"], 330_000)
        self.assertEqual(
            preview_row["delta"],
            round(5 * (330_000 / 12)) - 330_000,
        )

    def test_close_month_reconciles_mid_month_discounted_student_debt(self):
        preview_month = date(2026, 4, 1)
        for weekday in (1, 3, 5):
            GroupSchedule.objects.get_or_create(
                center=self.center,
                group=self.group,
                weekday=weekday,
                start_time="10:00",
            )

        student = User.objects.create_user(
            email="close-mid@payable.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Close",
            familya="Mid",
            telefon1="+998901000078",
        )
        enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=student,
            kurs_narhi=550_000,
            student_payable_amount=330_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        StudentGroupHistory.objects.create(
            student=student,
            group=self.group,
            center=self.center,
            start_date=date(2026, 4, 18),
            kurs_narxi=550_000,
            oqituvchi_foiz=40,
        )
        tm = TuitionMonth.objects.create(
            center=self.center,
            enrollment=enrollment,
            month=preview_month,
            fee_amount=330_000,
        )
        for day, status in ((20, "present"), (22, "present"), (24, "present"), (27, "present"), (29, "absent_unexcused")):
            Attendance.objects.create(
                center=self.center,
                group=self.group,
                student=student,
                teacher=self.teacher,
                date=date(2026, 4, day),
                status=status,
            )
        payment = Payment.objects.create(
            center=self.center,
            enrollment=enrollment,
            student=student,
            group=self.group,
            payment_type="cash",
            cash_amount=100_000,
            paid_date=date(2026, 4, 25),
            created_by=self.director,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=payment,
            tuition_month=tm,
            amount=100_000,
        )

        HistoricalFinanceService.close_month(
            self.center,
            preview_month.year,
            preview_month.month,
            self.director,
        )

        tm.refresh_from_db()
        expected_fee = round(5 * (330_000 / 12))
        self.assertEqual(tm.fee_amount, expected_fee)

        response = self.client.get(
            self.qarzdorlar_url,
            {"date_from": "2026-04-01", "date_to": "2026-04-30"},
        )
        rows = {row["student"].email: row for row in response.context["page_obj"].object_list}
        self.assertEqual(rows[student.email]["debt"], expected_fee - 100_000)

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
            "month_for_payment": month.strftime("%Y-%m-%d"),
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


class QarzdorlarDebtConsistencyTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Debt Logic Center", slug="debt-logic")
        activate_center(self.center)
        self.manager = User.objects.create_user(
            email="manager@debt-logic.test",
            password="testpass123",
            role="manager",
            center=self.center,
            ism="Debt",
            familya="Manager",
        )
        self.teacher = User.objects.create_user(
            email="teacher@debt-logic.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Debt",
            familya="Teacher",
            oqituvchi_foizi=40,
        )
        self.group_a = Group.objects.create(
            center=self.center,
            nom="Debt Group A",
            oqituvchi=self.teacher,
            kurs_narxi=100_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.group_b = Group.objects.create(
            center=self.center,
            nom="Debt Group B",
            oqituvchi=self.teacher,
            kurs_narxi=200_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.client.force_login(self.manager)
        self.qarzdorlar_url = f"/{self.center.slug}{reverse('education:qarzdorlar_home')}"

    def _student(self, email, ism):
        return User.objects.create_user(
            email=email,
            password="testpass123",
            role="student",
            center=self.center,
            ism=ism,
            familya="Student",
            telefon1="+998901009999",
        )

    def _enrollment(self, student, group, price):
        enrollment = Enrollment.objects.create(
            center=self.center,
            group=group,
            student=student,
            kurs_narhi=price,
            oqituvchi_foiz=40,
            is_active=True,
        )
        StudentGroupHistory.objects.create(
            student=student,
            group=group,
            center=self.center,
            start_date=date(2026, 3, 1),
            kurs_narxi=price,
            oqituvchi_foiz=40,
        )
        return enrollment

    def _allocate(self, enrollment, tuition_month, amount, paid_date):
        payment = Payment.objects.create(
            center=self.center,
            enrollment=enrollment,
            student=enrollment.student,
            group=enrollment.group,
            payment_type="cash",
            cash_amount=amount,
            paid_date=paid_date,
            created_by=self.manager,
        )
        return PaymentAllocation.objects.create(
            center=self.center,
            payment=payment,
            tuition_month=tuition_month,
            amount=amount,
        )

    def _single_row(self, response):
        rows = list(response.context["page_obj"].object_list)
        self.assertEqual(len(rows), 1)
        return rows[0]

    @freeze_time("2026-04-15")
    def test_overpayment_on_one_enrollment_does_not_close_another_enrollment_debt(self):
        month = date(2026, 4, 1)
        student = self._student("multi-overpay@debt-logic.test", "MultiOverpay")
        overpaid_enrollment = self._enrollment(student, self.group_a, 100_000)
        debt_enrollment = self._enrollment(student, self.group_b, 200_000)
        overpaid_tm = TuitionMonth.objects.create(
            center=self.center,
            enrollment=overpaid_enrollment,
            month=month,
            fee_amount=100_000,
        )
        debt_tm = TuitionMonth.objects.create(
            center=self.center,
            enrollment=debt_enrollment,
            month=month,
            fee_amount=200_000,
        )
        self._allocate(overpaid_enrollment, overpaid_tm, 150_000, month.replace(day=5))
        self._allocate(debt_enrollment, debt_tm, 50_000, month.replace(day=6))

        response = self.client.get(self.qarzdorlar_url, {
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
            "q": "MultiOverpay",
        })

        self.assertEqual(response.status_code, 200)
        row = self._single_row(response)
        self.assertEqual(row["debt"], 150_000)
        self.assertEqual(response.context["total_debt"], 150_000)
        self.assertEqual(response.context["filtered_debt"], 150_000)
        self.assertEqual(response.context["chart_data"][-1], 150_000)

    def test_date_from_date_to_counts_the_whole_month_range(self):
        student = self._student("range@debt-logic.test", "RangeFilter")
        enrollment = self._enrollment(student, self.group_a, 120_000)
        april = date(2026, 4, 1)
        may = date(2026, 5, 1)
        TuitionMonth.objects.create(
            center=self.center,
            enrollment=enrollment,
            month=april,
            fee_amount=100_000,
        )
        may_tm = TuitionMonth.objects.create(
            center=self.center,
            enrollment=enrollment,
            month=may,
            fee_amount=120_000,
        )
        self._allocate(enrollment, may_tm, 50_000, may.replace(day=7))

        range_response = self.client.get(self.qarzdorlar_url, {
            "date_from": "2026-04-01",
            "date_to": "2026-05-31",
            "q": "RangeFilter",
        })
        may_response = self.client.get(self.qarzdorlar_url, {
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
            "q": "RangeFilter",
        })

        self.assertEqual(range_response.status_code, 200)
        self.assertEqual(self._single_row(range_response)["debt"], 170_000)
        self.assertEqual(range_response.context["filtered_debt"], 170_000)
        self.assertEqual(range_response.context["effective_pay_month"], "2026-04")

        self.assertEqual(may_response.status_code, 200)
        self.assertEqual(self._single_row(may_response)["debt"], 70_000)
        self.assertEqual(may_response.context["filtered_debt"], 70_000)
        self.assertEqual(may_response.context["chart_data"][-1], 70_000)

    def test_qarzdorlar_get_does_not_create_or_update_tuition_months(self):
        month = date(2026, 4, 1)
        virtual_student = self._student("virtual@debt-logic.test", "VirtualNoWrite")
        virtual_enrollment = self._enrollment(virtual_student, self.group_a, 100_000)
        frozen_student = self._student("frozen@debt-logic.test", "FrozenNoWrite")
        frozen_enrollment = self._enrollment(frozen_student, self.group_b, 100_000)
        frozen_tm = TuitionMonth.objects.create(
            center=self.center,
            enrollment=frozen_enrollment,
            month=month,
            fee_amount=300_000,
        )
        before_count = TuitionMonth.objects.count()

        virtual_response = self.client.get(self.qarzdorlar_url, {
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
            "q": "VirtualNoWrite",
        })
        frozen_response = self.client.get(self.qarzdorlar_url, {
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
            "q": "FrozenNoWrite",
        })

        self.assertEqual(virtual_response.status_code, 200)
        self.assertEqual(self._single_row(virtual_response)["debt"], 100_000)
        self.assertFalse(
            TuitionMonth.objects.filter(enrollment=virtual_enrollment, month=month).exists()
        )
        self.assertEqual(TuitionMonth.objects.count(), before_count)

        self.assertEqual(frozen_response.status_code, 200)
        self.assertEqual(self._single_row(frozen_response)["debt"], 300_000)
        frozen_tm.refresh_from_db()
        self.assertEqual(frozen_tm.fee_amount, 300_000)
