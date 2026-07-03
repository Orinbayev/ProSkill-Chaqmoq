"""
Regression: guruhdan CHIQARILGAN o'quvchi chiqarilgan sanasidan (last_lesson_date)
KEYINGI oy uchun qarz olmasligi kerak.

Bug (RO'ZIMBOY ABDRIMOV keysi):
  - O'quvchi Iyun oyida guruhdan chiqarilgan (is_active=False, last_lesson_date=Iyun).
  - Guruhda Iyul uchun davomat yozuvlari qolgan (o'qituvchi butun guruhga qo'ygan).
  - `tuition_month_lesson_count` inactive o'quvchi uchun oydagi BARCHA davomatni
    sanardi (last_lesson_date'ni hisobga olmasdan) → Iyulda "19 ta dars" va to'liq
    350 000 so'm qarz paydo bo'lardi.

Tuzatish: chiqarilgan o'quvchi uchun davomat/dars soni last_lesson_date bilan
cheklanadi. Chiqarilgan oydan keyingi oy → 0 dars → 0 qarz.
"""
from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from billing.models import (
    CenterFeatureOverride,
    CenterSubscription,
    PlanFeature,
    SubscriptionPlan,
)
from education.models import (
    Attendance,
    Enrollment,
    Group,
    StudentGroupHistory,
    TuitionMonth,
)
from education.services.tuition import (
    billable_attendance_count,
    ensure_tuition_month,
    prorated_monthly_fee,
    tuition_month_lesson_count,
)


class RemovedStudentPostRemovalDebtTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Removal Center", slug="removal-center")
        self.teacher = User.objects.create_user(
            email="t@removal.test", password="x", role="teacher",
            center=self.center, ism="T", familya="Teacher", oqituvchi_foizi=50,
        )
        self.group = Group.objects.create(
            center=self.center, nom="IELTS G-1", oqituvchi=self.teacher,
            kurs_narxi=350_000, oqituvchi_foiz=50, oy_dars_soni=12,
        )
        self.student = User.objects.create_user(
            email="s@removal.test", password="x", role="student",
            center=self.center, ism="Rozimboy", familya="Abdrimov",
            telefon1="+998880001566",
        )
        # Iyun oyida chiqarilgan enrollment
        self.enr = Enrollment.objects.create(
            center=self.center, student=self.student, group=self.group,
            is_active=False,
            last_lesson_date=date(2026, 6, 30),
            joined_at=date(2026, 5, 1),
        )
        StudentGroupHistory.objects.create(
            student=self.student, group=self.group, center=self.center,
            start_date=date(2026, 5, 1), end_date=date(2026, 6, 30),
            kurs_narxi=350_000, oqituvchi_foiz=50,
        )
        # Sahifa 200 qaytarishi uchun faol obuna (billing middleware bloklamasin)
        self.director = User.objects.create_user(
            email="d@removal.test", password="x", role="director",
            center=self.center, ism="D", familya="Director",
        )
        plan = SubscriptionPlan.objects.create(
            code="TEST", title="Test", name="TEST", monthly_price=0, price=0,
            duration_days=30, max_students=2000, active=True,
        )
        CenterSubscription.objects.create(
            center=self.center, plan=plan,
            status=CenterSubscription.Status.ACTIVE,
            expires_at=timezone.now() + timedelta(days=30),
        )
        # qarzdorlar_home @require_feature("finance") bilan himoyalangan —
        # markaz uchun shu feature'ni yoqamiz (aks holda billing:plans'ga redirect).
        finance_feat, _ = PlanFeature.objects.get_or_create(
            code="finance",
            defaults={"name": "Moliya", "category": PlanFeature.Category.FINANCE,
                      "is_active": True},
        )
        CenterFeatureOverride.objects.get_or_create(
            center=self.center, feature=finance_feat, defaults={"enabled": True},
        )

    def _mark(self, d: date):
        Attendance.objects.create(
            group=self.group, student=self.student, center=self.center,
            date=d, status="present", present=True,
        )

    def test_post_removal_month_has_zero_lessons_and_debt(self):
        # Iyulda guruhga qolgan davomat yozuvlari (chiqarilgan o'quvchida bo'lmasligi kerak edi)
        for day in (2, 4, 6, 8, 10, 14, 16, 18, 20, 22, 24, 28, 30):
            self._mark(date(2026, 7, day))

        july = date(2026, 7, 1)
        self.assertEqual(tuition_month_lesson_count(self.enr, july), 0,
                         "Chiqarilgandan keyingi oyda dars soni 0 bo'lishi kerak")
        self.assertEqual(billable_attendance_count(self.enr, july), 0)
        self.assertEqual(prorated_monthly_fee(self.enr, july), 0,
                         "Chiqarilgandan keyingi oy uchun qarz yozilmasligi kerak")

    def test_soft_deleted_enrollment_no_attendance_has_zero_debt(self):
        """
        `enr.delete()` (guruhdan o'chirish) → is_deleted=True, lekin is_active=True
        va last_lesson_date=None. Iyulda davomat yo'q → jadval bo'yicha 13 dars
        yozilmasligi, qarz 0 bo'lishi kerak.
        """
        g = Group.objects.create(
            center=self.center, nom="IELTS G-DEL", oqituvchi=self.teacher,
            kurs_narxi=350_000, oqituvchi_foiz=50, oy_dars_soni=12,
        )
        student2 = User.objects.create_user(
            email="s2@removal.test", password="x", role="student",
            center=self.center, ism="Del", familya="Student",
        )
        enr = Enrollment.objects.create(
            center=self.center, student=student2, group=g,
            is_active=True, joined_at=date(2026, 5, 1),
        )
        StudentGroupHistory.objects.create(
            student=student2, group=g, center=self.center,
            start_date=date(2026, 5, 1), kurs_narxi=350_000, oqituvchi_foiz=50,
        )
        # Guruhdan o'chirish: soft-delete (is_active TEGILMAYDI, last_lesson_date YO'Q)
        enr.delete(deleted_by=self.director)
        enr = Enrollment.all_objects.get(pk=enr.pk)
        self.assertTrue(enr.is_deleted)
        self.assertTrue(enr.is_active)          # is_active o'zgармaydi
        self.assertIsNone(enr.last_lesson_date)

        july = date(2026, 7, 1)
        self.assertEqual(tuition_month_lesson_count(enr, july), 0,
                         "Soft-delete + davomat yo'q → 0 dars (jadval bo'yicha 13 emas)")
        self.assertEqual(prorated_monthly_fee(enr, july), 0,
                         "Soft-delete + davomat yo'q → 0 qarz")

    def test_removal_month_counts_only_up_to_last_lesson_date(self):
        # Iyun: last_lesson_date=30 → oydagi barcha davomat sanaladi
        for day in (2, 6, 10, 16, 22, 30):
            self._mark(date(2026, 6, day))
        # last_lesson_date'dan keyin xato yozilgan davomat (sanalmasligi kerak, lekin Iyun<=30 shart)
        june = date(2026, 6, 1)
        self.assertEqual(tuition_month_lesson_count(self.enr, june), 6)
        self.assertEqual(billable_attendance_count(self.enr, june), 6)

    def test_last_lesson_date_null_falls_back_to_history_end_date(self):
        self.enr.last_lesson_date = None
        self.enr.save(update_fields=["last_lesson_date"])
        # memoizatsiyani tozalash uchun yangidan olamiz
        enr = Enrollment.all_objects.get(pk=self.enr.pk)
        self._mark(date(2026, 7, 4))
        self.assertEqual(billable_attendance_count(enr, date(2026, 7, 1)), 0,
                         "last_lesson_date null bo'lsa, history.end_date bilan cheklanadi")

    def test_ensure_tuition_month_self_heals_wrong_post_removal_fee(self):
        """Noto'g'ri yozilgan Iyul TuitionMonth (350k) qayta hisoblanganda 0 ga tushadi."""
        # Iyulda guruhga qolgan davomatlar (bug manbai)
        for day in (2, 4, 6, 8, 10, 14, 16, 18, 20):
            self._mark(date(2026, 7, day))
        july = date(2026, 7, 1)
        # Bug natijasi: to'liq oy qarzi yozilgan
        wrong_tm, _ = TuitionMonth.all_objects.update_or_create(
            enrollment=self.enr, month=july,
            defaults={"fee_amount": 350_000, "center": self.center, "is_deleted": False},
        )
        # Sahifa ochilganda chaqiriladigan self-heal yo'li
        healed = ensure_tuition_month(self.enr, july)
        healed.refresh_from_db()
        self.assertEqual(healed.pk, wrong_tm.pk)
        self.assertEqual(healed.fee_amount, 0,
                         "ensure_tuition_month chiqarilgandan keyingi oy fee'sini 0 qilishi kerak")

    def test_qarzdorlar_page_excludes_post_removal_debtor(self):
        """End-to-end: chiqarilgan o'quvchi Iyulda qarzdorlar sahifasida chiqmasligi kerak."""
        # Iyulda guruhga qolgan davomatlar + bug natijasidagi noto'g'ri TuitionMonth
        for day in (2, 4, 6, 8, 10, 14, 16, 18, 20):
            self._mark(date(2026, 7, day))
        TuitionMonth.all_objects.update_or_create(
            enrollment=self.enr, month=date(2026, 7, 1),
            defaults={"fee_amount": 350_000, "center": self.center, "is_deleted": False},
        )
        self.client.force_login(self.director)
        url = f"/{self.center.slug}{reverse('education:qarzdorlar_home')}"
        # Iyul davrini aniq tanlaymiz (test bugungi sanaga bog'liq bo'lmasin)
        response = self.client.get(url, {"date_from": "2026-07-01", "date_to": "2026-07-31"})
        self.assertEqual(response.status_code, 200)
        debtor_emails = {
            row["student"].email for row in response.context["page_obj"].object_list
        }
        self.assertNotIn(self.student.email, debtor_emails,
                         "Chiqarilgan o'quvchi chiqarilgandan keyingi oyda qarzdor bo'lmasligi kerak")

    def test_active_student_is_unaffected(self):
        group2 = Group.objects.create(
            center=self.center, nom="IELTS G-2", oqituvchi=self.teacher,
            kurs_narxi=350_000, oqituvchi_foiz=50, oy_dars_soni=12,
        )
        active_enr = Enrollment.objects.create(
            center=self.center, student=self.student, group=group2,
            is_active=True, joined_at=date(2026, 5, 1),
        )
        for d in (date(2026, 7, 4), date(2026, 7, 6)):
            Attendance.objects.create(
                group=group2, student=self.student, center=self.center,
                date=d, status="present", present=True,
            )
        self.assertEqual(billable_attendance_count(active_enr, date(2026, 7, 1)), 2,
                         "Faol o'quvchiga klamp qo'llanmasligi kerak")
