"""Guruhdan guruhga ko'chirish — aniqlik tekshiruvi.

Ikki asosiy savolni sinaydi:
  1) Ko'chirilganда o'quvchi ESKI guruhda aktiv qolib ketadimi? (qolmasligi kerak)
  2) To'lov/qarz qayta hisoblanadimi — eski (o'tgan oy + proratsiya) qarz
     yo'qolmasdan, yangi guruh qarzi ustiga qo'shilib, HAQIQIY jami qarz chiqadimi?
"""
from datetime import date

from django.test import TestCase
from django.contrib.auth import get_user_model
from freezegun import freeze_time

from core.test_utils import activate_center
from education.models import Attendance, Enrollment, Group, TuitionMonth
from education.services.student_transfer import transfer_student_to_group
from education.services.tuition import ensure_tuition_month
from education.views import get_student_total_debt

User = get_user_model()

PER_A = 300_000 // 12  # 25_000 — A guruh bir dars narxi


@freeze_time("2026-07-19")
class GroupTransferVerification(TestCase):
    def setUp(self):
        self.center = Center = None
        from accounts.models import Center as _Center
        self.center = _Center.objects.create(name="Transfer Verify", slug="transfer-verify")
        activate_center(self.center)
        self.director = User.objects.create_user(
            email="dir@tv.test", password="x", role="director", center=self.center,
            ism="Dir", familya="TV",
        )
        self.teacher = User.objects.create_user(
            email="teach@tv.test", password="x", role="teacher", center=self.center,
            ism="Teach", familya="TV", oqituvchi_foizi=40,
        )
        self.student = User.objects.create_user(
            email="stu@tv.test", password="x", role="student", center=self.center,
            ism="Stu", familya="TV",
        )
        # A: 300k/oy, B: 500k/oy — ikkalasi 12 dars, jadval yo'q → oylik dars=12
        self.group_a = Group.objects.create(
            center=self.center, nom="A (300k)", oqituvchi=self.teacher,
            kurs_narxi=300_000, oqituvchi_foiz=40, oy_dars_soni=12,
        )
        self.group_b = Group.objects.create(
            center=self.center, nom="B (500k)", oqituvchi=self.teacher,
            kurs_narxi=500_000, oqituvchi_foiz=40, oy_dars_soni=12,
        )
        self.enr_a = Enrollment.objects.create(
            center=self.center, group=self.group_a, student=self.student,
            kurs_narhi=300_000, oqituvchi_foiz=40, monthly_lessons=12,
            joined_at=date(2026, 5, 1), is_active=True,
        )

    def _attend(self, group, days):
        for d in days:
            Attendance.objects.create(
                center=self.center, group=group, student=self.student,
                teacher=self.teacher, date=date(2026, 7, d),
                status="present", present=True,
            )

    def _transfer(self, when=date(2026, 7, 15)):
        return transfer_student_to_group(
            student=self.student, old_group=self.group_a, new_group=self.group_b,
            transfer_date=when, reason="Test ko'chirish", user=self.director,
        )

    # ── SAVOL 1: eski guruhda o'quvchi qolib ketmaydimi? ──
    def test_1_student_not_left_in_old_group(self):
        self._attend(self.group_a, [3, 5])
        self._transfer()
        self.enr_a.refresh_from_db()
        # eski enrollment nofaol
        self.assertFalse(self.enr_a.is_active, "Eski guruh enrollmenti hali aktiv!")
        # eski guruhda aktiv enrollment YO'Q
        self.assertEqual(
            Enrollment.objects.filter(group=self.group_a, student=self.student, is_active=True).count(),
            0, "O'quvchi eski guruhda aktiv qolib ketdi!",
        )
        # yangi guruhda AYNAN 1 ta aktiv enrollment
        self.assertEqual(
            Enrollment.objects.filter(group=self.group_b, student=self.student, is_active=True).count(),
            1, "O'quvchi yangi guruhga o'tmadi yoki dublikat bor!",
        )

    # ── SAVOL 2a: o'tgan oy qarzi ko'chirishда yo'qolmaydimi? ──
    def test_2_past_unpaid_debt_survives_transfer(self):
        # Iyun (o'tgan oy) — A guruhda to'lanmagan 300k qarz
        june_tm = ensure_tuition_month(self.enr_a, date(2026, 6, 1))
        self.assertEqual(int(june_tm.fee_amount), 300_000)
        debt_before = get_student_total_debt(self.student, self.center)
        self.assertGreaterEqual(debt_before, 300_000)

        self._attend(self.group_a, [4])
        self._transfer()

        # Iyun TM hali mavjud (nofaol enrollmentda) va qarz hisobiga kiradi
        june_tm.refresh_from_db()
        self.assertFalse(june_tm.is_deleted)
        debt_after = get_student_total_debt(self.student, self.center)
        self.assertGreaterEqual(
            debt_after, 300_000,
            f"O'tgan oy (iyun) qarzi yo'qoldi! oldin={debt_before} keyin={debt_after}",
        )

    # ── SAVOL 2b: ko'chirish oyi ikki barobar hisoblanmaydimi (proratsiya + cap)? ──
    def test_3_transfer_month_is_prorated_not_doubled(self):
        self._attend(self.group_a, [1, 3, 6, 9])  # A da 4 ta dars
        result = self._transfer()
        old_tm = TuitionMonth.objects.get(enrollment=self.enr_a, month=date(2026, 7, 1))
        new_tm = TuitionMonth.objects.get(enrollment=result["new_enrollment"], month=date(2026, 7, 1))
        # Eski fee = 4 dars × 25_000 = 100_000
        self.assertEqual(int(old_tm.fee_amount), PER_A * 4)
        self.assertGreater(int(new_tm.fee_amount), 0)
        # Ikki barobar EMAS: jami ≤ eng katta oylik (cap = max(300k, 500k) = 500k)
        combined = int(old_tm.fee_amount) + int(new_tm.fee_amount)
        self.assertLessEqual(combined, 500_000, f"Ko'chirish oyi ikki barobar hisoblandi: {combined}")
        self.assertNotEqual(combined, 800_000)  # 300k + 500k bo'lmasligi kerak

    # ── SAVOL 2c: HAQIQIY jami qarz = o'tgan oy + ko'chirish oyi (eski+yangi) ──
    def test_4_total_debt_combines_old_and_new(self):
        ensure_tuition_month(self.enr_a, date(2026, 6, 1))  # iyun 300k to'lanmagan
        self._attend(self.group_a, [1, 3, 6, 9])            # iyulda A da 4 dars
        result = self._transfer()
        old_tm = TuitionMonth.objects.get(enrollment=self.enr_a, month=date(2026, 7, 1))
        new_tm = TuitionMonth.objects.get(enrollment=result["new_enrollment"], month=date(2026, 7, 1))
        expected = 300_000 + int(old_tm.fee_amount) + int(new_tm.fee_amount)
        total = get_student_total_debt(self.student, self.center)
        self.assertEqual(
            total, expected,
            f"Jami qarz noto'g'ri! kutilgan={expected} (iyun 300k + iyul eski {old_tm.fee_amount} "
            f"+ iyul yangi {new_tm.fee_amount}), chiqqan={total}",
        )

    # ── ATOMICITY: yarim-yiqilган ko'chirish ma'lumotni buzib qoldirmaydimi? ──
    def test_6_failed_transfer_rolls_back_cleanly(self):
        from unittest.mock import patch
        june_tm = ensure_tuition_month(self.enr_a, date(2026, 6, 1))
        self.assertEqual(int(june_tm.fee_amount), 300_000)
        # Ko'chirish OYI uchun TuitionMonth OLDINDAN mavjud (300k) — mavjud
        # test aynan shu holatda yiqilardi.
        july_tm = ensure_tuition_month(self.enr_a, date(2026, 7, 1))
        self.assertEqual(int(july_tm.fee_amount), 300_000)
        self._attend(self.group_a, [2, 4])
        with patch(
            "education.services.student_transfer.StudentGroupTransfer.objects.create",
            side_effect=RuntimeError("simulyatsiya: oxirida xato"),
        ):
            with self.assertRaises(RuntimeError):
                self._transfer()
        # Rollback: hamma narsa ESKI holatiga qaytishi kerak
        self.enr_a.refresh_from_db()
        june_tm.refresh_from_db()
        self.assertTrue(self.enr_a.is_active, "Rollback: eski enrollment aktiv qolishi kerak edi!")
        self.assertEqual(
            int(june_tm.fee_amount), 300_000,
            "Rollback: eski TuitionMonth fee o'zgarib qoldi (ma'lumot buzildi)!",
        )
        self.assertFalse(
            Enrollment.objects.filter(group=self.group_b, student=self.student, is_active=True).exists(),
            "Rollback: yangi guruhda enrollment qolib ketdi!",
        )
        # Iyul old_tm — yaratilган bo'lmasligi yoki 300k qolishi kerak (proratsiyaga o'zgarmasin)
        july = TuitionMonth.all_objects.filter(enrollment=self.enr_a, month=date(2026, 7, 1)).first()
        if july is not None:
            self.assertEqual(
                int(july.fee_amount), 300_000,
                f"Rollback: iyul fee proratsiyaga o'zgarib qoldi ({july.fee_amount})!",
            )

    # ── Kelajakda: keyingi to'liq oy YANGI guruh narxi bilan ──
    def test_5_next_month_uses_new_group_price(self):
        self._attend(self.group_a, [2])
        result = self._transfer()
        new_enr = result["new_enrollment"]
        aug_tm = ensure_tuition_month(new_enr, date(2026, 8, 1))
        self.assertEqual(int(aug_tm.fee_amount), 500_000, "Keyingi oy yangi guruh narxi (500k) bo'lishi kerak")
