from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from accounts.models import Center, User
from chaqmoq.models import LightningHistory, Rule
from education.models import DailyLightningRecord, Enrollment, Group, Student


class LightningPersistenceTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Center", slug="center-persist")
        self.teacher = User.objects.create_user(
            email="teacher.persist@example.com",
            password="password",
            role="teacher",
            center=self.center,
            ism="Teach",
            familya="Er",
        )
        self.student_user = User.objects.create_user(
            email="student.persist@example.com",
            password="password",
            role="student",
            center=self.center,
            ism="Stud",
            familya="Ent",
        )
        self.group = Group.objects.create(
            nom="Persistence Group",
            center=self.center,
            oqituvchi=self.teacher,
            kurs_narxi=500000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        Enrollment.objects.create(
            group=self.group,
            student=self.student_user,
            center=self.center,
            kurs_narhi=500000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        self.student_model = Student.objects.create(
            user=self.student_user,
            center=self.center,
        )
        self.client.force_login(self.teacher)

    def test_group_detail_uses_student_model_history_sum(self):
        LightningHistory.objects.create(
            student=self.student_model,
            points=7,
            reason="Manual bonus",
            source="manual",
            teacher=self.teacher,
        )
        DailyLightningRecord.objects.create(
            group=self.group,
            student=self.student_user,
            center=self.center,
            date=self.group.tuzilgan.date(),
            plus_points=7,
            minus_points=0,
        )

        response = self.client.get(
            f"/{self.center.slug}{reverse('education:group_detail', args=[self.group.id])}",
            {"date": self.group.tuzilgan.date().isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        enrollment = response.context["enrollments"][0]
        self.assertEqual(enrollment.student.balance, 7)
        self.assertEqual(
            response.context["recent_history_map"][str(self.student_user.id)],
            {"add": 7, "sub": 0},
        )

    def test_recent_history_is_aggregated_per_student(self):
        selected_date = self.group.tuzilgan.date()
        DailyLightningRecord.objects.create(
            group=self.group,
            student=self.student_user,
            center=self.center,
            date=selected_date,
            plus_points=6,
            minus_points=-2,
        )
        DailyLightningRecord.objects.create(
            group=self.group,
            student=self.student_user,
            center=self.center,
            date=selected_date - timedelta(days=1),
            plus_points=99,
            minus_points=-11,
        )

        response = self.client.get(
            f"/{self.center.slug}{reverse('education:group_detail', args=[self.group.id])}",
            {"date": selected_date.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["recent_history_map"][str(self.student_user.id)],
            {"add": 6, "sub": -2},
        )

    def test_manual_points_persist_after_refresh(self):
        rule = Rule.objects.create(
            nom="Manual Plus",
            center=self.center,
            tur=Rule.PLUS,
            min_baho=1,
            max_baho=10,
        )

        post_response = self.client.post(
            f"/{self.center.slug}{reverse('education:group_points', args=[self.group.id])}",
            {
                "student_id": self.student_user.id,
                "rule_id": rule.id,
                "amount": 3,
                "request_id": "persist-test",
            },
        )

        self.assertEqual(post_response.status_code, 200)
        payload = post_response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["balance"], 3)

        history = LightningHistory.objects.get(student=self.student_model)
        self.assertEqual(history.points, 3)
        self.assertEqual(history.source, "manual")

        selected_date = self.group.tuzilgan.date()
        refresh_response = self.client.get(
            f"/{self.center.slug}{reverse('education:group_detail', args=[self.group.id])}",
            {"date": selected_date.isoformat()},
        )
        self.assertEqual(refresh_response.status_code, 200)
        enrollment = refresh_response.context["enrollments"][0]
        self.assertEqual(enrollment.student.balance, 3)
        self.assertEqual(
            refresh_response.context["recent_history_map"][str(self.student_user.id)],
            {"add": 3, "sub": 0},
        )
