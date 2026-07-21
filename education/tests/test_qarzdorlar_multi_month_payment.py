"""Qarzdorlar bo'limi: ko'p oylik qarz va to'lov stsenariylari.

Maqsad — foydalanuvchi tomonidan bayon qilingan haqiqiy stsenariyni tekshirish:

  Stsenariy 1: O'tgan oydan qarz qoldi, bu oyda joriy oy fee + o'tgan qarz = 2 oylik
              jami summa to'lanadi. Tizim ikkala oyda ham qarzni 0 ga tushirishi shart.

  Stsenariy 2: Faqat o'tgan oy qarzini to'lash → o'tgan oy 0, joriy oy hali qarzdor.

  Stsenariy 3: Status filterlari (active / deferred / all) ishlashi.

  Stsenariy 4: Min/Max debt filteri ishlashi.

Bu testlar `tuition.create_payment_and_allocate` orqali to'lov yozadi va
`qarzdorlar_home` view'ining context'idagi raqamlarni assert qiladi.
"""
from datetime import date, datetime, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from core.test_utils import activate_center
from education.models import (
    Enrollment,
    Group,
    StudentGroupHistory,
    TuitionMonth,
)
from education.services.tuition import (
    create_payment_and_allocate,
    ensure_tuition_month,
    month_first_day,
)


def _prev_month_start(today):
    first = today.replace(day=1)
    return (first - timedelta(days=1)).replace(day=1)


class QarzdorlarMultiMonthPaymentTests(TestCase):
    """O'tgan oy + joriy oy qarz/to'lov birlashgan stsenariylar."""

    def setUp(self):
        self.today = timezone.localdate()
        self.cur_month = month_first_day(self.today)
        self.prev_month = _prev_month_start(self.today)

        self.center = Center.objects.create(name="MM Center", slug="mm-center", features={"finance": True})
        activate_center(self.center)
        self.manager = User.objects.create_user(
            email="manager@mm.test",
            password="testpass123",
            role="manager",
            center=self.center,
            ism="MM",
            familya="Manager",
        )
        self.teacher = User.objects.create_user(
            email="teacher@mm.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="MM",
            familya="Teacher",
            oqituvchi_foizi=40,
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="Multi-month group",
            oqituvchi=self.teacher,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.student = User.objects.create_user(
            email="stu@mm.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Olim",
            familya="Olimov",
            telefon1="+998901234567",
        )
        # 2 oy oldin boshlangan deb hisoblaymiz
        history_start = (self.prev_month - timedelta(days=1)).replace(day=1)
        self.enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            kurs_narhi=500_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        StudentGroupHistory.objects.create(
            student=self.student,
            group=self.group,
            center=self.center,
            start_date=history_start,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
        )

        # O'tgan oy va joriy oy uchun TuitionMonth yarat (har birida 500 000 so'm fee).
        self.prev_tm = ensure_tuition_month(self.enrollment, self.prev_month)
        self.cur_tm = ensure_tuition_month(self.enrollment, self.cur_month)

        self.client.force_login(self.manager)
        self.url = f"/{self.center.slug}{reverse('education:qarzdorlar_home')}"

    # ─────────────────────────────────────────────────────────────────────
    # Yordamchilar
    # ─────────────────────────────────────────────────────────────────────
    def _refresh_tm(self, tm):
        tm.refresh_from_db()
        return tm

    def _debt_for_month(self, tm):
        tm = self._refresh_tm(tm)
        fee = int(getattr(tm, "fee_amount", 0) or getattr(tm, "summa", 0) or 0)
        paid = int(
            tm.allocations.filter(is_deleted=False).values_list("amount", flat=True).aggregate_or_zero()
            if hasattr(tm.allocations.filter(is_deleted=False).values_list("amount", flat=True), "aggregate_or_zero")
            else sum(tm.allocations.filter(is_deleted=False).values_list("amount", flat=True))
        )
        return max(0, fee - paid)

    def _student_total_debt_via_view(self, **filters):
        """Joriy oy filteri bilan view'ni chaqirib, jami qarz qaytaradi."""
        params = {
            "date_from": self.prev_month.isoformat(),
            "date_to": self.today.isoformat(),
        }
        params.update(filters)
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return response

    # ─────────────────────────────────────────────────────────────────────
    # STSENARIY 1: O'TGAN OY QARZI + JORIY OY FEE = 2 OYLIK JAMI TO'LOV
    # ─────────────────────────────────────────────────────────────────────
    def test_paying_two_months_at_once_clears_both(self):
        """
        Boshlang'ich holat:
          - O'tgan oy: fee=500 000, paid=0 → debt=500 000
          - Joriy oy:  fee=500 000, paid=0 → debt=500 000
          - Jami qarz: 1 000 000

        Foydalanuvchi 2 oylik to'lov kiritadi (1 000 000):
          - O'tgan oy yopilishi kerak (debt=0)
          - Joriy oy yopilishi kerak (debt=0)
          - Student umumiy qarzi 0
        """
        # 1) Boshlang'ich qarz tekshiruvi
        prev_fee = int(self.prev_tm.fee_amount)
        cur_fee = int(self.cur_tm.fee_amount)
        self.assertGreater(prev_fee, 0, "Prev oy fee 0 bo'lmasligi kerak")
        self.assertGreater(cur_fee, 0, "Joriy oy fee 0 bo'lmasligi kerak")
        total_expected_debt = prev_fee + cur_fee

        # 2) Qarzdorlar sahifasi 1 000 000 ko'rsatishi kerak (oxirgi 2 oy filterida)
        response = self._student_total_debt_via_view()
        filtered_debt = response.context["filtered_debt"]
        self.assertEqual(
            filtered_debt, total_expected_debt,
            f"O'tgan + joriy oy jami qarzi: kutilgan {total_expected_debt}, kelgan {filtered_debt}",
        )

        # 3) 2 oylik to'liq summa to'lanadi (start_month=prev_month — birinchi
        #    qarzdor oydan boshlab forward allocate)
        create_payment_and_allocate(
            enrollment=self.enrollment,
            created_by=self.manager,
            cash_amount=total_expected_debt,
            card_amount_som=0,
            start_month=self.prev_month,
            paid_at=datetime.combine(self.today, datetime.min.time()),
        )

        # 4) Ikkala TuitionMonth ham yopilishi shart
        self.prev_tm.refresh_from_db()
        self.cur_tm.refresh_from_db()
        prev_paid = sum(
            self.prev_tm.allocations.filter(is_deleted=False).values_list("amount", flat=True)
        )
        cur_paid = sum(
            self.cur_tm.allocations.filter(is_deleted=False).values_list("amount", flat=True)
        )
        self.assertEqual(prev_paid, prev_fee, f"O'tgan oy to'liq yopilmadi: paid={prev_paid}, fee={prev_fee}")
        self.assertEqual(cur_paid, cur_fee, f"Joriy oy to'liq yopilmadi: paid={cur_paid}, fee={cur_fee}")

        # 5) Qarzdorlar sahifasi endi 0 qarz ko'rsatishi kerak — student debtor
        #    bo'lmasligi kerak. Ya'ni page_obj.paginator.count == 0
        response = self._student_total_debt_via_view()
        self.assertEqual(
            response.context["filtered_debt"], 0,
            "Hamma to'langandan keyin filtered_debt 0 bo'lishi kerak",
        )
        self.assertEqual(
            response.context["page_obj"].paginator.count, 0,
            "Hamma to'langandan keyin qarzdorlar ro'yxati bo'sh bo'lishi kerak",
        )

    # ─────────────────────────────────────────────────────────────────────
    # STSENARIY 2: FAQAT O'TGAN OY QARZINI YOPADI
    # ─────────────────────────────────────────────────────────────────────
    def test_paying_only_previous_month_leaves_current_unpaid(self):
        """
        Faqat o'tgan oy qarzini to'laydi. Kutilayotgan natija:
          - O'tgan oy: paid=fee, debt=0
          - Joriy oy:  paid=0,   debt=fee (hali qarzdor)
          - Student qarz darajasi: faqat joriy oy fee (500 000)
        """
        prev_fee = int(self.prev_tm.fee_amount)
        cur_fee = int(self.cur_tm.fee_amount)

        create_payment_and_allocate(
            enrollment=self.enrollment,
            created_by=self.manager,
            cash_amount=prev_fee,
            card_amount_som=0,
            start_month=self.prev_month,
            paid_at=datetime.combine(self.today, datetime.min.time()),
        )

        self.prev_tm.refresh_from_db()
        self.cur_tm.refresh_from_db()

        prev_paid = sum(
            self.prev_tm.allocations.filter(is_deleted=False).values_list("amount", flat=True)
        )
        cur_paid = sum(
            self.cur_tm.allocations.filter(is_deleted=False).values_list("amount", flat=True)
        )
        self.assertEqual(prev_paid, prev_fee, "O'tgan oy to'liq yopildi")
        self.assertEqual(cur_paid, 0, "Joriy oy hali to'lanmagan")

        # Qarzdorlar sahifasida — student hali qarzdor (joriy oy fee)
        response = self._student_total_debt_via_view()
        self.assertEqual(
            response.context["filtered_debt"], cur_fee,
            f"Joriy oy qarzi qoladi: kutilgan {cur_fee}, kelgan {response.context['filtered_debt']}",
        )
        self.assertEqual(
            response.context["page_obj"].paginator.count, 1,
            "Student hali qarzdor — ro'yxatda bo'lishi kerak",
        )

    # ─────────────────────────────────────────────────────────────────────
    # STSENARIY 3: ORTIQCHA TO'LOV (overpayment forward allocation)
    # ─────────────────────────────────────────────────────────────────────
    def test_overpayment_flows_into_next_month_tuition(self):
        """
        Ortiqcha to'lov (mavjud qarzdan ko'p): qolgan summa kelgusi oy uchun
        TuitionMonth avtomatik yaratiladi va unga oqim qiladi. Bu o'quvchi
        500k to'lasa may + iyun ikkalasi qarzdorlar safidan chiqishi uchun
        kerak.
        """
        from education.services.tuition import add_month
        prev_fee = int(self.prev_tm.fee_amount)
        cur_fee = int(self.cur_tm.fee_amount)
        excess = cur_fee // 2
        overpay_amount = prev_fee + cur_fee + excess

        create_payment_and_allocate(
            enrollment=self.enrollment,
            created_by=self.manager,
            cash_amount=overpay_amount,
            card_amount_som=0,
            start_month=self.prev_month,
            paid_at=datetime.combine(self.today, datetime.min.time()),
        )

        self.prev_tm.refresh_from_db()
        self.cur_tm.refresh_from_db()
        prev_paid = sum(
            self.prev_tm.allocations.filter(is_deleted=False).values_list("amount", flat=True)
        )
        cur_paid = sum(
            self.cur_tm.allocations.filter(is_deleted=False).values_list("amount", flat=True)
        )
        self.assertEqual(prev_paid, prev_fee, "Prev oy aniq fee qadar yopilgan")
        self.assertEqual(cur_paid, cur_fee, "Joriy oy aniq fee qadar yopilgan (overflow emas)")

        # Kelgusi oy avtomatik yaratilgan va excess unga yozilgan
        next_month = add_month(self.cur_month, 1)
        next_tm = TuitionMonth.objects.filter(
            enrollment=self.enrollment, month=next_month, is_deleted=False
        ).first()
        self.assertIsNotNone(next_tm, "Kelgusi oy uchun TuitionMonth yaratilishi kerak")
        next_paid = sum(
            next_tm.allocations.filter(is_deleted=False).values_list("amount", flat=True)
        )
        self.assertEqual(next_paid, excess, "Excess summa kelgusi oyga yozilgan")

        # Qarzdorlar sahifasi (joriy oy filteri): qarz 0
        response = self._student_total_debt_via_view()
        self.assertEqual(response.context["filtered_debt"], 0)
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    # ─────────────────────────────────────────────────────────────────────
    # STSENARIY 4: STATUS FILTRI (active / deferred / all)
    # ─────────────────────────────────────────────────────────────────────
    def test_status_filter_active_excludes_deferred(self):
        """
        Tahririmizdan keyin: status=active → faqat is_deferred=False qarzdorlar
        Boshlanish: 1 ta qarzdor student (faol). Uni `is_deferred=True` qilamiz.
        Ko'rsatkich: status=active filterda chiqmasligi kerak.
        """
        # Boshlang'ich: status=active (default) — student qarzdor sifatida ko'rinishi kerak
        response = self.client.get(self.url, {"status": "active"})
        self.assertEqual(response.context["page_obj"].paginator.count, 1)

        # Enrollment'ni "kechiktirilgan" qilamiz
        self.enrollment.is_deferred = True
        self.enrollment.save(update_fields=["is_deferred"])

        # status=active → 0 qarzdor (deferred chiqarib tashlanadi)
        response = self.client.get(self.url, {"status": "active"})
        self.assertEqual(
            response.context["page_obj"].paginator.count, 0,
            "Kechiktirilgan student status=active ichida ko'rinmasligi kerak",
        )

        # status=deferred → 1 qarzdor (faqat kechiktirilganlar)
        response = self.client.get(self.url, {"status": "deferred"})
        self.assertEqual(
            response.context["page_obj"].paginator.count, 1,
            "status=deferred faqat is_deferred=True larni ko'rsatishi kerak",
        )

        # status=all → 1 qarzdor (ikkalasini ham)
        response = self.client.get(self.url, {"status": "all"})
        self.assertEqual(response.context["page_obj"].paginator.count, 1)

    def test_status_context_passed_to_template(self):
        """View context'da `selected_status` borligini tekshirish."""
        response = self.client.get(self.url, {"status": "deferred"})
        self.assertEqual(response.context["selected_status"], "deferred")

        response = self.client.get(self.url)
        self.assertEqual(response.context["selected_status"], "active")  # default

        response = self.client.get(self.url, {"status": "garbage"})
        self.assertEqual(response.context["selected_status"], "active")  # noto'g'ri qiymat → default

    # ─────────────────────────────────────────────────────────────────────
    # STSENARIY 5: MIN/MAX DEBT FILTRI
    # ─────────────────────────────────────────────────────────────────────
    def test_min_max_debt_filter_applies_correctly(self):
        """
        Boshlang'ich: 1 student, qarz ~1 000 000 (2 oy × 500 000).

        min_debt=2 000 000  → 0 qarzdor (filter chetda)
        max_debt=100 000    → 0 qarzdor (filter chetda)
        min_debt=500 000, max_debt=2 000 000 → 1 qarzdor (filter ichida)
        """
        # Tashqarida (min juda baland)
        response = self.client.get(self.url, {"min_debt": 2_000_000})
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

        # Tashqarida (max juda past)
        response = self.client.get(self.url, {"max_debt": 100_000})
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

        # Ichida
        response = self.client.get(self.url, {"min_debt": 500_000, "max_debt": 2_000_000})
        self.assertEqual(response.context["page_obj"].paginator.count, 1)


class PriceSyncTests(TestCase):
    def setUp(self):
        from accounts.models import Center, User
        from education.models import Group, Enrollment, StudentGroupHistory
        from education.services.tuition import ensure_tuition_month
        from django.utils import timezone

        self.center = Center.objects.create(name="Sync Center", slug="sync-center", features={"finance": True})
        
        self.manager = User.objects.create_user(
            email="manager@sync.test",
            password="testpass123",
            role="manager",
            center=self.center,
            ism="Sync",
            familya="Manager",
        )
        self.teacher = User.objects.create_user(
            email="teacher@sync.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Sync",
            familya="Teacher",
            oqituvchi_foizi=40,
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="Sync Group",
            oqituvchi=self.teacher,
            kurs_narxi=400_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        
        # O'quvchi 1: guruh eski narxi bilan
        self.student1 = User.objects.create_user(
            email="stu1@sync.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Stu",
            familya="One",
        )
        first_of_month = timezone.localdate().replace(day=1)
        self.enr1 = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student1,
            kurs_narhi=400_000,
            oqituvchi_foiz=40,
            is_active=True,
            joined_at=first_of_month,
        )
        self.hist1 = StudentGroupHistory.objects.create(
            student=self.student1,
            group=self.group,
            center=self.center,
            start_date=first_of_month,
            kurs_narxi=400_000,
            oqituvchi_foiz=40,
        )
        
        # O'quvchi 2: Narxi 0 bo'lgan
        self.student2 = User.objects.create_user(
            email="stu2@sync.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Stu",
            familya="Two",
        )
        self.enr2 = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student2,
            kurs_narhi=0,
            oqituvchi_foiz=40,
            is_active=True,
            joined_at=first_of_month,
        )
        self.hist2 = StudentGroupHistory.objects.create(
            student=self.student2,
            group=self.group,
            center=self.center,
            start_date=first_of_month,
            kurs_narxi=0,
            oqituvchi_foiz=40,
        )
        
        # O'quvchi 3: Custom narxli o'quvchi
        self.student3 = User.objects.create_user(
            email="stu3@sync.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Stu",
            familya="Three",
        )
        self.enr3 = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student3,
            kurs_narhi=300_000,
            oqituvchi_foiz=40,
            is_active=True,
            joined_at=first_of_month,
        )
        self.hist3 = StudentGroupHistory.objects.create(
            student=self.student3,
            group=self.group,
            center=self.center,
            start_date=first_of_month,
            kurs_narxi=300_000,
            oqituvchi_foiz=40,
        )
        
        self.tm1 = ensure_tuition_month(self.enr1, timezone.localdate())
        self.tm2 = ensure_tuition_month(self.enr2, timezone.localdate())
        self.tm3 = ensure_tuition_month(self.enr3, timezone.localdate())
        
        self.client.force_login(self.manager)

    def test_group_price_edit_syncs_correct_students(self):
        url = reverse("education:group_edit", args=[self.group.pk])
        group_edit_url = f"/{self.center.slug}{url}"
        
        post_data = {
            "nom": "Sync Group (Edited)",
            "oqituvchi": self.teacher.pk,
            "kurs_narxi": 600_000,
            "oqituvchi_foiz": 40,
        }
        
        response = self.client.post(group_edit_url, post_data)
        self.assertEqual(response.status_code, 302)
        
        self.group.refresh_from_db()
        self.assertEqual(self.group.kurs_narxi, 600_000)
        
        # enr1 updated
        self.enr1.refresh_from_db()
        self.assertEqual(self.enr1.kurs_narhi, 600_000)
        self.hist1.refresh_from_db()
        self.assertEqual(self.hist1.kurs_narxi, 600_000)
        self.tm1.refresh_from_db()
        self.assertEqual(self.tm1.fee_amount, 600_000)
        
        # enr2 updated
        self.enr2.refresh_from_db()
        self.assertEqual(self.enr2.kurs_narhi, 600_000)
        self.hist2.refresh_from_db()
        self.assertEqual(self.hist2.kurs_narxi, 600_000)
        self.tm2.refresh_from_db()
        self.assertEqual(self.tm2.fee_amount, 600_000)
        
        # enr3 untouched (custom price)
        self.enr3.refresh_from_db()
        self.assertEqual(self.enr3.kurs_narhi, 300_000)
        self.hist3.refresh_from_db()
        self.assertEqual(self.hist3.kurs_narxi, 300_000)
        self.tm3.refresh_from_db()
        self.assertEqual(self.tm3.fee_amount, 300_000)

    def test_student_enrollment_price_edit_via_ajax_syncs_tuition(self):
        url = reverse("accounts:student_edit_ajax", args=[self.student3.pk])
        ajax_url = f"/{self.center.slug}{url}" if not url.startswith(f"/{self.center.slug}") else url
        
        post_data = {
            "action": "enrollment_update",
            "enrollment_id": self.enr3.pk,
            "kurs_narhi": 350_000,
        }
        response = self.client.post(ajax_url, post_data)
        self.assertEqual(response.status_code, 200)
        
        self.enr3.refresh_from_db()
        self.assertEqual(self.enr3.kurs_narhi, 350_000)
        
        self.hist3.refresh_from_db()
        self.assertEqual(self.hist3.kurs_narxi, 350_000)
        
        self.tm3.refresh_from_db()
        self.assertEqual(self.tm3.fee_amount, 350_000)
