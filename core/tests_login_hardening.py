"""Phase 5: login enumeration + rate limit hardening."""
from __future__ import annotations

import json

from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase, override_settings

from accounts.auth_helpers import resolve_login_attempt
from accounts.login_throttle import (
    clear_failed_login,
    is_login_locked,
    login_max_failed_attempts,
    register_failed_login,
)
from accounts.models import User
from core.test_utils import create_active_center


@override_settings(
    LOGIN_MAX_FAILED_ATTEMPTS=3,
    LOGIN_THROTTLE_WINDOW_SECONDS=600,
    LOGIN_IP_MAX_FAILED_ATTEMPTS=100,
)
class LoginHardeningTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.factory = RequestFactory()
        self.center = create_active_center(name="Login Hard Center", slug="login-h")
        self.user = User.objects.create_user(
            email="login_hard@example.com",
            password="correct-pass",
            role="student",
            center=self.center,
            ism="Log",
            familya="In",
            is_active=True,
        )
        self.inactive = User.objects.create_user(
            email="inactive_hard@example.com",
            password="correct-pass",
            role="student",
            center=self.center,
            ism="In",
            familya="Active",
            is_active=False,
        )

    def _post_login(self, login: str, password: str, **extra):
        body = {"login": login, "password": password, "center_slug": self.center.slug}
        body.update(extra)
        return self.client.post(
            "/api/mobile/auth/login/",
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_missing_user_and_wrong_password_same_public_code(self):
        missing = self._post_login("nope@example.com", "whatever")
        wrong = self._post_login("login_hard@example.com", "wrong-pass")
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(missing.json()["code"], "invalid_credentials")
        self.assertEqual(wrong.json()["code"], "invalid_credentials")
        self.assertEqual(missing.json()["error"], wrong.json()["error"])

    def test_inactive_with_wrong_password_looks_like_invalid_credentials(self):
        resp = self._post_login("inactive_hard@example.com", "wrong-pass")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "invalid_credentials")

    def test_inactive_with_correct_password_reports_inactive(self):
        result = resolve_login_attempt(
            "inactive_hard@example.com", "correct-pass", center=self.center
        )
        self.assertIsNone(result.user)
        self.assertEqual(result.code, "inactive_user")

        resp = self._post_login("inactive_hard@example.com", "correct-pass")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], "inactive_user")

    def test_rate_limit_locks_after_max_failures(self):
        max_attempts = login_max_failed_attempts()
        self.assertEqual(max_attempts, 3)

        for i in range(max_attempts):
            resp = self._post_login("login_hard@example.com", f"bad-{i}")
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(resp.json()["code"], "invalid_credentials")

        locked = self._post_login("login_hard@example.com", "correct-pass")
        self.assertEqual(locked.status_code, 429)
        self.assertEqual(locked.json()["code"], "rate_limited")

        # Even correct password is blocked while locked
        still = self._post_login("login_hard@example.com", "correct-pass")
        self.assertEqual(still.status_code, 429)

    def test_success_clears_identifier_throttle(self):
        # Two failures then success → counter cleared
        self._post_login("login_hard@example.com", "bad-1")
        self._post_login("login_hard@example.com", "bad-2")
        ok = self._post_login("login_hard@example.com", "correct-pass")
        self.assertEqual(ok.status_code, 200)

        # Fresh failures allowed again (not still locked from previous)
        for i in range(2):
            resp = self._post_login("login_hard@example.com", f"again-{i}")
            self.assertEqual(resp.status_code, 401)

    def test_throttle_helpers_ip_and_identifier(self):
        request = self.factory.post("/api/mobile/auth/login/")
        request.META["REMOTE_ADDR"] = "203.0.113.10"
        self.assertFalse(is_login_locked(request, "login_hard@example.com"))
        register_failed_login(request, "login_hard@example.com")
        register_failed_login(request, "login_hard@example.com")
        register_failed_login(request, "login_hard@example.com")
        self.assertTrue(is_login_locked(request, "login_hard@example.com"))
        clear_failed_login(request, "login_hard@example.com")
        self.assertFalse(is_login_locked(request, "login_hard@example.com"))
