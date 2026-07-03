"""
force_month_debtors -- Markazdagi BARCHA faol o'quvchilarni tanlangan oy uchun
QIZIL (qarzdor) qiladi.

Farqi (mark_month_debtors dan):
    - mark_month_debtors: fee = paid + narx  => qarz bor, LEKIN o'quvchi
      shu oyga oldin to'lagan bo'lsa (yoki oldingi oy puli shu oyga
      biriktirilgan bo'lsa) paid > 0 bo'lib qoladi => SARIQ/YASHIL yonadi.
    - force_month_debtors: shu oyga biriktirilgan to'lov ulushlarini (live
      allocation) UZADI => paid = 0, va fee = kurs narxi => hamma QIZIL.

MUHIM:
    - To'lov (Payment) yozuvlari O'CHMAYDI. Faqat shu oyga BOG'LANISHI uziladi
      (PaymentAllocation.is_deleted=True). Pul yo'qolmaydi — bog'lanmagan
      (credit) bo'lib qoladi va boshqa oyga qayta biriktirilishi mumkin.
    - Bepul (narx=0) o'quvchi qarzdor bo'lolmaydi: fee=0 => YASHIL qoladi
      (u hech narsa qarz emas). Bunday o'quvchilar o'tkazib yuboriladi.
    - Davomatga bog'liq EMAS — markazdagi barcha faol enrollment olinadi.

Ishlatish (Render Shell):
    # 1) Avval TEKSHIRUV (hech narsa o'zgarmaydi):
    python manage.py force_month_debtors --center proskill --month 2026-07

    # 2) Ro'yxat to'g'ri bo'lsa, HAQIQATAN yozish:
    python manage.py force_month_debtors --center proskill --month 2026-07 --confirm
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q, Sum

from accounts.models import Center
from education.models import Enrollment, TuitionMonth, PaymentAllocation
from education.services.tuition import tuition_month_fee_field


class Command(BaseCommand):
    help = "Markazdagi barcha faol o'quvchini oy uchun QIZIL (qarzdor) qiladi (paid=0)"

    def add_arguments(self, parser):
        parser.add_argument("--center", required=True,
                            help="Markaz slug (masalan: proskill)")
        parser.add_argument("--month", required=True,
                            help="Oy YYYY-MM formatida (masalan: 2026-07)")
        parser.add_argument("--confirm", action="store_true",
                            help="Bermasangiz faqat ko'rsatadi (dry-run). Bersangiz yozadi.")

    def handle(self, *args, **opts):
        slug = opts["center"].strip()
        confirm = opts["confirm"]

        try:
            y, m = opts["month"].split("-")
            month = date(int(y), int(m), 1)
        except Exception:
            raise CommandError("Oy formati noto'g'ri. Namuna: --month 2026-07")

        fee_field = tuition_month_fee_field()

        center = Center.objects.filter(slug=slug).first()
        if not center:
            self.stdout.write(self.style.ERROR(f"❌ '{slug}' slug topilmadi. Mavjud markazlar:"))
            for c in Center.objects.all():
                self.stdout.write(f"   - {c.slug} | {c.name}")
            raise CommandError("Markaz topilmadi")

        _cq = (
            Q(center=center)
            | Q(center__isnull=True, group__center=center)
            | Q(center__isnull=True, student__center=center)
        )
        enrs = (
            Enrollment.objects
            .filter(is_active=True,
                    student__is_archived=False,
                    group__is_archived=False,
                    group__is_deleted=False)
            .filter(_cq)
            .select_related("student", "group")
            .order_by("group__nom", "student__familya")
        )

        self.stdout.write(f"Markaz : {center.name} ({center.slug})")
        self.stdout.write(f"Oy     : {month}")
        self.stdout.write(f"Faol o'quvchilar (enrollment): {enrs.count()}")
        self.stdout.write("Rejim  : " + ("✍️  YOZISH" if confirm
                                         else "👀 DRY-RUN (hech narsa saqlanmaydi)"))
        self.stdout.write("-" * 95)

        made_red = skipped = 0
        total_debt = 0
        unlinked_sum = 0

        with transaction.atomic():
            for e in enrs:
                price = int(getattr(e, "effective_student_payable_amount", 0) or 0)
                name = e.student.get_full_name()
                grp = getattr(e.group, "nom", "?")

                # Bepul (narx=0) => qarzdor bo'lolmaydi, o'tkazib yuboramiz.
                if price <= 0:
                    skipped += 1
                    self.stdout.write(f"  ⏭  SKIP (0 narx): {name} | {grp}")
                    continue

                # Shu oyga biriktirilgan LIVE ulushlar (allocation) — uziladi.
                allocs = PaymentAllocation.objects.filter(
                    is_deleted=False,
                    tuition_month__enrollment=e,
                    tuition_month__month=month,
                )
                paid_now = int(allocs.aggregate(s=Sum("amount"))["s"] or 0)

                # TuitionMonth — yaratamiz/tiklaymiz, fee=narx.
                tm = TuitionMonth.all_objects.filter(enrollment=e, month=month).first()
                if tm is None:
                    tm = TuitionMonth(enrollment=e, month=month, center=center)
                else:
                    tm.is_deleted = False

                setattr(tm, fee_field, price)
                tm.deleted_reason = "user_edit"

                if confirm:
                    tm.save()
                    if paid_now > 0:
                        # Payment yozuvi o'chmaydi — faqat shu oyga ulanishi uziladi.
                        allocs.update(is_deleted=True)

                made_red += 1
                total_debt += price
                unlinked_sum += paid_now
                flag = f"(paid={paid_now:,} → uzildi)" if paid_now else "(paid=0)"
                self.stdout.write(
                    f"  🔴 QIZIL : {name:26} | {grp:22} | qarz={price:>10,} so'm {flag}"
                )

            if not confirm:
                transaction.set_rollback(True)

        self.stdout.write("-" * 95)
        self.stdout.write(
            f"Qizil (qarzdor): {made_red} ta | O'tkazildi (0 narx): {skipped} ta"
        )
        self.stdout.write(
            f"Jami qarz: {total_debt:,} so'm | Uzilgan (bog'lanmagan) to'lov: {unlinked_sum:,} so'm"
        )
        if confirm:
            self.stdout.write(self.style.SUCCESS("✅ SAQLANDI! Endi hamma (bepullardan tashqari) QIZIL."))
        else:
            self.stdout.write(self.style.WARNING(
                "👀 DRY-RUN tugadi — to'g'ri bo'lsa oxiriga --confirm qo'shib qayta yuriting."
            ))
