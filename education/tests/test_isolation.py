"""
Tenant isolation regression suite (phase 9).

Center A staff must never see or mutate Center B data — list views, detail
IDOR, create assignment, finance pages, and API-ish endpoints.
"""
from __future__ import annotations

from urllib.parse import urlencode

from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from core.test_utils import create_active_center
from education.models import Category, Enrollment, Group, Payment


class TenantIsolationTest(TestCase):
    """Legacy class name kept so historical references still resolve."""

    def setUp(self):
        self.client = Client()

        self.center_a = create_active_center(name="Center A", slug="iso-a")
        self.center_b = create_active_center(name="Center B", slug="iso-b")

        self.teacher_a = User.objects.create_user(
            email="teacher_iso_a@example.com",
            password="password",
            role="teacher",
            center=self.center_a,
            ism="Teach",
            familya="A",
        )
        self.manager_a = User.objects.create_user(
            email="manager_iso_a@example.com",
            password="password",
            role="manager",
            center=self.center_a,
            ism="Mgr",
            familya="A",
        )
        self.teacher_b = User.objects.create_user(
            email="teacher_iso_b@example.com",
            password="password",
            role="teacher",
            center=self.center_b,
            ism="Teach",
            familya="B",
        )
        self.manager_b = User.objects.create_user(
            email="manager_iso_b@example.com",
            password="password",
            role="manager",
            center=self.center_b,
            ism="Mgr",
            familya="B",
        )
        self.student_a = User.objects.create_user(
            email="student_iso_a@example.com",
            password="password",
            role="student",
            center=self.center_a,
            ism="Stu",
            familya="A",
        )
        self.student_b = User.objects.create_user(
            email="student_iso_b@example.com",
            password="password",
            role="student",
            center=self.center_b,
            ism="Stu",
            familya="B",
        )

        self.cat_a = Category.objects.create(name="Lang A", center=self.center_a)
        self.cat_b = Category.objects.create(name="Lang B", center=self.center_b)

        self.group_a = Group.objects.create(
            nom="Group Iso A",
            center=self.center_a,
            oqituvchi=self.teacher_a,
            category_obj=self.cat_a,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
        )
        self.group_b = Group.objects.create(
            nom="Group Iso B SECRET",
            center=self.center_b,
            oqituvchi=self.teacher_b,
            category_obj=self.cat_b,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
        )

        self.enr_a = Enrollment.objects.create(
            student=self.student_a,
            group=self.group_a,
            center=self.center_a,
            is_active=True,
            kurs_narhi=500_000,
            monthly_price=500_000,
        )
        self.enr_b = Enrollment.objects.create(
            student=self.student_b,
            group=self.group_b,
            center=self.center_b,
            is_active=True,
            kurs_narhi=500_000,
            monthly_price=500_000,
        )

        Payment.objects.create(
            enrollment=self.enr_b,
            student=self.student_b,
            group=self.group_b,
            center=self.center_b,
            summa=123_456,
            cash_amount=123_456,
            payment_type="cash",
        )

        # Aliases used by older test method names / expectations
        self.user_a = self.teacher_a
        self.user_b = self.teacher_b

    def _url(self, center, name, *args, **query):
        path = reverse(name, args=args)
        url = f"/{center.slug}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        return url

    def _login(self, user):
        self.client.force_login(user)

    # ── List isolation ──────────────────────────────────────────────

    def test_group_list_isolation(self):
        """Manager A sees only Center A groups — not Center B."""
        self._login(self.manager_a)
        resp = self.client.get(self._url(self.center_a, "education:group_list"))
        self.assertEqual(resp.status_code, 200)
        rows = list(resp.context.get("rows") or [])
        row_ids = {getattr(r, "id", None) or r.get("id") for r in rows}
        # page_obj.object_list may be Group instances
        if rows and hasattr(rows[0], "pk"):
            row_ids = {r.pk for r in rows}
        self.assertIn(self.group_a.pk, row_ids)
        self.assertNotIn(self.group_b.pk, row_ids)
        content = resp.content.decode("utf-8", errors="ignore")
        self.assertIn("Group Iso A", content)
        self.assertNotIn("Group Iso B SECRET", content)

    def test_all_groups_overview_isolation(self):
        self._login(self.manager_a)
        resp = self.client.get(self._url(self.center_a, "education:all_groups"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8", errors="ignore")
        self.assertIn("Group Iso A", content)
        self.assertNotIn("Group Iso B SECRET", content)

    def test_teacher_my_groups_isolation(self):
        self._login(self.teacher_a)
        resp = self.client.get(self._url(self.center_a, "education:my_groups"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8", errors="ignore")
        self.assertNotIn("Group Iso B SECRET", content)

    # ── Detail IDOR ─────────────────────────────────────────────────

    def test_group_detail_idor_protection(self):
        self._login(self.teacher_a)
        resp_a = self.client.get(
            self._url(self.center_a, "education:group_detail", self.group_a.id)
        )
        self.assertEqual(resp_a.status_code, 200)

        resp_b = self.client.get(
            self._url(self.center_a, "education:group_detail", self.group_b.id)
        )
        self.assertEqual(resp_b.status_code, 404)

    def test_student_detail_cross_tenant_404(self):
        self._login(self.manager_a)
        ok = self.client.get(
            self._url(self.center_a, "education:student_detail", self.student_a.id)
        )
        self.assertEqual(ok.status_code, 200)
        bad = self.client.get(
            self._url(self.center_a, "education:student_detail", self.student_b.id)
        )
        self.assertEqual(bad.status_code, 404)

    def test_category_detail_cross_tenant_404(self):
        self._login(self.manager_a)
        bad = self.client.get(
            self._url(self.center_a, "education:category_detail", self.cat_b.id)
        )
        self.assertEqual(bad.status_code, 404)

    # ── Create always binds actor center ────────────────────────────

    def test_create_group_center_assignment(self):
        self._login(self.manager_a)
        url = self._url(self.center_a, "education:group_create_lang")
        data = {
            "nom": "New Iso Group A",
            "kurs_narxi": 500000,
            "oqituvchi_foiz": 40,
            "oy_dars_soni": 12,
            "oqituvchi": self.teacher_a.id,
        }
        self.client.post(url, data)
        new_group = Group.objects.filter(nom="New Iso Group A").first()
        self.assertIsNotNone(new_group)
        self.assertEqual(new_group.center_id, self.center_a.id)
        self.assertNotEqual(new_group.center_id, self.center_b.id)

    # ── Finance surfaces ────────────────────────────────────────────

    def test_tolovlar_home_hides_other_center_payment(self):
        self._login(self.manager_a)
        resp = self.client.get(self._url(self.center_a, "education:tolovlar_home"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8", errors="ignore")
        # Unique amount from center B payment must not appear
        self.assertNotIn("123456", content.replace(" ", "").replace(",", ""))
        self.assertNotIn("123 456", content)

    def test_qarzdorlar_home_hides_other_center_student(self):
        self._login(self.manager_a)
        resp = self.client.get(self._url(self.center_a, "education:qarzdorlar_home"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8", errors="ignore")
        self.assertNotIn(self.student_b.email, content)
        # student B full name should not leak as sole identifier of B tenant
        self.assertNotIn("Group Iso B SECRET", content)

    def test_students_with_debt_api_scoped(self):
        self._login(self.manager_a)
        resp = self.client.get(
            self._url(self.center_a, "education:students_with_debt_api")
        )
        # API may return 200 JSON list — must not include student_b
        self.assertIn(resp.status_code, (200, 302, 403))
        if resp.status_code == 200 and "application/json" in (
            resp.headers.get("Content-Type") or ""
        ):
            body = resp.content.decode("utf-8", errors="ignore")
            self.assertNotIn(self.student_b.email, body)
            self.assertNotIn(str(self.student_b.id), body)

    # ── Teacher B cannot read Center A (inverse) ────────────────────

    def test_teacher_b_cannot_open_group_a(self):
        self._login(self.teacher_b)
        resp = self.client.get(
            self._url(self.center_b, "education:group_detail", self.group_a.id)
        )
        self.assertEqual(resp.status_code, 404)

    def test_manager_b_list_excludes_group_a(self):
        self._login(self.manager_b)
        resp = self.client.get(self._url(self.center_b, "education:group_list"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8", errors="ignore")
        self.assertIn("Group Iso B SECRET", content)
        self.assertNotIn("Group Iso A", content)

    # ── ORM-level sanity (defense in depth for services) ────────────

    def test_enrollment_queryset_by_center(self):
        a_ids = set(
            Enrollment.objects.filter(center=self.center_a).values_list("id", flat=True)
        )
        b_ids = set(
            Enrollment.objects.filter(center=self.center_b).values_list("id", flat=True)
        )
        self.assertIn(self.enr_a.id, a_ids)
        self.assertNotIn(self.enr_b.id, a_ids)
        self.assertIn(self.enr_b.id, b_ids)
        self.assertNotIn(self.enr_a.id, b_ids)
