"""
Bir markazdagi BARCHA faol (o'qiyotgan) o'quvchilarni tanlangan oy uchun
qarzdorlar ro'yxatiga tushiradi — har birida qarz = kurs narxi bo'ladi.

Ishlatish (Render Shell):
    # 1) Avval TEKSHIRUV (hech narsa o'zgarmaydi, faqat ro'yxat chiqadi):
    python manage.py mark_month_debtors --center proskill --month 2026-07

    # 2) Ro'yxat to'g'ri bo'lsa, HAQIQATAN yozish:
    python manage.py mark_month_debtors --center proskill --month 2026-07 --confirm

Mantiq:
    - Markazdagi faol enrollmentlarni topadi (arxivlanmagan guruh/o'quvchi)
    - Har biriga oy uchun TuitionMonth yaratadi/yangilaydi
    - fee = joriy to'langan + kurs narxi  => qarz = kurs narxi (qarzdor kafolatlanadi)
    - deleted_reason="user_edit" bilan himoyalaydi (tizim avtomatik o'chirmaydi)
    - Kurs narxi 0 bo'lgan (bepul) o'quvchilar o'tkazib yuboriladi
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from accounts.models import Center
from education.models import Enrollment, TuitionMonth
from education.services.tuition import tuition_month_fee_field, get_month_paid


class Command(BaseCommand):
    help = "Markazdagi barcha faol o'quvchilarni tanlangan oy uchun qarzdor qiladi"

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

        # Oyni tekshiramiz
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
        self.stdout.write("-" * 90)

        created = updated = skipped = 0
        total_debt = 0

        with transaction.atomic():
            for e in enrs:
                fee = int(getattr(e, "effective_student_payable_amount", 0) or 0)
                name = e.student.get_full_name()
                grp = getattr(e.group, "nom", "?")

                if fee <= 0:
                    skipped += 1
                    self.stdout.write(f"  ⏭  SKIP (0 narx): {name} | {grp}")
                    continue

                tm = TuitionMonth.all_objects.filter(enrollment=e, month=month).first()
                paid = get_month_paid(tm) if tm else 0
                new_fee = paid + fee   # qarz = fee kafolatlanadi

                if tm is None:
                    tm = TuitionMonth(enrollment=e, month=month, center=center)
                    action = "🆕 YARAT"
                    created += 1
                else:
                    tm.is_deleted = False
                    action = "♻️  YANGI"
                    updated += 1

                setattr(tm, fee_field, new_fee)
                tm.deleted_reason = "user_edit"

                if confirm:
                    tm.save()

                debt = new_fee - paid
                total_debt += debt
                self.stdout.write(
                    f"  {action}: {name:26} | {grp:22} | "
                    f"qarz={debt:>10,} so'm (paid={paid:,})"
                )

            if not confirm:
                transaction.set_rollback(True)

        self.stdout.write("-" * 90)
        self.stdout.write(
            f"Yaratildi: {created} | Yangilandi: {updated} | O'tkazildi (0 narx): {skipped}"
        )
        self.stdout.write(
            f"Jami qarzdorlar: {created + updated} ta | Jami qarz: {total_debt:,} so'm"
        )
        if confirm:
            self.stdout.write(self.style.SUCCESS("✅ SAQLANDI!"))
        else:
            self.stdout.write(self.style.WARNING(
                "👀 DRY-RUN tugadi — to'g'ri bo'lsa oxiriga --confirm qo'shib qayta yuriting."
            ))
