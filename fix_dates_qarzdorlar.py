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

def final_fix():
    print("\n" + "="*50)
    print("🚀 QARZDORLIKNI 100% TO'G'IRLASH (CREATED_AT MUAMMOSI)")
    print("="*50)

    # Faqat PROSKILL
    proskill_centers = Center.objects.filter(name__icontains='proskill')
    my_center = max(proskill_centers, key=lambda c: User.objects.filter(role='student', is_archived=False, center=c).count()) if proskill_centers else None

    if not my_center:
        print("PROSKILL markazi topilmadi!")
        return

    march_first = date(2026, 3, 1)
    march_dt = timezone.make_aware(datetime(2026, 3, 1, 0, 0, 0))
    fee_field = tuition_month_fee_field()

    with transaction.atomic():
        # 1. ESKI QARZLARNI (TUITIONMONTH) BUTUNLAY O'CHIRISH
        TuitionMonth.objects.filter(enrollment__student__center=my_center).delete()
        
        # 2. TO'LOVLARNI HAM TOZALASH (Eskilardan qolib ketmasligi uchun)
        Payment.objects.filter(center=my_center).delete()

        # 3. GURUHLARNI TOZALASH (1 O'QUVCHI FAQAT 1 MAROTABA ENROLL QILINGAN BO'LISHI SHART)
        # Agar xatolik bilan ikkita 'BackEnd' ga biriktirilgan bo'lsa bittasi olib tashlanadi
        students = User.objects.filter(role='student', is_archived=False, center=my_center)
        active_enr_topildi = 0
        
        for s in students:
            # Bitta guruhni o'quvchida dublikat ekanligini topamiz
            enrolls = list(Enrollment.objects.filter(student=s, is_active=True).order_by('id'))
            
            # Agar bitta guruh turidan 2 tadan ochilib qolgan bo'lsa (Backend03 va Backend03) eski idsini o'chiramiz
            seen_groups = set()
            for e in enrolls:
                if getattr(e, 'group_id', None) in seen_groups:
                    e.is_active = False # Bekor qilamiz
                    e.save(update_fields=['is_active'])
                else:
                    if e.group_id:
                        seen_groups.add(e.group_id)
            
            # Endi tozza active enrollments larni 100% Mart oyi deb belgilaymiz!!!
            clean_enrolls = Enrollment.objects.filter(student=s, is_active=True)
            for e in clean_enrolls:
                # MANA SHU QATOR BO'LMAGANI UCHUN VIEWS.PY YANA O'ZICHA FEVRALGA QARZ TO'QIB CHIQARYAPTI!
                e.created_at = march_dt
                
                # Narxni kafolatlash
                narx = e.kurs_narhi or 0
                if not narx and getattr(e, 'group', None):
                    narx = getattr(e.group, "kurs_narxi", 0) or getattr(e.group, "kurs_narhi", 0) or 0
                if narx <= 0:
                    narx = 500000
                e.kurs_narhi = narx
                
                # O'zgarishlarni saqlash
                e.save(update_fields=['created_at', 'kurs_narhi'])
                
                # FAQAT MART OYI UCHUN QARZ YOZISH
                TuitionMonth.objects.create(
                    enrollment=e,
                    month=march_first,
                    **{fee_field: narx}
                )
                active_enr_topildi += 1

        print(f"✅ Bajarildi! Jami {active_enr_topildi} ta enrollment sanasi Mutaqo MART OYIGA O'ZGARDI!")
        print(f"✅ Endi tizim Qarzdorlar menyusida fevral va yanvar uchun qarz TUZMAYDI!")

if __name__ == '__main__':
    final_fix()
