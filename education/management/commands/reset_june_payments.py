"""
reset_june_payments -- Iyun 2026 to'lovlarini tozalash va TuitionMonth
fee larini guruh narxiga tenglashtirish.

Foydalanish:
  python manage.py reset_june_payments --preview          # faqat hisobot
  python manage.py reset_june_payments --confirm          # bajarish
  python manage.py reset_june_payments --center proskill --confirm
"""
from __future__ import annotations

import sys
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from education.models import (
    Enrollment,
    Payment,
    PaymentAllocation,
    TuitionMonth,
)
from education.services.tuition import effective_student_payable_amount


JUN_START = date(2026, 6, 1)
JUN_END   = date(2026, 6, 30)
JUN_MONTH = date(2026, 6, 1)


class Command(BaseCommand):
    help = "Iyun 2026 to'lovlarini tozalash va TuitionMonth fee ni to'g'irlash"

    def add_arguments(self, parser):
        parser.add_argument("--center", default=None, help="Center slug (bo'sh = hammasi)")
        parser.add_argument("--confirm", action="store_true", help="Bajarish (bo'lmasa faqat preview)")

    def handle(self, *args, **options):
        center_slug = options["center"]
        confirm     = options["confirm"]

        # 1) Iyun to'lovlari
        pay_qs = Payment.objects.filter(
            paid_date__gte=JUN_START,
            paid_date__lte=JUN_END,
        )
        if center_slug:
            pay_qs = pay_qs.filter(center__slug=center_slug)

        pay_ids  = list(pay_qs.values_list("id", flat=True))
        pay_sum  = pay_qs.aggregate(s=Sum("summa"))["s"] or 0
        alloc_qs = PaymentAllocation.objects.filter(payment_id__in=pay_ids)
        alloc_cnt = alloc_qs.count()

        # 2) Iyun TuitionMonth lar
        tm_qs = TuitionMonth.objects.filter(month=JUN_MONTH)
        if center_slug:
            tm_qs = tm_qs.filter(center__slug=center_slug)

        self.stdout.write("=" * 60)
        self.stdout.write(f"Iyun 2026 to'lovlari         : {len(pay_ids)} ta")
        self.stdout.write(f"Jami summa                   : {pay_sum:,} so'm")
        self.stdout.write(f"Tegishli allokatsiyalar      : {alloc_cnt} ta")
        self.stdout.write(f"Iyun TuitionMonth yozuvlari  : {tm_qs.count()} ta")
        self.stdout.write("=" * 60)

        if not pay_ids:
            self.stdout.write(self.style.WARNING("Iyun to'lovi topilmadi. Chiqilmoqda."))
            return

        if not confirm:
            self.stdout.write(self.style.WARNING(
                "\n--confirm bayrog'i berilmadi. Hech narsa o'chirilmadi.\n"
                "Bajarish uchun: python manage.py reset_june_payments --confirm"
            ))
            return

        with transaction.atomic():
            # --- Qadam 1: allokatsiyalarni soft-delete qilish ---
            deleted_alloc = PaymentAllocation.all_objects.filter(
                payment_id__in=pay_ids, is_deleted=False
            ).update(is_deleted=True)

            # --- Qadam 2: to'lovlarni soft-delete qilish ---
            deleted_pay = Payment.all_objects.filter(
                id__in=pay_ids, is_deleted=False
            ).update(is_deleted=True)

            # --- Qadam 3: Iyun TuitionMonth fee ni guruh narxiga tenglash ---
            fee_fixed = 0
            for tm in tm_qs.select_related("enrollment__group", "enrollment"):
                enr = tm.enrollment
                correct_fee = effective_student_payable_amount(enr)
                if correct_fee <= 0:
                    # Fallback: guruh narxi
                    try:
                        correct_fee = int(enr.group.kurs_narxi or 0)
                    except Exception:
                        correct_fee = 0
                if tm.fee_amount != correct_fee:
                    tm.fee_amount = correct_fee
                    tm.save(update_fields=["fee_amount"])
                    fee_fixed += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nMuvaffaqiyatli:\n"
            f"  To'lovlar o'chirildi     : {deleted_pay} ta\n"
            f"  Allokatsiyalar o'chirildi: {deleted_alloc} ta\n"
            f"  TuitionMonth fee to'g'irlandi: {fee_fixed} ta\n"
            f"\nEndi barcha o'quvchilar iyun uchun qarzdor bo'lib ko'rinadi."
        ))
