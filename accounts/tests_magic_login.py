"""Magic login (bir-bosishli kirish havolasi) testlari."""
from django.test import TestCase
from django.urls import reverse

from accounts.models import Center, User
from accounts.magic_login import make_magic_token, read_magic_token


class MagicTokenTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Test Markaz", slug="test-markaz")
        self.user = User.objects.create_user(
            email="ota@example.com", password="oldpass1", role="parent",
            center=self.center, ism="Ali", familya="Valiyev", telefon1="+998901112233",
        )

    def test_roundtrip_returns_user(self):
        token = make_magic_token(self.user)
        self.assertEqual(read_magic_token(token), self.user)

    def test_tampered_token_rejected(self):
        token = make_magic_token(self.user)
        self.assertIsNone(read_magic_token(token + "x"))

    def test_expired_token_rejected(self):
        token = make_magic_token(self.user)
        self.assertIsNone(read_magic_token(token, max_age=-1))

    def test_stale_after_password_change(self):
        token = make_magic_token(self.user)
        self.user.set_password("brandnew2")
        self.user.save(update_fields=["password"])
        # Parol o'zgardi → eski havola kuchsizlanadi.
        self.assertIsNone(read_magic_token(token))

    def test_inactive_user_rejected(self):
        token = make_magic_token(self.user)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertIsNone(read_magic_token(token))


class MagicLoginViewTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Test Markaz", slug="test-markaz")
        self.user = User.objects.create_user(
            email="oquvchi@example.com", password="oldpass1", role="student",
            center=self.center, ism="Vali", familya="Aliyev", telefon1="+998901112244",
        )

    def test_valid_link_logs_in_and_redirects_to_set_password(self):
        url = reverse("magic_login", kwargs={"token": make_magic_token(self.user)})
        resp = self.client.get(url)
        self.assertRedirects(resp, reverse("magic_set_password"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.id)

    def test_invalid_link_shows_expired_page(self):
        url = reverse("magic_login", kwargs={"token": "not-a-real-token"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)
        self.assertTemplateUsed(resp, "accounts/magic_expired.html")

    def test_set_password_keeps_user_logged_in(self):
        # 1) magic link orqali kirish
        self.client.get(reverse("magic_login", kwargs={"token": make_magic_token(self.user)}))
        # 2) yangi parol o'rnatish
        resp = self.client.post(reverse("magic_set_password"),
                                {"password": "yangi123", "confirm_password": "yangi123"})
        # Bosh sahifaga (markaz) yo'naltiriladi va tizimda qoladi
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, f"/{self.center.slug}/")
        self.assertIn("_auth_user_id", self.client.session)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("yangi123"))

    def test_set_password_rejects_weak(self):
        self.client.get(reverse("magic_login", kwargs={"token": make_magic_token(self.user)}))
        resp = self.client.post(reverse("magic_set_password"),
                                {"password": "abc", "confirm_password": "abc"})
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password("abc"))

    def test_set_password_requires_auth(self):
        resp = self.client.get(reverse("magic_set_password"))
        self.assertRedirects(resp, reverse("login"), target_status_code=200)
