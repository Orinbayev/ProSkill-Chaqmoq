import json

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Branch, Center, User
from chaqmoq.models import Ledger
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
        self.assertEqual(payload["charts"]["attendance_labels"], ["Kelgan", "Kelmagan", "Sababli"])
        self.assertEqual(payload["charts"]["attendance_counts"], [1, 0, 0])
        self.assertEqual(payload["charts"]["group_names"], ["Matematika A"])
        self.assertEqual(len(payload["top_groups"]), 1)

    def test_director_dashboard_page_renders_branch_controls(self):
        self.client.force_login(self.director)

        response = self.client.get(reverse("core:director_boshqaruv"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="bqBranchOverlay"')
        self.assertContains(response, "Filiallar Boshqaruvi")


class StudentDashboardBalanceTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(
            name="Student Dashboard Center",
            slug="student-dashboard-center",
            max_students=100,
            capacity_limit=100,
        )
        self.student = User.objects.create_user(
            email="student.dashboard@test.uz",
            password="strong-pass-123",
            role="student",
            center=self.center,
            ism="Student",
            familya="Dashboard",
        )
        self.teacher = User.objects.create_user(
            email="teacher.dashboard@test.uz",
            password="strong-pass-123",
            role="teacher",
            center=self.center,
            ism="Teacher",
            familya="Dashboard",
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="Dashboard Group",
            oqituvchi=self.teacher,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        Enrollment.objects.create(
            center=self.center,
            student=self.student,
            group=self.group,
            kurs_narhi=500_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        Ledger.objects.create(
            student=self.student,
            beruvchi=self.teacher,
            group=self.group,
            rule_nom="Bonus",
            rule_tur="plus",
            ball=300,
        )
        Ledger.objects.create(
            student=self.student,
            beruvchi=self.teacher,
            group=self.group,
            rule_nom="Jarima",
            rule_tur="minus",
            ball=-28,
        )
        self.client.force_login(self.student)

    def test_student_dashboard_init_api_returns_same_balance_as_ranking(self):
        response = self.client.get(f"/{self.center.slug}{reverse('core:dashboard_student_init_api')}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["balance"], 272)


class UserEditEnrollmentCreationTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(
            name="User Edit Center",
            slug="user-edit-center",
            max_students=100,
            capacity_limit=100,
        )
        self.manager = User.objects.create_user(
            email="manager.useredit@test.uz",
            password="strong-pass-123",
            role="manager",
            center=self.center,
            ism="Manager",
            familya="UserEdit",
        )
        self.teacher = User.objects.create_user(
            email="teacher.useredit@test.uz",
            password="strong-pass-123",
            role="teacher",
            center=self.center,
            ism="Teacher",
            familya="UserEdit",
        )
        self.student = User.objects.create_user(
            email="student.useredit@test.uz",
            password="strong-pass-123",
            role="student",
            center=self.center,
            ism="Student",
            familya="UserEdit",
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="Frontend N1",
            oqituvchi=self.teacher,
            kurs_narxi=650_000,
            oqituvchi_foiz=45,
            oy_dars_soni=14,
        )

    def test_user_edit_post_creates_enrollment_with_restored_pricing_fields(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("core:user_edit", args=[self.student.id]),
            {
                "ism": self.student.ism,
                "familya": self.student.familya,
                "email": self.student.email,
                "telefon1": self.student.telefon1 or "",
                "telefon2": self.student.telefon2 or "",
                "yangi_group_id": str(self.group.id),
            },
        )

        self.assertEqual(response.status_code, 302)

        enrollment = Enrollment.objects.get(student=self.student, group=self.group)
        self.assertTrue(enrollment.is_active)
        self.assertEqual(enrollment.kurs_narhi, self.group.kurs_narxi)
        self.assertEqual(enrollment.monthly_price, self.group.kurs_narxi)
        self.assertEqual(enrollment.monthly_lessons, self.group.oy_dars_soni)
        self.assertEqual(enrollment.active_lessons_count, 0)
        self.assertEqual(enrollment.paid_amount, 0)
        self.assertEqual(enrollment.pricing_type, Enrollment.PRICING_FULL)
        self.assertIsNotNone(enrollment.joined_at)
