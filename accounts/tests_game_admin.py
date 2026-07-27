"""SuperAdmin Chaqmoq Game panelining testlari."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from game.models import (
    GameCooldown,
    GameMode,
    GameProfile,
    ShopItem,
    Tarif,
    TarifSorovi,
)

User = get_user_model()


class GameAdminAsosi(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_superuser(
            email="su@chaqmoq.uz", password="parol123"
        )
        self.oquvchi = User.objects.create_user(
            email="oyinchi@chaqmoq.uz", password="parol123", ism="Aziz", role="student"
        )
        self.profile = GameProfile.objects.create(user=self.oquvchi)
        self.tarif = Tarif.objects.create(
            nom="Pro", narx_som=15_000, kun=7, jon_soni=3, soat=2, oyin_qulf_soat=6
        )
        self.client = Client(SERVER_NAME="127.0.0.1")
        self.client.force_login(self.superadmin)


class SahifaTests(GameAdminAsosi):
    def test_superadmin_kira_oladi(self):
        res = self.client.get("/platform/game/")
        self.assertEqual(res.status_code, 200)

    def test_oddiy_foydalanuvchi_kira_olmaydi(self):
        oddiy = Client(SERVER_NAME="127.0.0.1")
        oddiy.force_login(self.oquvchi)
        res = oddiy.get("/platform/game/")
        self.assertNotEqual(res.status_code, 200)


class DokonTests(GameAdminAsosi):
    def test_mahsulot_qoshiladi(self):
        res = self.client.post(
            "/platform/game/shop/save/",
            data={"nom": "Ruchka", "tur": "assesuar", "narx_chaqmoq": "12.5"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        item = ShopItem.objects.get(nom="Ruchka")
        self.assertEqual(item.narx_chaqmoq, Decimal("12.5"))

    def test_nomsiz_mahsulot_rad_etiladi(self):
        res = self.client.post(
            "/platform/game/shop/save/",
            data={"nom": "  ", "narx_chaqmoq": "5"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)

    def test_narx_nol_bolsa_rad_etiladi(self):
        res = self.client.post(
            "/platform/game/shop/save/",
            data={"nom": "Bepul", "narx_chaqmoq": "0"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)

    def test_mahsulot_tahrirlanadi(self):
        item = ShopItem.objects.create(nom="Eski", narx_chaqmoq=Decimal("5"))
        self.client.post(
            f"/platform/game/shop/{item.id}/save/",
            data={"nom": "Yangi", "narx_chaqmoq": "20", "tur": "ramka"},
            content_type="application/json",
        )
        item.refresh_from_db()
        self.assertEqual(item.nom, "Yangi")
        self.assertEqual(item.narx_chaqmoq, Decimal("20"))

    def test_sotilgan_mahsulot_ochirilmaydi_faqat_yashiriladi(self):
        """Xaridlar tarixi buzilmasligi kerak."""
        from game.models import Purchase

        item = ShopItem.objects.create(nom="Sotilgan", narx_chaqmoq=Decimal("5"))
        Purchase.objects.create(
            user=self.oquvchi, item=item, narx_chaqmoq=Decimal("5")
        )

        res = self.client.post(f"/platform/game/shop/{item.id}/delete/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["yashirildi"])

        item.refresh_from_db()
        self.assertFalse(item.faol)

    def test_sotilmagan_mahsulot_ochiriladi(self):
        item = ShopItem.objects.create(nom="Yangi", narx_chaqmoq=Decimal("5"))
        self.client.post(f"/platform/game/shop/{item.id}/delete/")
        self.assertFalse(ShopItem.objects.filter(pk=item.pk).exists())


class TolovTests(GameAdminAsosi):
    def _sorov(self):
        return TarifSorovi.objects.create(
            user=self.oquvchi,
            tarif=self.tarif,
            usul=TarifSorovi.USUL_NAQD,
            narx_som=self.tarif.narx_som,
        )

    def test_tasdiqlash_tarifni_yoqadi(self):
        sorov = self._sorov()
        res = self.client.post(
            f"/platform/game/payments/{sorov.id}/",
            data={"amal": "tasdiqlash"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200, res.content)

        sorov.refresh_from_db()
        self.assertEqual(sorov.holat, TarifSorovi.HOLAT_TOLANGAN)

        profile = GameProfile.objects.get(user=self.oquvchi)
        self.assertTrue(profile.pro)
        self.assertEqual(profile.oyin_qulf_soat, 6)

    def test_bekor_qilish(self):
        sorov = self._sorov()
        self.client.post(
            f"/platform/game/payments/{sorov.id}/",
            data={"amal": "bekor"},
            content_type="application/json",
        )
        sorov.refresh_from_db()
        self.assertEqual(sorov.holat, TarifSorovi.HOLAT_BEKOR)
        self.assertFalse(GameProfile.objects.get(user=self.oquvchi).pro)

    def test_ikki_marta_tasdiqlab_bolmaydi(self):
        sorov = self._sorov()
        birinchi = self.client.post(
            f"/platform/game/payments/{sorov.id}/",
            data={"amal": "tasdiqlash"}, content_type="application/json",
        )
        ikkinchi = self.client.post(
            f"/platform/game/payments/{sorov.id}/",
            data={"amal": "tasdiqlash"}, content_type="application/json",
        )
        self.assertEqual(birinchi.status_code, 200)
        self.assertEqual(ikkinchi.status_code, 409)


class LimitTests(GameAdminAsosi):
    def _grant(self, **body):
        return self.client.post(
            f"/platform/game/players/{self.profile.id}/grant/",
            data=body,
            content_type="application/json",
        )

    def test_jon_qoshiladi(self):
        oldin = GameProfile.objects.get(pk=self.profile.pk).joriy_jon
        res = self._grant(amal="jon", soni=5)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()["holat"]["jon"], oldin + 5)

    def test_chaqmoq_qoshiladi(self):
        res = self._grant(amal="chaqmoq", miqdor="10")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["holat"]["chaqmoq"], 10.0)

    def test_qulf_ochiladi(self):
        mode = GameMode.objects.create(nom="Test", motor="viktorina", savollar_soni=5)
        GameCooldown.objects.create(profile=self.profile, mode=mode)

        res = self._grant(amal="qulf")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(GameCooldown.objects.filter(profile=self.profile).exists())

    def test_tarif_sovga_qilinadi(self):
        res = self._grant(amal="tarif", tarif_id=self.tarif.id)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()["holat"]["tarif"], "Pro")

        profile = GameProfile.objects.get(pk=self.profile.pk)
        self.assertTrue(profile.pro)

    def test_mavjud_tarif_uzaytiriladi(self):
        """Ikki marta sovg'a qilinsa muddat qo'shiladi, yo'qolmaydi."""
        self._grant(amal="tarif", tarif_id=self.tarif.id)
        self._grant(amal="tarif", tarif_id=self.tarif.id)

        profile = GameProfile.objects.get(pk=self.profile.pk)
        qolgan = (profile.obuna.tugaydi - timezone.now()).days
        self.assertGreaterEqual(qolgan, 13)

    def test_nomalum_amal_rad_etiladi(self):
        self.assertEqual(self._grant(amal="hech_narsa").status_code, 400)


class QidiruvTests(GameAdminAsosi):
    def test_ism_boyicha_topiladi(self):
        res = self.client.get("/platform/game/players/search/?q=Aziz")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["oyinchilar"]), 1)

    def test_robot_royxatga_tushmaydi(self):
        GameProfile.objects.create(robot=True, robot_ism="Robot")
        res = self.client.get("/platform/game/players/search/")
        ismlar = [o["ism"] for o in res.json()["oyinchilar"]]
        self.assertNotIn("Robot", ismlar)
