from datetime import datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from education.models import Attendance, Category, Enrollment, Group, Payment, TuitionMonth
from store.models import Expense, Lead, LeadStatus, Manba


class DirectorDashboardAPITests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.now = timezone.make_aware(datetime.combine(self.today, time(10, 0)))

        self.center = Center.objects.create(
            name="Insight Center",
            slug="insight-center",
            max_students=100,
            capacity_limit=100,
        )
        self.category = Category.objects.create(center=self.center, name="Matematika")

        self.director = User.objects.create_user(
            email="director@test.com",
            password="testpass123",
            role="director",
            center=self.center,
            ism="Direktor",
            familya="Test",
        )
        self.teacher_strong = User.objects.create_user(
            email="teacher.strong@test.com",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Ali",
            familya="Strong",
        )
        self.teacher_weak = User.objects.create_user(
            email="teacher.weak@test.com",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Vali",
            familya="Weak",
        )

        self.student_source_a = self._student("student.a@test.com", "Aziza", "One")
        self.student_source_b = self._student("student.b@test.com", "Bekzod", "Two")
        self.student_no_lead = self._student("student.c@test.com", "Sarvar", "Three")

        self.group_strong = Group.objects.create(
            center=self.center,
            nom="Strong Group",
            category_obj=self.category,
            oqituvchi=self.teacher_strong,
            kurs_narxi=600_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.group_weak = Group.objects.create(
            center=self.center,
            nom="Weak Group",
            category_obj=self.category,
            oqituvchi=self.teacher_weak,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )

        self.enrollment_a = self._enroll(self.student_source_a, self.group_strong, 600_000)
        self.enrollment_b = self._enroll(self.student_source_b, self.group_weak, 500_000)
        self.enrollment_c = self._enroll(self.student_no_lead, self.group_strong, 600_000)

        TuitionMonth.objects.create(center=self.center, enrollment=self.enrollment_a, month=self.today.replace(day=1), fee_amount=600_000)
        TuitionMonth.objects.create(center=self.center, enrollment=self.enrollment_b, month=self.today.replace(day=1), fee_amount=500_000)
        TuitionMonth.objects.create(center=self.center, enrollment=self.enrollment_c, month=self.today.replace(day=1), fee_amount=600_000)

        self._payment(self.enrollment_a, 1_000_000)
        self._payment(self.enrollment_c, 500_000)

        for day_offset in range(10):
            lesson_date = self.today - timedelta(days=day_offset)
            Attendance.objects.create(
                center=self.center,
                group=self.group_strong,
                student=self.student_source_a,
                teacher=self.teacher_strong,
                date=lesson_date,
                present=True,
                status="present",
            )
            Attendance.objects.create(
                center=self.center,
                group=self.group_strong,
                student=self.student_no_lead,
                teacher=self.teacher_strong,
                date=lesson_date,
                present=True,
                status="present",
            )

        for day_offset in range(3):
            Attendance.objects.create(
                center=self.center,
                group=self.group_weak,
                student=self.student_source_b,
                teacher=self.teacher_weak,
                date=self.today - timedelta(days=day_offset),
                present=False,
                status="absent_unexcused",
            )

        Expense.objects.create(center=self.center, summa=300_000, izoh="Ijara", sana=self.now)

        self.source_telegram = Manba.objects.create(center=self.center, nom="Telegram")
        self.source_instagram = Manba.objects.create(center=self.center, nom="Instagram")
        self.lead_registered = LeadStatus.objects.create(center=self.center, nom="Registered", code=LeadStatus.Code.REGISTERED)

        Lead.objects.create(
            center=self.center,
            ism="LeadA",
            familya="Alpha",
            telefon1="+998901111111",
            yosh=18,
            manba=self.source_telegram,
            status=self.lead_registered,
            converted_user=self.student_source_a,
            converted_to_student=True,
            converted_at=timezone.now(),
            converted_by=self.director,
            created_by=self.director,
        )
        Lead.objects.create(
            center=self.center,
            ism="LeadB",
            familya="Beta",
            telefon1="+998902222222",
            yosh=19,
            manba=self.source_instagram,
            status=self.lead_registered,
            converted_user=self.student_source_b,
            converted_to_student=True,
            converted_at=timezone.now(),
            converted_by=self.director,
            created_by=self.director,
        )

        self.client.force_login(self.director)

    def _student(self, email, ism, familya):
        return User.objects.create_user(
            email=email,
            password="testpass123",
            role="student",
            center=self.center,
            ism=ism,
            familya=familya,
            date_joined=timezone.now(),
        )

    def _enroll(self, student, group, fee):
        return Enrollment.objects.create(
            center=self.center,
            student=student,
            group=group,
            kurs_narhi=fee,
            oqituvchi_foiz=group.oqituvchi_foiz,
            is_active=True,
        )

    def _payment(self, enrollment, amount):
        return Payment.objects.create(
            center=self.center,
            enrollment=enrollment,
            student=enrollment.student,
            group=enrollment.group,
            payment_type="cash",
            cash_amount=amount,
            paid_date=self.today,
            created_by=self.director,
        )

    def _get_dashboard(self, **params):
        base_params = {
            "date_from": (self.today - timedelta(days=29)).isoformat(),
            "date_to": self.today.isoformat(),
        }
        base_params.update(params)
        return self.client.get(reverse("core:director_dashboard_api"), base_params)

    def test_dashboard_api_returns_real_payload_and_no_join_duplication(self):
        response = self._get_dashboard()
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("overview", payload)
        self.assertIn("executive", payload)
        self.assertIn("groups", payload)
        self.assertIn("marketing", payload)
        self.assertEqual(payload["finance"]["income"], 1_500_000)
        self.assertEqual(payload["groups"]["top_profitable"][0]["group_name"], "Strong Group")
        self.assertEqual(payload["groups"]["top_profitable"][0]["revenue"], 1_500_000)
        self.assertEqual(payload["teachers"]["ranking"][0]["teacher_name"], "Ali Strong")
        self.assertEqual(payload["teachers"]["ranking"][0]["revenue"], 1_500_000)
        self.assertEqual(len(payload["executive"]["today_strip"]), 4)
        self.assertEqual(payload["executive"]["trend_signal"]["title"], "Qarzdorlik bosimi oshgan")

    def test_source_filter_scopes_finance_to_converted_students(self):
        response = self._get_dashboard(source=str(self.source_telegram.id))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["finance"]["income"], 1_000_000)
        self.assertEqual(payload["students"]["active_students"], 1)
        self.assertEqual(payload["filters"]["applied"]["source_ids"], [self.source_telegram.id])

    def test_group_close_candidate_is_flagged(self):
        response = self._get_dashboard()
        payload = response.json()

        close_candidates = payload["groups"]["close_candidates"]
        self.assertTrue(close_candidates)
        self.assertEqual(close_candidates[0]["group_name"], "Weak Group")
        self.assertEqual(close_candidates[0]["primary_action"], "Yopish tavsiya etiladi")

    def test_director_home_uses_new_dashboard_template(self):
        response = self.client.get(f"/{self.center.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Direktor boshqaruv paneli")
        self.assertContains(response, 'id="todayStrip"')
        self.assertContains(response, 'id="trendSignal"')
        self.assertContains(response, 'id="groupPreview"')
        self.assertContains(response, 'id="teacherPerformanceChart"')
        self.assertContains(response, 'id="detailDrawer"')
