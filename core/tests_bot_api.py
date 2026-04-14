import json
from datetime import time

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import Center, User
from education.models import Attendance, Category, Enrollment, Group, GroupSchedule, Payment, PaymentAllocation, TuitionMonth
from store.models import Lead, LeadStatus, Manba


@override_settings(API_SECRET="x" * 40)
class BotAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.headers = {"HTTP_X_API_SECRET": "x" * 40}
        self.today = timezone.localdate()
        self.center = Center.objects.create(
            name="Bot Center",
            slug="bot-center",
            max_students=100,
            capacity_limit=100,
            phone="+998901234567",
            payment_day=5,
        )
        self.category = Category.objects.create(center=self.center, name="IT")

        self.student = User.objects.create_user(
            email="student@bot.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Ali",
            familya="Student",
            telegram_id="1001",
            is_telegram_linked=True,
        )
        self.parent = User.objects.create_user(
            email="parent@bot.test",
            password="testpass123",
            role="parent",
            center=self.center,
            ism="Parent",
            familya="One",
            telegram_id="2002",
            is_telegram_linked=True,
        )
        self.teacher = User.objects.create_user(
            email="teacher@bot.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Teacher",
            familya="One",
            telegram_id="3003",
            is_telegram_linked=True,
        )
        self.manager = User.objects.create_user(
            email="manager@bot.test",
            password="testpass123",
            role="manager",
            center=self.center,
            ism="Manager",
            familya="One",
            telegram_id="4004",
            is_telegram_linked=True,
        )
        self.parent.children.add(self.student)

        self.group = Group.objects.create(
            center=self.center,
            nom="Python Group",
            category_obj=self.category,
            oqituvchi=self.teacher,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
            lessons_per_week=3,
        )
        self.enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            kurs_narhi=500_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        GroupSchedule.objects.create(
            center=self.center,
            group=self.group,
            weekday=1,
            start_time=time(9, 0),
            end_time=time(10, 30),
            room="2-kabinet",
        )
        GroupSchedule.objects.create(
            center=self.center,
            group=self.group,
            weekday=3,
            start_time=time(9, 0),
            end_time=time(10, 30),
            room="2-kabinet",
        )
        self.tuition_month = TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.enrollment,
            month=self.today.replace(day=1),
            fee_amount=500_000,
        )
        self.payment = Payment.objects.create(
            center=self.center,
            enrollment=self.enrollment,
            student=self.student,
            group=self.group,
            payment_type="cash",
            cash_amount=200_000,
            paid_date=self.today,
            created_by=self.manager,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=self.payment,
            tuition_month=self.tuition_month,
            amount=200_000,
        )
        Attendance.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            teacher=self.teacher,
            date=self.today,
            status="present",
            present=True,
        )

        self.source = Manba.objects.create(center=self.center, nom="Instagram")
        self.status = LeadStatus.objects.create(center=self.center, nom="Yangi", code=LeadStatus.Code.NEW)
        Lead.objects.create(
            center=self.center,
            ism="Aziza",
            familya="Lead",
            telefon1="+998901111111",
            yosh=17,
            manba=self.source,
            status=self.status,
            created_by=self.manager,
        )

    def test_student_bot_dashboard_returns_sections(self):
        response = self.client.get(
            "/hisob/login/bot-dashboard/",
            {"telegram_id": "1001", "email": self.student.email},
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["role"], "student")
        self.assertEqual(payload["student"]["payment"]["debt"], 300_000)
        self.assertEqual(payload["student"]["schedule"][0]["group_name"], "Python Group")
        self.assertEqual(payload["student"]["schedule"][0]["weekday_label"], "Du 09:00–10:30 | Cho 09:00–10:30")
        self.assertEqual(payload["student"]["schedule"][0]["time_label"], "2-kabinet")

    def test_teacher_bot_dashboard_returns_schedule_by_group(self):
        response = self.client.get(
            "/hisob/login/bot-dashboard/",
            {"telegram_id": "3003", "email": self.teacher.email},
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["role"], "teacher")
        schedule_by_group = payload["teacher"]["schedule_by_group"]
        self.assertEqual(schedule_by_group[0]["group_name"], "Python Group")
        self.assertEqual(
            schedule_by_group[0]["slots"],
            [
                {"day": "Du", "time": "09:00–10:30", "room": "2-kabinet"},
                {"day": "Cho", "time": "09:00–10:30", "room": "2-kabinet"},
            ],
        )

    def test_teacher_attendance_mark_updates_today_status(self):
        response = self.client.post(
            "/hisob/login/bot-group-attendance-mark/",
            data=json.dumps(
                {
                    "telegram_id": "3003",
                    "email": self.teacher.email,
                    "group_id": self.group.id,
                    "student_id": self.student.id,
                    "status": "absent",
                }
            ),
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        attendance = Attendance.objects.get(group=self.group, student=self.student, date=self.today)
        self.assertEqual(attendance.status, "absent_unexcused")

    def test_manager_inline_student_search_finds_student(self):
        response = self.client.get(
            "/hisob/login/bot-inline-student-search/",
            {"telegram_id": "4004", "q": "Ali"},
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["group_name"], "Python Group")

    def test_scheduler_payment_reminders_include_parent_payload(self):
        response = self.client.get(
            "/hisob/login/bot-scheduler-payment-reminders/",
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        chat_ids = {item["chat_id"] for item in items}
        self.assertIn("1001", chat_ids)
        self.assertIn("2002", chat_ids)
