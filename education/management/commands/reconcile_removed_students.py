"""
reconcile_removed_students -- Guruhdan CHIQARILGAN o'quvchilarning qarzini
HAQIQIY DAVOMATGA qarab to'g'ri oy(lar)ga joylashtiradi.

Muammo:
    O'quvchi guruhda o'qib (davomat qilingan) oy oxirida chiqarilgan. Uning
    qarzi noto'g'ri oyga (mas. IYUL) yozilib qolgan yoki to'g'ri oy (IYUN) uchun
    TuitionMonth umuman yaratilmagan → to'lov qilishda IYUN oyi ko'rinmaydi.

Yechim (har chiqarilgan enrollment uchun):
    1. Davomat bo'lgan har oy (last_lesson_date'gacha) uchun TuitionMonth'ni
       haqiqiy davomatga qarab reconcile qiladi (yaratadi/yangilaydi) → to'lov
       modalida o'sha oy chiqadi.
    2. Davomatsiz, last_lesson_date'dan keyingi FANTOM fee>0 (paid=0) oylarni
       0 ga tushiradi (soft-delete).

XAVFSIZLIK:
    - To'langan (paid>0) TuitionMonth'ga TEGMAYDI (o'tkazib yuboradi, ogohlantiradi).
    - Faqat tanlangan markaz (ko'p-ijarachi izolyatsiya).
    - dry-run default; --confirm bermaguncha HECH NARSA yozilmaydi.

Ishlatish (Render Shell):
    # 1) Avval TEKSHIRUV (hech narsa o'zgarmaydi):
    python manage.py reconcile_removed_students --center teacherowski
    # 2) To'g'ri bo'lsa, yozish:
    python manage.py reconcile_removed_students --center teacherowski --confirm
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from accounts.models import Center
from education.models import Enrollment
from education.services.removed_debt_repair import reconcile_removed_enrollment


class Command(BaseCommand):
    help = "Chiqarilgan o'quvchilar qarzini davomatga qarab to'g'ri oyga tiklaydi"

    def add_arguments(self, parser):
        parser.add_argument("--center", required=True, help="Markaz slug (mas: teacherowski)")
        parser.add_argument("--phone", default="", help="Faqat bitta o'quvchi (telefon bo'yicha)")
        parser.add_argument("--confirm", action="store_true",
                            help="Bermasangiz dry-run. Bersangiz yozadi.")

    def handle(self, *args, **opts):
        slug = opts["center"].strip()
        confirm = opts["confirm"]

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
            Enrollment.all_objects
            .filter(Q(is_active=False) | Q(is_deleted=True))
            .filter(student__is_archived=False, group__is_archived=False)
            .filter(_cq)
            .select_related("student", "group")
            .order_by("group__nom", "student__familya")
        )
        if opts["phone"]:
            enrs = enrs.filter(Q(student__telefon1__icontains=opts["phone"])
                               | Q(student__telefon2__icontains=opts["phone"]))

        self.stdout.write(f"Markaz : {center.name} ({center.slug})")
        self.stdout.write(f"Chiqarilgan enrollment: {enrs.count()}")
        self.stdout.write("Rejim  : " + ("✍️  YOZISH" if confirm
                                         else "👀 DRY-RUN (hech narsa saqlanmaydi)"))
        self.stdout.write("-" * 95)

        n_reconciled = n_phantom = n_paid_skip = n_touched = 0
        for e in enrs:
            rep = reconcile_removed_enrollment(e, apply=confirm)
            if not (rep["reconciled"] or rep["phantoms"] or rep["skipped_paid"]):
                continue
            n_touched += 1
            name = e.student.get_full_name() or f"student#{e.student_id}"
            grp = getattr(e.group, "nom", "?")
            self.stdout.write(f"\n👤 {name} | {grp} (enr={e.id})")
            for m, fee in rep["reconciled"]:
                n_reconciled += 1
                self.stdout.write(f"    ✅ TIKLANDI  {m:%Y-%m}  qarz={fee:>10,} so'm  (to'lovda ko'rinadi)")
            for m, fee in rep["phantoms"]:
                n_phantom += 1
                self.stdout.write(f"    🗑  FANTOM→0 {m:%Y-%m}  (eski noto'g'ri qarz {fee:,} so'm)")
            for item in rep["skipped_paid"]:
                n_paid_skip += 1
                m, fee, paid = item
                self.stdout.write(f"    ⏭  TEGILMADI {m:%Y-%m}  paid={paid:,} (qo'lda tekshiring)")

        self.stdout.write("\n" + "-" * 95)
        self.stdout.write(
            f"O'quvchilar: {n_touched} | Tiklangan oylar: {n_reconciled} | "
            f"Fantom→0: {n_phantom} | To'langani uchun tegilmadi: {n_paid_skip}"
        )
        if confirm:
            self.stdout.write(self.style.SUCCESS("✅ SAQLANDI! Endi to'g'ri oylar to'lovda ko'rinadi."))
        else:
            self.stdout.write(self.style.WARNING(
                "👀 DRY-RUN tugadi — to'g'ri bo'lsa oxiriga --confirm qo'shib qayta yuriting."
            ))
