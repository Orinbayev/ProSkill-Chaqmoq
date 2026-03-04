import os
import django
from datetime import date, datetime
from django.utils import timezone
from django.db import transaction

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import Center, User
from education.models import Enrollment, TuitionMonth, Payment
from education.services.tuition import tuition_month_fee_field

def final_complete_fix():
    print("\n" + "="*55)
    print("🚀 TO'LIQ TUZATISH: Har guruh uchun alohida qarz")
    print("="*55)

    proskill_centers = Center.objects.filter(name__icontains='proskill')
    my_center = max(proskill_centers, key=lambda c: User.objects.filter(role='student', is_archived=False, center=c).count()) if proskill_centers else None

    if not my_center:
        print("❌ PROSKILL markazi topilmadi!")
        return

    print(f"✅ Markaz: {my_center.name} (ID: {my_center.id})")
    
    fee_field = tuition_month_fee_field()
    march_first = date(2026, 3, 1)
    march_dt = timezone.make_aware(datetime(2026, 3, 1, 0, 0, 0))

    with transaction.atomic():
        # 1. Avval barcha aktiv Enrollment larni olamiz
        enrollments = list(Enrollment.objects.filter(
            is_active=True,
            student__is_archived=False,
            center=my_center,
            group__is_archived=False    # ✅ arxivdagi guruh pullari qo'shilmasin
        ).select_related('student', 'group'))
        
        enr_ids = [e.id for e in enrollments]
        
        # 2. FAQAT shu enrollment larning TuitionMonth larini o'chiramiz
        deleted, _ = TuitionMonth.objects.filter(enrollment_id__in=enr_ids).delete()
        print(f"🗑️  Eski qarzlar o'chirildi: {deleted} ta")

        # 3. To'lovlarni ham tozalash
        pd, _ = Payment.objects.filter(center=my_center).delete()
        print(f"🗑️  Eski to'lovlar o'chirildi: {pd} ta")

        created = 0
        skipped = 0

        for e in enrollments:
            # Narxni aniqlaymiz
            narx = e.kurs_narhi or 0
            if not narx and getattr(e, 'group', None):
                narx = getattr(e.group, 'kurs_narxi', 0) or 0

            # ✅ Narxi 0 bo'lsa - qarz yaratmaymiz, qarzdorlar ro'yxatiga tushmasin
            if narx <= 0:
                skipped += 1
                continue

            # Sana mutlaqo martga bog'lansin (avtomat ko'payishni oldini olish)
            e.created_at = march_dt
            e.save(update_fields=['created_at'])

            # get_or_create - xato chiqmasin uchun
            tm, was_created = TuitionMonth.objects.get_or_create(
                enrollment=e,
                month=march_first,
                defaults={fee_field: narx}
            )
            # agar allaqachon bor bo'lsa ham narxini yangilab qo'yamiz
            if not was_created:
                setattr(tm, fee_field, narx)
                tm.save(update_fields=[fee_field])

            created += 1

    print(f"\n✅ Jami {created} ta Enrollment uchun Mart qarzi yaratildi!")
    print("   (Agar o'quvchi 2 ta guruhda bo'lsa → 2 ta qarz yozildi, jadvalda 1 qatorda kombinatsiya ko'rinadi)")
    print(f"\n⏭️  Skip qilingan: {skipped} ta")
    print("\n" + "="*55)
    print("🎯 Endi Qarzdorlar sahifasini yangilang!")
    print("="*55 + "\n")

if __name__ == '__main__':
    final_complete_fix()
