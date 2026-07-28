"""O'quvchi HOLATI sahifasi — bo'lim kesimidagi tarix to'g'ri yig'ilishini tekshiradi.

Asosiy kafolatlar:
  * Bo'limlar (Category) bo'yicha guruhlash va oylar birlashmasi.
  * Chaqmoq bo'yicha yagona manba — Ledger; bo'limlar + "umumiy" yig'indisi
    markaz balansiga ANIQ teng.
  * To'lovlar, oylik hisob (yozilgan/to'langan/qarz) va chek havolasi.
  * Davomat holatlarini eski (status='present', present=False) yozuvlar bilan
    birga to'g'ri tasniflash.
  * Tenant izolyatsiyasi va rol cheklovi.
"""
from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from billing.models import CenterSubscription, SubscriptionPlan
from chaqmoq.models import Ledger, Rule
from education.models import (
    Attendance,
    Category,
    Enrollment,
    Group,
    Payment,
    PaymentAllocation,
    StudentGroupHistory,
    TuitionMonth,
)
from education.services.student_status import attendance_state, build_student_status


def _active_subscription(center):
    plan = SubscriptionPlan.objects.create(
        code=f"TEST-{center.pk}", title="Test", name="TEST", monthly_price=0,
        price=0, duration_days=30, max_students=2000, active=True,
    )
    CenterSubscription.objects.create(
        center=center, plan=plan,
        status=CenterSubscription.Status.ACTIVE,
        expires_at=timezone.now() + timedelta(days=30),
    )


class StudentStatusServiceTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Status Center", slug="status-center")
        _active_subscription(self.center)

        self.director = User.objects.create_user(
            email="d@status.test", password="x", role="director",
            center=self.center, ism="Dilshod", familya="Direktor",
        )
        self.teacher = User.objects.create_user(
            email="t@status.test", password="x", role="teacher",
            center=self.center, ism="Tohir", familya="Ustoz",
        )
        self.student = User.objects.create_user(
            email="s@status.test", password="x", role="student",
            center=self.center, ism="Aziz", familya="Karimov",
        )

        self.cat_it = Category.objects.create(name="IT", center=self.center, icon="💻")
        self.cat_en = Category.objects.create(name="ENGLISH", center=self.center, icon="📘")

        self.g_it = Group.objects.create(
            center=self.center, nom="Python Boshlang'ich", oqituvchi=self.teacher,
            category_obj=self.cat_it, kurs_narxi=500_000, oqituvchi_foiz=40, oy_dars_soni=12,
        )
        self.g_en = Group.objects.create(
            center=self.center, nom="General English A2", oqituvchi=self.teacher,
            category_obj=self.cat_en, kurs_narxi=400_000, oqituvchi_foiz=40, oy_dars_soni=8,
        )

        self.enr_it = Enrollment.objects.create(
            center=self.center, student=self.student, group=self.g_it,
            is_active=True, joined_at=date(2026, 1, 10), kurs_narhi=500_000,
        )
        self.enr_en = Enrollment.objects.create(
            center=self.center, student=self.student, group=self.g_en,
            is_active=False, joined_at=date(2026, 2, 1),
            last_lesson_date=date(2026, 3, 31), kurs_narhi=400_000,
        )
        StudentGroupHistory.objects.create(
            student=self.student, group=self.g_it, center=self.center,
            start_date=date(2026, 1, 10), end_date=None,
        )
        StudentGroupHistory.objects.create(
            student=self.student, group=self.g_en, center=self.center,
            start_date=date(2026, 2, 1), end_date=date(2026, 3, 31),
        )

        # ── Davomat ──
        # IT: 1 keldi, 1 eski uslubdagi "kelmadi", 1 sababli
        Attendance.objects.create(group=self.g_it, student=self.student, center=self.center,
                                  date=date(2026, 1, 5), status="present", present=True)
        Attendance.objects.create(group=self.g_it, student=self.student, center=self.center,
                                  date=date(2026, 1, 7), present=False)  # status default 'present'
        Attendance.objects.create(group=self.g_it, student=self.student, center=self.center,
                                  date=date(2026, 2, 3), status="absent_excused", present=False)
        # ENGLISH: 2 keldi
        Attendance.objects.create(group=self.g_en, student=self.student, center=self.center,
                                  date=date(2026, 2, 4), status="present", present=True)
        Attendance.objects.create(group=self.g_en, student=self.student, center=self.center,
                                  date=date(2026, 3, 2), status="present", present=True)

        # ── Oylik hisob + to'lov ──
        self.tm_jan = TuitionMonth.objects.create(
            center=self.center, enrollment=self.enr_it, month=date(2026, 1, 1), fee_amount=500_000,
        )
        self.tm_feb = TuitionMonth.objects.create(
            center=self.center, enrollment=self.enr_it, month=date(2026, 2, 1), fee_amount=500_000,
        )
        self.payment = Payment.objects.create(
            enrollment=self.enr_it, student=self.student, group=self.g_it, center=self.center,
            payment_type="cash", cash_amount=500_000, paid_date=date(2026, 1, 15),
            created_by=self.director,
        )
        PaymentAllocation.objects.create(
            center=self.center, payment=self.payment, tuition_month=self.tm_jan, amount=500_000,
        )

        # ── Chaqmoq ──
        self.rule_plus = Rule.objects.create(
            nom="Uy vazifasi", center=self.center, tur=Rule.PLUS, min_baho=1, max_baho=10,
        )
        self.rule_minus = Rule.objects.create(
            nom="Dars buzish", center=self.center, tur=Rule.MINUS, min_baho=1, max_baho=10,
        )
        Ledger.objects.create(student=self.student, beruvchi=self.teacher, group=self.g_it,
                              rule=self.rule_plus, ball=10, sana=timezone.now())
        Ledger.objects.create(student=self.student, beruvchi=self.teacher, group=self.g_it,
                              rule=self.rule_minus, ball=-3, sana=timezone.now())
        Ledger.objects.create(student=self.student, beruvchi=self.teacher, group=self.g_en,
                              rule=self.rule_plus, ball=5, sana=timezone.now())
        # Guruhga bog'lanmagan avtomatik jarima
        Ledger.objects.create(student=self.student, beruvchi=None, group=None,
                              rule=self.rule_minus, ball=-5, sana=timezone.now())

        self.data = build_student_status(self.student, self.center)

    # ── Bo'limlar ──

    def test_sections_are_grouped_by_category(self):
        names = sorted(s["name"] for s in self.data["sections"])
        self.assertEqual(names, ["ENGLISH", "IT"])

    def test_active_section_is_listed_first(self):
        self.assertEqual(self.data["sections"][0]["name"], "IT")
        self.assertTrue(self.data["sections"][0]["is_active"])

    def _section(self, name):
        return next(s for s in self.data["sections"] if s["name"] == name)

    def test_months_count_per_section_is_union_of_activity(self):
        # IT: davomat Yanvar+Fevral, oylik hisob Yanvar+Fevral → 2 oy
        self.assertEqual(self._section("IT")["months_count"], 2)
        # ENGLISH: davomat Fevral+Mart → 2 oy
        self.assertEqual(self._section("ENGLISH")["months_count"], 2)

    def test_total_months_deduplicates_overlapping_months(self):
        # Yanvar, Fevral, Mart → Fevral ikki bo'limda bo'lsa ham bir marta.
        self.assertEqual(self.data["totals"]["months_count"], 3)

    # ── Chaqmoq ──

    def test_chaqmoq_split_per_group(self):
        it = self._section("IT")
        self.assertEqual(it["plus"], 10)
        self.assertEqual(it["minus"], 3)
        self.assertEqual(it["net"], 7)
        self.assertEqual(self._section("ENGLISH")["net"], 5)

    def test_group_less_ledger_goes_to_general_bucket(self):
        general = self.data["general"]
        self.assertEqual(general["count"], 1)
        self.assertEqual(general["net"], -5)
        self.assertTrue(general["entries"][0]["is_auto"])

    def test_balance_equals_center_scoped_ledger_sum(self):
        expected = sum(Ledger.objects.filter(student=self.student).values_list("ball", flat=True))
        self.assertEqual(self.data["totals"]["balance"], expected)
        # Bo'limlar + umumiy = balans (hech qayerda yo'qolmaydi)
        parts = sum(s["net"] for s in self.data["sections"]) + self.data["general"]["net"]
        self.assertEqual(parts, self.data["totals"]["balance"])

    def test_ledger_entry_keeps_reason_and_author(self):
        entry = self._section("IT")["groups"][0]["chaqmoq"]["entries"][0]
        self.assertIn(entry["reason"], {"Uy vazifasi", "Dars buzish"})
        self.assertEqual(entry["given_by"], "Tohir Ustoz")

    # ── To'lovlar ──

    def test_payment_row_has_amount_months_and_receipt(self):
        card = self._section("IT")["groups"][0]
        self.assertEqual(card["payments"]["count"], 1)
        row = card["payments"]["rows"][0]
        self.assertEqual(row["amount"], 500_000)
        self.assertEqual(row["amount_text"], "500 000")
        self.assertEqual(row["created_by"], "Dilshod Direktor")
        self.assertEqual(row["covered_months"], ["Yanvar 2026 — 500 000 so'm"])
        self.assertEqual(
            row["receipt_url"],
            reverse("education:payment_receipt_pdf", args=[self.payment.id]),
        )

    def test_tuition_rows_show_paid_and_debt(self):
        rows = {r["key"]: r for r in self._section("IT")["groups"][0]["tuition"]["rows"]}
        self.assertEqual(rows["2026-01"]["paid"], 500_000)
        self.assertEqual(rows["2026-01"]["debt"], 0)
        self.assertEqual(rows["2026-01"]["status"], "paid")
        self.assertEqual(rows["2026-02"]["paid"], 0)
        self.assertEqual(rows["2026-02"]["debt"], 500_000)
        self.assertEqual(rows["2026-02"]["status"], "unpaid")
        self.assertEqual(self._section("IT")["debt"], 500_000)
        # Jami to'lov = real Payment yozuvlari; qarz = bo'limlar qarzi yig'indisi.
        self.assertEqual(self.data["totals"]["paid"], 500_000)
        self.assertEqual(
            self.data["totals"]["debt"],
            sum(s["debt"] for s in self.data["sections"]),
        )

    # ── Davomat ──

    def test_legacy_present_false_row_counts_as_absent(self):
        stats = self._section("IT")["att"]
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["present"], 1)
        self.assertEqual(stats["excused"], 1)
        self.assertEqual(stats["absent"], 1)
        self.assertEqual(stats["attended"], 1)
        self.assertEqual(stats["missed"], 2)
        self.assertEqual(stats["rate"], 33)

    def test_attendance_state_mapping(self):
        self.assertEqual(attendance_state("present", True, False), "present")
        self.assertEqual(attendance_state("present", False, False), "absent")
        self.assertEqual(attendance_state("late", False, False), "late")
        self.assertEqual(attendance_state("absent_excused", False, False), "excused")
        self.assertEqual(attendance_state("absent_unexcused", False, False), "unexcused")
        self.assertEqual(attendance_state("", False, True), "forced")

    def test_attendance_months_are_newest_first(self):
        months = self._section("IT")["groups"][0]["attendance"]["months"]
        self.assertEqual([m["key"] for m in months], ["2026-02", "2026-01"])
        self.assertEqual(months[1]["label"], "Yanvar 2026")

    # ── Guruh a'zoligi sanasi ──

    def test_group_dates_come_from_history(self):
        it_group = self._section("IT")["groups"][0]
        self.assertEqual(it_group["start_date"], date(2026, 1, 10))
        self.assertIsNone(it_group["end_date"], "Faol guruhda tugash sanasi bo'lmasligi kerak")

        en_group = self._section("ENGLISH")["groups"][0]
        self.assertEqual(en_group["end_date"], date(2026, 3, 31))
        self.assertFalse(en_group["is_active"])

    # ── Sahifa ──

    def test_page_renders_full_history(self):
        self.client.force_login(self.director)
        url = f"/{self.center.slug}" + reverse("education:student_status", args=[self.student.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        self.assertIn("Python Boshlang&#x27;ich", html)
        self.assertIn("General English A2", html)
        self.assertIn("Uy vazifasi", html)          # chaqmoq sababi
        self.assertIn("Yanvar 2026", html)          # oylik hisob
        self.assertIn("500 000", html)              # to'lov summasi
        self.assertIn(                              # chek yuklab olish havolasi
            reverse("education:payment_receipt_pdf", args=[self.payment.id]),
            html,
        )
        self.assertIn("Umumiy chaqmoq", html)       # guruhsiz yozuvlar bo'limi


class StudentStatusViewTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="View Center", slug="view-center")
        _active_subscription(self.center)
        self.director = User.objects.create_user(
            email="d@view.test", password="x", role="director",
            center=self.center, ism="D", familya="Direktor",
        )
        self.teacher = User.objects.create_user(
            email="t@view.test", password="x", role="teacher",
            center=self.center, ism="T", familya="Ustoz",
        )
        self.student = User.objects.create_user(
            email="s@view.test", password="x", role="student",
            center=self.center, ism="Sardor", familya="Aliyev",
        )
        # TenantMiddleware slug-prefiksli URL kutadi.
        self.path = reverse("education:student_status", args=[self.student.id])
        self.url = f"/{self.center.slug}{self.path}"

    def test_director_can_open_page(self):
        self.client.force_login(self.director)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "education/student_status.html")
        self.assertFalse(response.context["has_data"])

    def test_teacher_is_forbidden(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_students_list_menu_has_holat_link(self):
        """O'quvchilar ro'yxatidagi 3-nuqta menyusida "Holat" tugmasi bo'lishi shart.

        Ro'yxat ikki joyda chiziladi: sahifa ochilganda `core/stats_users.html`,
        qidiruv/sahifalashda esa `core/includes/student_list_table.html`.
        Ikkalasida ham havola bo'lishi kerak.
        """
        self.client.force_login(self.director)
        list_url = f"/{self.center.slug}" + reverse("core:stat_students")

        full_page = self.client.get(list_url)
        self.assertEqual(full_page.status_code, 200)
        self.assertContains(full_page, self.path)
        self.assertContains(full_page, "Holat")

        ajax_page = self.client.get(list_url, headers={"x-requested-with": "XMLHttpRequest"})
        self.assertEqual(ajax_page.status_code, 200)
        self.assertContains(ajax_page, self.path)
        self.assertContains(ajax_page, "Holat")

    def test_other_center_student_is_not_found(self):
        """IDOR: boshqa markaz direktori bu o'quvchining holatini ko'ra olmaydi."""
        other = Center.objects.create(name="Other Center", slug="other-center")
        _active_subscription(other)
        other_director = User.objects.create_user(
            email="d@other.test", password="x", role="director",
            center=other, ism="O", familya="Direktor",
        )
        self.client.force_login(other_director)
        response = self.client.get(f"/{other.slug}{self.path}")
        self.assertEqual(response.status_code, 404)
