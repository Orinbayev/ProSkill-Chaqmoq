"""
Cross-tenant IDOR regression tests for critical education views.

Scenario: manager of Center A must not read/mutate Center B objects by ID.
"""
from __future__ import annotations

from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from core.test_utils import create_active_center
from education.models import Category, Enrollment, Group


class EducationIdorTenantTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.center_a = create_active_center(name="Center A", slug="idor-a")
        self.center_b = create_active_center(name="Center B", slug="idor-b")

        self.manager_a = User.objects.create_user(
            email="manager_idor_a@example.com",
            password="password",
            role="manager",
            center=self.center_a,
            ism="Manager",
            familya="A",
        )
        self.teacher_b = User.objects.create_user(
            email="teacher_idor_b@example.com",
            password="password",
            role="teacher",
            center=self.center_b,
            ism="Teacher",
            familya="B",
        )
        self.student_a = User.objects.create_user(
            email="student_idor_a@example.com",
            password="password",
            role="student",
            center=self.center_a,
            ism="Student",
            familya="A",
        )
        self.student_b = User.objects.create_user(
            email="student_idor_b@example.com",
            password="password",
            role="student",
            center=self.center_b,
            ism="Student",
            familya="B",
        )

        self.group_a = Group.objects.create(
            nom="Group A",
            center=self.center_a,
            oqituvchi=None,
            kurs_narxi=500000,
            oqituvchi_foiz=40,
        )
        self.group_b = Group.objects.create(
            nom="Group B",
            center=self.center_b,
            oqituvchi=self.teacher_b,
            kurs_narxi=500000,
            oqituvchi_foiz=40,
        )
        Enrollment.objects.create(
            student=self.student_a,
            group=self.group_a,
            center=self.center_a,
            is_active=True,
        )
        Enrollment.objects.create(
            student=self.student_b,
            group=self.group_b,
            center=self.center_b,
            is_active=True,
        )

        self.cat_b = Category.objects.create(name="Foreign Cat", center=self.center_b)

        self.client.force_login(self.manager_a)

    def _tenant_url(self, name, *args, **query):
        """
        Slug-prefixed URL so TenantMiddleware binds center_a without dropping
        query params (plain reverse() gets a redirect that loses ?query).
        """
        path = reverse(name, args=args)
        url = f"/{self.center_a.slug}{path}"
        if query:
            from urllib.parse import urlencode

            url = f"{url}?{urlencode(query)}"
        return url

    def test_student_detail_own_center_ok(self):
        url = self._tenant_url("education:student_detail", self.student_a.id)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.student_a.ism)

    def test_student_detail_other_center_404(self):
        url = self._tenant_url("education:student_detail", self.student_b.id)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_student_payments_pdf_other_center_404(self):
        url = self._tenant_url(
            "education:student_payments_pdf",
            student_id=self.student_b.id,
            group_id=self.group_b.id,
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_group_rollcall_other_center_404(self):
        url = self._tenant_url("education:group_rollcall", self.group_b.id)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_attendance_today_other_center_404(self):
        url = self._tenant_url("education:attendance_today", self.group_b.id)
        resp = self.client.post(url, {"enr_id": "1", "status": "present"})
        self.assertEqual(resp.status_code, 404)

    def test_category_detail_other_center_404(self):
        url = self._tenant_url("education:category_detail", self.cat_b.id)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_teacher_income_other_center_teacher_404(self):
        url = self._tenant_url(
            "education:teacher_income_dashboard",
            teacher_id=self.teacher_b.id,
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_student_exam_report_other_center_404(self):
        url = self._tenant_url("education:student_exam_report", self.student_b.id)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)
