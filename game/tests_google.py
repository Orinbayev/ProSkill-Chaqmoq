"""Google orqali ro'yxatdan o'tish va mustaqil o'yinchi profili testlari."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from game.google_auth import GoogleXatosi, foydalanuvchini_top_yoki_yarat
from game.models import GameProfile

User = get_user_model()

GOOGLE_MALUMOT = {
    "sub": "google-123",
    "email": "yangi@gmail.com",
    "ism": "Aziz",
    "familya": "Yusupov",
    "rasm": "",
}


@override_settings(GOOGLE_OAUTH_CLIENT_IDS="test-client-id")
class GoogleKirishTests(TestCase):
    def _kirish(self, malumot=None, token="fake-token"):
        with patch("game.mobile_api.google_tokenni_tekshir", return_value=malumot or GOOGLE_MALUMOT):
            return self.client.post(
                "/api/mobile/game/auth/google/",
                data={"id_token": token},
                content_type="application/json",
            )

    def test_yangi_foydalanuvchi_yaratiladi(self):
        res = self._kirish()
        self.assertEqual(res.status_code, 200, res.content)

        javob = res.json()
        self.assertTrue(javob["yangi"])
        self.assertIn("access_token", javob)

        user = User.objects.get(email="yangi@gmail.com")
        self.assertTrue(user.game_only)
        self.assertIsNone(user.center)
        self.assertTrue(GameProfile.objects.filter(user=user).exists())

    def test_ikkinchi_kirishda_yangi_yaratilmaydi(self):
        self._kirish()
        res = self._kirish()
        self.assertFalse(res.json()["yangi"])
        self.assertEqual(User.objects.filter(email="yangi@gmail.com").count(), 1)

    def test_profil_toliq_emas_deb_belgilanadi(self):
        """Yosh kiritilmaguncha profil to'liq emas."""
        javob = self._kirish().json()
        self.assertFalse(javob["profil"]["toliq"])

    def test_markaz_hisobi_oyinga_aylanmaydi(self):
        """Shu email bilan o'quv markazi o'quvchisi bo'lsa, u o'z hisobiga kiradi."""
        from accounts.models import Center

        center = Center.objects.create(name="Markaz", slug="markaz-test")
        User.objects.create_user(
            email="yangi@gmail.com", password="parol123",
            ism="Bor", familya="O'quvchi", role="student", center=center,
        )

        res = self._kirish()
        self.assertEqual(res.status_code, 200)

        user = User.objects.get(email="yangi@gmail.com")
        self.assertFalse(user.game_only)
        self.assertEqual(user.center_id, center.id)

    @override_settings(GOOGLE_OAUTH_CLIENT_IDS="")
    def test_sozlanmagan_bolsa_aniq_xabar(self):
        res = self.client.post(
            "/api/mobile/game/auth/google/",
            data={"id_token": "x"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["code"], "google_sozlanmagan")

    def test_notogri_token_rad_etiladi(self):
        with patch(
            "game.mobile_api.google_tokenni_tekshir",
            side_effect=GoogleXatosi("Token yaroqsiz", "token_notogri"),
        ):
            res = self.client.post(
                "/api/mobile/game/auth/google/",
                data={"id_token": "yomon"},
                content_type="application/json",
            )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["code"], "token_notogri")


class ProfilToldirishTests(TestCase):
    def setUp(self):
        self.user, _ = foydalanuvchini_top_yoki_yarat(GOOGLE_MALUMOT)
        GameProfile.objects.get_or_create(user=self.user)
        self.client.force_login(self.user)

    def test_ism_familya_yosh_saqlanadi(self):
        res = self.client.post(
            "/api/mobile/game/auth/profile/",
            data={"ism": "Aziz", "familya": "Yusupov", "yosh": 14},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200, res.content)

        profil = res.json()["profil"]
        self.assertTrue(profil["toliq"])
        self.assertEqual(profil["yosh"], 14)

    def test_qisqa_ism_rad_etiladi(self):
        res = self.client.post(
            "/api/mobile/game/auth/profile/",
            data={"ism": "A", "familya": "Yusupov", "yosh": 14},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "ism_qisqa")

    def test_notogri_yosh_rad_etiladi(self):
        res = self.client.post(
            "/api/mobile/game/auth/profile/",
            data={"ism": "Aziz", "familya": "Yusupov", "yosh": 200},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "yosh_notogri")

    def test_markaz_oquvchisi_bu_endpointdan_foydalanmaydi(self):
        markaz_oquvchi = User.objects.create_user(
            email="markaz@chaqmoq.uz", password="parol123",
            ism="Markaz", familya="O'quvchi", role="student",
        )
        GameProfile.objects.create(user=markaz_oquvchi)
        self.client.force_login(markaz_oquvchi)

        res = self.client.post(
            "/api/mobile/game/auth/profile/",
            data={"ism": "Yangi", "familya": "Ism", "yosh": 14},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 403)

    def test_me_endpointi_profil_va_oyin_holatini_beradi(self):
        res = self.client.get("/api/mobile/game/me/")
        self.assertEqual(res.status_code, 200)
        javob = res.json()
        self.assertIn("profil", javob)
        self.assertIn("oyin", javob)
        self.assertIn("orin", javob)


class MarkazsizReytingTests(TestCase):
    """O'yin reytingi barcha markazlar va mustaqil o'yinchilarni birlashtiradi."""

    def setUp(self):
        from accounts.models import Center

        self.center = Center.objects.create(name="Markaz", slug="reyting-markaz")

        self.markazli = User.objects.create_user(
            email="markazli@chaqmoq.uz", password="x", ism="Markazli",
            role="student", center=self.center,
        )
        GameProfile.objects.create(user=self.markazli, center=self.center, hafta_xp=100)

        self.mustaqil, _ = foydalanuvchini_top_yoki_yarat(GOOGLE_MALUMOT)
        GameProfile.objects.create(user=self.mustaqil, center=None, hafta_xp=50)

    def test_mustaqil_oyinchida_doira_umumiy(self):
        self.client.force_login(self.mustaqil)
        javob = self.client.get("/api/mobile/game/league/").json()

        self.assertEqual(javob["doira"], "umumiy")
        self.assertFalse(javob["markaz_bor"])

    def test_umumiy_reytingda_ikkalasi_ham_korinadi(self):
        self.client.force_login(self.mustaqil)
        javob = self.client.get("/api/mobile/game/league/").json()

        ismlar = [q["ism"] for q in javob["qatorlar"]]
        self.assertIn("Markazli", ismlar)
        self.assertIn("Aziz", ismlar)

    def test_markazli_oquvchida_doira_almashtirgich_bor(self):
        self.client.force_login(self.markazli)
        javob = self.client.get("/api/mobile/game/league/").json()

        self.assertEqual(javob["doira"], "markaz")
        self.assertTrue(javob["markaz_bor"])

    def test_markaz_doirasida_mustaqil_oyinchi_korinmaydi(self):
        self.client.force_login(self.markazli)
        javob = self.client.get("/api/mobile/game/league/?doira=markaz").json()

        ismlar = [q["ism"] for q in javob["qatorlar"]]
        self.assertNotIn("Aziz", ismlar)
