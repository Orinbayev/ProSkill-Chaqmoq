"""User'ning aniq 4 senariysini tekshiruvchi integration testlar.

Senariylar (Uzbek user description'idan):

  1) Aprel 40k qarz qoldi -> may'ga "o'tdi" -> may 250k qarz qoshildi ->
     foydalanuvchi 290k to'laydi -> ikkala oy yopiladi.

  2) Faqat may 250k qarz, foydalanuvchi 500k to'laydi -> may yopiladi va
     iyun uchun TuitionMonth avtomatik yaratilib u ham yopiladi (overflow
     auto-create future TuitionMonth — yangi feature).

  3) Re-enrollment: foydalanuvchi aprel'dan yangi 500k oylik kursga retroactive
     yoziladi -> aprel uchun TuitionMonth avtomatik yaratiladi va qarz chiqadi
     (enroll_student'ga ensure_all_tuition_months_since_start qo'shilgan).

  4) Avtomatik start_month tanlash: agar payment'da start_month berilmasa,
     find_earliest_unpaid_month eng eski qarz oydan boshlasin.
"""
from datetime import date, datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import Center, User
from education.models import (
    Enrollment,
    Group,
    StudentGroupHistory,
    TuitionMonth,
    PaymentAllocation,
)
from education.services.enrollment_service import EnrollmentService
from education.services.tuition import (
    create_payment_and_allocate,
    ensure_tuition_month,
    month_first_day,
    add_month,
)


def _prev_month_start(today):
    first = today.replace(day=1)
    return (first - timedelta(days=1)).replace(day=1)


def _allocations_sum(tm):
    return int(
        sum(tm.allocations.filter(is_deleted=False).values_list("amount", flat=True))
    )


class PaymentCarryoverTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.cur_month = month_first_day(self.today)
        self.prev_month = _prev_month_start(self.today)
        self.next_month = add_month(self.cur_month, 1)

        self.center = Center.objects.create(name="Carryover Center", slug="carryover-center")
        self.manager = User.objects.create_user(
            email="manager@carry.test",
            password="testpass123",
            role="manager",
            center=self.center,
            ism="Carry",
            familya="Manager",
        )
        self.teacher = User.objects.create_user(
            email="teacher@carry.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Carry",
            familya="Teacher",
            oqituvchi_foizi=40,
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="Carryover Group",
            oqituvchi=self.teacher,
            kurs_narxi=250_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.student = User.objects.create_user(
            email="stu@carry.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Olim",
            familya="Olimov",
            telefon1="+998901111111",
        )
        # Enrollment aprel boshidan, oylik 250k. find_earliest_unpaid_month
        # uchun aniq boshlanish nuqtasi.
        self.enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            kurs_narhi=250_000,
            student_payable_amount=250_000,
            oqituvchi_foiz=40,
            is_active=True,
            joined_at=self.prev_month,
        )
        StudentGroupHistory.objects.create(
            student=self.student,
            group=self.group,
            center=self.center,
            start_date=self.prev_month,
            kurs_narxi=250_000,
            oqituvchi_foiz=40,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Senariy 1: Aprel + may qarz qoldi, jami summa to'lov ikkala oyni yopadi
    # ──────────────────────────────────────────────────────────────────────
    def test_two_months_debt_cleared_by_combined_payment(self):
        prev_tm = ensure_tuition_month(self.enrollment, self.prev_month)
        cur_tm = ensure_tuition_month(self.enrollment, self.cur_month)
        self.assertEqual(prev_tm.fee_amount, 250_000)
        self.assertEqual(cur_tm.fee_amount, 250_000)

        total_debt = prev_tm.fee_amount + cur_tm.fee_amount  # 500k

        create_payment_and_allocate(
            enrollment=self.enrollment,
            created_by=self.manager,
            cash_amount=total_debt,
            card_amount_som=0,
            start_month=self.prev_month,
            paid_at=datetime.combine(self.today, datetime.min.time()),
        )

        prev_tm.refresh_from_db()
        cur_tm.refresh_from_db()
        self.assertEqual(_allocations_sum(prev_tm), 250_000, "Aprel to'liq yopilishi kerak")
        self.assertEqual(_allocations_sum(cur_tm), 250_000, "May to'liq yopilishi kerak")
        self.assertEqual(prev_tm.fee_amount - _allocations_sum(prev_tm), 0)
        self.assertEqual(cur_tm.fee_amount - _allocations_sum(cur_tm), 0)

    # ──────────────────────────────────────────────────────────────────────
    # Senariy 2: Faqat may 250k qarz, 500k to'lov -> iyun avtomatik yopiladi
    # ──────────────────────────────────────────────────────────────────────
    def test_overpayment_auto_creates_next_month_tuition(self):
        cur_tm = ensure_tuition_month(self.enrollment, self.cur_month)
        self.assertEqual(cur_tm.fee_amount, 250_000)

        # Iyun TuitionMonth hali YO'Q
        self.assertFalse(
            TuitionMonth.objects.filter(
                enrollment=self.enrollment, month=self.next_month
            ).exists(),
            "Test boshida iyun TuitionMonth bo'lmasligi kerak",
        )

        # Foydalanuvchi 500k to'laydi (kerakli 250k + qoshimcha 250k)
        create_payment_and_allocate(
            enrollment=self.enrollment,
            created_by=self.manager,
            cash_amount=500_000,
            card_amount_som=0,
            start_month=self.cur_month,
            paid_at=datetime.combine(self.today, datetime.min.time()),
        )

        # May yopildi
        cur_tm.refresh_from_db()
        self.assertEqual(_allocations_sum(cur_tm), 250_000, "May yopilishi kerak")
        self.assertEqual(
            cur_tm.fee_amount - _allocations_sum(cur_tm), 0,
            "May qarzdor bo'lmasligi kerak",
        )

        # Iyun avtomatik yaratildi va to'lovdan ortgani unga yozildi
        next_tm = TuitionMonth.objects.filter(
            enrollment=self.enrollment, month=self.next_month, is_deleted=False
        ).first()
        self.assertIsNotNone(next_tm, "Iyun TuitionMonth avtomatik yaratilishi kerak")
        self.assertEqual(next_tm.fee_amount, 250_000)
        self.assertEqual(_allocations_sum(next_tm), 250_000, "Iyun to'liq yopilishi kerak")
        self.assertEqual(
            next_tm.fee_amount - _allocations_sum(next_tm), 0,
            "Iyun qarzdor bo'lmasligi kerak (avtomatik chiqish)",
        )

    # ──────────────────────────────────────────────────────────────────────
    # Senariy 3: Re-enrollment retroactive — yangi 500k kursga aprel'dan
    # qoshilganda aprel uchun TuitionMonth avtomatik yaratilib qarz chiqadi
    # ──────────────────────────────────────────────────────────────────────
    def test_re_enrollment_in_past_month_creates_debt(self):
        # Yangi guruh, oylik 500k
        new_group = Group.objects.create(
            center=self.center,
            nom="Premium Group",
            oqituvchi=self.teacher,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        # Bu guruhga aprel oyi boshidan retroactive yozaylik
        new_enrollment = EnrollmentService.enroll_student(
            student=self.student,
            group=new_group,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            student_payable_amount=500_000,
            start_date=self.prev_month,  # aprel boshi
        )

        # Aprel uchun TuitionMonth yaratilgan bo'lishi shart (retroactive)
        prev_tm_new = TuitionMonth.objects.filter(
            enrollment=new_enrollment, month=self.prev_month, is_deleted=False
        ).first()
        self.assertIsNotNone(
            prev_tm_new,
            "Yangi enrollment uchun aprel TuitionMonth retroactive yaratilishi kerak",
        )
        self.assertEqual(
            prev_tm_new.fee_amount, 500_000,
            "Yangi 500k kurs uchun aprel fee 500k bo'lishi kerak (to'liq oy)",
        )
        # Hech qanday allocation yo'q -> qarz = fee
        self.assertEqual(_allocations_sum(prev_tm_new), 0)
        debt = prev_tm_new.fee_amount - _allocations_sum(prev_tm_new)
        self.assertGreater(debt, 0, "Yangi retroactive enrollment qarz chiqarishi kerak")

        # Joriy oy (may) uchun ham TuitionMonth yaratilgan
        cur_tm_new = TuitionMonth.objects.filter(
            enrollment=new_enrollment, month=self.cur_month, is_deleted=False
        ).first()
        self.assertIsNotNone(cur_tm_new, "May TuitionMonth ham yaratilishi kerak")

    # ──────────────────────────────────────────────────────────────────────
    # Senariy: bir o'quvchining 2 yo'nalishi — bitta to'lov ikkalasiga
    # to'g'ri taqsimlanadi va qolgan qarz aniq ko'rinadi
    # ──────────────────────────────────────────────────────────────────────
    def test_single_payment_distributes_across_multiple_enrollments(self):
        from django.urls import reverse
        self.enrollment.joined_at = self.cur_month
        self.enrollment.save(update_fields=["joined_at"])
        StudentGroupHistory.objects.filter(
            student=self.student,
            group=self.group,
        ).update(start_date=self.cur_month)

        # 2-yo'nalish: 400k oylik (Programming kabi)
        prog_group = Group.objects.create(
            center=self.center,
            nom="Programming",
            oqituvchi=self.teacher,
            kurs_narxi=400_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        prog_enrollment = Enrollment.objects.create(
            center=self.center,
            group=prog_group,
            student=self.student,
            kurs_narhi=400_000,
            student_payable_amount=400_000,
            oqituvchi_foiz=40,
            is_active=True,
            joined_at=self.cur_month,
        )
        StudentGroupHistory.objects.create(
            student=self.student,
            group=prog_group,
            center=self.center,
            start_date=self.cur_month,
            kurs_narxi=400_000,
            oqituvchi_foiz=40,
        )

        # English (250k oylik) qarzini joriy oy uchun ta'minlaymiz
        eng_tm = ensure_tuition_month(self.enrollment, self.cur_month)
        prog_tm = ensure_tuition_month(prog_enrollment, self.cur_month)
        self.assertEqual(eng_tm.fee_amount, 250_000)
        self.assertEqual(prog_tm.fee_amount, 400_000)
        # Jami qarz: 250k + 400k = 650k. Foydalanuvchi 500k to'laydi.

        self.client.force_login(self.manager)
        url = f"/{self.center.slug}" + reverse("education:create_payment")
        response = self.client.post(url, {
            "student_id": self.student.id,
            "cash_amount": "500000",
            "card_amount": "0",
            "month": self.cur_month.strftime("%Y-%m"),
            "paid_date": self.today.isoformat(),
        })
        self.assertIn(response.status_code, (302, 303))

        eng_tm.refresh_from_db()
        prog_tm.refresh_from_db()

        eng_paid = _allocations_sum(eng_tm)
        prog_paid = _allocations_sum(prog_tm)

        # English (1-yozilgan) to'liq yopilishi kerak
        self.assertEqual(eng_paid, 250_000, "English 250k to'liq yopilishi kerak")
        # Programming'ga qoldiq 250k yozilgan (400k - 250k = 150k qarz qoldi)
        self.assertEqual(prog_paid, 250_000, "Programming'ga 250k yozilishi kerak")
        # Jami yozilgan = 500k
        self.assertEqual(eng_paid + prog_paid, 500_000)

        # Qolgan qarz: Programming 150k
        eng_debt = eng_tm.fee_amount - eng_paid
        prog_debt = prog_tm.fee_amount - prog_paid
        self.assertEqual(eng_debt, 0)
        self.assertEqual(prog_debt, 150_000, "Programming hali 150k qarzdor bo'lishi kerak")
        self.assertEqual(eng_debt + prog_debt, 150_000, "Jami qolgan qarz 150k")

    # ──────────────────────────────────────────────────────────────────────
    # Senariy: To'lovni faqat tanlangan oy uchun o'chirish — boshqa oyga
    # ta'sir bermaslik. PaymentAllocation'lar ham soft-delete qilinadi.
    # ──────────────────────────────────────────────────────────────────────
    def test_per_month_payment_delete_isolates_to_target_month(self):
        from django.urls import reverse

        # Aprel + may'ga to'liq to'lov (har biri 250k) — jami 500k
        prev_tm = ensure_tuition_month(self.enrollment, self.prev_month)
        cur_tm = ensure_tuition_month(self.enrollment, self.cur_month)
        create_payment_and_allocate(
            enrollment=self.enrollment,
            created_by=self.manager,
            cash_amount=500_000,
            card_amount_som=0,
            start_month=self.prev_month,
            paid_at=datetime.combine(self.today, datetime.min.time()),
        )
        prev_tm.refresh_from_db()
        cur_tm.refresh_from_db()
        self.assertEqual(_allocations_sum(prev_tm), 250_000)
        self.assertEqual(_allocations_sum(cur_tm), 250_000)

        # Aprel'ni o'chiramiz (keep_in_group=1, month=prev_month)
        self.client.force_login(self.manager)
        url = (
            f"/{self.center.slug}"
            + reverse("education:enrollment_delete", args=[self.enrollment.id])
        )
        response = self.client.post(url, {
            "keep_in_group": "1",
            "month": self.prev_month.strftime("%Y-%m"),
        })
        self.assertIn(response.status_code, (302, 303))

        # Aprel TuitionMonth — soft-deleted (qarzdorlar safidan chiqdi)
        prev_tm.refresh_from_db()
        self.assertTrue(prev_tm.is_deleted, "Aprel TuitionMonth o'chirilishi kerak")

        # Aprel allocation'lari — soft-deleted
        prev_alloc_active = prev_tm.allocations.filter(is_deleted=False).count()
        self.assertEqual(prev_alloc_active, 0, "Aprel allocation'lari o'chirilishi kerak")

        # MAY tegmasin
        cur_tm.refresh_from_db()
        self.assertFalse(cur_tm.is_deleted, "May TuitionMonth tegilmasligi kerak")
        self.assertEqual(
            _allocations_sum(cur_tm), 250_000,
            "May allocation'lari saqlanishi kerak (250k to'liq)",
        )
        self.assertEqual(
            cur_tm.fee_amount - _allocations_sum(cur_tm), 0,
            "May qarzdor bo'lmasligi kerak",
        )

    # ──────────────────────────────────────────────────────────────────────
    # Senariy 4: start_month=None -> eng eski to'lanmagan oydan boshlasin
    # ──────────────────────────────────────────────────────────────────────
    def test_default_start_month_picks_earliest_unpaid(self):
        prev_tm = ensure_tuition_month(self.enrollment, self.prev_month)
        cur_tm = ensure_tuition_month(self.enrollment, self.cur_month)

        # Ikki oy ham qarzdor, kichik to'lov (faqat aprel'ni yopadi)
        create_payment_and_allocate(
            enrollment=self.enrollment,
            created_by=self.manager,
            cash_amount=250_000,
            card_amount_som=0,
            start_month=None,  # avtomatik tanlash
            paid_at=datetime.combine(self.today, datetime.min.time()),
        )

        prev_tm.refresh_from_db()
        cur_tm.refresh_from_db()
        # Eng eski qarz = aprel -> u to'liq yopilishi kerak
        self.assertEqual(_allocations_sum(prev_tm), 250_000, "Aprel birinchi yopiladi")
        # May hali qarzdor
        self.assertEqual(_allocations_sum(cur_tm), 0)
        self.assertEqual(cur_tm.fee_amount - _allocations_sum(cur_tm), 250_000)

    # ──────────────────────────────────────────────────────────────────────
    # Senariy: Guruhlararo avtomatik to'lov/kredit netting
    # ──────────────────────────────────────────────────────────────────────
    def test_automatic_cross_group_credit_netting(self):
        from education.services.tuition import auto_net_student_credits
        
        # Pay off English enrollment fully first to avoid it stealing the credit balance
        english_payment = create_payment_and_allocate(
            enrollment=self.enrollment,
            created_by=self.manager,
            cash_amount=250_000,
            card_amount_som=0,
            start_month=self.cur_month,
            paid_at=datetime.combine(self.today, datetime.min.time()),
        )

        # Now set the credit balance explicitly
        self.enrollment.credit_balance = 100_000
        self.enrollment.save(update_fields=["credit_balance"])

        # 2. Create another active group (Math) with an unpaid debt
        math_group = Group.objects.create(
            center=self.center,
            nom="Math Group",
            oqituvchi=self.teacher,
            kurs_narxi=300_000,
            oy_dars_soni=12,
        )
        math_enrollment = Enrollment.objects.create(
            center=self.center,
            group=math_group,
            student=self.student,
            kurs_narhi=300_000,
            student_payable_amount=300_000,
            is_active=True,
            joined_at=self.cur_month,
        )
        StudentGroupHistory.objects.create(
            student=self.student,
            group=math_group,
            center=self.center,
            start_date=self.cur_month,
            kurs_narxi=300_000,
        )

        math_tm = ensure_tuition_month(math_enrollment, self.cur_month)
        self.assertEqual(math_tm.fee_amount, 300_000)

        # 3. Initially, Math enrollment has 300k debt
        self.assertEqual(_allocations_sum(math_tm), 0)

        # 4. Trigger auto_net_student_credits
        auto_net_student_credits(self.student)

        # 5. Verify the credit was transferred!
        self.enrollment.refresh_from_db()
        math_tm.refresh_from_db()

        # English credit balance should be decremented to 0
        self.assertEqual(self.enrollment.credit_balance, 0)
        # Math group should have 100k allocation from the English payment!
        self.assertEqual(_allocations_sum(math_tm), 100_000)
