"""
Markazdagi o'quvchilarni DAVOMAT asosida oy uchun qarzdor qiladi.

QOIDA (foydalanuvchi talabi):
  - O'quvchi shu guruhda shu OYDA davomat qilingan bo'lsa
        => qarz = o'quvchiga belgilangan narx (effective_student_payable_amount)
        => iyul to'lovlari tozalanadi (paid=0) => guruhda QIZIL (qarzdor) ko'rinadi
  - Davomat qilinmagan bo'lsa (yoki guruhdan chiqib ketib shu oyda davomati yo'q)
        => qarz YO'Q (TuitionMonth o'chiriladi) => qarzdorlarda chiqmaydi
  - Narxi 0 bo'lgan (bepul) o'quvchi davomat qilgan bo'lsa
        => fee=0 => guruhda YASHIL (to'landi) ko'rinadi

billable_attendance_count() chiqarilgan o'quvchini (last_lesson_date) hisobga oladi:
shu oyda davomati bo'lsa ham keyingi oyda 0 qaytaradi => avtomatik to'g'ri.

Ishlatish (Render Shell):
    python manage.py rebuild_month_debtors --center proskill --month 2026-07
    python manage.py rebuild_month_debtors --center proskill --month 2026-07 --confirm
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q, Sum

from accounts.models import Center
from education.models import Enrollment, TuitionMonth, PaymentAllocation
from education.services.tuition import (
    tuition_month_fee_field, billable_attendance_count, month_first_day,
)
from django.utils import timezone


class Command(BaseCommand):
    help = "Davomat asosida oy uchun qarzdorlarni qayta quradi"

    def add_arguments(self, parser):
        parser.add_argument("--center", required=True, help="Markaz slug (proskill)")
        parser.add_argument("--month", required=True, help="Oy YYYY-MM (2026-07)")
        parser.add_argument("--confirm", action="store_true",
                            help="Bermasangiz faqat ko'rsatadi (dry-run)")

    def handle(self, *args, **opts):
        slug = opts["center"].strip()
        confirm = opts["confirm"]
        try:
            y, m = opts["month"].split("-")
            month = date(int(y), int(m), 1)
        except Exception:
            raise CommandError("Oy formati: --month 2026-07")

        fee_field = tuition_month_fee_field()

        center = Center.objects.filter(slug=slug).first()
        if not center:
            self.stdout.write(self.style.ERROR(f"❌ '{slug}' topilmadi. Markazlar:"))
            for c in Center.objects.all():
                self.stdout.write(f"   - {c.slug} | {c.name}")
            raise CommandError("Markaz yo'q")

        _cq = (Q(center=center)
               | Q(center__isnull=True, group__center=center)
               | Q(center__isnull=True, student__center=center))

        # Aktiv + chiqarilgan (lekin shu oyda davomati bo'lishi mumkin) — hammasi.
        # Arxivlangan/o'chirilgan guruh/o'quvchi olinmaydi.
        enrs = (Enrollment.all_objects
                .filter(student__is_archived=False,
                        group__is_archived=False,
                        group__is_deleted=False)
                .filter(_cq)
                .select_related("student", "group")
                .order_by("group__nom", "student__familya"))

        self.stdout.write(f"Markaz : {center.name} ({center.slug})")
        self.stdout.write(f"Oy     : {month}")
        self.stdout.write(f"Tekshiriladigan enrollmentlar: {enrs.count()}")
        self.stdout.write("Rejim  : " + ("✍️  YOZISH" if confirm else "👀 DRY-RUN"))
        self.stdout.write("-" * 95)

        debtor = paid_free = cleared = 0
        total_debt = 0
        freed_pay = 0

        with transaction.atomic():
            for e in enrs:
                att = billable_attendance_count(e, month)
                price = int(getattr(e, "effective_student_payable_amount", 0) or 0)
                name = e.student.get_full_name()
                grp = getattr(e.group, "nom", "?")

                tm = TuitionMonth.all_objects.filter(enrollment=e, month=month).first()

                # ── DAVOMAT YO'Q => qarz bo'lmasin ──
                if att <= 0:
                    if tm and not tm.is_deleted:
                        cleared += 1
                        if confirm:
                            tm.is_deleted = True
                            tm.deleted_reason = "manual_cleared"
                            tm.deleted_at = timezone.now()
                            tm.save(update_fields=["is_deleted", "deleted_reason", "deleted_at"])
                    continue

                # ── DAVOMAT BOR => TuitionMonth kerak ──
                if tm is None:
                    tm = TuitionMonth(enrollment=e, month=month, center=center)
                else:
                    tm.is_deleted = False

                # narx=0 (bepul) => YASHIL (to'landi)
                if price <= 0:
                    setattr(tm, fee_field, 0)
                    tm.deleted_reason = "user_edit"
                    if confirm:
                        tm.save()
                    paid_free += 1
                    self.stdout.write(f"  🟢 BEPUL : {name:26} | {grp:22} | fee=0")
                    continue

                # narx>0 => QIZIL (qarzdor): fee=narx, iyul to'lovlarini tozalash (paid=0)
                allocs = PaymentAllocation.objects.filter(
                    tuition_month__enrollment=e, tuition_month__month=month,
                    is_deleted=False,
                )
                paid_now = int(allocs.aggregate(s=Sum("amount"))["s"] or 0)

                setattr(tm, fee_field, price)
                tm.deleted_reason = "user_edit"
                if confirm:
                    tm.save()
                    if paid_now > 0:
                        # to'lov bog'lanishini bekor qilamiz (Payment yozuvi o'chmaydi,
                        # faqat shu oyga ulanishi uziladi => paid=0 => QIZIL)
                        allocs.update(is_deleted=True)

                freed_pay += paid_now
                debtor += 1
                total_debt += price
                flag = f"(paid→0, {paid_now:,} uzildi)" if paid_now else ""
                self.stdout.write(
                    f"  🔴 QARZ  : {name:26} | {grp:22} | qarz={price:>10,} so'm {flag}"
                )

            if not confirm:
                transaction.set_rollback(True)

        self.stdout.write("-" * 95)
        self.stdout.write(
            f"🔴 Qarzdor: {debtor} | 🟢 Bepul(to'landi): {paid_free} | "
            f"🧹 Tozalandi(davomatsiz): {cleared}"
        )
        self.stdout.write(f"Jami qarz: {total_debt:,} so'm | Uzilgan to'lov bog'lanishi: {freed_pay:,} so'm")
        if confirm:
            self.stdout.write(self.style.SUCCESS("✅ SAQLANDI!"))
        else:
            self.stdout.write(self.style.WARNING(
                "👀 DRY-RUN — to'g'ri bo'lsa oxiriga --confirm qo'shib qayta yuriting."))
