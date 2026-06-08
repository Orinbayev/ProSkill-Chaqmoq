from datetime import date
from django.test import TestCase
from django.urls import reverse
from accounts.models import Center, User
from education.models import Group, Enrollment, Attendance
from billing.models import SubscriptionPlan

class RemovedStudentsVisibilityTest(TestCase):
    def setUp(self):
        # Create billing plan required for some operations
        self.plan = SubscriptionPlan.objects.create(
            code="START",
            title="Start Plan",
            monthly_price=0,
            active=True
        )

        # Setup tenant center
        self.center = Center.objects.create(
            name="Test Center", slug="test-center"
        )
        self.director = User.objects.create_user(
            email="director@test.com", password="password",
            role="director", center=self.center,
            ism="Dir", familya="Test"
        )
        self.teacher = User.objects.create_user(
            email="teacher@test.com", password="password",
            role="teacher", center=self.center,
            ism="Teach", familya="Test"
        )
        self.student = User.objects.create_user(
            email="student@test.com", password="password",
            role="student", center=self.center,
            ism="Ali", familya="Valiyev"
        )

        # Setup group
        self.group = Group.objects.create(
            center=self.center, nom="Test Group",
            oqituvchi=self.teacher,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )

        # Setup enrollment
        self.enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            kurs_narhi=500_000,
            oqituvchi_foiz=40,
            is_active=True,
            joined_at=date(2026, 6, 1),
            monthly_lessons=12,
        )

    def test_active_student_visibility(self):
        """Active student is visible on all group detail, rollcall, and monthly views."""
        self.client.force_login(self.director)
        
        # 1. Group Detail Page
        url = reverse("education:group_detail", args=[self.group.id])
        resp = self.client.get(f"/{self.center.slug}{url}?date=2026-06-08", follow=True)
        self.assertEqual(resp.status_code, 200)
        enrollments = [e.id for e in resp.context.get("enrollments", [])]
        self.assertIn(self.enrollment.id, enrollments)

        # 2. Group Rollcall Page
        url_roll = reverse("education:group_rollcall", args=[self.group.id])
        resp_roll = self.client.get(f"/{self.center.slug}{url_roll}?date=2026-06-08", follow=True)
        self.assertEqual(resp_roll.status_code, 200)
        students = [s.id for s in resp_roll.context.get("students", [])]
        self.assertIn(self.student.id, students)

        # 3. Monthly Attendance Grid
        url_grid = reverse("education:group_month_attendance", args=[self.group.id])
        resp_grid = self.client.get(f"/{self.center.slug}{url_grid}?year=2026&month=6", follow=True)
        self.assertEqual(resp_grid.status_code, 200)
        students_grid = [row["student"].id for row in resp_grid.context.get("rows", [])]
        self.assertIn(self.student.id, students_grid)

    def test_inactive_student_no_attendance_hidden(self):
        """Inactive student with no attendance in selected month is hidden from all views."""
        # Deactivate enrollment
        self.enrollment.is_active = False
        self.enrollment.save()

        self.client.force_login(self.director)

        # 1. Group Detail Page (June 2026)
        url = reverse("education:group_detail", args=[self.group.id])
        resp = self.client.get(f"/{self.center.slug}{url}?date=2026-06-08", follow=True)
        self.assertEqual(resp.status_code, 200)
        enrollments = [e.id for e in resp.context.get("enrollments", [])]
        self.assertNotIn(self.enrollment.id, enrollments)

        # 2. Group Rollcall Page (June 2026)
        url_roll = reverse("education:group_rollcall", args=[self.group.id])
        resp_roll = self.client.get(f"/{self.center.slug}{url_roll}?date=2026-06-08", follow=True)
        self.assertEqual(resp_roll.status_code, 200)
        students = [s.id for s in resp_roll.context.get("students", [])]
        self.assertNotIn(self.student.id, students)

        # 3. Monthly Attendance Grid (June 2026)
        url_grid = reverse("education:group_month_attendance", args=[self.group.id])
        resp_grid = self.client.get(f"/{self.center.slug}{url_grid}?year=2026&month=6", follow=True)
        self.assertEqual(resp_grid.status_code, 200)
        students_grid = [row["student"].id for row in resp_grid.context.get("rows", [])]
        self.assertNotIn(self.student.id, students_grid)

    def test_inactive_student_with_attendance_visible(self):
        """Inactive student with attendance remains visible for that selected month, but hidden in the next."""
        # Deactivate enrollment
        self.enrollment.is_active = False
        self.enrollment.save()

        # Add attendance record in June 2026
        Attendance.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            teacher=self.teacher,
            date=date(2026, 6, 5),
            status="present",
            present=True,
            created_by=self.director
        )

        self.client.force_login(self.director)

        # --- Check June 2026 (Should be VISIBLE) ---
        # 1. Group Detail Page
        url = reverse("education:group_detail", args=[self.group.id])
        resp = self.client.get(f"/{self.center.slug}{url}?date=2026-06-08", follow=True)
        self.assertEqual(resp.status_code, 200)
        enrollments = [e.id for e in resp.context.get("enrollments", [])]
        self.assertIn(self.enrollment.id, enrollments)

        # 2. Group Rollcall Page
        url_roll = reverse("education:group_rollcall", args=[self.group.id])
        resp_roll = self.client.get(f"/{self.center.slug}{url_roll}?date=2026-06-08", follow=True)
        self.assertEqual(resp_roll.status_code, 200)
        students = [s.id for s in resp_roll.context.get("students", [])]
        self.assertIn(self.student.id, students)

        # 3. Monthly Attendance Grid
        url_grid = reverse("education:group_month_attendance", args=[self.group.id])
        resp_grid = self.client.get(f"/{self.center.slug}{url_grid}?year=2026&month=6", follow=True)
        self.assertEqual(resp_grid.status_code, 200)
        students_grid = [row["student"].id for row in resp_grid.context.get("rows", [])]
        self.assertIn(self.student.id, students_grid)

        # --- Check July 2026 (Should be HIDDEN) ---
        # 1. Group Detail Page
        resp_july = self.client.get(f"/{self.center.slug}{url}?date=2026-07-01", follow=True)
        self.assertEqual(resp_july.status_code, 200)
        enrollments_july = [e.id for e in resp_july.context.get("enrollments", [])]
        self.assertNotIn(self.enrollment.id, enrollments_july)

        # 2. Group Rollcall Page
        resp_roll_july = self.client.get(f"/{self.center.slug}{url_roll}?date=2026-07-01", follow=True)
        self.assertEqual(resp_roll_july.status_code, 200)
        students_july = [s.id for s in resp_roll_july.context.get("students", [])]
        self.assertNotIn(self.student.id, students_july)

        # 3. Monthly Attendance Grid
        resp_grid_july = self.client.get(f"/{self.center.slug}{url_grid}?year=2026&month=7", follow=True)
        self.assertEqual(resp_grid_july.status_code, 200)
        students_grid_july = [row["student"].id for row in resp_grid_july.context.get("rows", [])]
        self.assertNotIn(self.student.id, students_grid_july)
