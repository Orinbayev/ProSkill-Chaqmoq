"""Chaqmoq Game — iqtisodiyot qoidalari testlari.

Bu yerdagi raqamlar mahsulot qarori: chaqmoq mukofoti, jon limiti, tarif
tiklanishi. Ular tasodifan o'zgarib ketmasligi kerak — shuning uchun test.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from game.models import (
    BEPUL_JON,
    SAVOLLAR_SONI,
    Duel,
    GameProfile,
    Obuna,
    Question,
    QuestionCategory,
    Tarif,
    chaqmoq_mukofoti,
)
from game.services import _robot_javoblari, ball_hisobla

User = get_user_model()


class ChaqmoqMukofotiTests(TestCase):
    """10 ta savoldan nechta to'g'ri → nechta chaqmoq."""

    def test_hammasi_togri_3_chaqmoq(self):
        self.assertEqual(chaqmoq_mukofoti(10), Decimal("3.0"))

    def test_saksondan_yuqori_2_chaqmoq(self):
        self.assertEqual(chaqmoq_mukofoti(9), Decimal("2.0"))
        self.assertEqual(chaqmoq_mukofoti(8), Decimal("2.0"))

    def test_yarmi_1_chaqmoq(self):
        self.assertEqual(chaqmoq_mukofoti(7), Decimal("1.0"))
        self.assertEqual(chaqmoq_mukofoti(5), Decimal("1.0"))

    def test_beshdan_kam_yarim_chaqmoq(self):
        self.assertEqual(chaqmoq_mukofoti(4), Decimal("0.5"))
        self.assertEqual(chaqmoq_mukofoti(0), Decimal("0.5"))


class BallTests(TestCase):
    def test_har_togri_javob_1_ball(self):
        # Vaqtdan qat'i nazar har to'g'ri javob aniq 1 ball.
        self.assertEqual(ball_hisobla(True, 0), 1)
        self.assertEqual(ball_hisobla(True, 10_000), 1)

    def test_notogri_javob_ball_bermaydi(self):
        self.assertEqual(ball_hisobla(False, 1000), 0)


class RobotTests(TestCase):
    def test_robot_mahoratiga_mos_javob_beradi(self):
        """0.7 mahoratli robot 10 tadan taxminan 7 tasiga to'g'ri javob beradi."""
        robot = GameProfile(robot=True, robot_ism="Test", maxorat=0.7)

        natijalar = [
            sum(1 for togri, _ in _robot_javoblari(robot, SAVOLLAR_SONI) if togri)
            for _ in range(200)
        ]
        o_rtacha = sum(natijalar) / len(natijalar)

        # O'rtacha 7 ga yaqin bo'lsin, lekin har duel bir xil bo'lmasin.
        self.assertAlmostEqual(o_rtacha, 7.0, delta=0.5)
        self.assertGreater(len(set(natijalar)), 1, "Robot har duelda bir xil o'ynayapti")

    def test_javoblar_soni_savollar_soniga_teng(self):
        robot = GameProfile(robot=True, robot_ism="Test", maxorat=0.9)
        javoblar = _robot_javoblari(robot, SAVOLLAR_SONI)
        self.assertEqual(len(javoblar), SAVOLLAR_SONI)


class DuelJavobTests(TestCase):
    """Raqibning bali bosqichma-bosqich ochilishi kerak.

    Regressiya: avval `raqib_jami` sifatida robotning 10 ta savol bo'yicha
    YAKUNIY bali qaytarilardi — natijada birinchi javobdanoq raqibning butun
    hisobi ko'rinib qolar va duelning poyga hissi yo'qolardi.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email="duel@chaqmoq.uz", password="parol123", ism="Test", role="student"
        )
        GameProfile.objects.create(user=self.user)
        GameProfile.objects.create(robot=True, robot_ism="Robot", maxorat=0.8)

        kategoriya = QuestionCategory.objects.create(nom="Test", daraja="A1")
        for i in range(SAVOLLAR_SONI):
            Question.objects.create(
                kategoriya=kategoriya,
                savol=f"word{i}",
                togri_javob=f"togri{i}",
                notogri_1="a", notogri_2="b", notogri_3="c",
            )

        self.client.force_login(self.user)

    def test_raqib_bali_bosqichma_bosqich_osadi(self):
        res = self.client.post("/api/mobile/game/duel/start/", content_type="application/json")
        self.assertEqual(res.status_code, 200, res.content)
        duel = res.json()

        oldingi = 0
        yakuniy = Duel.objects.get(id=duel["duel_id"]).raqib_ball

        for savol in duel["savollar"]:
            javob = self.client.post(
                f"/api/mobile/game/duel/{duel['duel_id']}/answer/",
                data={"tartib": savol["tartib"], "tanlangan": "x", "sarflangan_ms": 3000},
                content_type="application/json",
            ).json()

            jami = javob["raqib_jami"]
            self.assertGreaterEqual(jami, oldingi, "Raqib bali kamayib ketdi")
            self.assertLessEqual(jami, yakuniy, "Raqib bali yakuniy baldan oshib ketdi")

            if savol["tartib"] < SAVOLLAR_SONI:
                self.assertLess(
                    jami, yakuniy + 1,
                    "Yakuniy bal muddatidan oldin ochilib qoldi",
                )
            oldingi = jami

        # Oxirgi savoldan keyin raqibning bali to'liq ochilgan bo'lishi kerak.
        self.assertEqual(oldingi, yakuniy)


class DostlikTests(TestCase):
    """Robotga do'stlik yuborilsa avtomatik qabul bo'ladi.

    Robot javob bera olmaydi — agar so'rov "kutilmoqda"da qolsa, foydalanuvchi
    hech qachon robotni do'st sifatida qo'sha olmasdi. Shuning uchun darhol qabul.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email="odam@chaqmoq.uz", password="parol123", ism="Odam", role="student"
        )
        GameProfile.objects.create(user=self.user)

        # Robot — login qila olmaydigan hisob bilan.
        bot_user = User.objects.create_user(
            email="bot@chaqmoq.game", password="x", ism="Zarina",
            role="student", is_active=False,
        )
        self.robot = GameProfile.objects.create(
            user=bot_user, robot=True, robot_ism="Zarina", maxorat=0.7
        )

        self.client.force_login(self.user)

    def test_robotga_dostlik_avtomatik_qabul(self):
        res = self.client.post(
            f"/api/mobile/game/friends/{self.robot.user_id}/request/",
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()["holat"], "qabul")

        # Do'stlar ro'yxatida darhol ko'rinadi.
        res = self.client.get("/api/mobile/game/friends/")
        dostlar = res.json()["dostlar"]
        self.assertEqual(len(dostlar), 1)
        self.assertEqual(dostlar[0]["ism"], "Zarina")

    def test_odamga_dostlik_kutilmoqda(self):
        boshqa = User.objects.create_user(
            email="boshqa@chaqmoq.uz", password="x", ism="Boshqa", role="student"
        )
        GameProfile.objects.create(user=boshqa)

        res = self.client.post(
            f"/api/mobile/game/friends/{boshqa.id}/request/",
            content_type="application/json",
        )
        self.assertEqual(res.json()["holat"], "kutilmoqda")

        # Hali do'st emas — so'rov javob kutmoqda.
        res = self.client.get("/api/mobile/game/friends/")
        self.assertEqual(len(res.json()["dostlar"]), 0)


class OnlaynTests(TestCase):
    """Onlayn o'yinchilar ro'yxati — do'stlik/duel taklifi uchun."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="men@chaqmoq.uz", password="parol123", ism="Men", role="student"
        )
        GameProfile.objects.create(user=self.user)

        bot_user = User.objects.create_user(
            email="bot@chaqmoq.game", password="x", ism="Robot1",
            role="student", is_active=False,
        )
        self.robot = GameProfile.objects.create(
            user=bot_user, robot=True, robot_ism="Robot1", maxorat=0.7
        )
        self.client.force_login(self.user)

    def test_robotlar_doim_onlayn(self):
        res = self.client.get("/api/mobile/game/online/")
        self.assertEqual(res.status_code, 200)
        oyinchilar = res.json()["oyinchilar"]
        self.assertEqual(len(oyinchilar), 1)
        self.assertEqual(oyinchilar[0]["ism"], "Robot1")
        self.assertTrue(oyinchilar[0]["robot"])

    def test_dost_bolgach_onlaynda_korinmaydi(self):
        # Do'st bo'lgach — u do'stlar ro'yxatida, onlaynda takrorlanmaydi.
        self.client.post(
            f"/api/mobile/game/friends/{self.robot.user_id}/request/",
            content_type="application/json",
        )
        res = self.client.get("/api/mobile/game/online/")
        self.assertEqual(len(res.json()["oyinchilar"]), 0)

    def test_faol_bolmagan_odam_onlaynda_yoq(self):
        eski = User.objects.create_user(
            email="eski@chaqmoq.uz", password="x", ism="Eski", role="student"
        )
        # oxirgi_faol — 10 daqiqa oldin (ONLAYN_DAQIQA=5 dan tashqarida).
        GameProfile.objects.create(
            user=eski,
            oxirgi_faol=timezone.now() - timedelta(minutes=10),
        )
        res = self.client.get("/api/mobile/game/online/")
        ismlar = [o["ism"] for o in res.json()["oyinchilar"]]
        self.assertNotIn("Eski", ismlar)


class RegisterTests(TestCase):
    """Yangi foydalanuvchi faqat login+parol bilan to'liq qo'shiladi."""

    def test_login_parol_bilan_royxat(self):
        res = self.client.post(
            "/api/mobile/game/register/",
            data={"login": "yangi_oquvchi", "parol": "parol123"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.json()["access_token"])

        # Foydalanuvchi va o'yin profili yaratildi.
        user = User.objects.get(ism="yangi_oquvchi")
        self.assertTrue(hasattr(user, "game_profile"))
        # @ bo'lmasa sun'iy email yasaladi.
        self.assertEqual(user.email, "yangi_oquvchi@chaqmoq.game")
        # Chaqmoq 0 dan boshlanadi.
        self.assertEqual(user.game_profile.chaqmoq, 0)

    def test_band_login_rad_etiladi(self):
        User.objects.create_user(
            email="band@chaqmoq.game", password="x", ism="band", role="student"
        )
        res = self.client.post(
            "/api/mobile/game/register/",
            data={"login": "band", "parol": "parol123"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()["code"], "login_band")


class JonTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@chaqmoq.uz", password="x", ism="Test", role="student"
        )
        self.profile = GameProfile.objects.create(user=self.user)

    def test_bepul_reja_3_jon(self):
        self.assertEqual(self.profile.max_jon, BEPUL_JON)
        self.assertEqual(self.profile.joriy_jon, 3)

    def test_uch_duel_kunlik_limit(self):
        """Bepul rejada kuniga 3 marta o'ynash mumkin, keyin jon tugaydi."""
        for _ in range(3):
            self.assertTrue(self.profile.jon_sarfla())
        self.assertEqual(self.profile.joriy_jon, 0)
        self.assertFalse(self.profile.jon_sarfla())

    def test_ertasi_kuni_jonlar_tiklanadi(self):
        for _ in range(3):
            self.profile.jon_sarfla()
        self.assertEqual(self.profile.joriy_jon, 0)

        # Kunni orqaga surib, "ertaga bo'ldi" holatini yaratamiz.
        self.profile.jon_kuni = timezone.localdate() - timedelta(days=1)
        self.profile.save(update_fields=["jon_kuni"])

        self.assertEqual(self.profile.joriy_jon, BEPUL_JON)

    def test_tarif_soatlik_tiklanish(self):
        """10 000 so'mlik tarif: har 10 soatda 3 ta jon."""
        tarif = Tarif.objects.create(
            nom="Boshlang'ich", narx_som=10_000, kun=7, jon_soni=3, soat=10
        )
        Obuna.objects.create(
            user=self.user,
            tarif=tarif,
            tugaydi=timezone.now() + timedelta(days=7),
            tolangan=True,
        )
        profile = GameProfile.objects.get(pk=self.profile.pk)

        for _ in range(3):
            profile.jon_sarfla()
        self.assertEqual(profile.joriy_jon, 0)

        # 10 soat o'tdi.
        profile.jon_yangilangan = timezone.now() - timedelta(hours=10, minutes=1)
        profile.save(update_fields=["jon_yangilangan"])

        self.assertEqual(profile.joriy_jon, 3)

    def test_tarif_tugasa_bepulga_qaytadi(self):
        tarif = Tarif.objects.create(
            nom="Kuchli", narx_som=30_000, kun=15, jon_soni=3, soat=5
        )
        Obuna.objects.create(
            user=self.user,
            tarif=tarif,
            tugaydi=timezone.now() - timedelta(days=1),  # muddati o'tgan
            tolangan=True,
        )
        profile = GameProfile.objects.get(pk=self.profile.pk)

        self.assertIsNone(profile.obuna)
        self.assertFalse(profile.pro)
        self.assertEqual(profile.max_jon, BEPUL_JON)
