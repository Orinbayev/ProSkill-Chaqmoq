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
