"""
Prorated oylik to'lov va davomatga asoslangan reconcile testlari.

8 ta asosiy stsenariy (A–H) foydalanuvchi bilan kelishilgan jadval asosida:
  A: to'liq oy, to'liq narx, 12 dars keldi
  B: to'liq oy, 2 sababli (10 billable)
  C: 18-sanada qo'shildi, 5 dars hisoblanadi, chegirma yo'q
  D: to'liq oy, chegirma (330k)
  E: tekin o'quvchi (student_payable_amount=0)
  F: 18-sanada qo'shildi + chegirma 330k, 5 dars
  G: tekin + 18-sanada qo'shildi, 5 dars
  H: to'liq oy, 3 sababsiz + 1 sababli (11 billable)
"""
from datetime import date

from django.test import TestCase

from accounts.models import Center, User
from education.models import (
    Attendance,
    Enrollment,
    FinancialMonth,
    Group,
    GroupSchedule,
    MonthlyFinanceSnapshot,
    StudentGroupHistory,
    TeacherSalarySnapshot,
    TuitionMonth,
)
from education.services.historical_finance_service import HistoricalFinanceService
from education.services.tuition import (
    attendance_based_fee,
    auto_lesson_pattern_for_date,
    billable_attendance_count,
    ensure_tuition_month,
    expected_lessons_in_period,
    pattern_lessons_between,
    prorated_monthly_fee,
    resolve_lesson_schedule,
    reconcile_tuition_month,
    scheduled_lessons_between,
    tuition_month_lesson_count,
    tuition_month_preview,
    tuition_month_fee_field,
)


BASE_PRICE = 550_000
LESSONS_PER_MONTH = 12
# per_lesson for 550k/12 = 45_833.33...


def _tm_fee(tm):
    return int(getattr(tm, tuition_month_fee_field(), 0) or 0)


class ProratedTuitionTests(TestCase):
    MONTH = date(2026, 4, 1)  # April 2026

    def setUp(self):
        self.center = Center.objects.create(name="C1", slug="c1")
        self.teacher = User.objects.create_user(
            email="t@c1.test",
            password="p",
            role="teacher",
            center=self.center,
            ism="T",
            familya="T",
            oqituvchi_foizi=40,
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="G1",
            oqituvchi=self.teacher,
            kurs_narxi=BASE_PRICE,
            oqituvchi_foiz=40,
            oy_dars_soni=LESSONS_PER_MONTH,
        )
        # Jadval: Du/Chor/Jum (1,3,5) — haftada 3 dars, oyiga ~13
        for wd in (1, 3, 5):
            GroupSchedule.objects.create(
                center=self.center,
                group=self.group,
                weekday=wd,
                start_time="10:00",
            )

    # ---------- yordamchilar ----------
    def _make_student(self, email, ism="S"):
        return User.objects.create_user(
            email=email,
            password="p",
            role="student",
            center=self.center,
            ism=ism,
            familya="X",
            telefon1=f"+998901{len(email):07d}",
        )

    def _enroll(self, student, start_date=None, payable=None):
        enr = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=student,
            kurs_narhi=BASE_PRICE,
            oqituvchi_foiz=40,
            student_payable_amount=payable,
            is_active=True,
        )
        if start_date:
            StudentGroupHistory.objects.create(
                student=student,
                group=self.group,
                center=self.center,
                start_date=start_date,
                kurs_narxi=BASE_PRICE,
                oqituvchi_foiz=40,
            )
        return enr

    def _attend(self, enr, day, status):
        return Attendance.objects.create(
            group=enr.group,
            student=enr.student,
            teacher=self.teacher,
            date=date(self.MONTH.year, self.MONTH.month, day),
            status=status,
        )

    # ================== PROROTE (creation) ==================

    def test_A_full_month_all_present(self):
        """Scenariy A: to'liq oy, hech kim kirmasdan oldin qo'shildi → to'liq narx"""
        s = self._make_student("a@t")
        enr = self._enroll(s, start_date=date(2026, 3, 1))  # old enrollment
        self.assertEqual(prorated_monthly_fee(enr, self.MONTH), BASE_PRICE)

    def test_C_partial_month_18_no_discount(self):
        """Scenariy C: 18-sanada qo'shildi, chegirma yo'q — expected × per_lesson"""
        s = self._make_student("c@t")
        enr = self._enroll(s, start_date=date(2026, 4, 18))
        # 18-aprel 2026 = shanba, demak avtomatik "Juft kunlari".
        fee = prorated_monthly_fee(enr, self.MONTH)
        per_lesson = BASE_PRICE / LESSONS_PER_MONTH  # 45,833.33
        expected = pattern_lessons_between(date(2026, 4, 18), date(2026, 4, 30), "even")
        self.assertEqual(fee, round(expected * per_lesson))
        self.assertLess(fee, BASE_PRICE)  # to'liq narxdan kam

    def test_D_full_month_with_discount(self):
        """Scenariy D: to'liq oy, chegirma 330k → 330k"""
        s = self._make_student("d@t")
        enr = self._enroll(s, start_date=date(2026, 3, 1), payable=330_000)
        self.assertEqual(prorated_monthly_fee(enr, self.MONTH), 330_000)

    def test_E_free_student(self):
        """Scenariy E: tekin o'quvchi → 0"""
        s = self._make_student("e@t")
        enr = self._enroll(s, start_date=date(2026, 3, 1), payable=0)
        self.assertEqual(prorated_monthly_fee(enr, self.MONTH), 0)

    def test_F_partial_plus_discount(self):
        """Scenariy F: 18-sanada qo'shildi + chegirma 330k"""
        s = self._make_student("f@t")
        enr = self._enroll(s, start_date=date(2026, 4, 18), payable=330_000)
        per_lesson = 330_000 / LESSONS_PER_MONTH  # 27,500
        expected = pattern_lessons_between(date(2026, 4, 18), date(2026, 4, 30), "even")
        self.assertEqual(prorated_monthly_fee(enr, self.MONTH), round(expected * per_lesson))

    def test_G_free_plus_partial(self):
        """Scenariy G: tekin + 18-sanada qo'shildi → 0"""
        s = self._make_student("g@t")
        enr = self._enroll(s, start_date=date(2026, 4, 18), payable=0)
        self.assertEqual(prorated_monthly_fee(enr, self.MONTH), 0)

    def test_before_enrollment_month(self):
        """Qo'shilmagan oy uchun — 0 (yolg'on qarz yaratilmaydi)"""
        s = self._make_student("bef@t")
        enr = self._enroll(s, start_date=date(2026, 4, 18))
        self.assertEqual(prorated_monthly_fee(enr, date(2026, 3, 1)), 0)

    # ================== RECONCILE (end-of-month) ==================

    def test_B_full_month_2_excused(self):
        """
        Scenariy B: to'liq oy, 10 keldi + 2 sababli (hisoblanmaydi)
        Davomatga qarab reconcile: 10 × 45,833 = 458,333
        """
        s = self._make_student("b@t")
        enr = self._enroll(s, start_date=date(2026, 3, 1))
        # 10 ta present
        for d in (1, 3, 6, 8, 10, 13, 15, 17, 20, 22):
            self._attend(enr, d, "present")
        # 2 ta sababli (pul yozilmaydi)
        self._attend(enr, 24, "absent_excused")
        self._attend(enr, 27, "absent_excused")

        tm = reconcile_tuition_month(enr, self.MONTH)
        per_lesson = BASE_PRICE / LESSONS_PER_MONTH
        self.assertEqual(_tm_fee(tm), round(10 * per_lesson))

    def test_H_full_month_mixed(self):
        """Scenariy H: 8 keldi + 3 sababsiz + 1 sababli → billable=11"""
        s = self._make_student("h@t")
        enr = self._enroll(s, start_date=date(2026, 3, 1))
        for d in (1, 3, 6, 8, 10, 13, 15, 17):
            self._attend(enr, d, "present")
        for d in (20, 22, 24):
            self._attend(enr, d, "absent_unexcused")
        self._attend(enr, 27, "absent_excused")

        tm = reconcile_tuition_month(enr, self.MONTH)
        per_lesson = BASE_PRICE / LESSONS_PER_MONTH
        self.assertEqual(_tm_fee(tm), round(11 * per_lesson))

    def test_C_reconcile_5_attended(self):
        """Scenariy C full: 18-sanada qo'shildi, 4 keldi + 1 sababsiz = 5 billable"""
        s = self._make_student("cr@t")
        enr = self._enroll(s, start_date=date(2026, 4, 18))
        for d in (20, 22, 27, 29):
            self._attend(enr, d, "present")
        self._attend(enr, 24, "absent_unexcused")

        tm = reconcile_tuition_month(enr, self.MONTH)
        per_lesson = BASE_PRICE / LESSONS_PER_MONTH
        self.assertEqual(_tm_fee(tm), round(5 * per_lesson))
        # Qarz yolg'on emas:
        self.assertLess(_tm_fee(tm), BASE_PRICE)

    def test_reconcile_respects_discount(self):
        """Chegirmali o'quvchida fee = billable × (effective / 12), asl emas"""
        s = self._make_student("rd@t")
        enr = self._enroll(s, start_date=date(2026, 3, 1), payable=330_000)
        for d in (1, 3, 6, 8, 10, 13, 15, 17, 20, 22, 24, 27):
            self._attend(enr, d, "present")
        tm = reconcile_tuition_month(enr, self.MONTH)
        self.assertEqual(_tm_fee(tm), 330_000)  # to'liq chegirmali narx, cap hit

    def test_reconcile_cap_at_effective_price(self):
        """13 dars (jadvaldagi max) → capped at effective_price emas, chunki per_lesson × 13 > 550k"""
        s = self._make_student("cap@t")
        enr = self._enroll(s, start_date=date(2026, 3, 1))
        # 13 ta present (oy_dars_soni=12 dan ko'p)
        for d in (1, 3, 6, 8, 10, 13, 15, 17, 20, 22, 24, 27, 29):
            self._attend(enr, d, "present")
        tm = reconcile_tuition_month(enr, self.MONTH)
        self.assertEqual(_tm_fee(tm), BASE_PRICE)  # cap

    # ================== ensure_tuition_month integration ==================

    def test_ensure_creates_prorated_first_month(self):
        """ensure_tuition_month yangi o'quvchi uchun prorated fee ni ishlatadi"""
        s = self._make_student("e1@t")
        enr = self._enroll(s, start_date=date(2026, 4, 18))
        tm = ensure_tuition_month(enr, self.MONTH)
        per_lesson = BASE_PRICE / LESSONS_PER_MONTH
        expected = pattern_lessons_between(date(2026, 4, 18), date(2026, 4, 30), "even")
        self.assertEqual(_tm_fee(tm), round(expected * per_lesson))
        self.assertLess(_tm_fee(tm), BASE_PRICE)

    def test_billable_counts_present_and_unexcused_only(self):
        """billable = present + absent_unexcused; sababli sanalmaydi"""
        s = self._make_student("bc@t")
        enr = self._enroll(s, start_date=date(2026, 3, 1))
        self._attend(enr, 1, "present")
        self._attend(enr, 3, "absent_unexcused")
        self._attend(enr, 6, "absent_excused")  # sanalmaydi
        self.assertEqual(billable_attendance_count(enr, self.MONTH), 2)

    def test_scheduled_between_respects_weekdays(self):
        """Jadval bo'yicha Du/Chor/Jum — boshqa kunlar sanalmaydi"""
        # April 2026 da Dushanba kunlari: 6, 13, 20, 27 (4 ta)
        count = scheduled_lessons_between(
            self.group, date(2026, 4, 1), date(2026, 4, 30)
        )
        # Du (6,13,20,27), Chor (1,8,15,22,29), Jum (3,10,17,24) = 4+5+4 = 13
        self.assertEqual(count, 13)

    def test_pattern_lessons_between_uses_workweek_parity_and_ignores_sunday(self):
        self.assertEqual(pattern_lessons_between(date(2026, 4, 18), date(2026, 4, 30), "even"), 6)
        self.assertEqual(pattern_lessons_between(date(2026, 4, 18), date(2026, 4, 30), "odd"), 5)
        self.assertEqual(pattern_lessons_between(date(2026, 4, 18), date(2026, 4, 30), "daily"), 11)
        self.assertEqual(pattern_lessons_between(date(2026, 4, 19), date(2026, 4, 19), "odd"), 0)
        self.assertEqual(pattern_lessons_between(date(2026, 4, 19), date(2026, 4, 19), "even"), 0)
        self.assertEqual(pattern_lessons_between(date(2026, 4, 19), date(2026, 4, 19), "daily"), 0)

    def test_pattern_lessons_between_covers_30_31_and_february_months(self):
        cases = (
            (date(2026, 4, 1), date(2026, 4, 30), 13, 13, 26),
            (date(2026, 5, 1), date(2026, 5, 31), 13, 13, 26),
            (date(2026, 2, 1), date(2026, 2, 28), 12, 12, 24),
        )
        for start, end, odd_count, even_count, daily_count in cases:
            with self.subTest(start=start, end=end):
                self.assertEqual(pattern_lessons_between(start, end, "odd"), odd_count)
                self.assertEqual(pattern_lessons_between(start, end, "even"), even_count)
                self.assertEqual(pattern_lessons_between(start, end, "daily"), daily_count)

    def test_pattern_lessons_between_respects_month_start_middle_and_end(self):
        cases = (
            (date(2026, 4, 1), date(2026, 4, 30), 13, 13, 26),
            (date(2026, 4, 15), date(2026, 4, 30), 7, 7, 14),
            (date(2026, 4, 30), date(2026, 4, 30), 0, 1, 1),
            (date(2026, 5, 15), date(2026, 5, 31), 7, 7, 14),
            (date(2026, 5, 31), date(2026, 5, 31), 0, 0, 0),
            (date(2026, 2, 15), date(2026, 2, 28), 6, 6, 12),
            (date(2026, 2, 28), date(2026, 2, 28), 0, 1, 1),
        )
        for start, end, odd_count, even_count, daily_count in cases:
            with self.subTest(start=start, end=end):
                self.assertEqual(pattern_lessons_between(start, end, "odd"), odd_count)
                self.assertEqual(pattern_lessons_between(start, end, "even"), even_count)
                self.assertEqual(pattern_lessons_between(start, end, "daily"), daily_count)

    def test_pattern_lessons_between_can_naturally_return_12_13_or_14(self):
        self.assertEqual(pattern_lessons_between(date(2026, 2, 1), date(2026, 2, 28), "odd"), 12)
        self.assertEqual(pattern_lessons_between(date(2026, 4, 1), date(2026, 4, 30), "odd"), 13)
        self.assertEqual(pattern_lessons_between(date(2026, 7, 1), date(2026, 7, 31), "odd"), 14)
        self.assertEqual(pattern_lessons_between(date(2026, 1, 1), date(2026, 1, 31), "even"), 14)

    def test_partial_month_uses_enrollment_lesson_pattern(self):
        s = self._make_student("pattern-even@t")
        enr = self._enroll(s, start_date=date(2026, 4, 18))
        enr.lesson_pattern = "even"
        enr.joined_at = date(2026, 4, 18)
        enr.monthly_lessons = LESSONS_PER_MONTH
        enr.save(update_fields=["lesson_pattern", "joined_at", "monthly_lessons"])

        expected_lessons = 6
        expected_fee = round((BASE_PRICE * expected_lessons) / LESSONS_PER_MONTH)

        self.assertEqual(expected_lessons_in_period(enr, date(2026, 4, 18), date(2026, 4, 30)), expected_lessons)
        self.assertEqual(prorated_monthly_fee(enr, self.MONTH), expected_fee)

    def test_full_month_preview_uses_same_pattern_count_source(self):
        s = self._make_student("pattern-full-odd@t")
        enr = self._enroll(s, start_date=date(2026, 4, 1))
        enr.lesson_pattern = "odd"
        enr.joined_at = date(2026, 4, 1)
        enr.monthly_lessons = LESSONS_PER_MONTH
        enr.save(update_fields=["lesson_pattern", "joined_at", "monthly_lessons"])

        expected_lessons = pattern_lessons_between(date(2026, 4, 1), date(2026, 4, 30), "odd")
        preview = tuition_month_preview(enr, self.MONTH)

        self.assertEqual(tuition_month_lesson_count(enr, self.MONTH), expected_lessons)
        self.assertEqual(preview["lesson_count"], expected_lessons)
        self.assertEqual(preview["lesson_pattern_label"], "Toq kunlari")
        self.assertEqual(preview["fee_amount"], BASE_PRICE)

    def test_tuition_preview_keeps_teacher_and_center_shares_balanced(self):
        s = self._make_student("preview-pattern@t")
        enr = self._enroll(s, start_date=date(2026, 4, 18))
        enr.lesson_pattern = "odd"
        enr.joined_at = date(2026, 4, 18)
        enr.monthly_lessons = LESSONS_PER_MONTH
        enr.save(update_fields=["lesson_pattern", "joined_at", "monthly_lessons"])

        preview = tuition_month_preview(enr, self.MONTH)

        self.assertEqual(preview["lesson_count"], 5)
        self.assertEqual(preview["teacher_share"] + preview["center_share"], preview["full_turnover"])
        self.assertEqual(preview["fee_amount"], round((BASE_PRICE * 5) / LESSONS_PER_MONTH))
        self.assertEqual(preview["counted_days_summary"], "Hisoblangan kunlar: Dush, Chor, Jum")

    def test_auto_lesson_pattern_examples_follow_real_weekday(self):
        self.assertEqual(auto_lesson_pattern_for_date(date(2026, 4, 24)), "odd")
        self.assertEqual(auto_lesson_pattern_for_date(date(2026, 4, 25)), "even")
        self.assertEqual(auto_lesson_pattern_for_date(date(2026, 4, 27)), "odd")

    def test_sunday_start_date_is_shifted_to_next_monday_for_counting(self):
        schedule = resolve_lesson_schedule(date(2026, 4, 26), "odd")

        self.assertEqual(schedule["start_date"], date(2026, 4, 27))
        self.assertEqual(schedule["lesson_pattern"], "odd")
        self.assertEqual(
            schedule["adjustment_note"],
            "Yakshanba tanlangani uchun hisob-kitob 27.04.2026 dan boshlandi",
        )

    def test_teacher_salary_is_capped_at_full_month_share(self):
        """
        13 ta billable bo'lsa ham teacher full-month cap dan oshmaydi:
        550k * 40% = 220k
        """
        s = self._make_student("cap-teacher@t")
        enr = self._enroll(s, start_date=date(2026, 3, 1))
        for d in (1, 3, 6, 8, 10, 13, 15, 17, 20, 22, 24, 27, 29):
            self._attend(enr, d, "present")

        salary_data = HistoricalFinanceService.calculate_teacher_salary(
            self.teacher,
            self.MONTH.year,
            self.MONTH.month,
            self.center,
        )

        self.assertEqual(salary_data["salary"], 220_000)
        self.assertEqual(salary_data["attendance_count"], 13)
        self.assertEqual(salary_data["details"][0]["enrollments"][0]["daromad"], 220_000)

    def test_teacher_salary_uses_full_price_even_when_student_has_discount(self):
        """
        O'quvchi 330k to'lasa ham teacher payout 550k bazadan hisoblanadi.
        5 dars uchun: 5 * (550k / 12) * 40%
        """
        s = self._make_student("discount-teacher@t")
        enr = self._enroll(s, start_date=date(2026, 4, 18), payable=330_000)
        for d in (20, 22, 24, 27):
            self._attend(enr, d, "present")
        self._attend(enr, 29, "absent_unexcused")

        salary_data = HistoricalFinanceService.calculate_teacher_salary(
            self.teacher,
            self.MONTH.year,
            self.MONTH.month,
            self.center,
        )

        expected_teacher = round(5 * (BASE_PRICE / LESSONS_PER_MONTH) * 0.4)
        self.assertEqual(salary_data["salary"], expected_teacher)

        tm = reconcile_tuition_month(enr, self.MONTH)
        self.assertEqual(_tm_fee(tm), round(5 * (330_000 / LESSONS_PER_MONTH)))

    def test_close_month_creates_snapshots_and_keeps_free_student_out_of_debt(self):
        s = self._make_student("free-close@t")
        enr = self._enroll(s, start_date=date(2026, 3, 1), payable=0)
        self._attend(enr, 1, "present")

        fin_month = HistoricalFinanceService.close_month(
            self.center,
            self.MONTH.year,
            self.MONTH.month,
            user=None,
        )

        tm = TuitionMonth.objects.get(enrollment=enr, month=self.MONTH)
        self.assertEqual(_tm_fee(tm), 0)

        teacher_snap = TeacherSalarySnapshot.objects.get(
            teacher=self.teacher,
            financial_month=fin_month,
        )
        finance_snap = MonthlyFinanceSnapshot.objects.get(financial_month=fin_month)

        self.assertGreater(teacher_snap.salary, 0)
        self.assertLess(finance_snap.center_profit, 0)
        self.assertEqual(FinancialMonth.objects.filter(pk=fin_month.pk, is_closed=True).count(), 1)

        fin_month_again = HistoricalFinanceService.close_month(
            self.center,
            self.MONTH.year,
            self.MONTH.month,
            user=None,
        )
        self.assertEqual(fin_month_again.id, fin_month.id)
        self.assertEqual(
            TeacherSalarySnapshot.objects.filter(financial_month=fin_month).count(),
            1,
        )
        self.assertEqual(
            MonthlyFinanceSnapshot.objects.filter(financial_month=fin_month).count(),
            1,
        )
