"""
Shu sessiyada kiritilgan to'lov tuzatishlari uchun regression testlar:

1. reset_student_month_payments — oy to'liq qarzga qaytadi, to'lov o'chadi,
   fee haqiqiy kurs narxiga qaytadi, credit 0 bo'ladi.
2. _auto_link_payment_to_tm — bekor qilingan to'lovni qayta bog'lamaydi
   (resurrection bug).
3. edit_student_month_debt — user_edit himoyasi: _etm qo'lda kiritilgan
   fee ni qayta yozmaydi.
4. delete_student_month — kelajak oy o'chirilganda to'lov ham bekor bo'ladi
   va oy keyingi to'lovda qayta tiklanadi (o'tkazib yuborilmaydi).
"""
from datetime import date, datetime, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from billing.models import SubscriptionPlan
from education.models import Enrollment, Group, Payment, PaymentAllocation, TuitionMonth
from education.services.tuition import (
    create_payment_and_allocate,
    ensure_tuition_month,
    tuition_month_fee_field,
)


def _paid(tm) -> int:
    return sum(
        int(a.amount or 0)
        for a in PaymentAllocation.objects.filter(
            tuition_month=tm, payment__is_deleted=False
        )
    )


class SessionPaymentFixesTests(TestCase):
    def setUp(self):
        SubscriptionPlan.objects.create(
            code="START", title="Start Plan", monthly_price=0, active=True
        )
        self.center = Center.objects.create(name="Smoke Center", slug="smoke-center")
        self.director = User.objects.create_user(
            email="dir@smoke.com", password="pw", role="director",
            center=self.center, ism="Dir", familya="Smoke",
        )
        self.teacher = User.objects.create_user(
            email="t@smoke.com", password="pw", role="teacher",
            center=self.center, ism="Teach", familya="Smoke",
        )
        self.student = User.objects.create_user(
            email="s@smoke.com", password="pw", role="student",
            center=self.center, ism="Stu", familya="Smoke",
        )
        self.group = Group.objects.create(
            center=self.center, nom="Smoke Group",
            oqituvchi=self.teacher, kurs_narxi=650_000,
            oqituvchi_foiz=40, oy_dars_soni=12,
        )
        today = timezone.localdate()
        self.cur_month = today.replace(day=1)
        prev_last = self.cur_month - timedelta(days=1)
        self.prev_month = prev_last.replace(day=1)
        nxt = (self.cur_month + timedelta(days=32)).replace(day=1)
        self.next_month = nxt

        self.enrollment = Enrollment.objects.create(
            center=self.center, group=self.group, student=self.student,
            kurs_narhi=650_000, oqituvchi_foiz=40, is_active=True,
            joined_at=self.prev_month, monthly_lessons=12,
        )
        self.fee_field = tuition_month_fee_field()
        self.client.force_login(self.director)

    def _url(self, name):
        return f"/{self.center.slug}" + reverse(
            f"education:{name}", args=[self.student.id]
        )

    def _month_str(self, d: date) -> str:
        return f"{d.year:04d}-{d.month:02d}"

    # ── 1. Reset: oy to'liq qarzga qaytadi ────────────────────────────────
    def test_reset_month_payments_returns_full_debt(self):
        tm = ensure_tuition_month(self.enrollment, self.cur_month)
        fee = int(getattr(tm, self.fee_field))
        self.assertGreater(fee, 0)

        create_payment_and_allocate(
            enrollment=self.enrollment,
            created_by=self.director,
            cash_amount=fee,
            card_amount_som=0,
            start_month=self.cur_month,
            paid_at=datetime.combine(timezone.localdate(), datetime.min.time()),
        )
        tm.refresh_from_db()
        self.assertEqual(_paid(tm), fee, "To'lov oyni yopishi kerak edi")

        resp = self.client.post(
            self._url("reset_student_month_payments"),
            {"month": self._month_str(self.cur_month)},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

        tm.refresh_from_db()
        self.assertEqual(_paid(tm), 0, "Reset dan keyin to'langan 0 bo'lishi kerak")
        self.assertEqual(
            int(getattr(tm, self.fee_field)), fee,
            "Fee haqiqiy kurs narxida qolishi kerak",
        )
        self.enrollment.refresh_from_db()
        self.assertEqual(
            int(self.enrollment.credit_balance or 0), 0,
            "Credit 0 bo'lishi kerak — avtomatik qayta yozilmasin",
        )
        # To'lov To'lovlar bo'limidan ham o'chgan
        self.assertFalse(
            Payment.objects.filter(
                enrollment=self.enrollment, is_deleted=False, summa__gt=0
            ).exists(),
            "Bekor qilingan to'lov o'chirilishi kerak",
        )

    # ── 2. Resurrection: _etm bekor qilingan to'lovni qayta bog'lamaydi ──
    def test_cancelled_payment_not_resurrected_by_etm(self):
        tm = ensure_tuition_month(self.enrollment, self.cur_month)
        fee = int(getattr(tm, self.fee_field))
        create_payment_and_allocate(
            enrollment=self.enrollment,
            created_by=self.director,
            cash_amount=fee,
            card_amount_som=0,
            start_month=self.cur_month,
            paid_at=datetime.combine(timezone.localdate(), datetime.min.time()),
        )
        self.client.post(
            self._url("reset_student_month_payments"),
            {"month": self._month_str(self.cur_month)},
        )

        # Sahifa qayta yuklanishini simulyatsiya qilamiz: _etm bir necha marta
        ensure_tuition_month(self.enrollment, self.cur_month)
        ensure_tuition_month(self.enrollment, self.cur_month)

        tm.refresh_from_db()
        self.assertEqual(
            _paid(tm), 0,
            "Bekor qilingan to'lov _etm tomonidan qayta tirilmasligi kerak",
        )

    # ── 3. user_edit himoyasi: _etm qo'lda kiritilgan fee ni saqlaydi ────
    def test_manual_debt_edit_survives_etm(self):
        ensure_tuition_month(self.enrollment, self.cur_month)
        resp = self.client.post(
            self._url("edit_student_month_debt"),
            {"month": self._month_str(self.cur_month), "new_debt": "300000"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

        # Sahifa qayta yuklanishi: _etm fee ni qayta hisoblashga urinadi
        tm = ensure_tuition_month(self.enrollment, self.cur_month)
        self.assertEqual(
            int(getattr(tm, self.fee_field)), 300_000,
            "Qo'lda o'rnatilgan qarz _etm dan keyin ham saqlanishi kerak",
        )

    # ── 4. Kelajak oy o'chirilganda oy o'tkazib yuborilmaydi ─────────────
    def test_future_month_delete_cancels_payment_and_month_comes_back(self):
        cur_tm = ensure_tuition_month(self.enrollment, self.cur_month)
        cur_fee = int(getattr(cur_tm, self.fee_field))

        # Joriy oyni yopamiz + kelajak oyga ortiqcha to'lov
        next_fee_probe = ensure_tuition_month(self.enrollment, self.next_month)
        next_fee = int(getattr(next_fee_probe, self.fee_field))
        create_payment_and_allocate(
            enrollment=self.enrollment,
            created_by=self.director,
            cash_amount=cur_fee + next_fee,
            card_amount_som=0,
            start_month=self.cur_month,
            paid_at=datetime.combine(timezone.localdate(), datetime.min.time()),
        )
        next_tm = TuitionMonth.objects.get(
            enrollment=self.enrollment, month=self.next_month
        )
        self.assertEqual(_paid(next_tm), next_fee, "Kelajak oy to'langan bo'lishi kerak")

        # Kelajak oyni o'chiramiz
        resp = self.client.post(
            self._url("delete_student_month"),
            {"month": self._month_str(self.next_month)},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

        # Pul credit ga EMAS — to'lov kamaytirilgan/bekor bo'lgan
        # va oy _etm orqali qayta tiklanadi (o'tkazib yuborilmaydi)
        restored = ensure_tuition_month(self.enrollment, self.next_month)
        self.assertFalse(
            restored.is_deleted,
            "Kelajak oy keyingi hisob-kitobda qayta tiklanishi kerak",
        )
        self.assertGreater(
            int(getattr(restored, self.fee_field)), 0,
            "Tiklangan oyda fee > 0 bo'lishi kerak",
        )
        restored.refresh_from_db()
        self.assertEqual(
            _paid(restored), 0,
            "O'chirilgandan keyin kelajak oy to'lanmagan bo'lishi kerak",
        )

    # ── 5a. O'tgan oy reset: qarz = davomat asosida ──────────────────────
    def test_reset_past_month_uses_attendance_based_fee(self):
        from education.models import Attendance
        from education.services.tuition import attendance_based_fee

        prev_tm = ensure_tuition_month(self.enrollment, self.prev_month)

        # O'tgan oyda 4 ta darsga kelgan
        for day in (3, 5, 10, 12):
            Attendance.objects.create(
                center=self.center, group=self.group,
                student=self.student, teacher=self.teacher,
                date=self.prev_month.replace(day=day),
                status="present", present=True,
            )

        # To'lov qilingan, keyin reset bosiladi
        create_payment_and_allocate(
            enrollment=self.enrollment,
            created_by=self.director,
            cash_amount=100_000,
            card_amount_som=0,
            start_month=self.prev_month,
            paid_at=datetime.combine(timezone.localdate(), datetime.min.time()),
        )
        resp = self.client.post(
            self._url("reset_student_month_payments"),
            {"month": self._month_str(self.prev_month)},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

        expected = attendance_based_fee(self.enrollment, self.prev_month)
        self.assertGreater(expected, 0, "4 ta davomat uchun qarz > 0 bo'lishi kerak")

        prev_tm.refresh_from_db()
        self.assertEqual(
            int(getattr(prev_tm, self.fee_field)), expected,
            "O'tgan oy qarzi davomat asosida bo'lishi kerak "
            "(nechta dars → shuncha qarz), jadval asosida emas",
        )
        self.assertEqual(_paid(prev_tm), 0)

        # _etm bu qiymatni qayta yozmasligi kerak (user_edit himoyasi)
        ensure_tuition_month(self.enrollment, self.prev_month)
        prev_tm.refresh_from_db()
        self.assertEqual(
            int(getattr(prev_tm, self.fee_field)), expected,
            "_etm o'tgan oy davomat-asosidagi qarzini qayta yozmasligi kerak",
        )

    # ── 5b. Joriy oy reset: qarz = to'liq oylik narx ─────────────────────
    def test_reset_current_month_uses_full_fee(self):
        tm = ensure_tuition_month(self.enrollment, self.cur_month)
        full_fee = int(getattr(tm, self.fee_field))
        self.assertGreater(full_fee, 0)

        create_payment_and_allocate(
            enrollment=self.enrollment,
            created_by=self.director,
            cash_amount=full_fee,
            card_amount_som=0,
            start_month=self.cur_month,
            paid_at=datetime.combine(timezone.localdate(), datetime.min.time()),
        )
        self.client.post(
            self._url("reset_student_month_payments"),
            {"month": self._month_str(self.cur_month)},
        )
        tm.refresh_from_db()
        self.assertEqual(
            int(getattr(tm, self.fee_field)), full_fee,
            "Joriy oy reset dan keyin to'liq oylik narx bo'lishi kerak",
        )
        self.assertEqual(_paid(tm), 0)

    # ── 6. O'tgan oy qarzi yangi oyda to'lansa — o'tgan oyga yoziladi ────
    def test_prev_month_debt_paid_now_shows_under_prev_month_filter(self):
        prev_tm = ensure_tuition_month(self.enrollment, self.prev_month)
        prev_fee = int(getattr(prev_tm, self.fee_field))
        self.assertGreater(prev_fee, 0)

        # Iyun qarzini iyulda to'laymiz — month_for_payment=iyun
        # (create_payment view'dagi kabi start_month=o'tgan oy)
        create_payment_and_allocate(
            enrollment=self.enrollment,
            created_by=self.director,
            cash_amount=prev_fee,
            card_amount_som=0,
            start_month=self.prev_month,
            paid_at=datetime.combine(timezone.localdate(), datetime.min.time()),
        )
        prev_tm.refresh_from_db()
        self.assertEqual(
            _paid(prev_tm), prev_fee,
            "To'lov O'TGAN oyga yozilishi kerak (month_for_payment)",
        )
        # Joriy oyga hech narsa yozilmagan
        cur_tm_qs = TuitionMonth.objects.filter(
            enrollment=self.enrollment, month=self.cur_month
        ).first()
        if cur_tm_qs:
            self.assertEqual(
                _paid(cur_tm_qs), 0,
                "Joriy oyga allocation tushmasligi kerak",
            )

        # To'lovlar bo'limi: o'tgan oy filtrida KO'RINADI
        tolovlar_url = f"/{self.center.slug}/talim/tolovlar/"
        resp = self.client.get(tolovlar_url, {"pay_month": str(self.prev_month.month)})
        self.assertEqual(resp.status_code, 200)
        pay_ids = [p.id for p in resp.context["filtered_payments"]]
        self.assertEqual(
            len(pay_ids), 1,
            "O'tgan oy filtrida iyulda to'langan iyun to'lovi ko'rinishi kerak",
        )

        # Joriy oy filtrida KO'RINMAYDI (bu to'lov iyul uchun emas)
        resp2 = self.client.get(tolovlar_url, {"pay_month": str(self.cur_month.month)})
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(
            len(resp2.context["filtered_payments"]), 0,
            "Joriy oy filtrida o'tgan oy uchun to'lov ko'rinmasligi kerak",
        )

    # ── 7. Aniq oy tanlansa — ortiqcha KEYINGI oyga o'tadi (carry-forward) ─
    def test_explicit_month_payment_excess_carries_to_next_month(self):
        """
        Founder talabi (2026-07): menejer aniq oy tanlab, o'sha oy qarzidan
        KO'P to'lasa — tanlangan oy qarzi TO'LIQ yopiladi, ORTIQCHA summa
        keyingi oy(lar) to'loviga hisoblanadi (oldingi oylarga tegilmaydi).
        Hisobot allocation asosida: har oy filtri o'z ulushini ko'rsatadi,
        yig'indi jami to'lovga teng (double-count yo'q).
        """
        prev_tm = ensure_tuition_month(self.enrollment, self.prev_month)
        prev_fee = int(getattr(prev_tm, self.fee_field))
        self.assertGreater(prev_fee, 0)
        cur_tm0 = ensure_tuition_month(self.enrollment, self.cur_month)
        self.assertGreaterEqual(int(getattr(cur_tm0, self.fee_field)), 100_000)

        # O'tgan oy qarzidan 100k KO'P to'laymiz, oyni aniq tanlab
        pay_total = prev_fee + 100_000
        url = f"/{self.center.slug}" + reverse("education:create_payment")
        resp = self.client.post(url, {
            "enrollment_id": self.enrollment.id,
            "cash_amount": str(pay_total),
            "card_amount": "0",
            "paid_date": timezone.localdate().isoformat(),
            "month_for_payment": self._month_str(self.prev_month),
            "next": f"/{self.center.slug}/talim/tolovlar/",
        })
        self.assertEqual(resp.status_code, 302)

        # O'tgan oy faqat QARZICHA yopiladi, ortig'i JORIY oyga o'tadi
        prev_tm.refresh_from_db()
        self.assertEqual(
            _paid(prev_tm), prev_fee,
            "Tanlangan oyga faqat o'z qarzicha yozilishi kerak",
        )
        cur_tm = TuitionMonth.objects.filter(
            enrollment=self.enrollment, month=self.cur_month
        ).first()
        self.assertIsNotNone(cur_tm)
        self.assertEqual(
            _paid(cur_tm), 100_000,
            "Ortiqcha 100k keyingi (joriy) oyga o'tishi kerak",
        )

        # Hisobot: har oy filtri O'Z ulushini ko'rsatadi
        tolovlar_url = f"/{self.center.slug}/talim/tolovlar/"
        r_prev = self.client.get(tolovlar_url, {"pay_month": str(self.prev_month.month)})
        r_cur = self.client.get(tolovlar_url, {"pay_month": str(self.cur_month.month)})
        self.assertEqual(int(r_prev.context["filtered_income"]), prev_fee)
        self.assertEqual(int(r_cur.context["filtered_income"]), 100_000)
        # Oylar yig'indisi = to'liq to'lov (double counting yo'q)
        self.assertEqual(
            int(r_prev.context["filtered_income"]) + int(r_cur.context["filtered_income"]),
            pay_total,
        )

    # ── 8. Bo'lingan to'lov har oy filtrida faqat O'Z QISMINI ko'rsatadi ─
    def test_split_payment_counted_once_per_month_filter(self):
        """
        Eski (strict fix'dan oldingi) bo'lingan to'lov: 600k = may 400k + iyun
        200k. May filtrida 400k, iyun filtrida 200k chiqishi kerak — TO'LIQ
        600k emas. Aks holda oylar yig'indisi umumiy daromaddan oshib ketadi.
        """
        prev_tm = ensure_tuition_month(self.enrollment, self.prev_month)
        cur_tm = ensure_tuition_month(self.enrollment, self.cur_month)

        pay = Payment.objects.create(
            center=self.center, enrollment=self.enrollment,
            student=self.student, group=self.group,
            summa=600_000, cash_amount=600_000,
            paid_date=timezone.localdate(),
        )
        PaymentAllocation.objects.create(
            center=self.center, payment=pay,
            tuition_month=prev_tm, amount=400_000,
        )
        PaymentAllocation.objects.create(
            center=self.center, payment=pay,
            tuition_month=cur_tm, amount=200_000,
        )

        tolovlar_url = f"/{self.center.slug}/talim/tolovlar/"

        r_prev = self.client.get(tolovlar_url, {"pay_month": str(self.prev_month.month)})
        self.assertEqual(
            int(r_prev.context["filtered_income"]), 400_000,
            "O'tgan oy filtrida faqat o'sha oyga yozilgan 400k chiqishi kerak",
        )
        row_prev = r_prev.context["page_rows"][0]
        self.assertEqual(
            int(row_prev["total_sum"]), 400_000,
            "Jadval qatorida ham faqat o'sha oy qismi ko'rinishi kerak",
        )

        r_cur = self.client.get(tolovlar_url, {"pay_month": str(self.cur_month.month)})
        self.assertEqual(
            int(r_cur.context["filtered_income"]), 200_000,
            "Joriy oy filtrida faqat 200k chiqishi kerak",
        )

        # Oylar yig'indisi = to'lovning to'liq summasi (double counting yo'q)
        self.assertEqual(
            int(r_prev.context["filtered_income"]) + int(r_cur.context["filtered_income"]),
            600_000,
        )

    # ── 9. Oylar yig'indisi = umumiy daromad (conservation) ─────────────
    def test_month_filters_sum_equals_total_income(self):
        """
        Har xil holatdagi to'lovlar: bog'langan, bo'lingan, bog'lanishi
        bekor qilingan. Oy filtrlari yig'indisi umumiy daromadga TENG
        bo'lishi shart — hech bir so'm ikki marta yoki nol marta sanalmasin.
        """
        prev_tm = ensure_tuition_month(self.enrollment, self.prev_month)
        cur_tm = ensure_tuition_month(self.enrollment, self.cur_month)
        today = timezone.localdate()

        # A: o'tgan oyga to'liq bog'langan (joriy oyda to'langan)
        pay_a = Payment.objects.create(
            center=self.center, enrollment=self.enrollment,
            student=self.student, group=self.group,
            summa=300_000, cash_amount=300_000, paid_date=today,
        )
        PaymentAllocation.objects.create(
            center=self.center, payment=pay_a,
            tuition_month=prev_tm, amount=300_000,
        )
        # B: bo'lingan (o'tgan oy 100k + joriy oy 150k)
        pay_b = Payment.objects.create(
            center=self.center, enrollment=self.enrollment,
            student=self.student, group=self.group,
            summa=250_000, cash_amount=250_000, paid_date=today,
        )
        PaymentAllocation.objects.create(
            center=self.center, payment=pay_b,
            tuition_month=prev_tm, amount=100_000,
        )
        PaymentAllocation.objects.create(
            center=self.center, payment=pay_b,
            tuition_month=cur_tm, amount=150_000,
        )
        # C: allocation'i BEKOR QILINGAN (reset) — foydalanuvchi ko'rgan
        # regressiya: bu to'lov hech bir oyda ko'rinmay yo'qolib qolardi.
        pay_c = Payment.objects.create(
            center=self.center, enrollment=self.enrollment,
            student=self.student, group=self.group,
            summa=200_000, cash_amount=200_000, paid_date=today,
        )
        _dead = PaymentAllocation.objects.create(
            center=self.center, payment=pay_c,
            tuition_month=cur_tm, amount=200_000,
        )
        _dead.is_deleted = True
        _dead.save(update_fields=["is_deleted"])

        # D: ESKI BUZILGAN yozuv — ikki marta taqsimlangan (alloc jami 400k >
        # summa 200k). Foydalanuvchining "oylar yig'indisi umumiydan katta"
        # muammosining sababi. Eng eski oy ulushi olinadi, ortiqcha kesiladi.
        pay_d = Payment.objects.create(
            center=self.center, enrollment=self.enrollment,
            student=self.student, group=self.group,
            summa=200_000, cash_amount=200_000, paid_date=today,
        )
        PaymentAllocation.objects.create(
            center=self.center, payment=pay_d,
            tuition_month=prev_tm, amount=200_000,
        )
        PaymentAllocation.objects.create(
            center=self.center, payment=pay_d,
            tuition_month=cur_tm, amount=200_000,
        )

        total = 300_000 + 250_000 + 200_000 + 200_000

        tolovlar_url = f"/{self.center.slug}/talim/tolovlar/"
        r_prev = self.client.get(tolovlar_url, {"pay_month": str(self.prev_month.month)})
        r_cur = self.client.get(tolovlar_url, {"pay_month": str(self.cur_month.month)})

        prev_income = int(r_prev.context["filtered_income"])
        cur_income = int(r_cur.context["filtered_income"])

        # O'tgan oy: A 300k + B ning 100k + D ning 200k (kesilgan) = 600k
        self.assertEqual(prev_income, 600_000)
        # Joriy oy: B ning 150k + C qoldiq 200k = 350k.
        # D ning joriy oydagi "sharpa" 200k allocationi SANALMAYDI
        # (summa allaqachon tugagan) — aks holda yig'indi oshib ketadi.
        self.assertEqual(
            cur_income, 350_000,
            "Buzilgan (ikki marta taqsimlangan) to'lovning ortiqcha "
            "allocationi sanalmasligi kerak",
        )
        # Conservation: yig'indi = umumiy
        self.assertEqual(prev_income + cur_income, total)

        # Diagramma ham xuddi shu raqamlarni ko'rsatadi (filtr = ustun).
        # Oy filtri tanlanganda diagramma yanvar–dekabr oynasida bo'ladi:
        # ustun indeksi = oy - 1
        chart_data = r_cur.context["chart_data"]
        self.assertEqual(
            chart_data[self.prev_month.month - 1], prev_income,
            "O'tgan oy ustuni = o'tgan oy filtri",
        )
        self.assertEqual(
            chart_data[self.cur_month.month - 1], cur_income,
            "Joriy oy ustuni = joriy oy filtri",
        )

    # ── 5. Reset yetim to'lovlarni ham o'chiradi ─────────────────────────
    def test_reset_deletes_orphan_payments_of_that_month(self):
        tm = ensure_tuition_month(self.enrollment, self.cur_month)
        # Yetim to'lov: shu oy sanasida, hech qanday allocation siz
        orphan = Payment.objects.create(
            center=self.center, enrollment=self.enrollment,
            student=self.student, group=self.group,
            summa=200_000, cash_amount=200_000,
            paid_date=timezone.localdate(),
        )
        resp = self.client.post(
            self._url("reset_student_month_payments"),
            {"month": self._month_str(self.cur_month)},
        )
        self.assertEqual(resp.status_code, 200)
        orphan.refresh_from_db()
        self.assertTrue(
            orphan.is_deleted,
            "Yetim to'lov reset da o'chirilishi kerak — aks holda "
            "_auto_link uni qayta bog'lab tiriltiraveradi",
        )
