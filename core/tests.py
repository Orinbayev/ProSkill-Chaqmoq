import json

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Branch, Center, User
from education.models import Attendance, Enrollment, Group, Payment


class BranchApiTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.center = Center.objects.create(
            name="Branch Center",
            slug="branch-center",
            max_students=100,
            capacity_limit=100,
        )
        self.director = User.objects.create_user(
            email="director.branch@test.uz",
            password="strong-pass-123",
            role="director",
            center=self.center,
            ism="Direktor",
            familya="Branch",
        )
        self.manager = User.objects.create_user(
            email="manager.branch@test.uz",
            password="strong-pass-123",
            role="manager",
            center=self.center,
            ism="Manager",
            familya="Branch",
        )
        self.teacher = User.objects.create_user(
            email="teacher.branch@test.uz",
            password="strong-pass-123",
            role="teacher",
            center=self.center,
            ism="Oqituvchi",
            familya="Branch",
        )
        self.student_a = User.objects.create_user(
            email="student.a.branch@test.uz",
            password="strong-pass-123",
            role="student",
            center=self.center,
            ism="Ali",
            familya="A",
        )
        self.student_b = User.objects.create_user(
            email="student.b.branch@test.uz",
            password="strong-pass-123",
            role="student",
            center=self.center,
            ism="Vali",
            familya="B",
        )

        self.branch_a = Branch.objects.create(center=self.center, name="Chilonzor")
        self.branch_b = Branch.objects.create(center=self.center, name="Yunusobod")

        self.group_a = Group.objects.create(
            center=self.center,
            branch=self.branch_a,
            nom="Matematika A",
            oqituvchi=self.teacher,
            kurs_narxi=600_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.group_b = Group.objects.create(
            center=self.center,
            branch=self.branch_b,
            nom="Matematika B",
            oqituvchi=self.teacher,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )

        self.enrollment_a = Enrollment.objects.create(
            center=self.center,
            student=self.student_a,
            group=self.group_a,
            kurs_narhi=600_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        self.enrollment_b = Enrollment.objects.create(
            center=self.center,
            student=self.student_b,
            group=self.group_b,
            kurs_narhi=500_000,
            oqituvchi_foiz=40,
            is_active=True,
        )

    def test_branch_list_api_includes_groups_and_students_stats(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("core:branch_list_api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])

        row = next(item for item in payload["branches"] if item["id"] == self.branch_a.id)
        self.assertEqual(row["groups_count"], 1)
        self.assertEqual(row["students_count"], 1)

    def test_director_can_create_update_and_delete_branch(self):
        self.client.force_login(self.director)

        create_response = self.client.post(
            reverse("core:branch_create"),
            data=json.dumps({
                "name": "Sergeli",
                "address": "Sergeli 5",
                "phone": "+998901234567",
            }),
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 200)
        new_branch_id = create_response.json()["branch"]["id"]

        update_response = self.client.post(
            reverse("core:branch_update", args=[self.branch_a.id]),
            data=json.dumps({
                "name": "Chilonzor Updated",
                "address": "Chilonzor 10",
                "phone": "+998909999999",
                "is_active": False,
            }),
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.branch_a.refresh_from_db()
        self.assertEqual(self.branch_a.name, "Chilonzor Updated")
        self.assertFalse(self.branch_a.is_active)

        delete_response = self.client.post(reverse("core:branch_delete", args=[self.branch_a.id]))
        self.assertEqual(delete_response.status_code, 200)
        self.group_a.refresh_from_db()
        self.assertIsNone(self.group_a.branch)
        self.assertFalse(Branch.objects.filter(pk=self.branch_a.id).exists())
        self.assertTrue(Branch.objects.filter(pk=new_branch_id).exists())

    def test_manager_cannot_create_branch(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("core:branch_create"),
            data=json.dumps({"name": "No Permission"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "Faqat direktor")

    def test_director_dashboard_api_filters_by_branch(self):
        Payment.objects.create(
            center=self.center,
            enrollment=self.enrollment_a,
            student=self.student_a,
            group=self.group_a,
            payment_type="cash",
            cash_amount=200_000,
            paid_date=self.today,
            created_by=self.director,
        )
        Payment.objects.create(
            center=self.center,
            enrollment=self.enrollment_b,
            student=self.student_b,
            group=self.group_b,
            payment_type="cash",
            cash_amount=300_000,
            paid_date=self.today,
            created_by=self.director,
        )
        Attendance.objects.create(
            center=self.center,
            group=self.group_a,
            student=self.student_a,
            teacher=self.teacher,
            date=self.today,
            present=True,
            status="present",
        )
        Attendance.objects.create(
            center=self.center,
            group=self.group_b,
            student=self.student_b,
            teacher=self.teacher,
            date=self.today,
            present=False,
            status="absent_unexcused",
        )

        self.client.force_login(self.director)
        response = self.client.get(
            reverse("core:director_boshqaruv_api"),
            {
                "date_from": self.today.isoformat(),
                "date_to": self.today.isoformat(),
                "branch_id": self.branch_a.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["kpis"]["revenue"], 200_000)
        self.assertEqual(payload["kpis"]["total_groups"], 1)
        self.assertEqual(payload["kpis"]["active_students"], 1)
        self.assertEqual(payload["kpis"]["avg_attendance"], 100.0)
        self.assertEqual(payload["charts"]["group_names"], ["Matematika A"])
        self.assertEqual(len(payload["top_groups"]), 1)

    def test_director_dashboard_page_renders_branch_controls(self):
        self.client.force_login(self.director)

        response = self.client.get(reverse("core:director_boshqaruv"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="bqBranchBtn"')
        self.assertContains(response, "Filiallar Boshqaruvi")
