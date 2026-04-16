from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from education.models import (
    Attendance,
    Category,
    CenterExpense,
    Enrollment,
    ExamResult,
    ExamSession,
    Group,
    Payment,
    PaymentAllocation,
    StudentGroupHistory,
    TuitionMonth,
)


class DashboardFeatureTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.month_start = self.today.replace(day=1)

        self.center = Center.objects.create(
            name="Feature Center",
            slug="feature-center",
            status=Center.STATUS_ACTIVE,
        )
        self.director = User.objects.create_user(
            email="director@feature.test",
            password="testpass123",
            role="director",
            center=self.center,
            ism="Diyor",
            familya="Director",
        )
        self.teacher = User.objects.create_user(
            email="teacher@feature.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Talim",
            familya="Teacher",
            oqituvchi_foizi=40,
        )
        self.student_paid = User.objects.create_user(
            email="student.paid@feature.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Ali",
            familya="Paid",
        )
        self.student_debtor = User.objects.create_user(
            email="student.debtor@feature.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Vali",
            familya="Debtor",
        )
        self.parent = User.objects.create_user(
            email="parent@feature.test",
            password="testpass123",
            role="parent",
            center=self.center,
            ism="Ona",
            familya="Aliyeva",
            telegram_id="12345",
        )
        self.parent.children.add(self.student_debtor)

        self.category = Category.objects.create(center=self.center, name="Matematika")
        self.group = Group.objects.create(
            center=self.center,
            nom="Alpha",
            category_obj=self.category,
            oqituvchi=self.teacher,
            kurs_narxi=600_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
            max_students=10,
        )
        self.second_group = Group.objects.create(
            center=self.center,
            nom="Beta",
            category_obj=self.category,
            oqituvchi=self.teacher,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
            max_students=5,
        )

        self.enrollment_paid = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student_paid,
            kurs_narhi=600_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        self.enrollment_debtor = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student_debtor,
            kurs_narhi=600_000,
            oqituvchi_foiz=40,
            is_active=True,
        )

        TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.enrollment_paid,
            month=self.month_start,
            fee_amount=600_000,
        )
        TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.enrollment_debtor,
            month=self.month_start,
            fee_amount=600_000,
        )

        payment = Payment.objects.create(
            center=self.center,
            enrollment=self.enrollment_paid,
            student=self.student_paid,
            group=self.group,
            payment_type="cash",
            cash_amount=600_000,
            paid_date=self.today,
            created_by=self.director,
        )
        paid_month = TuitionMonth.objects.get(enrollment=self.enrollment_paid, month=self.month_start)
        PaymentAllocation.objects.create(
            center=self.center,
            payment=payment,
            tuition_month=paid_month,
            amount=600_000,
        )

        Attendance.objects.create(
            center=self.center,
            group=self.group,
            student=self.student_paid,
            teacher=self.teacher,
            date=self.today,
            status="present",
            present=True,
        )
        Attendance.objects.create(
            center=self.center,
            group=self.group,
            student=self.student_debtor,
            teacher=self.teacher,
            date=self.today,
            status="absent_unexcused",
            present=False,
        )

        StudentGroupHistory.objects.create(
            center=self.center,
            group=self.group,
            student=self.student_debtor,
            start_date=self.month_start - timedelta(days=20),
            end_date=self.today,
            kurs_narxi=600_000,
            oqituvchi_foiz=40,
        )

        self.exam_session = ExamSession.objects.create(
            center=self.center,
            group=self.group,
            teacher=self.teacher,
            exam_date=self.today,
            attendance_date=self.today,
            status=ExamSession.STATUS_COMPLETED,
            created_by=self.director,
        )
        ExamResult.objects.create(
            center=self.center,
            session=self.exam_session,
            group=self.group,
            student=self.student_paid,
            teacher=self.teacher,
            percent=88,
            score=88,
            passed=True,
            exam_date=self.today,
            created_by=self.director,
        )

        CenterExpense.objects.create(
            center=self.center,
            category=CenterExpense.CATEGORY_RENT,
            amount=200_000,
            description="Ijara",
            date=self.today,
            created_by=self.director,
        )

        self.client.force_login(self.director)

    def test_dashboard_quick_stats_api_returns_live_numbers(self):
        response = self.client.get(reverse("core:dashboard_quick_stats"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["today_income"], 600_000)
        self.assertEqual(payload["debtors"], 1)
        self.assertEqual(payload["active_groups"], 2)
        self.assertEqual(payload["attendance_pct"], 50)
        self.assertEqual(payload["attendance_label"], "1/2")

    def test_dashboard_hub_renders_director_home_cards(self):
        response = self.client.get(reverse("core:dashboard_hub"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bugungi tushum")
        self.assertContains(response, "Faol guruhlar")

    def test_financial_api_contains_new_expense_breakdown_and_year_compare(self):
        response = self.client.get(reverse("core:financial_api"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["kpis"]["revenue"], 600_000)
        self.assertEqual(payload["kpis"]["expenses"], 200_000)
        self.assertIn("year_compare", payload)
        self.assertEqual(len(payload["year_compare"]["this_year"]), 12)
        expense_labels = [row["label"] for row in payload["breakdowns"]["expenses"]]
        self.assertIn("Ijara", expense_labels)

    def test_groups_and_teacher_api_include_capacity_and_rating_metrics(self):
        groups_response = self.client.get(reverse("core:groups_api"))
        self.assertEqual(groups_response.status_code, 200)
        groups_payload = groups_response.json()
        self.assertIn("groups", groups_payload)
        self.assertEqual(groups_payload["groups"][0]["capacity"], 10)
        self.assertGreaterEqual(groups_payload["groups"][0]["fill_pct"], 0)

        teachers_response = self.client.get(reverse("core:teacher_performance_api"))
        self.assertEqual(teachers_response.status_code, 200)
        teachers_payload = teachers_response.json()
        teacher_row = teachers_payload["teachers"][0]
        self.assertIn("score", teacher_row)
        self.assertIn("avg_attendance_pct", teacher_row)
        self.assertIn("exam_avg_score", teacher_row)
        self.assertIn("dropout_count", teacher_row)
        self.assertGreaterEqual(teacher_row["score"], 0)
