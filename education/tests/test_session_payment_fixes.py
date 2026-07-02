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

    # ── 7. Aniq oy tanlansa — ortiqcha ham SHU OYGA (keyingiga oshmaydi) ─
    def test_explicit_month_payment_stays_in_that_month_even_with_excess(self):
        prev_tm = ensure_tuition_month(self.enrollment, self.prev_month)
        prev_fee = int(getattr(prev_tm, self.fee_field))
        self.assertGreater(prev_fee, 0)

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

        # Butun summa O'TGAN OYDA — joriy oyga hech narsa oshmagan
        prev_tm.refresh_from_db()
        self.assertEqual(
            _paid(prev_tm), pay_total,
            "Tanlangan oyga butun summa yozilishi kerak (ortiqcha bilan birga)",
        )
        cur_tm = TuitionMonth.objects.filter(
            enrollment=self.enrollment, month=self.cur_month
        ).first()
        if cur_tm:
            self.assertEqual(
                _paid(cur_tm), 0,
                "Joriy oyga ortiqcha summa OSHMASLIGI kerak",
            )

        # To'lovlar filtri: faqat o'tgan oyda ko'rinadi
        tolovlar_url = f"/{self.center.slug}/talim/tolovlar/"
        r_prev = self.client.get(tolovlar_url, {"pay_month": str(self.prev_month.month)})
        self.assertEqual(len(r_prev.context["filtered_payments"]), 1)
        r_cur = self.client.get(tolovlar_url, {"pay_month": str(self.cur_month.month)})
        self.assertEqual(
            len(r_cur.context["filtered_payments"]), 0,
            "Joriy oy filtrida bu to'lov KO'RINMASLIGI kerak",
        )

        # Diagramma: pul O'TGAN OY ustunida (oxirgi 12 oyning 11-chisi)
        r_chart = self.client.get(tolovlar_url)
        chart_data = r_chart.context["chart_data"]
        self.assertEqual(len(chart_data), 12)
        self.assertEqual(
            chart_data[10], pay_total,
            "Diagrammada pul to'langan oyda emas, QAYSI OY UCHUN "
            "ekanida ko'rinishi kerak (o'tgan oy ustuni)",
        )
        self.assertEqual(
            chart_data[11], 0,
            "Joriy oy ustunida bu pul bo'lmasligi kerak",
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
