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
    BEPUL_JON_SOAT,
    BEPUL_OYIN_QULF_SOAT,
    SAVOLLAR_SONI,
    Duel,
    GameMode,
    GameProfile,
    Obuna,
    Question,
    QuestionCategory,
    Tarif,
    chaqmoq_aniqlik_boyicha,
    chaqmoq_mukofoti,
)
from game.services import _robot_javoblari, ball_hisobla

User = get_user_model()


class ChaqmoqMukofotiTests(TestCase):
    """Mukofot narvoni — mahsulot qarori, tasodifan o'zgarmasligi kerak.

    100% → +5,  75% → +3,  50% → +2,  30% → 0,  30% dan past → −1 (jarima).
    """

    def test_toliq_bilsa_besh_chaqmoq(self):
        self.assertEqual(chaqmoq_mukofoti(10), Decimal("5"))

    def test_yetmish_besh_foiz_uch_chaqmoq(self):
        self.assertEqual(chaqmoq_mukofoti(9), Decimal("3"))
        self.assertEqual(chaqmoq_mukofoti(8), Decimal("3"))

    def test_ellik_foiz_ikki_chaqmoq(self):
        self.assertEqual(chaqmoq_mukofoti(7), Decimal("2"))
        self.assertEqual(chaqmoq_mukofoti(5), Decimal("2"))

    def test_ottiz_foiz_chaqmoqsiz(self):
        self.assertEqual(chaqmoq_mukofoti(4), Decimal("0"))
        self.assertEqual(chaqmoq_mukofoti(3), Decimal("0"))

    def test_ottiz_foizdan_past_jarima(self):
        """Tavakkaliga bosishning ma'nosi qolmasligi uchun jarima."""
        self.assertEqual(chaqmoq_mukofoti(2), Decimal("-1"))
        self.assertEqual(chaqmoq_mukofoti(0), Decimal("-1"))

    def test_uzunlikdan_qatiy_nazar_bir_xil(self):
        """5 savolli o'yin ham, 40 savolli ham foiz bo'yicha baholanadi."""
        self.assertEqual(chaqmoq_mukofoti(5, 5), chaqmoq_mukofoti(40, 40))
        self.assertEqual(chaqmoq_mukofoti(4, 5), chaqmoq_mukofoti(32, 40))


class ChaqmoqBalansTests(TestCase):
    """Jarima balansni manfiyga tushirmasligi kerak."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="balans@chaqmoq.uz", password="x", ism="Test", role="student"
        )
        self.profile = GameProfile.objects.create(user=self.user)

    def test_jarima_nolda_toxtaydi(self):
        self.profile.chaqmoq = Decimal("0.0")
        haqiqiy = self.profile.chaqmoq_qosh(Decimal("-1"))
        self.assertEqual(self.profile.chaqmoq, Decimal("0.0"))
        self.assertEqual(haqiqiy, Decimal("0.0"))

    def test_jarima_borini_yechadi(self):
        self.profile.chaqmoq = Decimal("0.5")
        haqiqiy = self.profile.chaqmoq_qosh(Decimal("-1"))
        self.assertEqual(self.profile.chaqmoq, Decimal("0.0"))
        self.assertEqual(haqiqiy, Decimal("-0.5"))

    def test_tarif_bonusi_mukofotga_qoshiladi(self):
        tarif = Tarif.objects.create(
            nom="Bonusli", narx_som=15_000, kun=7, jon_soni=3, soat=2,
            oyin_qulf_soat=6, chaqmoq_bonus_foiz=50,
        )
        Obuna.objects.create(
            user=self.user, tarif=tarif,
            tugaydi=timezone.now() + timedelta(days=7), tolangan=True,
        )
        profile = GameProfile.objects.get(pk=self.profile.pk)
        profile.chaqmoq_qosh(Decimal("4"))
        self.assertEqual(profile.chaqmoq, Decimal("6.0"))

    def test_tarif_bonusi_jarimaga_qoshilmaydi(self):
        tarif = Tarif.objects.create(
            nom="Bonusli", narx_som=15_000, kun=7, jon_soni=3, soat=2,
            chaqmoq_bonus_foiz=50,
        )
        Obuna.objects.create(
            user=self.user, tarif=tarif,
            tugaydi=timezone.now() + timedelta(days=7), tolangan=True,
        )
        profile = GameProfile.objects.get(pk=self.profile.pk)
        profile.chaqmoq = Decimal("5.0")
        profile.chaqmoq_qosh(Decimal("-1"))
        self.assertEqual(profile.chaqmoq, Decimal("4.0"))


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

    def test_uch_oyin_limiti(self):
        """Bepul rejada 3 marta o'ynash mumkin, keyin jon tugaydi."""
        for _ in range(3):
            self.assertTrue(self.profile.jon_sarfla())
        self.assertEqual(self.profile.joriy_jon, 0)
        self.assertFalse(self.profile.jon_sarfla())

    def test_sakkiz_soatdan_keyin_jonlar_tiklanadi(self):
        for _ in range(3):
            self.profile.jon_sarfla()
        self.assertEqual(self.profile.joriy_jon, 0)

        # 8 soat hali o'tmagan — jon tiklanmaydi.
        self.profile.jon_yangilangan = timezone.now() - timedelta(hours=7, minutes=50)
        self.profile.save(update_fields=["jon_yangilangan"])
        self.assertEqual(self.profile.joriy_jon, 0)

        # 8 soat o'tdi — to'liq tiklanadi.
        self.profile.jon_yangilangan = timezone.now() - timedelta(
            hours=BEPUL_JON_SOAT, minutes=1
        )
        self.profile.save(update_fields=["jon_yangilangan"])
        self.assertEqual(self.profile.joriy_jon, BEPUL_JON)

    def test_keyingi_jon_soniyasi_hisoblanadi(self):
        self.profile.jon_sarfla()
        qolgan = self.profile.keyingi_jon_soniya()
        self.assertGreater(qolgan, 0)
        self.assertLessEqual(qolgan, BEPUL_JON_SOAT * 3600)

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


# ═══════════════════════════════════════════════════════════════
# O'YINLAR KATALOGI VA YAKKA SESSIYALAR
# ═══════════════════════════════════════════════════════════════

class OyinAsosi(TestCase):
    """Katalog testlari uchun umumiy tayyorgarlik."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="oyin@chaqmoq.uz", password="parol123", ism="Test", role="student"
        )
        GameProfile.objects.create(user=self.user)
        self.kategoriya = QuestionCategory.objects.create(nom="Test", daraja="A1")
        self.savollar_yarat(12)
        self.client.force_login(self.user)

    def savollar_yarat(self, soni: int, kategoriya=None):
        kategoriya = kategoriya or self.kategoriya
        mavjud = Question.objects.count()
        for i in range(mavjud, mavjud + soni):
            Question.objects.create(
                kategoriya=kategoriya,
                savol=f"word{i}",
                togri_javob=f"togri{i}",
                notogri_1="a", notogri_2="b", notogri_3="c",
            )

    def oyin_yarat(self, **kwargs):
        maydonlar = {
            "nom": "Viktorina",
            "motor": "viktorina",
            "savollar_soni": 5,
            "savol_soniya": 10,
            "jon_narxi": 1,
            "xp_mukofot": 40,
        }
        maydonlar.update(kwargs)
        return GameMode.objects.create(**maydonlar)

    def katalog(self) -> list[dict]:
        res = self.client.get("/api/mobile/game/catalog/")
        self.assertEqual(res.status_code, 200, res.content)
        return res.json()["oyinlar"]


class KatalogTests(OyinAsosi):
    """Admin paneldagi o'zgarish ilovaga darrov yetib borishi kerak —
    o'yin ro'yxati kodda emas, bazada."""

    def test_yangi_oyin_katalogda_paydo_boladi(self):
        self.assertEqual(self.katalog(), [])

        self.oyin_yarat(nom="Yangi o'yin")

        oyinlar = self.katalog()
        self.assertEqual(len(oyinlar), 1)
        self.assertEqual(oyinlar[0]["nom"], "Yangi o'yin")
        self.assertTrue(oyinlar[0]["ochiq"])

    def test_faolsiz_oyin_korinmaydi(self):
        self.oyin_yarat(nom="Yashirin", faol=False)
        self.assertEqual(self.katalog(), [])

    def test_ochirilgan_oyin_korinmaydi(self):
        mode = self.oyin_yarat(nom="O'chadigan")
        mode.delete()  # soft delete
        self.assertEqual(self.katalog(), [])

    def test_boshqa_markaz_oyini_korinmaydi(self):
        from accounts.models import Center

        boshqa = Center.objects.create(name="Boshqa", slug="boshqa-markaz")
        self.oyin_yarat(nom="Begona", center=boshqa)
        self.assertEqual(self.katalog(), [])

    def test_savol_yetmasa_qulflanadi(self):
        # Xotira motori kamida 4 ta savol talab qiladi.
        Question.objects.all().delete()
        self.savollar_yarat(2)
        self.oyin_yarat(nom="Xotira", motor="xotira", savollar_soni=6)

        oyin = self.katalog()[0]
        self.assertFalse(oyin["ochiq"])
        self.assertEqual(oyin["qulf"], "savol_yetarli_emas")

    def test_pro_oyin_bepul_oquvchiga_qulflangan(self):
        self.oyin_yarat(nom="Pro o'yin", faqat_pro=True)

        oyin = self.katalog()[0]
        self.assertFalse(oyin["ochiq"])
        self.assertEqual(oyin["qulf"], "pro_kerak")

    def test_kategoriya_filtri_savol_sanogiga_tasir_qiladi(self):
        boshqa_kategoriya = QuestionCategory.objects.create(nom="Boshqa", daraja="B1")
        self.savollar_yarat(3, kategoriya=boshqa_kategoriya)

        mode = self.oyin_yarat(nom="Faqat B1")
        mode.kategoriyalar.add(boshqa_kategoriya)

        oyin = self.katalog()[0]
        self.assertEqual(oyin["mavjud_savol"], 3)

    def test_ikonka_va_rang_motordan_meros_boladi(self):
        self.oyin_yarat(nom="Sprint", motor="sprint", savollar_soni=10, savol_soniya=0)
        oyin = self.katalog()[0]
        self.assertEqual(oyin["ikonka"], "⚡")
        self.assertEqual(oyin["sozlamalar"]["davomiylik_soniya"], 60)


class SessiyaTests(OyinAsosi):
    """Yakka o'yin oqimi: boshla → javob → yakunla."""

    def boshla(self, mode, status=200):
        res = self.client.post(
            f"/api/mobile/game/play/{mode.id}/start/", content_type="application/json"
        )
        self.assertEqual(res.status_code, status, res.content)
        return res.json()

    def test_toliq_oqim_mukofot_beradi(self):
        mode = self.oyin_yarat(savollar_soni=5, xp_mukofot=40, chaqmoq_koef=Decimal("1.0"))
        boshlanish = self.boshla(mode)

        self.assertEqual(boshlanish["tur"], "sessiya")
        self.assertEqual(len(boshlanish["savollar"]), 5)
        # Viktorinada to'g'ri javob ilovaga oldindan berilmaydi.
        self.assertNotIn("javob", boshlanish["savollar"][0])

        sessiya_id = boshlanish["sessiya_id"]
        for savol in boshlanish["savollar"]:
            togri = Question.objects.get(savol=savol["savol"]).togri_javob
            self.client.post(
                f"/api/mobile/game/play/session/{sessiya_id}/answer/",
                data={"tartib": savol["tartib"], "tanlangan": togri, "sarflangan_ms": 1200},
                content_type="application/json",
            )

        natija = self.client.post(
            f"/api/mobile/game/play/session/{sessiya_id}/finish/",
            content_type="application/json",
        ).json()

        self.assertEqual(natija["togri_javoblar"], 5)
        self.assertEqual(natija["aniqlik"], 100)
        self.assertEqual(natija["olingan_xp"], 40)
        # 100% → narvon bo'yicha 5 chaqmoq.
        self.assertEqual(natija["olingan_chaqmoq"], 5.0)

    def test_jon_sarflanadi(self):
        mode = self.oyin_yarat(jon_narxi=1)
        oldin = GameProfile.objects.get(user=self.user).joriy_jon
        self.boshla(mode)
        keyin = GameProfile.objects.get(user=self.user).joriy_jon
        self.assertEqual(keyin, oldin - 1)

    def test_jon_tugasa_boshlanmaydi(self):
        mode = self.oyin_yarat(jon_narxi=1)
        profile = GameProfile.objects.get(user=self.user)
        for _ in range(BEPUL_JON):
            profile.jon_sarfla()

        javob = self.boshla(mode, status=409)
        self.assertEqual(javob["code"], "jon_yoq")

    def test_bepul_oyin_jon_talab_qilmaydi(self):
        mode = self.oyin_yarat(jon_narxi=0)
        profile = GameProfile.objects.get(user=self.user)
        for _ in range(BEPUL_JON):
            profile.jon_sarfla()

        self.boshla(mode)  # jon 0 bo'lsa ham ochiladi

    def test_pro_oyin_bepul_oquvchida_boshlanmaydi(self):
        mode = self.oyin_yarat(faqat_pro=True)
        javob = self.boshla(mode, status=403)
        self.assertEqual(javob["code"], "pro_kerak")

    def test_togrilikni_server_hal_qiladi(self):
        """Ilova «to'g'ri javob berdim» deb ayta olmaydi — faqat variant yuboradi."""
        mode = self.oyin_yarat(savollar_soni=5)
        boshlanish = self.boshla(mode)
        savol = boshlanish["savollar"][0]

        javob = self.client.post(
            f"/api/mobile/game/play/session/{boshlanish['sessiya_id']}/answer/",
            data={"tartib": savol["tartib"], "tanlangan": "butunlay-boshqa", "togri": True},
            content_type="application/json",
        ).json()

        self.assertFalse(javob["togri"])
        self.assertEqual(javob["ball"], 0)

    def test_bir_savolga_ikki_marta_javob_berilmaydi(self):
        mode = self.oyin_yarat(savollar_soni=5)
        boshlanish = self.boshla(mode)
        tartib = boshlanish["savollar"][0]["tartib"]
        url = f"/api/mobile/game/play/session/{boshlanish['sessiya_id']}/answer/"

        birinchi = self.client.post(
            url, data={"tartib": tartib, "tanlangan": "a"}, content_type="application/json"
        )
        ikkinchi = self.client.post(
            url, data={"tartib": tartib, "tanlangan": "b"}, content_type="application/json"
        )

        self.assertEqual(birinchi.status_code, 200)
        self.assertEqual(ikkinchi.status_code, 409)

    def test_yakunlash_takrorlansa_mukofot_ikkilanmaydi(self):
        mode = self.oyin_yarat(savollar_soni=5)
        boshlanish = self.boshla(mode)
        sessiya_id = boshlanish["sessiya_id"]
        savol = boshlanish["savollar"][0]
        togri = Question.objects.get(savol=savol["savol"]).togri_javob
        self.client.post(
            f"/api/mobile/game/play/session/{sessiya_id}/answer/",
            data={"tartib": savol["tartib"], "tanlangan": togri},
            content_type="application/json",
        )

        url = f"/api/mobile/game/play/session/{sessiya_id}/finish/"
        birinchi = self.client.post(url, content_type="application/json").json()
        ikkinchi = self.client.post(url, content_type="application/json").json()

        self.assertEqual(birinchi["xp"], ikkinchi["xp"])
        self.assertEqual(birinchi["chaqmoq"], ikkinchi["chaqmoq"])

    def test_javobsiz_chiqib_ketsa_mukofot_yoq(self):
        mode = self.oyin_yarat(savollar_soni=5)
        boshlanish = self.boshla(mode)
        natija = self.client.post(
            f"/api/mobile/game/play/session/{boshlanish['sessiya_id']}/finish/",
            content_type="application/json",
        ).json()

        self.assertEqual(natija["olingan_xp"], 0)
        self.assertEqual(natija["olingan_chaqmoq"], 0.0)

    def test_boshqa_oquvchining_sessiyasiga_javob_berib_bolmaydi(self):
        mode = self.oyin_yarat(savollar_soni=5)
        boshlanish = self.boshla(mode)

        begona = User.objects.create_user(
            email="begona@chaqmoq.uz", password="parol123", ism="Begona", role="student"
        )
        GameProfile.objects.create(user=begona)
        self.client.force_login(begona)

        res = self.client.post(
            f"/api/mobile/game/play/session/{boshlanish['sessiya_id']}/answer/",
            data={"tartib": 1, "tanlangan": "a"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 404)

    def test_xotira_motorida_javob_ochiq_keladi(self):
        """Xotira/juftlashda kartaning ikkala tomoni ekranda — javobni
        yashirishning ma'nosi yo'q, shuning uchun u ataylab yuboriladi."""
        mode = self.oyin_yarat(nom="Xotira", motor="xotira", savollar_soni=6, savol_soniya=0)
        boshlanish = self.boshla(mode)
        self.assertIn("javob", boshlanish["savollar"][0])


class DuelKatalogTests(OyinAsosi):
    """Duel ham katalogdan boshqariladi — uzunligi va mukofoti admin qo'lida."""

    def setUp(self):
        super().setUp()
        GameProfile.objects.create(robot=True, robot_ism="Robot", maxorat=0.8)

    def test_katalogdagi_duel_uzunligi_hurmat_qilinadi(self):
        mode = self.oyin_yarat(nom="Qisqa duel", motor="duel", savollar_soni=5)
        # `robot: true` — raqib qidirmasdan darhol robot bilan.
        res = self.client.post(
            f"/api/mobile/game/play/{mode.id}/start/",
            data={"robot": True},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        javob = res.json()

        self.assertEqual(javob["tur"], "duel")
        self.assertEqual(len(javob["savollar"]), 5)

    def test_eski_duel_endpointi_ishlashda_davom_etadi(self):
        """Eski ilova versiyalari `mode_id` yubormaydi — buzilmasligi kerak."""
        res = self.client.post(
            "/api/mobile/game/duel/start/", content_type="application/json"
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(len(res.json()["savollar"]), SAVOLLAR_SONI)



# ═══════════════════════════════════════════════════════════════
# O'YIN QULFI (COOLDOWN)
# ═══════════════════════════════════════════════════════════════

class OyinQulfiTests(OyinAsosi):
    """O'ynalgan o'yin qulflanadi — bitta o'yinni takrorlab chaqmoq yig'ib
    bo'lmaydi, 3 ta jon turli o'yinlarga sarflanadi."""

    def boshla(self, mode, status=200):
        res = self.client.post(
            f"/api/mobile/game/play/{mode.id}/start/",
            data={"robot": True},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, status, res.content)
        return res.json()

    def test_oynalgan_oyin_qulflanadi(self):
        mode = self.oyin_yarat(savollar_soni=5)
        self.boshla(mode)

        javob = self.boshla(mode, status=409)
        self.assertEqual(javob["code"], "oyin_qulflangan")

    def test_qulflangan_oyin_katalogda_korinadi(self):
        mode = self.oyin_yarat(savollar_soni=5)
        self.boshla(mode)

        oyin = self.katalog()[0]
        self.assertFalse(oyin["ochiq"])
        self.assertEqual(oyin["qulf"], "oyin_qulflangan")
        self.assertGreater(oyin["qulf_soniya"], 0)
        self.assertLessEqual(oyin["qulf_soniya"], BEPUL_OYIN_QULF_SOAT * 3600)

    def test_boshqa_oyin_qulflanmaydi(self):
        """Bittasini o'ynash boshqasini yopmasligi kerak."""
        birinchi = self.oyin_yarat(nom="Birinchi", savollar_soni=5)
        ikkinchi = self.oyin_yarat(nom="Ikkinchi", savollar_soni=5)

        self.boshla(birinchi)
        self.boshla(ikkinchi)  # xatolik bo'lmasligi kerak

    def test_qulf_muddati_otgach_ochiladi(self):
        from game.models import GameCooldown

        mode = self.oyin_yarat(savollar_soni=5)
        self.boshla(mode)

        qulf = GameCooldown.objects.get(mode=mode)
        qulf.oxirgi_oynalgan = timezone.now() - timedelta(
            hours=BEPUL_OYIN_QULF_SOAT, minutes=1
        )
        qulf.save(update_fields=["oxirgi_oynalgan"])

        # Jon ham kerak — tiklab qo'yamiz.
        profile = GameProfile.objects.get(user=self.user)
        profile.jon = 3
        profile.save(update_fields=["jon"])

        self.boshla(mode)

    def test_tarif_qulfni_qisqartiradi(self):
        from game.cooldowns import qulflangan_soniya
        from game.models import GameCooldown

        mode = self.oyin_yarat(savollar_soni=5)
        self.boshla(mode)

        tarif = Tarif.objects.create(
            nom="Tez", narx_som=15_000, kun=7, jon_soni=3, soat=2, oyin_qulf_soat=6
        )
        Obuna.objects.create(
            user=self.user, tarif=tarif,
            tugaydi=timezone.now() + timedelta(days=7), tolangan=True,
        )

        qulf = GameCooldown.objects.get(mode=mode)
        qulf.oxirgi_oynalgan = timezone.now() - timedelta(hours=7)
        qulf.save(update_fields=["oxirgi_oynalgan"])

        profile = GameProfile.objects.get(user=self.user)
        # Bepulda hali qulflangan bo'lardi (24 soat), tarif bilan ochiq (6 soat).
        self.assertEqual(qulflangan_soniya(profile, mode), 0)


# ═══════════════════════════════════════════════════════════════
# REAL DUEL (PvP)
# ═══════════════════════════════════════════════════════════════

class RealDuelTests(OyinAsosi):
    """Ikki o'quvchi bir xil savollar bilan o'ynashi va hisob jonli
    ko'rinishi kerak."""

    def setUp(self):
        super().setUp()
        GameProfile.objects.create(robot=True, robot_ism="Robot", maxorat=0.8)
        self.mode = self.oyin_yarat(nom="Duel", motor="duel", savollar_soni=5)

        self.ikkinchi = User.objects.create_user(
            email="ikki@chaqmoq.uz", password="parol123", ism="Ikkinchi", role="student"
        )
        GameProfile.objects.create(user=self.ikkinchi)

    def boshla(self, client=None):
        client = client or self.client
        res = client.post(
            f"/api/mobile/game/play/{self.mode.id}/start/",
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        return res.json()

    def test_birinchi_oquvchi_navbatga_tushadi(self):
        javob = self.boshla()
        self.assertEqual(javob["tur"], "kutish")
        self.assertIn("navbat_id", javob)

    def test_ikkinchi_oquvchi_kelsa_juftlanadi(self):
        birinchi = self.boshla()
        self.assertEqual(birinchi["tur"], "kutish")

        from django.test import Client

        boshqa = Client()
        boshqa.force_login(self.ikkinchi)
        ikkinchi = self.boshla(boshqa)

        self.assertEqual(ikkinchi["tur"], "duel")
        self.assertTrue(ikkinchi["pvp"])

        # Birinchi o'quvchi navbatni so'raganda duelni oladi.
        holat = self.client.get(
            f"/api/mobile/game/queue/{birinchi['navbat_id']}/"
        ).json()
        self.assertEqual(holat["holat"], "topildi")
        self.assertTrue(holat["pvp"])

    def test_juftlangan_duellarda_savollar_bir_xil(self):
        from django.test import Client

        birinchi = self.boshla()
        boshqa = Client()
        boshqa.force_login(self.ikkinchi)
        ikkinchi = self.boshla(boshqa)

        meniki = self.client.get(
            f"/api/mobile/game/queue/{birinchi['navbat_id']}/"
        ).json()

        mening_savollarim = [s["savol"] for s in meniki["savollar"]]
        uning_savollari = [s["savol"] for s in ikkinchi["savollar"]]
        self.assertEqual(mening_savollarim, uning_savollari)

        # Variantlar tartibi ham bir xil — bittasiga "osonroq" tushmasligi kerak.
        self.assertEqual(
            [s["variantlar"] for s in meniki["savollar"]],
            [s["variantlar"] for s in ikkinchi["savollar"]],
        )

    def test_raqib_topilmasa_robotga_otadi(self):
        javob = self.boshla()
        robot = self.client.post(
            f"/api/mobile/game/queue/{javob['navbat_id']}/robot/",
            content_type="application/json",
        )
        self.assertEqual(robot.status_code, 200, robot.content)
        self.assertFalse(robot.json()["pvp"])

    def test_navbatda_turish_jon_yemaydi(self):
        """Raqib topilmasa o'quvchi bekorga jon yo'qotmasligi kerak."""
        oldin = GameProfile.objects.get(user=self.user).joriy_jon
        self.boshla()
        keyin = GameProfile.objects.get(user=self.user).joriy_jon
        self.assertEqual(oldin, keyin)

    def test_pvp_natijasi_ikkalasi_tugagach_hisoblanadi(self):
        from django.test import Client

        birinchi = self.boshla()
        boshqa = Client()
        boshqa.force_login(self.ikkinchi)
        ikkinchi_duel = self.boshla(boshqa)

        meniki = self.client.get(
            f"/api/mobile/game/queue/{birinchi['navbat_id']}/"
        ).json()

        # Men hammasiga to'g'ri javob beraman.
        for savol in meniki["savollar"]:
            togri = Question.objects.get(savol=savol["savol"]).togri_javob
            self.client.post(
                f"/api/mobile/game/duel/{meniki['duel_id']}/answer/",
                data={"tartib": savol["tartib"], "tanlangan": togri},
                content_type="application/json",
            )
        natija = self.client.post(
            f"/api/mobile/game/duel/{meniki['duel_id']}/finish/",
            content_type="application/json",
        ).json()

        # Raqib hali o'ynayapti — g'olib ma'lum emas, lekin chaqmoq berilgan.
        self.assertTrue(natija["kutilmoqda"])
        self.assertEqual(natija["olingan_chaqmoq"], 5.0)

        # Raqib xato javob berib tugatadi.
        for savol in ikkinchi_duel["savollar"]:
            boshqa.post(
                f"/api/mobile/game/duel/{ikkinchi_duel['duel_id']}/answer/",
                data={"tartib": savol["tartib"], "tanlangan": "xato"},
                content_type="application/json",
            )
        boshqa.post(
            f"/api/mobile/game/duel/{ikkinchi_duel['duel_id']}/finish/",
            content_type="application/json",
        )

        yakuniy = self.client.post(
            f"/api/mobile/game/duel/{meniki['duel_id']}/finish/",
            content_type="application/json",
        ).json()
        self.assertFalse(yakuniy["kutilmoqda"])
        self.assertEqual(yakuniy["natija"], "galaba")


# ═══════════════════════════════════════════════════════════════
# TARIF SOTIB OLISH VA MUROJAATLAR
# ═══════════════════════════════════════════════════════════════

class TarifSotibOlishTests(OyinAsosi):
    def setUp(self):
        super().setUp()
        self.tarif = Tarif.objects.create(
            nom="Tezkor", narx_som=15_000, kun=7, jon_soni=3, soat=2,
            oyin_qulf_soat=6, chaqmoq_bonus_foiz=25,
        )

    def test_naqd_sorov_yaratiladi(self):
        res = self.client.post(
            f"/api/mobile/game/tariffs/{self.tarif.id}/buy/",
            data={"usul": "naqd"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertIn("sorov_id", res.json())

    def test_ikki_marta_sorov_yuborilmaydi(self):
        self.client.post(
            f"/api/mobile/game/tariffs/{self.tarif.id}/buy/",
            data={"usul": "naqd"}, content_type="application/json",
        )
        ikkinchi = self.client.post(
            f"/api/mobile/game/tariffs/{self.tarif.id}/buy/",
            data={"usul": "naqd"}, content_type="application/json",
        )
        self.assertEqual(ikkinchi.status_code, 409)
        self.assertEqual(ikkinchi.json()["code"], "sorov_mavjud")

    def test_tasdiqlangach_obuna_yoqiladi(self):
        from game.models import TarifSorovi
        from game.payments import obunani_yoq

        self.client.post(
            f"/api/mobile/game/tariffs/{self.tarif.id}/buy/",
            data={"usul": "naqd"}, content_type="application/json",
        )
        sorov = TarifSorovi.objects.get(user=self.user)
        obunani_yoq(sorov)

        profile = GameProfile.objects.get(user=self.user)
        self.assertTrue(profile.pro)
        self.assertEqual(profile.jon_soat, 2)
        self.assertEqual(profile.oyin_qulf_soat, 6)
        self.assertEqual(profile.chaqmoq_bonus_foiz, 25)

    def test_tasdiqlash_ikki_marta_obuna_yaratmaydi(self):
        from game.models import Obuna, TarifSorovi
        from game.payments import obunani_yoq

        self.client.post(
            f"/api/mobile/game/tariffs/{self.tarif.id}/buy/",
            data={"usul": "naqd"}, content_type="application/json",
        )
        sorov = TarifSorovi.objects.get(user=self.user)
        obunani_yoq(sorov)
        obunani_yoq(sorov)

        self.assertEqual(Obuna.objects.filter(user=self.user).count(), 1)

    def test_tariflar_royxati_bepul_qoidani_ham_beradi(self):
        javob = self.client.get("/api/mobile/game/tariffs/").json()
        self.assertEqual(javob["bepul"]["jon_soat"], BEPUL_JON_SOAT)
        self.assertEqual(javob["bepul"]["oyin_qulf_soat"], BEPUL_OYIN_QULF_SOAT)
        self.assertEqual(len(javob["tariflar"]), 1)


class MurojaatTests(OyinAsosi):
    def test_taklif_yuboriladi(self):
        res = self.client.post(
            "/api/mobile/game/feedback/send/",
            data={"tur": "taklif", "matn": "Yangi o'yin qo'shsangiz zo'r bo'lardi"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200, res.content)

        royxat = self.client.get("/api/mobile/game/feedback/").json()
        self.assertEqual(len(royxat["murojaatlar"]), 1)
        self.assertEqual(royxat["murojaatlar"][0]["tur"], "taklif")

    def test_qisqa_matn_rad_etiladi(self):
        res = self.client.post(
            "/api/mobile/game/feedback/send/",
            data={"matn": "ok"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "matn_qisqa")

    def test_boshqa_oquvchining_murojaati_korinmaydi(self):
        self.client.post(
            "/api/mobile/game/feedback/send/",
            data={"matn": "Mening shikoyatim"},
            content_type="application/json",
        )

        begona = User.objects.create_user(
            email="begona2@chaqmoq.uz", password="parol123", ism="B", role="student"
        )
        GameProfile.objects.create(user=begona)
        self.client.force_login(begona)

        royxat = self.client.get("/api/mobile/game/feedback/").json()
        self.assertEqual(royxat["murojaatlar"], [])


class JarimaKoeffitsiyentTests(TestCase):
    """Jarima o'yin koeffitsiyentiga bog'liq bo'lmasligi kerak — jazo har
    o'yinda bir xil: aniq 1 chaqmoq."""

    def test_koeffitsiyent_mukofotni_olchaydi(self):
        from game.models import mukofotni_olchash

        self.assertEqual(
            mukofotni_olchash(Decimal("5"), Decimal("0.8")), Decimal("4.0")
        )

    def test_koeffitsiyent_jarimaga_tegmaydi(self):
        from game.models import mukofotni_olchash

        self.assertEqual(
            mukofotni_olchash(Decimal("-1"), Decimal("0.5")), Decimal("-1")
        )
        self.assertEqual(
            mukofotni_olchash(Decimal("-1"), Decimal("2.0")), Decimal("-1")
        )
