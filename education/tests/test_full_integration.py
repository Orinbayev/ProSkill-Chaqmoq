"""
To'liq integratsion test:
1. O'quvchini A guruhga qo'shish (500k/oy, 12 dars)
2. A guruhda 4 ta davomat qilish
3. A → B guruhga ko'chirish
4. B guruhda 6 ta davomat qilish
5. Fee to'g'ri hisoblanganini tekshirish (166,664 + 249,996 = 416,660)
6. Chaqmoq: ko'p qoldirgan o'quvchiga jarima
7. Chaqmoq: to'liq kelgan o'quvchiga bonus
"""
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Center, User
from chaqmoq.models import Ledger, Rule
from education.models import Attendance, Enrollment, Group, TuitionMonth
from education.services.student_transfer import transfer_student_to_group
from education.services.tuition import (
    get_month_paid,
    reconcile_tuition_month,
    tuition_month_fee,
)


MONTH = date(2026, 4, 1)          # Test oyi: Aprel 2026
TRANSFER_DATE = date(2026, 4, 15)  # Ko'chirish sanasi
NEXT_MONTH_FIRST = date(2026, 5, 1)  # Chaqmoq qoidalari ishlatiladigan sana


# ───────────────────────────── helpers ─────────────────────────────

def _att(center, group, student, teacher, day, status, director):
    return Attendance.objects.create(
        center=center,
        group=group,
        student=student,
        teacher=teacher,
        date=date(2026, 4, day),
        status=status,
        present=(status == "present"),
        forced=False,
        created_by=director,
    )


# ══════════════════════════════════════════════════════════════════════
#  TEST 1: Guruhdan guruhga ko'chirish + fee hisoblash
# ══════════════════════════════════════════════════════════════════════

class TransferAndFeeIntegrationTest(TestCase):
    """
    Scenario:
      - O'quvchi A guruhga qo'shiladi (500k/oy, 12 dars)
      - A guruhda 4 ta "present" davomat → 4 × 41,666 = 166,664 so'm
      - 15-aprelda B guruhga ko'chiriladi (ham 500k/oy, 12 dars)
      - B guruhda 6 ta "present" davomat → 6 × 41,666 = 249,996 so'm
      - Ikkala TuitionMonth reconcile qilinadi
      - Jami qarz: 166,664 + 249,996 = 416,660 so'm
      - To'lov qilinmagan — barcha qarz o'quvchida turibdi
    """

    def setUp(self):
        self.center = Center.objects.create(
            name="Integration Center", slug="integration-center"
        )
        self.director = User.objects.create_user(
            email="director@int.test", password="pass",
            role="director", center=self.center,
            ism="Dir", familya="Int",
        )
        self.teacher = User.objects.create_user(
            email="teacher@int.test", password="pass",
            role="teacher", center=self.center,
            ism="Teacher", familya="Int",
        )
        self.student = User.objects.create_user(
            email="student@int.test", password="pass",
            role="student", center=self.center,
            ism="Ali", familya="Valiyev",
        )

        # A va B guruh: narxi 500k, oylik dars soni 12
        self.group_a = Group.objects.create(
            center=self.center, nom="A Guruh",
            oqituvchi=self.teacher,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.group_b = Group.objects.create(
            center=self.center, nom="B Guruh",
            oqituvchi=self.teacher,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )

        # A guruhga qo'shish
        self.enrollment_a = Enrollment.objects.create(
            center=self.center,
            group=self.group_a,
            student=self.student,
            kurs_narhi=500_000,
            oqituvchi_foiz=40,
            is_active=True,
            joined_at=MONTH,
            monthly_lessons=12,
        )

    # ─── A guruhda 4 ta present davomat ───────────────────────────────
    def _add_a_attendances(self):
        for day in (1, 5, 8, 12):  # 4 ta dars
            _att(self.center, self.group_a, self.student,
                 self.teacher, day, "present", self.director)

    # ─── B guruhda 6 ta present davomat ───────────────────────────────
    def _add_b_attendances(self, new_enrollment):
        for day in (15, 17, 20, 22, 25, 28):  # 6 ta dars
            _att(self.center, self.group_b, self.student,
                 self.teacher, day, "present", self.director)

    def test_transfer_and_prorated_fee(self):
        # 1. A guruhda 4 ta davomat
        self._add_a_attendances()

        # 2. Ko'chirish
        result = transfer_student_to_group(
            student=self.student,
            old_group=self.group_a,
            new_group=self.group_b,
            transfer_date=TRANSFER_DATE,
            reason="Integratsion test ko'chirish",
            user=self.director,
        )
        new_enrollment = result["new_enrollment"]
        old_tm = result["old_tuition_month"]
        new_tm = result["new_tuition_month"]

        # 3. B guruhda 6 ta davomat
        self._add_b_attendances(new_enrollment)

        # 4. Oy oxirida reconcile (haqiqiy davomatga moslashtirish)
        old_tm_reconciled = reconcile_tuition_month(self.enrollment_a, MONTH)
        new_tm_reconciled = reconcile_tuition_month(new_enrollment, MONTH)

        # ─── Hisob tekshiruvi ─────────────────────────────────────────
        per_lesson = 500_000 / 12

        expected_a_fee = round(4 * per_lesson)   # 166,667
        expected_b_fee = round(6 * per_lesson)   # 250,000
        expected_total = expected_a_fee + expected_b_fee  # 416,667

        actual_a_fee = tuition_month_fee(old_tm_reconciled)
        actual_b_fee = tuition_month_fee(new_tm_reconciled)
        actual_total = actual_a_fee + actual_b_fee

        self.assertEqual(
            actual_a_fee, expected_a_fee,
            f"A guruh fee noto'g'ri: {actual_a_fee} != {expected_a_fee} (4 dars × {per_lesson})"
        )
        self.assertEqual(
            actual_b_fee, expected_b_fee,
            f"B guruh fee noto'g'ri: {actual_b_fee} != {expected_b_fee} (6 dars × {per_lesson})"
        )
        self.assertEqual(
            actual_total, expected_total,
            f"Jami fee noto'g'ri: {actual_total} != {expected_total}"
        )


        # To'lov qilinmagan — qarz = fee
        self.assertEqual(get_month_paid(old_tm_reconciled), 0, "A guruh: to'lov bo'lmasligi kerak")
        self.assertEqual(get_month_paid(new_tm_reconciled), 0, "B guruh: to'lov bo'lmasligi kerak")

        # Ko'chirish yozuvi (archive) yaratilgan
        self.assertIsNotNone(result["transfer"])
        self.assertEqual(result["transfer"].old_group, self.group_a)
        self.assertEqual(result["transfer"].new_group, self.group_b)

        # Eski enrollment o'chirilgan, yangi aktiv
        self.enrollment_a.refresh_from_db()
        new_enrollment.refresh_from_db()
        self.assertFalse(self.enrollment_a.is_active, "Eski enrollment aktiv bo'lmasligi kerak")
        self.assertTrue(new_enrollment.is_active, "Yangi enrollment aktiv bo'lishi kerak")

        print(f"\n{'='*55}")
        print(f"  TRANSFER VA FEE TEST NATIJALARI")
        print(f"{'='*55}")
        print(f"  Bir dars narxi     : {per_lesson:>10,} so'm")
        print(f"  A guruh  (4 dars)  : {actual_a_fee:>10,} so'm")
        print(f"  B guruh  (6 dars)  : {actual_b_fee:>10,} so'm")
        print(f"  JAMI QARZ          : {actual_total:>10,} so'm")
        print(f"  Kutilgan jami      : {expected_total:>10,} so'm")
        print(f"  Natija             : {'✓ TO\'G\'RI' if actual_total == expected_total else '✗ XATO'}")
        print(f"{'='*55}")

    def test_credit_balance_transfers_with_student(self):
        """Ortiqcha to'lov yangi guruhga ko'chirilishi kerak."""
        self.enrollment_a.credit_balance = 50_000
        self.enrollment_a.save(update_fields=["credit_balance"])

        result = transfer_student_to_group(
            student=self.student,
            old_group=self.group_a,
            new_group=self.group_b,
            transfer_date=TRANSFER_DATE,
            reason="Credit balance test",
            user=self.director,
        )
        new_enrollment = result["new_enrollment"]
        self.enrollment_a.refresh_from_db()
        new_enrollment.refresh_from_db()

        self.assertEqual(
            self.enrollment_a.credit_balance, 0,
            "Eski enrollment credit_balance 0 bo'lishi kerak"
        )
        self.assertEqual(
            new_enrollment.credit_balance, 50_000,
            "Yangi enrollment credit_balance 50,000 bo'lishi kerak"
        )
        print(f"\n  Credit balance ko'chirildi: 0 → 50,000 ✓")

    def test_cannot_transfer_to_closed_group(self):
        """Yopilgan guruhga ko'chirish taqiqlangan."""
        from django.core.exceptions import ValidationError
        self.group_b.is_closed = True
        self.group_b.save(update_fields=["is_closed"])

        with self.assertRaises(ValidationError) as ctx:
            transfer_student_to_group(
                student=self.student,
                old_group=self.group_a,
                new_group=self.group_b,
                transfer_date=TRANSFER_DATE,
                reason="Test",
                user=self.director,
            )
        self.assertIn("Yopilgan", str(ctx.exception))
        print(f"\n  Yopilgan guruhga ko'chirish to'g'ri taqiqlandi ✓")

    def test_cannot_transfer_to_full_group(self):
        """To'liq guruhga ko'chirish taqiqlangan."""
        from django.core.exceptions import ValidationError
        self.group_b.max_students = 1
        self.group_b.save(update_fields=["max_students"])

        # Guruhga boshqa o'quvchi qo'shamiz → to'ldi
        other = User.objects.create_user(
            email="other@int.test", password="pass",
            role="student", center=self.center,
            ism="Boshqa", familya="O'quvchi",
        )
        Enrollment.objects.create(
            center=self.center, group=self.group_b,
            student=other, kurs_narhi=500_000,
            oqituvchi_foiz=40, is_active=True,
        )

        with self.assertRaises(ValidationError) as ctx:
            transfer_student_to_group(
                student=self.student,
                old_group=self.group_a,
                new_group=self.group_b,
                transfer_date=TRANSFER_DATE,
                reason="Test",
                user=self.director,
            )
        self.assertIn("to'liq", str(ctx.exception))
        print(f"\n  To'liq guruhga ko'chirish to'g'ri taqiqlandi ✓")

    def test_cannot_transfer_with_future_date(self):
        """Kelajak sanada ko'chirish taqiqlangan."""
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError) as ctx:
            transfer_student_to_group(
                student=self.student,
                old_group=self.group_a,
                new_group=self.group_b,
                transfer_date=date(2099, 1, 1),
                reason="Test",
                user=self.director,
            )
        self.assertIn("kelajakda", str(ctx.exception))
        print(f"\n  Kelajak sana bilan ko'chirish to'g'ri taqiqlandi ✓")


# ══════════════════════════════════════════════════════════════════════
#  TEST 2: Chaqmoq jarima (ko'p qoldirsa) va bonus (to'liq kelsa)
# ══════════════════════════════════════════════════════════════════════

class ChaqmoqAttendanceRuleIntegrationTest(TestCase):
    """
    Scenario:
      - missed_student: Aprelda 4 ta sababsiz dars qoldiradi
        → Mayning 1-kunida -5 chaqmoq ayirilishi kerak
      - full_student: Aprelda 12 ta darsga keladi, 0 ta sababsiz qoldirmaydi
        → Mayning 1-kunida +10 chaqmoq qo'shilishi kerak
      - partial_student: 2 ta qoldiradi, 5 ta keladi
        → Hech qanday o'zgarish bo'lmasligi kerak
    """

    def setUp(self):
        self.center = Center.objects.create(
            name="Chaqmoq Center", slug="chaqmoq-center"
        )
        self.director = User.objects.create_user(
            email="director@chq.test", password="pass",
            role="director", center=self.center,
            ism="Dir", familya="Chq",
        )
        self.teacher = User.objects.create_user(
            email="teacher@chq.test", password="pass",
            role="teacher", center=self.center,
            ism="Teacher", familya="Chq",
        )
        self.group = Group.objects.create(
            center=self.center, nom="Chaqmoq Guruh",
            oqituvchi=self.teacher,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )

        # Jarima qoidasi: 3 ta sababsiz qoldirsa → -5 chaqmoq
        self.penalty_rule = Rule.objects.create(
            center=self.center,
            nom="Davomat jarimasi (test)",
            tur=Rule.ATTENDANCE_PENALTY,
            absence_limit=3,
            lightning_penalty=-5,
            period="monthly",
        )
        # Bonus qoidasi: 12 ta kelsa va 0 sababsiz → +10 chaqmoq
        self.bonus_rule = Rule.objects.create(
            center=self.center,
            nom="Davomat bonusi (test)",
            tur=Rule.ATTENDANCE_BONUS,
            presence_limit=12,
            lightning_bonus=10,
            period="monthly",
        )

        self.missed_student = self._make_student("missed", "+998901110001")
        self.full_student = self._make_student("full", "+998901110002")
        self.partial_student = self._make_student("partial", "+998901110003")

    def _make_student(self, key, phone):
        user = User.objects.create_user(
            email=f"{key}@chq.test", password="pass",
            role="student", center=self.center,
            ism=key.capitalize(), familya="O'quvchi",
            telefon1=phone,
        )
        Enrollment.objects.create(
            center=self.center, group=self.group,
            student=user, kurs_narhi=500_000,
            oqituvchi_foiz=40, is_active=True,
        )
        return user

    def _att(self, student, day, status):
        _att(self.center, self.group, student,
             self.teacher, day, status, self.director)

    def _run_monthly_rules(self):
        out = StringIO()
        call_command("apply_monthly_rules", "--force-date", "2026-05-01", stdout=out)
        return out.getvalue()

    def test_missed_student_gets_chaqmoq_deducted(self):
        """4 ta sababsiz qoldirgan → -5 chaqmoq ayiriladi."""
        # Aprelda 4 ta sababsiz qoldirish (limit: 3)
        for day in (2, 6, 10, 14):
            self._att(self.missed_student, day, "absent_unexcused")
        # + 2 ta keldi (aralash)
        for day in (4, 8):
            self._att(self.missed_student, day, "present")

        output = self._run_monthly_rules()

        ledger = Ledger.objects.filter(
            student=self.missed_student,
            rule=self.penalty_rule,
            related_month=MONTH,
        ).first()

        self.assertIsNotNone(ledger, "Jarima yozuvi yaratilmagan!")
        self.assertEqual(ledger.ball, -5, f"Jarima -5 bo'lishi kerak, {ledger.ball} chiqdi")

        # Bonus berilmasligi kerak
        self.assertFalse(
            Ledger.objects.filter(student=self.missed_student, rule=self.bonus_rule).exists(),
            "Ko'p qoldirgan o'quvchiga bonus berilmasligi kerak"
        )

        print(f"\n{'='*55}")
        print(f"  CHAQMOQ JARIMA TEST")
        print(f"{'='*55}")
        print(f"  4 ta sababsiz qoldirdi (limit: 3)")
        print(f"  Ayirildi: {ledger.ball} chaqmoq  ✓")
        print(f"{'='*55}")

    def test_full_student_gets_chaqmoq_bonus(self):
        """12 ta keldi, 0 sababsiz qoldirmadi → +10 chaqmoq qo'shiladi."""
        # Aprelda 12 ta present
        for day in (1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23):
            self._att(self.full_student, day, "present")

        output = self._run_monthly_rules()

        ledger = Ledger.objects.filter(
            student=self.full_student,
            rule=self.bonus_rule,
            related_month=MONTH,
        ).first()

        self.assertIsNotNone(ledger, "Bonus yozuvi yaratilmagan!")
        self.assertEqual(ledger.ball, 10, f"Bonus +10 bo'lishi kerak, {ledger.ball} chiqdi")

        # Jarima berilmasligi kerak
        self.assertFalse(
            Ledger.objects.filter(student=self.full_student, rule=self.penalty_rule).exists(),
            "To'liq kelgan o'quvchiga jarima berilmasligi kerak"
        )

        print(f"\n{'='*55}")
        print(f"  CHAQMOQ BONUS TEST")
        print(f"{'='*55}")
        print(f"  12 ta darsga keldi, 0 sababsiz qoldirmadi")
        print(f"  Qo'shildi: +{ledger.ball} chaqmoq  ✓")
        print(f"{'='*55}")

    def test_partial_student_gets_nothing(self):
        """2 ta qoldirdi, 5 ta keldi → na jarima, na bonus."""
        for day in (2, 6):
            self._att(self.partial_student, day, "absent_unexcused")  # 2 ta (limit: 3)
        for day in (4, 8, 12, 16, 20):
            self._att(self.partial_student, day, "present")  # 5 ta (limit: 12)

        self._run_monthly_rules()

        self.assertFalse(
            Ledger.objects.filter(student=self.partial_student).exists(),
            "O'rtacha o'quvchiga hech narsa berilmasligi kerak"
        )
        print(f"\n  O'rtacha o'quvchi: na jarima, na bonus  ✓")

    def test_idempotency_run_twice_no_duplicate(self):
        """Qoida ikki marta ishga tushsa ham bir marta yoziladi."""
        for day in (2, 6, 10, 14):
            self._att(self.missed_student, day, "absent_unexcused")

        self._run_monthly_rules()
        self._run_monthly_rules()  # Ikkinchi marta

        count = Ledger.objects.filter(
            student=self.missed_student,
            rule=self.penalty_rule,
            related_month=MONTH,
        ).count()
        self.assertEqual(count, 1, f"Bir marta yozilishi kerak, {count} marta yozildi!")
        print(f"\n  Idempotentlik: 2 marta ishga tushsa ham 1 ta yozuv  ✓")

    def test_balance_calculation(self):
        """Chaqmoq balans to'g'ri hisoblanadi (jarima + bonus = net)."""
        # missed_student: jarima oladi
        for day in (2, 6, 10, 14):
            self._att(self.missed_student, day, "absent_unexcused")
        # full_student: bonus oladi
        for day in (1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23):
            self._att(self.full_student, day, "present")

        self._run_monthly_rules()

        missed_balance = sum(
            Ledger.objects.filter(student=self.missed_student).values_list("ball", flat=True)
        )
        full_balance = sum(
            Ledger.objects.filter(student=self.full_student).values_list("ball", flat=True)
        )

        self.assertEqual(missed_balance, -5, f"Missed balans: {missed_balance} != -5")
        self.assertEqual(full_balance, 10, f"Full balans: {full_balance} != 10")

        print(f"\n{'='*55}")
        print(f"  CHAQMOQ BALANS")
        print(f"{'='*55}")
        print(f"  Ko'p qoldirgan o'quvchi : {missed_balance:>+4} chaqmoq")
        print(f"  To'liq kelgan o'quvchi  : {full_balance:>+4} chaqmoq")
        print(f"{'='*55}")
