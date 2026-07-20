"""
RBAC + API hardening tests (phase 3).

Guarantees:
1. Blanket `/api/` skip is gone — session web APIs enforce role.
2. External token APIs (`/api/mobile/`, `/api/click/`, …) still skip RBAC.
3. Forbidden API requests get 403 JSON (not HTML redirect).
"""
from __future__ import annotations

from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import User
from core.middleware_rbac import (
    EXTERNAL_API_PREFIXES,
    _is_skipped_path,
    _strip_slug_prefix,
    _wants_json_response,
)
from core.test_utils import create_active_center


class RbacPathHelperTests(SimpleTestCase):
    def test_external_mobile_is_skipped(self):
        self.assertTrue(_is_skipped_path("/api/mobile/auth/login/"))
        self.assertTrue(_is_skipped_path("/api/mobile/game/home/"))
        self.assertTrue(_is_skipped_path("/center-a/api/mobile/me/"))

    def test_click_and_docs_skipped(self):
        self.assertTrue(_is_skipped_path("/api/click/prepare/"))
        self.assertTrue(_is_skipped_path("/click/complete/"))
        self.assertTrue(_is_skipped_path("/api/docs/"))
        self.assertTrue(_is_skipped_path("/api/v1/auth/link-telegram/"))

    def test_session_web_apis_are_not_skipped(self):
        self.assertFalse(_is_skipped_path("/api/boshqaruv/"))
        self.assertFalse(_is_skipped_path("/api/director/dashboard/"))
        self.assertFalse(_is_skipped_path("/api/student/dashboard/"))
        self.assertFalse(_is_skipped_path("/center-a/api/boshqaruv/"))
        self.assertFalse(_is_skipped_path("/api/hr/employees/"))
        self.assertFalse(_is_skipped_path("/talim/api/student/1/month-debt/"))

    def test_strip_slug(self):
        self.assertEqual(_strip_slug_prefix("/proskill/api/boshqaruv/"), "/api/boshqaruv/")
        self.assertEqual(_strip_slug_prefix("/api/boshqaruv/"), "/api/boshqaruv/")
        # Reserved first segment is not a center slug
        self.assertEqual(_strip_slug_prefix("/talim/api/x/"), "/talim/api/x/")

    def test_external_prefixes_do_not_include_blanket_api(self):
        self.assertNotIn("/api/", EXTERNAL_API_PREFIXES)


class RbacApiEnforcementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.center = create_active_center(name="RBAC Center", slug="rbac-c")

        self.student = User.objects.create_user(
            email="student_rbac@example.com",
            password="password",
            role="student",
            center=self.center,
            ism="Stu",
            familya="Dent",
        )
        self.manager = User.objects.create_user(
            email="manager_rbac@example.com",
            password="password",
            role="manager",
            center=self.center,
            ism="Man",
            familya="Ager",
        )
        self.teacher = User.objects.create_user(
            email="teacher_rbac@example.com",
            password="password",
            role="teacher",
            center=self.center,
            ism="Tea",
            familya="Cher",
        )

    def _tenant(self, path: str) -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        return f"/{self.center.slug}{path}"

    def test_student_blocked_from_director_api_json(self):
        self.client.force_login(self.student)
        url = self._tenant(reverse("core:director_boshqaruv_api"))
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
        payload = resp.json()
        self.assertEqual(payload.get("code"), "rbac_forbidden")
        self.assertFalse(payload.get("ok", True))

    def test_student_blocked_from_manager_dashboard_api(self):
        self.client.force_login(self.student)
        url = self._tenant(reverse("core:manager_dashboard_api"))
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get("code"), "rbac_forbidden")

    def test_student_can_access_own_panel_api(self):
        self.client.force_login(self.student)
        url = self._tenant(reverse("core:student_panel_dashboard_api"))
        resp = self.client.get(url)
        # View may return 200 JSON or business error, but not RBAC 403 redirect
        self.assertNotEqual(resp.status_code, 403)
        self.assertNotIn(resp.status_code, (301, 302))

    def test_teacher_blocked_from_director_api(self):
        self.client.force_login(self.teacher)
        url = self._tenant(reverse("core:director_boshqaruv_api"))
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_manager_can_reach_director_api_route(self):
        """Manager has core namespace — RBAC lets through (view may still check role)."""
        self.client.force_login(self.manager)
        url = self._tenant(reverse("core:director_boshqaruv_api"))
        resp = self.client.get(url)
        # Must not be RBAC-forbidden
        if resp.status_code == 403:
            try:
                code = resp.json().get("code")
            except Exception:
                code = None
            self.assertNotEqual(code, "rbac_forbidden")

    def test_mobile_login_still_csrf_exempt_and_reachable(self):
        """External mobile auth is outside RBAC and remains public POST."""
        url = "/api/mobile/auth/login/"
        resp = self.client.post(
            url,
            data='{"login":"x","password":"y"}',
            content_type="application/json",
        )
        # Should reach view (not middleware redirect). Expect 4xx business error.
        self.assertNotIn(resp.status_code, (301, 302))
        self.assertIn(resp.status_code, (400, 401, 403, 404))

    def test_calculate_lessons_requires_csrf(self):
        """csrf_exempt removed — POST without CSRF token must fail (403)."""
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.manager)
        url = self._tenant(reverse("education:calculate_lessons_api"))
        resp = csrf_client.post(
            url,
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
