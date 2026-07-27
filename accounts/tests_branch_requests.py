"""Filial so'rovlari: tasdiqlash mantiqining testlari.

Asosiy tekshiruv — tasdiqlangandan keyin filial **haqiqatan ro'yxatda
ko'rinadi**. Ilgari Django admin'da status qo'lda o'zgartirilsa markaz
yaratilmasdi va direktor filialni ko'rmasdi; shu holat qaytmasligi kerak.
"""

from __future__ import annotations

import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import BranchRequest, Center, DirectorCenterAccess, User
from accounts.services import branch_requests as branch_service


class FilialTasdiqlashTest(TestCase):
    def setUp(self):
        self.asosiy = Center.objects.create(
            name="Asosiy Markaz", slug="asosiy-markaz", status=Center.STATUS_ACTIVE
        )
        self.director = User.objects.create_user(
            email="dir@example.com", password="parol12345",
            role="director", center=self.asosiy,
        )
        self.sorov = BranchRequest.objects.create(
            requester=self.director,
            parent_center=self.asosiy,
            name="Chilonzor Filiali",
            address="Toshkent, Chilonzor",
            phone="+998901234567",
        )

    def test_tasdiqlash_markaz_yaratadi(self):
        markaz = branch_service.tasdiqla(self.sorov)

        self.assertEqual(markaz.name, "Chilonzor Filiali")
        self.assertEqual(markaz.parent_center_id, self.asosiy.id)
        self.assertEqual(markaz.status, Center.STATUS_ACTIVE)
        self.assertEqual(markaz.plan, self.asosiy.plan)

        self.sorov.refresh_from_db()
        self.assertEqual(self.sorov.status, BranchRequest.Status.APPROVED)
        self.assertEqual(self.sorov.created_center_id, markaz.id)
        self.assertIsNotNone(self.sorov.reviewed_at)

    def test_direktorga_ruxsat_beriladi(self):
        """Busiz filial yaratilsa ham ro'yxatda ko'rinmaydi — asosiy bug shu edi."""
        markaz = branch_service.tasdiqla(self.sorov)

        self.assertTrue(
            DirectorCenterAccess.objects.filter(
                director=self.director, center=markaz, is_active=True
            ).exists()
        )

    def test_filial_markazlar_royxatida_korinadi(self):
        """Uchdan-uchgacha: tasdiqlangach direktor uni almashtirgichda ko'radi."""
        markaz = branch_service.tasdiqla(self.sorov)

        self.client.force_login(self.director)
        # Direktor tenant marshrutidan foydalanadi (/hisob/…); /platform/ ostidagi
        # xuddi shu view'ni RBAC faqat superadminga ochadi.
        javob = self.client.get(reverse("accounts:my_centers"))
        self.assertEqual(javob.status_code, 200)

        malumot = javob.json()
        idlar = [m["id"] for m in malumot["centers"]]
        self.assertIn(markaz.id, idlar, "Yangi filial markazlar ro'yxatida yo'q")

    def test_ikki_marta_tasdiqlash_yangi_markaz_ochmaydi(self):
        """Telegram tugmasi ikki marta bosilishi mumkin."""
        birinchi = branch_service.tasdiqla(self.sorov)
        ikkinchi = branch_service.tasdiqla(self.sorov)

        self.assertEqual(birinchi.id, ikkinchi.id)
        self.assertEqual(Center.objects.filter(parent_center=self.asosiy).count(), 1)

    def test_rad_etilganni_tasdiqlab_bolmaydi(self):
        branch_service.rad_et(self.sorov, sabab="Hujjat yetarli emas")

        with self.assertRaises(branch_service.FilialXatosi):
            branch_service.tasdiqla(self.sorov)

    def test_tasdiqlanganni_rad_etib_bolmaydi(self):
        branch_service.tasdiqla(self.sorov)

        with self.assertRaises(branch_service.FilialXatosi):
            branch_service.rad_et(self.sorov)

    def test_nosoz_qator_tuzatiladi(self):
        """Django admin'da qo'lda 'approved' qilingan qator (markazsiz) tuzalsin."""
        BranchRequest.objects.filter(pk=self.sorov.pk).update(
            status=BranchRequest.Status.APPROVED, created_center=None
        )
        self.sorov.refresh_from_db()

        markaz = branch_service.tasdiqla(self.sorov)

        self.sorov.refresh_from_db()
        self.assertEqual(self.sorov.created_center_id, markaz.id)
        self.assertTrue(
            DirectorCenterAccess.objects.filter(
                director=self.director, center=markaz, is_active=True
            ).exists()
        )

    def test_tuzatish_buyrugi(self):
        from io import StringIO

        from django.core.management import call_command

        BranchRequest.objects.filter(pk=self.sorov.pk).update(
            status=BranchRequest.Status.APPROVED, created_center=None
        )

        chiqish = StringIO()
        call_command("filiallarni_tuzat", "--bajar", stdout=chiqish)

        self.sorov.refresh_from_db()
        self.assertIsNotNone(self.sorov.created_center)
        self.assertIn("Tuzatildi: 1", chiqish.getvalue())

    def test_bir_xil_nom_slug_toknashuvi(self):
        """Xuddi shu nomli markaz bo'lsa ham slug band bo'lmasligi kerak."""
        Center.objects.create(
            name="Chilonzor Filiali", slug="chilonzor-filiali",
            status=Center.STATUS_ACTIVE,
        )
        markaz = branch_service.tasdiqla(self.sorov)
        self.assertNotEqual(markaz.slug, "chilonzor-filiali")


class SuperadminFilialPanelTest(TestCase):
    def setUp(self):
        self.asosiy = Center.objects.create(
            name="Asosiy", slug="asosiy", status=Center.STATUS_ACTIVE
        )
        self.director = User.objects.create_user(
            email="dir2@example.com", password="parol12345",
            role="director", center=self.asosiy,
        )
        self.superadmin = User.objects.create_superuser(
            email="super@example.com", password="parol12345",
        )
        self.sorov = BranchRequest.objects.create(
            requester=self.director, parent_center=self.asosiy, name="Yunusobod",
        )

    def test_sahifada_sorov_korinadi(self):
        """Asosiy shikoyat: panelda ariza umuman yo'q edi."""
        self.client.force_login(self.superadmin)
        javob = self.client.get(reverse("platform_global:superadmin_filiallar"))

        self.assertEqual(javob.status_code, 200)
        self.assertContains(javob, "Yunusobod")
        self.assertEqual(javob.context["kutilmoqda_soni"], 1)

    def test_paneldan_tasdiqlash(self):
        self.client.force_login(self.superadmin)
        javob = self.client.post(
            reverse("platform_global:branch_request_action", args=[self.sorov.id]),
            data=json.dumps({"amal": "tasdiqla"}),
            content_type="application/json",
        )

        self.assertEqual(javob.status_code, 200)
        self.assertTrue(javob.json()["ok"])

        self.sorov.refresh_from_db()
        self.assertEqual(self.sorov.status, BranchRequest.Status.APPROVED)
        self.assertIsNotNone(self.sorov.created_center)

    def test_oddiy_foydalanuvchi_kira_olmaydi(self):
        self.client.force_login(self.director)
        javob = self.client.get(reverse("platform_global:superadmin_filiallar"))
        self.assertNotEqual(javob.status_code, 200)

    def test_dashboardda_kutilayotgan_soni(self):
        self.client.force_login(self.superadmin)
        javob = self.client.get(reverse("platform_global:superadmin_dashboard"))
        self.assertEqual(javob.context["kutilayotgan_filial_soni"], 1)
