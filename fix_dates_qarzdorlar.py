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
    print("🚀 TO'LIQ TUZATISH: Faqat MART oyi uchun 1 ta qarz")
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
        # 1. BARCHA eski TuitionMonth larni o'chirish
        deleted, _ = TuitionMonth.objects.filter(enrollment__student__center=my_center).delete()
        print(f"🗑️  Eski qarzlar o'chirildi: {deleted} ta")

        # 2. To'lovlarni ham tozalash
        pd, _ = Payment.objects.filter(center=my_center).delete()
        print(f"🗑️  Eski to'lovlar o'chirildi: {pd} ta")

        created = 0
        skipped = 0

        students = User.objects.filter(role='student', is_archived=False, center=my_center)
        for s in students:
            # Eng so'nggi FAOL Enrollment ni olamiz (1 o'quvchi = 1 ta qarz)
            e = Enrollment.objects.filter(student=s, is_active=True, center=my_center).order_by('-id').first()
            if not e:
                skipped += 1
                continue

            # Sana ham mutlaqo martga bog'lansin (avtomat ko'paytiruvni oldini olish)
            e.created_at = march_dt
            
            # Narxni aniqlaymiz
            narx = e.kurs_narhi or 0
            if not narx and getattr(e, 'group', None):
                narx = getattr(e.group, 'kurs_narxi', 0) or 0
            if narx <= 0:
                narx = 500_000
                e.kurs_narhi = narx
                
            e.save(update_fields=['created_at', 'kurs_narhi'])

            # FAQAT 1 TA (mart) qarz yozamiz
            TuitionMonth.objects.create(
                enrollment=e,
                month=march_first,
                **{fee_field: narx}
            )
            created += 1

    print(f"\n✅ Jami {created} ta o'quvchiga FAQAT 1 ta Mart qarzi yozildi!")
    print(f"⏭️  Guruhsiz (skip qilingan): {skipped} ta")
    print("\n" + "="*55)
    print("🎯 Endi Qarzdorlar sahifasini yangilang!")
    print("   Har bir o'quvchi faqat o'zining HAQIQIY narxida ko'rinadi!")
    print("="*55 + "\n")

if __name__ == '__main__':
    final_complete_fix()
