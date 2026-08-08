"""Ko'p filialli ruxsatlar: filial ko'rinishi + o'qituvchi izolyatsiyasi.

Bu fayl ikki muammoning regressiya himoyasi:

  1) FILIAL KO'RINMASLIGI — bir direktor yaratgan filial ikkinchi direktorga
     ko'rinmasdi, chunki `DirectorCenterAccess` yozuvi faqat so'rov beruvchi
     uchun yaratilardi. Markaz almashtirgich aynan shu jadvaldan o'qiydi.

  2) O'QITUVCHINING KO'P FILIALI — o'qituvchi har filial uchun alohida
     login ochishga majbur edi. Endi `TeacherCenterAccess` + sessiya orqali
     almashish bor, LEKIN u tenant izolyatsiyasini buzmasligi shart:
     ruxsat berilmagan filial ma'lumoti umuman ko'rinmasligi kerak.

MUHIM (test barqarorligi): `core.middleware` da process-local cache'lar bor
(`_CENTER_CACHE`, `_SLUG_CACHE`, `_SUB_BLOCK_CACHE`). TestCase har testdan
keyin tranzaksiyani qaytaradi, shuning uchun ID'lar takrorlanadi va eski
cache boshqa testning markazini qaytarib yuborishi mumkin. Har `setUp` da
ularni tozalaymiz — aks holda testlar TARTIBGA bog'liq bo'lib qoladi.
"""

from __future__ import annotations

import json

from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import (
    BranchRequest,
    Center,
    DirectorCenterAccess,
    TeacherCenterAccess,
    User,
)
from accounts.services import branch_requests as branch_service
from accounts.services.center_access import (
    RuxsatXatosi,
    grant_teacher_access,
    revoke_teacher_access,
)
from core.test_utils import ALL_FEATURE_CODES, activate_center, create_active_center
from education.models import Group

# `can_add_branch()` shu feature'ni talab qiladi, `core.test_utils` esa uni
# standart ro'yxatga kiritmagan — filial so'rovi API'sini sinash uchun qo'shamiz.
FILIAL_FEATURES = list(ALL_FEATURE_CODES) + ["filial_qoshish"]


def _keshlarni_tozala() -> None:
    """Middleware'ning process-local cache'lari + Django cache."""
    from core.middleware import _CENTER_CACHE, _SLUG_CACHE, _SUB_BLOCK_CACHE

    _CENTER_CACHE.clear()
    _SLUG_CACHE.clear()
    _SUB_BLOCK_CACHE.clear()
    cache.clear()


def _filial_limitini_ochir() -> None:
    """Test tarifida filial limitini cheksiz qiladi (`max_branches=0`).

    `create_active_center` yaratadigan TEST_ALL tarifida `max_branches=1`
    (ya'ni filial qo'shib bo'lmaydi). Filial so'rovi API'sini sinash uchun
    limitni ochamiz — aks holda so'rov "limit tugadi" (400) bilan to'xtaydi
    va biz sinamoqchi bo'lgan mantiqqa yetib bormaydi.
    """
    from billing.models import SubscriptionPlan

    SubscriptionPlan.objects.filter(code="TEST_ALL").update(max_branches=0)
    cache.clear()


# ═══════════════════════════════════════════════════════════════════════
#  1-MUAMMO: filial belgilangan direktorga ko'rinadi, begonaga ko'rinmaydi
# ═══════════════════════════════════════════════════════════════════════

class FilialKorinishiTest(TestCase):
    """Yangi filial KIMGA ko'rinishi kerak — va kimga aslo ko'rinmasligi."""

    def setUp(self):
        _keshlarni_tozala()
        self.client = Client()

        # ── A mijoz: root markaz + ikki direktor ──
        self.root_a = create_active_center(
            name="Alfa Markaz", slug="alfa", features=FILIAL_FEATURES,
        )
        self.direktor_1 = User.objects.create_user(
            email="d1@alfa.uz", password="parol12345",
            role="director", center=self.root_a, ism="Aziz", familya="Birinchi",
        )
        self.direktor_2 = User.objects.create_user(
            email="d2@alfa.uz", password="parol12345",
            role="director", center=self.root_a, ism="Bobur", familya="Ikkinchi",
        )

        # ── B mijoz: butunlay boshqa markaz daraxti (begona) ──
        self.root_b = create_active_center(
            name="Beta Markaz", slug="beta", features=FILIAL_FEATURES,
        )
        self.begona_direktor = User.objects.create_user(
            email="d@beta.uz", password="parol12345",
            role="director", center=self.root_b, ism="Begona", familya="Direktor",
        )

        _filial_limitini_ochir()

    def _markazlar_royxati(self, foydalanuvchi) -> list[int]:
        """`accounts:my_centers` JSON'idan markaz ID larini oladi."""
        self.client.force_login(foydalanuvchi)
        javob = self.client.get(reverse("accounts:my_centers"))
        self.assertEqual(javob.status_code, 200)
        return [m["id"] for m in javob.json()["centers"]]

    # ── (a) Asosiy talab ────────────────────────────────────────────

    def test_target_director_filialni_koradi(self):
        """1-direktor so'raydi, filial 2-direktorga biriktiriladi → 2-direktor ko'radi."""
        so_rov = BranchRequest.objects.create(
            requester=self.direktor_1,
            parent_center=self.root_a,
            target_director=self.direktor_2,   # ⬅ boshqa direktorga
            name="Chilonzor Filiali",
        )

        filial = branch_service.tasdiqla(so_rov)

        # DB darajasida ruxsat bor va FAOL
        self.assertTrue(
            DirectorCenterAccess.objects.filter(
                director=self.direktor_2, center=filial, is_active=True
            ).exists(),
            "target_director uchun DirectorCenterAccess yaratilmagan — "
            "filial almashtirgichda ko'rinmaydi (asosiy bug)",
        )
        # View darajasida ham ko'rinadi
        self.assertIn(filial.id, self._markazlar_royxati(self.direktor_2))

    def test_sorovchi_ham_filialni_koradi(self):
        """Boshqa direktorga biriktirilsa ham, so'rov beruvchi ko'rishi kerak."""
        so_rov = BranchRequest.objects.create(
            requester=self.direktor_1, parent_center=self.root_a,
            target_director=self.direktor_2, name="Yunusobod Filiali",
        )
        filial = branch_service.tasdiqla(so_rov)

        self.assertIn(filial.id, self._markazlar_royxati(self.direktor_1))

    def test_begona_direktorga_korinmaydi(self):
        """⛔ Boshqa mijozning direktori bu filialni KO'RMASLIGI shart."""
        so_rov = BranchRequest.objects.create(
            requester=self.direktor_1, parent_center=self.root_a,
            target_director=self.direktor_2, name="Sergeli Filiali",
        )
        filial = branch_service.tasdiqla(so_rov)

        self.assertNotIn(filial.id, self._markazlar_royxati(self.begona_direktor))
        self.assertFalse(
            DirectorCenterAccess.objects.filter(
                director=self.begona_direktor, center=filial
            ).exists()
        )

    def test_target_yoq_bolsa_eski_xatti_harakat(self):
        """`target_director` bo'sh → faqat so'rov beruvchiga (backward compatible)."""
        so_rov = BranchRequest.objects.create(
            requester=self.direktor_1, parent_center=self.root_a,
            name="Olmazor Filiali",
        )
        filial = branch_service.tasdiqla(so_rov)

        self.assertIn(filial.id, self._markazlar_royxati(self.direktor_1))
        self.assertNotIn(filial.id, self._markazlar_royxati(self.direktor_2))

    def test_tasdiqlangandan_keyin_biriktirish_ham_ishlaydi(self):
        """So'rov tasdiqlangach `target_director` qo'yilsa — ruxsat qayta kafolatlanadi."""
        so_rov = BranchRequest.objects.create(
            requester=self.direktor_1, parent_center=self.root_a, name="Keyingi Filial",
        )
        filial = branch_service.tasdiqla(so_rov)
        self.assertNotIn(filial.id, self._markazlar_royxati(self.direktor_2))

        # Superadmin keyinroq boshqa direktorga biriktiradi
        so_rov.target_director = self.direktor_2
        so_rov.save(update_fields=["target_director"])
        branch_service.tasdiqla(so_rov)  # idempotent, lekin ruxsat beradi

        self.assertIn(filial.id, self._markazlar_royxati(self.direktor_2))
        # Yangi markaz OCHILMAGAN bo'lishi kerak
        self.assertEqual(Center.objects.filter(parent_center=self.root_a).count(), 1)

    # ── Cross-tenant himoyasi ───────────────────────────────────────

    def test_api_orqali_ozining_direktorini_biriktiradi(self):
        """✅ To'liq oqim: API → so'rov → tasdiqlash → 2-direktor ko'radi."""
        self.client.force_login(self.direktor_1)
        javob = self.client.post(
            reverse("accounts:branch_request"),
            data=json.dumps({
                "name": "Shayxontohur Filiali",
                "target_director_id": self.direktor_2.id,
            }),
            content_type="application/json",
        )
        self.assertEqual(javob.status_code, 200, javob.content)
        self.assertTrue(javob.json()["ok"])

        so_rov = BranchRequest.objects.get(pk=javob.json()["request_id"])
        self.assertEqual(so_rov.target_director_id, self.direktor_2.id)

        filial = branch_service.tasdiqla(so_rov)
        self.assertIn(filial.id, self._markazlar_royxati(self.direktor_2))

    def test_begona_direktorni_biriktirib_bolmaydi_api(self):
        """⛔ Direktor so'rovda begona direktorni ko'rsatsa → 403.

        Tekshiruv tarif limitidan OLDIN turishi shart — aks holda xavfsizlik
        xatosi "limit tugadi" (400) javobi ostida yashirinib qolardi.
        """
        self.client.force_login(self.direktor_1)
        javob = self.client.post(
            reverse("accounts:branch_request"),
            data=json.dumps({
                "name": "Buzg'unchi Filial",
                "target_director_id": self.begona_direktor.id,
            }),
            content_type="application/json",
        )
        self.assertEqual(javob.status_code, 403, javob.content)
        self.assertFalse(javob.json()["ok"])
        self.assertEqual(BranchRequest.objects.count(), 0)

    def test_mavjud_bolmagan_direktor_404(self):
        self.client.force_login(self.direktor_1)
        javob = self.client.post(
            reverse("accounts:branch_request"),
            data=json.dumps({"name": "Yoq Filial", "target_director_id": 999999}),
            content_type="application/json",
        )
        self.assertEqual(javob.status_code, 404)
        self.assertEqual(BranchRequest.objects.count(), 0)

    def test_superadmin_panel_begona_direktorni_rad_etadi(self):
        """⛔ Superadmin panelida ham daraxt tekshiruvi ishlaydi."""
        superadmin = User.objects.create_superuser(
            email="super@chaqmoq.uz", password="parol12345",
        )
        so_rov = BranchRequest.objects.create(
            requester=self.direktor_1, parent_center=self.root_a, name="Yakkasaroy",
        )

        self.client.force_login(superadmin)
        javob = self.client.post(
            reverse("platform_global:branch_request_action", args=[so_rov.id]),
            data=json.dumps({
                "amal": "tasdiqla",
                "direktor_id": self.begona_direktor.id,
            }),
            content_type="application/json",
        )

        self.assertEqual(javob.status_code, 400)
        so_rov.refresh_from_db()
        self.assertEqual(so_rov.status, BranchRequest.Status.PENDING)
        self.assertIsNone(so_rov.created_center_id)

    def test_superadmin_panel_ozining_direktoriga_biriktiradi(self):
        """✅ To'g'ri daraxtdagi direktor — biriktiriladi va ko'rinadi."""
        superadmin = User.objects.create_superuser(
            email="super2@chaqmoq.uz", password="parol12345",
        )
        so_rov = BranchRequest.objects.create(
            requester=self.direktor_1, parent_center=self.root_a, name="Mirzo Ulugbek",
        )

        self.client.force_login(superadmin)
        javob = self.client.post(
            reverse("platform_global:branch_request_action", args=[so_rov.id]),
            data=json.dumps({"amal": "tasdiqla", "direktor_id": self.direktor_2.id}),
            content_type="application/json",
        )
        self.assertEqual(javob.status_code, 200)
        self.assertTrue(javob.json()["ok"])

        so_rov.refresh_from_db()
        self.assertEqual(so_rov.target_director_id, self.direktor_2.id)
        self.assertIn(so_rov.created_center_id, self._markazlar_royxati(self.direktor_2))


# ═══════════════════════════════════════════════════════════════════════
#  2-MUAMMO: o'qituvchi bitta login bilan bir necha filialda
# ═══════════════════════════════════════════════════════════════════════

class OqituvchiKopFilialTest(TestCase):
    """Bitta hisob + `TeacherCenterAccess` = filiallar o'rtasida almashish."""

    def setUp(self):
        _keshlarni_tozala()
        self.client = Client()

        # ── A mijoz: root + 1 filial ──
        self.root = create_active_center(name="Root Markaz", slug="root-m")
        self.filial = activate_center(
            Center.objects.create(
                name="Filial 1", slug="filial-1", parent_center=self.root,
            )
        )

        # ── B mijoz: begona markaz ──
        self.begona = create_active_center(name="Begona", slug="begona-m")

        # O'qituvchi: uy markazi = root
        self.oqituvchi = User.objects.create_user(
            email="ustoz@root.uz", password="parol12345",
            role="teacher", center=self.root, ism="Ustoz", familya="Root",
        )
        self.direktor = User.objects.create_user(
            email="dir@root.uz", password="parol12345",
            role="director", center=self.root, ism="Dir", familya="Root",
        )

        # Guruhlar: har markazda bittasi, o'qituvchi hammasida "oqituvchi"
        self.guruh_root = Group.objects.create(
            nom="Root guruh", center=self.root, oqituvchi=self.oqituvchi,
            kurs_narxi=500000, oqituvchi_foiz=40,
        )
        self.guruh_filial = Group.objects.create(
            nom="Filial guruh", center=self.filial, oqituvchi=self.oqituvchi,
            kurs_narxi=500000, oqituvchi_foiz=40,
        )
        self.guruh_begona = Group.objects.create(
            nom="Begona guruh", center=self.begona, oqituvchi=self.oqituvchi,
            kurs_narxi=500000, oqituvchi_foiz=40,
        )

    def _url(self, center: Center, name: str, *args) -> str:
        """Slug-prefiksli URL (TenantMiddleware markazni shundan ham ko'radi)."""
        return f"/{center.slug}{reverse(name, args=args)}"

    # ── Ruxsat berish servisi ───────────────────────────────────────

    def test_ruxsat_beriladi_va_idempotent(self):
        r1 = grant_teacher_access(self.oqituvchi, self.filial, granted_by=self.direktor)
        r2 = grant_teacher_access(self.oqituvchi, self.filial, granted_by=self.direktor)

        self.assertEqual(r1.pk, r2.pk)
        self.assertEqual(TeacherCenterAccess.objects.count(), 1)
        self.assertTrue(r1.is_active)

    def test_begona_markazga_ruxsat_berilmaydi(self):
        """⛔ Boshqa markaz daraxtiga ruxsat — cross-tenant, taqiqlanadi."""
        with self.assertRaises(RuxsatXatosi):
            grant_teacher_access(self.oqituvchi, self.begona, granted_by=self.direktor)

        self.assertFalse(TeacherCenterAccess.objects.exists())

    def test_oz_markaziga_ruxsat_kerak_emas(self):
        with self.assertRaises(RuxsatXatosi):
            grant_teacher_access(self.oqituvchi, self.root)

    def test_ruxsat_olib_tashlanadi(self):
        grant_teacher_access(self.oqituvchi, self.filial)
        self.assertTrue(revoke_teacher_access(self.oqituvchi, self.filial))

        # Soft: yozuv tarixda qoladi, lekin faol emas
        self.assertTrue(TeacherCenterAccess.objects.filter(is_active=False).exists())
        self.assertFalse(self.oqituvchi.has_center_access(self.filial.id))

    # ── Ro'yxat va almashish ────────────────────────────────────────

    def test_royxatda_ikki_markaz_korinadi(self):
        grant_teacher_access(self.oqituvchi, self.filial)

        self.client.force_login(self.oqituvchi)
        javob = self.client.get(reverse("accounts:teacher_my_centers"))

        self.assertEqual(javob.status_code, 200)
        malumot = javob.json()
        self.assertTrue(malumot["can_switch"])
        idlar = {m["id"] for m in malumot["centers"]}
        self.assertEqual(idlar, {self.root.id, self.filial.id})
        self.assertNotIn(self.begona.id, idlar)

    def test_ruxsatsiz_bitta_markaz(self):
        """Ruxsat berilmagan o'qituvchi uchun almashtirgich yoqilmaydi."""
        self.client.force_login(self.oqituvchi)
        malumot = self.client.get(reverse("accounts:teacher_my_centers")).json()

        self.assertFalse(malumot["can_switch"])
        self.assertEqual([m["id"] for m in malumot["centers"]], [self.root.id])

    def test_almashish_ishlaydi(self):
        grant_teacher_access(self.oqituvchi, self.filial)

        self.client.force_login(self.oqituvchi)
        javob = self.client.post(
            reverse("accounts:teacher_switch_center"),
            data=json.dumps({"center_id": self.filial.id}),
            content_type="application/json",
        )

        self.assertEqual(javob.status_code, 200)
        self.assertTrue(javob.json()["ok"])
        self.assertEqual(self.client.session["active_center_id"], self.filial.id)

    def test_ruxsatsiz_almashish_403(self):
        """⛔ Ruxsat yo'q → 403 va sessiyaga HECH NARSA yozilmaydi."""
        self.client.force_login(self.oqituvchi)
        javob = self.client.post(
            reverse("accounts:teacher_switch_center"),
            data=json.dumps({"center_id": self.begona.id}),
            content_type="application/json",
        )

        self.assertEqual(javob.status_code, 403)
        self.assertIsNone(self.client.session.get("active_center_id"))

    def test_ruxsat_olingach_almashish_toxtaydi(self):
        grant_teacher_access(self.oqituvchi, self.filial)
        revoke_teacher_access(self.oqituvchi, self.filial)

        self.client.force_login(self.oqituvchi)
        javob = self.client.post(
            reverse("accounts:teacher_switch_center"),
            data=json.dumps({"center_id": self.filial.id}),
            content_type="application/json",
        )
        self.assertEqual(javob.status_code, 403)

    # ── (b) IDOR: ruxsatsiz filial ma'lumoti KO'RINMAYDI ────────────

    def test_almashgach_filial_guruhini_koradi(self):
        """✅ Ruxsat bor → filialga o'tgach o'sha filial guruhi ko'rinadi."""
        grant_teacher_access(self.oqituvchi, self.filial)
        self.client.force_login(self.oqituvchi)
        self.client.post(
            reverse("accounts:teacher_switch_center"),
            data=json.dumps({"center_id": self.filial.id}),
            content_type="application/json",
        )

        javob = self.client.get(self._url(self.filial, "education:my_groups"))
        self.assertEqual(javob.status_code, 200)
        self.assertContains(javob, "Filial guruh")
        # Root markaz guruhi bu ko'rinishda BO'LMASLIGI kerak
        self.assertNotContains(javob, "Root guruh")

    def test_begona_guruh_detali_404(self):
        """⛔ Begona markaz guruhiga to'g'ridan-to'g'ri ID bilan kirish → 404."""
        grant_teacher_access(self.oqituvchi, self.filial)
        self.client.force_login(self.oqituvchi)

        javob = self.client.get(
            self._url(self.root, "education:group_detail", self.guruh_begona.id)
        )
        self.assertEqual(javob.status_code, 404)

    def test_begona_slug_markazni_almashtirmaydi(self):
        """⛔ URL'da begona slug yozish `request.center` ni O'ZGARTIRMAYDI.

        TenantMiddleware autentifikatsiya qilingan foydalanuvchi uchun markazni
        avval sessiya/`user.center` dan bog'laydi; URL slug faqat `request.center`
        BO'SH bo'lganda ishlaydi. Shuning uchun begona slug ma'lumot bermaydi.
        """
        self.client.force_login(self.oqituvchi)

        javob = self.client.get(
            self._url(self.begona, "education:group_detail", self.guruh_begona.id)
        )
        self.assertEqual(javob.status_code, 404)

    def test_soxta_sessiya_tozalanadi(self):
        """⛔ ENG MUHIM: sessiyaga QO'LDA yozilgan `active_center_id` ishlamaydi.

        Middleware har requestda `has_center_access()` ni qayta tekshiradi,
        ruxsat bo'lmasa sessiyani tozalaydi va `user.center` ga qaytaradi.
        """
        self.client.force_login(self.oqituvchi)

        # Hujum: brauzer sessiyasiga begona markaz ID sini yozib qo'yamiz
        sessiya = self.client.session
        sessiya["active_center_id"] = self.begona.id
        sessiya.save()

        javob = self.client.get(
            self._url(self.begona, "education:group_detail", self.guruh_begona.id)
        )
        self.assertEqual(javob.status_code, 404, "Soxta sessiya bilan begona guruh ochildi!")

        # Sessiya tozalangan bo'lishi kerak
        self.assertIsNone(
            self.client.session.get("active_center_id"),
            "Ruxsatsiz active_center_id sessiyada qoldi",
        )

    def test_soxta_sessiya_bilan_filial_guruhi_ham_korinmaydi(self):
        """Ruxsat berilmagan FILIAL uchun ham xuddi shunday (o'z daraxtida bo'lsa ham)."""
        self.client.force_login(self.oqituvchi)

        sessiya = self.client.session
        sessiya["active_center_id"] = self.filial.id   # ruxsat berilMAGAN
        sessiya.save()

        javob = self.client.get(
            self._url(self.filial, "education:group_detail", self.guruh_filial.id)
        )
        self.assertEqual(javob.status_code, 404)
        self.assertIsNone(self.client.session.get("active_center_id"))

    def test_oquvchi_almashtira_olmaydi(self):
        """⛔ Almashish faqat director/teacher uchun — o'quvchi sessiyasi e'tiborsiz."""
        oquvchi = User.objects.create_user(
            email="oq@root.uz", password="parol12345",
            role="student", center=self.root, ism="O'quvchi", familya="Root",
        )
        grant_teacher_access(self.oqituvchi, self.filial)

        self.client.force_login(oquvchi)
        sessiya = self.client.session
        sessiya["active_center_id"] = self.filial.id
        sessiya.save()

        # O'quvchi teacher endpointiga ham kira olmaydi (RBAC)
        javob = self.client.post(
            reverse("accounts:teacher_switch_center"),
            data=json.dumps({"center_id": self.filial.id}),
            content_type="application/json",
        )
        self.assertIn(javob.status_code, (302, 403))

    # ── Direktor/manager panelidan biriktirish ──────────────────────

    def test_direktor_oqituvchini_filialga_biriktiradi(self):
        self.client.force_login(self.direktor)
        javob = self.client.post(
            reverse("accounts:teacher_center_access"),
            data=json.dumps({
                "teacher_id": self.oqituvchi.id,
                "center_id": self.filial.id,
            }),
            content_type="application/json",
        )

        self.assertEqual(javob.status_code, 200)
        self.assertTrue(javob.json()["ok"])
        self.assertTrue(self.oqituvchi.has_center_access(self.filial.id))

    def test_direktor_begona_filialga_biriktira_olmaydi(self):
        """⛔ Direktor faqat O'Z daraxtidagi filialga biriktiradi."""
        self.client.force_login(self.direktor)
        javob = self.client.post(
            reverse("accounts:teacher_center_access"),
            data=json.dumps({
                "teacher_id": self.oqituvchi.id,
                "center_id": self.begona.id,
            }),
            content_type="application/json",
        )

        self.assertEqual(javob.status_code, 403)
        self.assertFalse(TeacherCenterAccess.objects.exists())

    def test_oqituvchi_ozini_biriktira_olmaydi(self):
        """⛔ Ruxsat berish faqat direktor/manager huquqi."""
        self.client.force_login(self.oqituvchi)
        javob = self.client.post(
            reverse("accounts:teacher_center_access"),
            data=json.dumps({
                "teacher_id": self.oqituvchi.id,
                "center_id": self.filial.id,
            }),
            content_type="application/json",
        )

        self.assertIn(javob.status_code, (302, 403))
        self.assertFalse(TeacherCenterAccess.objects.filter(is_active=True).exists())


# ═══════════════════════════════════════════════════════════════════════
#  N+1: ruxsat aniqlash so'rov sonini OSHIRMASLIGI kerak
# ═══════════════════════════════════════════════════════════════════════

class RuxsatNPlusBirTest(TestCase):
    """Filiallar soni ortsa ham query soni O'ZGARMASLIGI shart."""

    def setUp(self):
        _keshlarni_tozala()
        self.root = create_active_center(name="Perf Root", slug="perf-root")
        self.oqituvchi = User.objects.create_user(
            email="perf@root.uz", password="parol12345",
            role="teacher", center=self.root, ism="Perf", familya="Ustoz",
        )
        self.direktor = User.objects.create_user(
            email="perfdir@root.uz", password="parol12345",
            role="director", center=self.root, ism="Perf", familya="Dir",
        )

    def _filiallar_yarat(self, soni: int) -> list[Center]:
        natija = []
        for i in range(soni):
            filial = Center.objects.create(
                name=f"Perf filial {i}", slug=f"perf-filial-{i}",
                parent_center=self.root,
            )
            natija.append(filial)
        return natija

    def test_accessible_centers_bitta_query(self):
        """5 filial bo'lsa ham `accessible_centers()` = 1 query."""
        for filial in self._filiallar_yarat(5):
            grant_teacher_access(self.oqituvchi, filial)

        oqituvchi = User.objects.get(pk=self.oqituvchi.pk)
        with self.assertNumQueries(1):
            markazlar = list(oqituvchi.accessible_centers())

        self.assertEqual(len(markazlar), 6)  # root + 5 filial

    def test_has_center_access_bitta_query(self):
        filial = self._filiallar_yarat(1)[0]
        grant_teacher_access(self.oqituvchi, filial)

        oqituvchi = User.objects.get(pk=self.oqituvchi.pk)
        with self.assertNumQueries(1):
            self.assertTrue(oqituvchi.has_center_access(filial.id))

        # O'z markazi — query umuman kerak emas (`center_id` allaqachon bor)
        with self.assertNumQueries(0):
            self.assertTrue(oqituvchi.has_center_access(self.root.id))

    def test_direktor_uchun_ham_bitta_query(self):
        from accounts.services.center_access import grant_director_access

        for filial in self._filiallar_yarat(4):
            grant_director_access(self.direktor, filial)

        direktor = User.objects.get(pk=self.direktor.pk)
        with self.assertNumQueries(1):
            markazlar = list(direktor.accessible_centers())

        self.assertEqual(len(markazlar), 5)

    def test_center_tree_ids_bitta_query(self):
        """Daraxt ID lari — rekursiv `get_root_center()` emas, bitta so'rov."""
        from accounts.services.center_access import center_tree_ids

        filiallar = self._filiallar_yarat(5)

        with self.assertNumQueries(1):
            idlar = center_tree_ids(self.root)

        self.assertEqual(idlar, {self.root.id} | {f.id for f in filiallar})

    def test_view_query_soni_filiallar_bilan_osmaydi(self):
        """`teacher_my_centers` view'i: 2 filial va 6 filialda bir xil query soni.

        MUHIM O'LCHASH QOIDASI: har o'lchashdan oldin bitta "isitish" so'rovi
        yuboriladi. Sababi — `Center.objects.create()` `core.signals` orqali
        `invalidate_center_tree_cache()` ni chaqiradi va middleware'ning
        block-check cache'i bo'shaydi. Isitishsiz o'lchov N+1 emas, cache
        holatini o'lchab qo'yardi (bu test avval aynan shu sababdan yiqilgan).

        TASDIQ: aniq tenglik EMAS, balki "o'smaydi" (kichik tolerantlik bilan).
        Middleware cache'i va sessiya yozuvi tufayli hisob ±1 tebranishi mumkin,
        lekin N+1 bo'lganda 4 ta qo'shimcha filial kamida 4 ta qo'shimcha
        query beradi — bu tolerantlikdan ancha katta.
        """
        client = Client()
        client.force_login(self.oqituvchi)
        url = reverse("accounts:teacher_my_centers")

        # ── 1-bosqich: 2 filial ──
        for filial in self._filiallar_yarat(2):
            grant_teacher_access(self.oqituvchi, filial)
        client.get(url)                       # isitish (cache + sessiya)
        with _QuerySanoq() as s1:
            javob1 = client.get(url)
        self.assertEqual(len(javob1.json()["centers"]), 3)   # root + 2

        # ── 2-bosqich: yana 4 filial (jami 6) ──
        for i in range(4):
            filial = Center.objects.create(
                name=f"Qoshimcha {i}", slug=f"qoshimcha-{i}", parent_center=self.root,
            )
            grant_teacher_access(self.oqituvchi, filial)
        client.get(url)                       # isitish
        with _QuerySanoq() as s2:
            javob2 = client.get(url)
        self.assertEqual(len(javob2.json()["centers"]), 7)   # root + 6

        TOLERANTLIK = 1
        self.assertLessEqual(
            s2.soni, s1.soni + TOLERANTLIK,
            f"Filiallar 2 → 6 ga ko'paygach query soni {s1.soni} → {s2.soni} "
            f"bo'ldi. Bu N+1: har filial uchun alohida so'rov ketmoqda.",
        )


class _QuerySanoq:
    """`assertNumQueries` ning qiymat qaytaradigan varianti (taqqoslash uchun)."""

    def __enter__(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self._ctx = CaptureQueriesContext(connection)
        self._ctx.__enter__()
        return self

    def __exit__(self, *args):
        self._ctx.__exit__(*args)
        self.soni = len(self._ctx.captured_queries)
        return False
