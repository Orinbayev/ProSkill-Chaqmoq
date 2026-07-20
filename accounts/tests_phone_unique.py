"""Phase 6: unique login phone among alive users."""
from __future__ import annotations

from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import User
from core.test_utils import create_active_center


class LoginPhoneUniqueTests(TestCase):
    def setUp(self):
        self.center = create_active_center(name="Phone Unique Center", slug="phone-u")

    def _user(self, email: str, phone: str | None, **extra):
        return User.objects.create_user(
            email=email,
            password="pass12345",
            role=extra.pop("role", "student"),
            center=self.center,
            ism=extra.pop("ism", "U"),
            familya=extra.pop("familya", "Ser"),
            phone_number=phone,
            **extra,
        )

    def test_empty_phone_stored_as_null_and_many_allowed(self):
        u1 = self._user("a@phone.test", "")
        u2 = self._user("b@phone.test", None)
        u1.refresh_from_db()
        u2.refresh_from_db()
        self.assertIsNone(u1.phone_number)
        self.assertIsNone(u2.phone_number)

    def test_duplicate_alive_phone_rejected(self):
        self._user("a@phone.test", "+998901112233")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._user("b@phone.test", "90 111 22 33")  # same after normalize

    def test_login_phone_taken_helper(self):
        u = self._user("a@phone.test", "+998901112233")
        self.assertTrue(User.login_phone_taken("+998901112233"))
        self.assertTrue(User.login_phone_taken("901112233"))
        self.assertFalse(User.login_phone_taken("+998901112233", exclude_pk=u.pk))
        self.assertFalse(User.login_phone_taken("+998909999999"))

    def test_soft_deleted_user_frees_phone(self):
        u1 = self._user("a@phone.test", "+998901112233")
        u1.delete()  # soft delete
        # Same phone can be used by a new alive user
        u2 = self._user("b@phone.test", "+998901112233")
        self.assertEqual(u2.phone_number, "+998901112233")
        self.assertTrue(User.all_objects.filter(pk=u1.pk, is_deleted=True).exists())

    def test_normalize_on_save(self):
        u = self._user("a@phone.test", "90-111-22-33")
        u.refresh_from_db()
        self.assertEqual(u.phone_number, "+998901112233")
