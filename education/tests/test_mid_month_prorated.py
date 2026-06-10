"""
Oyning o'rtasidan qo'shilgan o'quvchi uchun prorated qarz testi.

Stsenariy:
  Guruh: Du/Ch jadval (hafnada 2 kun), oy_dars_soni=8, narx=800_000
  O'quvchi: 2026-06-10 (Chorshanba) qo'shildi
  Oy: 2026-06-01

June 2026 takvimi:
  Du: 1, 8, 15, 22, 29
  Ch: 3, 10, 17, 24

O'tilgan darslar (June 1–9): June 1(Du), 3(Ch), 8(Du) = 3 dars
Qolgan darslar (June 10–30): June 10(Ch), 15(Du), 17(Ch), 22(Du), 24(Ch), 29(Du) = 6 dars

Per lesson = 800_000 / 8 = 100_000
Kutilayotgan qarz = 6 * 100_000 = 600_000
"""
from datetime import date
from django.test import TestCase

from accounts.models import Center, User
from education.models import (
    Enrollment, Group, GroupSchedule, StudentGroupHistory, TuitionMonth,
    Payment, PaymentAllocation,
)
from education.services.tuition import (
    prorated_monthly_fee,
    tuition_month_lesson_count,
    ensure_tuition_month,
    scheduled_lessons_between,
    tuition_month_fee_field,
    calculate_student_month_billing,
    calculate_enrollment_debt_snapshots,
    month_first_day,
)

PRICE = 800_000
LESSONS_PER_MONTH = 8
JOIN_DATE = date(2026, 6, 10)   # Chorshanba
MONTH = date(2026, 6, 1)


def _fee(tm):
    return int(getattr(tm, tuition_month_fee_field(), 0) or 0)


class MidMonthProratedTest(TestCase):
    """O'quvchi oyning o'rtasidan qo'shilganda to'g'ri qarz hisoblanadi."""

    def setUp(self):
        self.center = Center.objects.create(name="TestCenter", slug="testcenter")
        self.teacher = User.objects.create_user(
            email="teacher@mid.test", password="p",
            role="teacher", center=self.center,
            ism="T", familya="T", oqituvchi_foizi=40,
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="Guruh-2kun",
            oqituvchi=self.teacher,
            kurs_narxi=PRICE,
            oqituvchi_foiz=40,
            oy_dars_soni=LESSONS_PER_MONTH,
        )
        # Jadval: Du(1) va Ch(3) — haftada 2 kun
        for wd in (1, 3):
            GroupSchedule.objects.create(
                center=self.center,
                group=self.group,
                weekday=wd,
                start_time="10:00",
            )

    def _make_student(self, email):
        return User.objects.create_user(
            email=email, password="p",
            role="student", center=self.center,
            ism="S", familya="X",
            telefon1=f"+9989011234567",
        )

    def _enroll(self, student, start_date):
        enr = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=student,
            kurs_narhi=PRICE,
            oqituvchi_foiz=40,
            is_active=True,
        )
        StudentGroupHistory.objects.create(
            student=student,
            group=self.group,
            center=self.center,
            start_date=start_date,
            kurs_narxi=PRICE,
            oqituvchi_foiz=40,
        )
        return enr

    # ─── 1. JADVAL TO'G'RI HISOBLANADIMI ────────────────────────────────────

    def test_schedule_count_full_month(self):
        """June 2026 da Du/Ch jadvali bo'yicha jami darslar soni."""
        count = scheduled_lessons_between(self.group, date(2026, 6, 1), date(2026, 6, 30))
        # Du: 1,8,15,22,29 = 5 | Ch: 3,10,17,24 = 4 → jami 9
        self.assertEqual(count, 9,
            f"Oy davomida jami dars noto'g'ri: {count} (kutilgan 9)")

    def test_schedule_count_from_join_date(self):
        """June 10 dan June 30 gacha Du/Ch bo'yicha darslar."""
        count = scheduled_lessons_between(self.group, date(2026, 6, 10), date(2026, 6, 30))
        # June 10(Ch), 15(Du), 17(Ch), 22(Du), 24(Ch), 29(Du) = 6
        self.assertEqual(count, 6,
            f"Qo'shilgan kundan boshlab dars soni noto'g'ri: {count} (kutilgan 6)")

    # ─── 2. PRORATED FEE TO'G'RI HISOBLANADIMI ──────────────────────────────

    def test_prorated_fee_join_june10(self):
        """June 10 dan qo'shilgan o'quvchi uchun prorated to'lov."""
        s = self._make_student("s1@mid.test")
        enr = self._enroll(s, JOIN_DATE)

        fee = prorated_monthly_fee(enr, MONTH)

        # GroupSchedule mavjud → scheduled_lessons_between ishlatiladi
        # June 10–30: 6 ta dars
        # Per lesson = 800_000 / 8 = 100_000
        # Debt = 6 * 100_000 = 600_000
        expected = 600_000
        self.assertEqual(fee, expected,
            f"Prorated fee noto'g'ri: {fee:,} (kutilgan {expected:,})")

    def test_prorated_fee_full_month(self):
        """Oy boshida qo'shilgan o'quvchi to'liq narxni to'laydi."""
        s = self._make_student("s2@mid.test")
        enr = self._enroll(s, date(2026, 5, 1))  # avvalgi oyda qo'shilgan

        fee = prorated_monthly_fee(enr, MONTH)
        # To'liq oy → kurs_narxi = 800_000
        self.assertEqual(fee, PRICE,
            f"To'liq oylik fee noto'g'ri: {fee:,} (kutilgan {PRICE:,})")

    def test_lesson_count_from_join_date(self):
        """tuition_month_lesson_count to'g'ri ishlaydi."""
        s = self._make_student("s3@mid.test")
        enr = self._enroll(s, JOIN_DATE)

        count = tuition_month_lesson_count(enr, MONTH)
        self.assertEqual(count, 6,
            f"Lesson count noto'g'ri: {count} (kutilgan 6)")

    # ─── 3. OY BOSHIDA QOSHILGANDA LESSON COUNT ─────────────────────────────

    def test_lesson_count_june1_join(self):
        """Oy birinchisida qo'shilsa — barcha darslar hisoblanadi."""
        s = self._make_student("s4@mid.test")
        enr = self._enroll(s, date(2026, 6, 1))

        count = tuition_month_lesson_count(enr, MONTH)
        # Du: 1,8,15,22,29 + Ch: 3,10,17,24 = 9
        self.assertEqual(count, 9,
            f"June 1 dan qoshilsа lesson count noto'g'ri: {count} (kutilgan 9)")

    # ─── 4. ENSURE_TUITION_MONTH — DB DA TO'G'RI YOZILADI ──────────────────

    def test_ensure_tuition_month_creates_correct_fee(self):
        """ensure_tuition_month saqlaganda prorated fee to'g'ri."""
        s = self._make_student("s5@mid.test")
        enr = self._enroll(s, JOIN_DATE)

        tm = ensure_tuition_month(enr, MONTH)
        self.assertEqual(_fee(tm), 600_000,
            f"TuitionMonth da fee noto'g'ri: {_fee(tm):,} (kutilgan 600,000)")

    # ─── 5. QARZ SNAPSHOT — QARZDORLAR BO'LIMIDA TO'G'RI ────────────────────

    def test_debt_snapshot_no_payment(self):
        """To'lov yo'q → qarz = fee."""
        s = self._make_student("s6@mid.test")
        enr = self._enroll(s, JOIN_DATE)
        ensure_tuition_month(enr, MONTH)

        snapshots = calculate_enrollment_debt_snapshots(
            [enr], [MONTH], cumulative_up_to=date(2026, 6, 30)
        )
        snap = snapshots[enr.id]
        self.assertEqual(snap["debt"], 600_000,
            f"Qarz noto'g'ri: {snap['debt']:,} (kutilgan 600,000)")

    def test_debt_snapshot_partial_payment(self):
        """300k to'lov → qolgan qarz 300k."""
        s = self._make_student("s7@mid.test")
        enr = self._enroll(s, JOIN_DATE)
        tm = ensure_tuition_month(enr, MONTH)

        payment = Payment.objects.create(
            center=self.center,
            enrollment=enr,
            student=s,
            group=self.group,
            cash_amount=300_000,
            summa=300_000,
            paid_date=date(2026, 6, 10),
            created_by=self.teacher,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=payment,
            tuition_month=tm,
            amount=300_000,
        )

        snapshots = calculate_enrollment_debt_snapshots(
            [enr], [MONTH], cumulative_up_to=date(2026, 6, 30)
        )
        snap = snapshots[enr.id]
        self.assertEqual(snap["debt"], 300_000,
            f"Qisman to'lovdan keyin qarz noto'g'ri: {snap['debt']:,} (kutilgan 300,000)")

    def test_debt_snapshot_full_payment(self):
        """600k to'liq to'lov → qarz 0."""
        s = self._make_student("s8@mid.test")
        enr = self._enroll(s, JOIN_DATE)
        tm = ensure_tuition_month(enr, MONTH)

        payment = Payment.objects.create(
            center=self.center,
            enrollment=enr,
            student=s,
            group=self.group,
            cash_amount=600_000,
            summa=600_000,
            paid_date=date(2026, 6, 10),
            created_by=self.teacher,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=payment,
            tuition_month=tm,
            amount=600_000,
        )

        snapshots = calculate_enrollment_debt_snapshots(
            [enr], [MONTH], cumulative_up_to=date(2026, 6, 30)
        )
        snap = snapshots[enr.id]
        self.assertEqual(snap["debt"], 0,
            f"To'liq to'lovdan keyin qarz nolga tushishi kerak: {snap['debt']:,}")

    # ─── 6. O'QITUVCHI VA MARKAZ ULUSHI ─────────────────────────────────────

    def test_billing_breakdown_teacher_center_shares(self):
        """
        O'qituvchi va markaz ulushi to'g'ri hisoblanadi:
          fee = 600_000
          o'qituvchi 40% → 800_000 * 40% / 8 * 6 = 40_000 * 6 = 240_000
          markaz = 600_000 - 240_000 = 360_000
        """
        billing = calculate_student_month_billing(
            course_price=PRICE,
            standard_lessons_count=LESSONS_PER_MONTH,
            calculated_lessons_count=6,
            teacher_percent=40,
        )
        self.assertEqual(billing["student_debt"], 600_000)
        self.assertEqual(billing["teacher_amount"], 240_000,
            f"O'qituvchi ulushi: {billing['teacher_amount']:,} (kutilgan 240,000)")
        self.assertEqual(billing["center_amount"], 360_000,
            f"Markaz ulushi: {billing['center_amount']:,} (kutilgan 360,000)")

    # ─── 7. OLDINGI OY UCHUN QARZ YARATILMASLIGI ────────────────────────────

    def test_no_debt_before_join_month(self):
        """O'quvchi qo'shilmasdan oldingi oy uchun qarz = 0."""
        s = self._make_student("s9@mid.test")
        enr = self._enroll(s, JOIN_DATE)

        fee = prorated_monthly_fee(enr, date(2026, 5, 1))
        self.assertEqual(fee, 0,
            f"May oyida (qo'shilishdan oldin) qarz bo'lmasligi kerak: {fee:,}")

    # ─── 8. OY_DARS_SONI VA SCHEDULE MUVOFIQLIK ─────────────────────────────

    def test_oy_dars_soni_vs_schedule_consistency(self):
        """
        oy_dars_soni=8 va Du/Ch jadval — mos.
        To'liq oy uchun jadval 9 ta dars chiqaradi (5 Du + 4 Ch).
        Prorated fee: min(jadval_dars, oy_dars_soni) ga qarab.

        Eslatma: scheduled_lessons_between 9 ta chiqarsa ham,
        fee HECH QACHON kurs_narxidan oshmaydi.
        """
        s = self._make_student("s10@mid.test")
        enr = self._enroll(s, date(2026, 5, 1))  # to'liq oy

        fee = prorated_monthly_fee(enr, MONTH)
        self.assertLessEqual(fee, PRICE,
            f"Fee kurs narxidan oshmasligi kerak: {fee:,} > {PRICE:,}")
        self.assertEqual(fee, PRICE,
            f"To'liq oyda fee kurs narxiga teng bo'lishi kerak: {fee:,}")
