"""Phase 4: mobile access token TTL, refresh rotation, revoke."""
from __future__ import annotations

from datetime import timedelta

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from core.models import MobileAccessToken
from core.mobile_api import (
    _create_mobile_access_token,
    _hash_token,
    _mobile_token_lifetime_days,
    _token_effective_expires_at,
)
from core.test_utils import create_active_center


@override_settings(MOBILE_ACCESS_TOKEN_DAYS=30, MOBILE_ACCESS_TOKEN_MAX_PER_USER=3)
class MobileTokenTtlTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.center = create_active_center(name="Token TTL Center", slug="ttl-c")
        self.user = User.objects.create_user(
            email="token_ttl@example.com",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Tok",
            familya="En",
        )

    def _login(self, **extra):
        payload = {
            "login": "token_ttl@example.com",
            "password": "testpass123",
            "center_slug": self.center.slug,
            "device_name": extra.get("device_name", "TestPhone"),
            "device_platform": extra.get("device_platform", "android"),
        }
        import json

        resp = self.client.post(
            "/api/mobile/auth/login/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()

    def test_login_token_lifetime_is_about_30_days_not_180(self):
        self.assertEqual(_mobile_token_lifetime_days(), 30)
        payload = self._login()
        self.assertIn("access_token", payload)
        self.assertIn("expires_at", payload)
        self.assertIn("expires_in", payload)
        self.assertEqual(payload.get("token_lifetime_days"), 30)

        expires_in = int(payload["expires_in"])
        # ~30 days in seconds, allow clock skew window
        self.assertGreater(expires_in, 29 * 24 * 3600)
        self.assertLess(expires_in, 31 * 24 * 3600)

        token_row = MobileAccessToken.objects.get(
            key_hash=_hash_token(payload["access_token"])
        )
        delta = token_row.expires_at - token_row.created_at
        self.assertLessEqual(delta.days, 30)
        self.assertGreaterEqual(delta.days, 29)

    def test_legacy_180_day_token_is_clamped_on_use(self):
        raw = "legacy-raw-token-value-aaaaaaaa"
        token = MobileAccessToken.objects.create(
            user=self.user,
            center=self.center,
            key_prefix=raw[:16],
            key_hash=_hash_token(raw),
            device_name="Old",
            device_platform="ios",
            expires_at=timezone.now() + timedelta(days=180),
        )
        # Force created_at to "now" via update (auto_now_add otherwise)
        MobileAccessToken.objects.filter(pk=token.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )
        token.refresh_from_db()

        effective = _token_effective_expires_at(token)
        # created 40 days ago + 30 day policy → already expired
        self.assertLessEqual(effective, timezone.now())

        resp = self.client.get(
            "/api/mobile/me/",
            HTTP_AUTHORIZATION=f"Bearer {raw}",
        )
        self.assertEqual(resp.status_code, 401)

    def test_refresh_rotates_token_and_revokes_old(self):
        payload = self._login()
        old_raw = payload["access_token"]
        old_row = MobileAccessToken.objects.get(key_hash=_hash_token(old_raw))

        refresh = self.client.post(
            "/api/mobile/auth/refresh/",
            data="{}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {old_raw}",
        )
        self.assertEqual(refresh.status_code, 200)
        new_payload = refresh.json()
        new_raw = new_payload["access_token"]
        self.assertNotEqual(new_raw, old_raw)

        old_row.refresh_from_db()
        self.assertTrue(old_row.is_revoked)

        # Old token no longer works
        dead = self.client.get(
            "/api/mobile/me/",
            HTTP_AUTHORIZATION=f"Bearer {old_raw}",
        )
        self.assertEqual(dead.status_code, 401)

        # New token works
        ok = self.client.get(
            "/api/mobile/me/",
            HTTP_AUTHORIZATION=f"Bearer {new_raw}",
        )
        self.assertEqual(ok.status_code, 200)

    def test_logout_revokes_token(self):
        payload = self._login()
        raw = payload["access_token"]
        out = self.client.post(
            "/api/mobile/auth/logout/",
            data="{}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw}",
        )
        self.assertEqual(out.status_code, 200)
        self.assertFalse(out.json().get("authenticated", True))

        me = self.client.get(
            "/api/mobile/me/",
            HTTP_AUTHORIZATION=f"Bearer {raw}",
        )
        self.assertEqual(me.status_code, 401)

    def test_logout_all_revokes_every_session(self):
        p1 = self._login(device_name="PhoneA")
        p2 = self._login(device_name="PhoneB")
        r1, r2 = p1["access_token"], p2["access_token"]

        resp = self.client.post(
            "/api/mobile/auth/logout-all/",
            data="{}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {r1}",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json().get("revoked_count", 0), 1)

        for raw in (r1, r2):
            me = self.client.get(
                "/api/mobile/me/",
                HTTP_AUTHORIZATION=f"Bearer {raw}",
            )
            self.assertEqual(me.status_code, 401)

    def test_sessions_list_and_revoke_by_id(self):
        p1 = self._login(device_name="PhoneA")
        p2 = self._login(device_name="PhoneB")
        r2 = p2["access_token"]

        listing = self.client.get(
            "/api/mobile/auth/sessions/",
            HTTP_AUTHORIZATION=f"Bearer {r2}",
        )
        self.assertEqual(listing.status_code, 200)
        sessions = listing.json()["sessions"]
        self.assertGreaterEqual(len(sessions), 2)

        # Revoke the non-current session
        other = next(s for s in sessions if not s["is_current"])
        rev = self.client.post(
            f"/api/mobile/auth/sessions/{other['id']}/revoke/",
            data="{}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {r2}",
        )
        self.assertEqual(rev.status_code, 200)
        self.assertTrue(rev.json()["ok"])
        self.assertFalse(rev.json()["was_current"])

        # Current token still works
        me = self.client.get(
            "/api/mobile/me/",
            HTTP_AUTHORIZATION=f"Bearer {r2}",
        )
        self.assertEqual(me.status_code, 200)

    def test_max_per_user_prunes_oldest(self):
        # MAX_PER_USER = 3
        tokens = []
        for i in range(5):
            payload = self._login(device_name=f"Device{i}")
            tokens.append(payload["access_token"])

        active = MobileAccessToken.objects.filter(
            user=self.user, is_revoked=False
        ).count()
        self.assertLessEqual(active, 3)

        # Oldest logins should be dead
        for raw in tokens[:2]:
            me = self.client.get(
                "/api/mobile/me/",
                HTTP_AUTHORIZATION=f"Bearer {raw}",
            )
            self.assertEqual(me.status_code, 401)

        # Newest should live
        me = self.client.get(
            "/api/mobile/me/",
            HTTP_AUTHORIZATION=f"Bearer {tokens[-1]}",
        )
        self.assertEqual(me.status_code, 200)
