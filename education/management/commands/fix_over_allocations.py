"""
Ikki-marta-hisoblash bugi buzgan eski to'lovlarni topadi va tuzatadi.

Bug: create_payment_and_allocate + _auto_link to'lovni ikki marta
taqsimlab, summa 650k bo'lsa allocation'lar jami 1.3M bo'lib qolardi
(ikkinchi qismi keyingi oyga "sharpa to'lov" sifatida yozilardi).
Bug 2026-07-02 da tuzatilgan; bu buyruq undan OLDIN buzilgan
yozuvlarni tozalaydi.

Ishlatish:
    python manage.py fix_over_allocations           # faqat ko'rsatadi (dry-run)
    python manage.py fix_over_allocations --fix     # haqiqatan tuzatadi

Tuzatish mantiqi: allocation'lar jami > payment.summa bo'lsa,
ortiqcha qism ENG KEYINGI oylardan boshlab o'chiriladi (sharpa
to'lov doim keyingi oyga yozilgan edi). O'quvchining haqiqiy
to'lovi (eng eski oydagi) saqlanadi.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from education.models import Payment, PaymentAllocation


class Command(BaseCommand):
    help = "Ikki marta taqsimlangan (over-allocated) to'lovlarni topadi va tuzatadi"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Haqiqatan tuzatish (bermasangiz faqat ro'yxat chiqadi)",
        )

    def handle(self, *args, **options):
        do_fix = options["fix"]

        # Jami aktiv allocation'i summasidan katta bo'lgan paymentlar
        damaged = []
        rows = (
            PaymentAllocation.objects.filter(payment__is_deleted=False)
            .values("payment_id")
            .annotate(total=Sum("amount"))
        )
        totals = {r["payment_id"]: int(r["total"] or 0) for r in rows}
        pays = Payment.objects.filter(id__in=list(totals.keys())).select_related("student")
        for p in pays:
            allocated = totals.get(p.id, 0)
            summa = int(p.summa or 0)
            if allocated > summa:
                damaged.append((p, allocated, summa))

        if not damaged:
            self.stdout.write(self.style.SUCCESS("✅ Buzilgan to'lov topilmadi — hammasi toza."))
            return

        self.stdout.write(f"🔎 {len(damaged)} ta buzilgan to'lov topildi:\n")
        fixed = 0
        for p, allocated, summa in damaged:
            student = getattr(p, "student", None)
            name = student.get_full_name() if student else "?"
            excess = allocated - summa
            self.stdout.write(
                f"  Payment #{p.id} | {name} | summa={summa:,} | "
                f"taqsimlangan={allocated:,} | ortiqcha={excess:,}"
            )

            if not do_fix:
                continue

            with transaction.atomic():
                # Eng keyingi oylardan boshlab ortiqchani o'chiramiz
                allocs = list(
                    PaymentAllocation.objects.filter(payment=p)
                    .select_related("tuition_month")
                    .order_by("-tuition_month__month", "-id")
                )
                to_free = excess
                for alloc in allocs:
                    if to_free <= 0:
                        break
                    amt = int(alloc.amount or 0)
                    if amt <= to_free:
                        self.stdout.write(
                            f"     ✂ {alloc.tuition_month.month} dan {amt:,} o'chirildi"
                        )
                        to_free -= amt
                        alloc.is_deleted = True
                        alloc.save(update_fields=["is_deleted"])
                    else:
                        self.stdout.write(
                            f"     ✂ {alloc.tuition_month.month} dan {to_free:,} kamaytirildi"
                        )
                        alloc.amount = amt - to_free
                        alloc.save(update_fields=["amount"])
                        to_free = 0
                fixed += 1

        if do_fix:
            self.stdout.write(self.style.SUCCESS(f"\n✅ {fixed} ta to'lov tuzatildi."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️  Bu faqat ro'yxat (dry-run). Tuzatish uchun: "
                    "python manage.py fix_over_allocations --fix"
                )
            )
