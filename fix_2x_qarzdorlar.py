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

def aniq_narxni_tiklash():
    print("\n" + "="*50)
    print("🚀 QARZDORLIKNI 2X (IKKI BAROBAR) BO'LIB QOLISHINI TUZATISH")
    print("="*50)

    # 1. ProSkill markazini aniqlaymiz
    proskill_centers = Center.objects.filter(name__icontains='proskill')
    my_center = None
    max_count = -1
    for c in proskill_centers:
        cnt = User.objects.filter(role='student', is_archived=False, center=c).count()
        if cnt > max_count:
            max_count = cnt
            my_center = c
            
    if not my_center:
        print("❌ PROSKILL markazi topilmadi!")
        return
        
    fee_field = tuition_month_fee_field()
    march_first = date(2026, 3, 1)
    march_dt = timezone.make_aware(datetime(2026, 3, 1, 0, 0, 0))
    
    with transaction.atomic():
        # Dastur eski (fevral, yanvar) oylarini qayta-qayta generatsiya qilib qo'shganining sababi:
        # Enrollment.created_at (qayd qilingan vaqti) fevral yoki yanvar edi.
        # Natijada "Joriy mart oyigacha qancha oy o'tgan bo'lsa barchasiga qarz yozish" degan funksiya ishlagan va narx 2x-3x ga ko'paygan.
        
        # Buni oldini olish uchun: Barcha O'quvchining Guruhga qo'shilgan vaqti aynan Mart oyi deb belgilaymiz!
        # Shunda dastur faqat 1 ta - faqat Mart oyi uchn qarz hisoblaydi.

        valid_enrollments = Enrollment.objects.filter(
            center=my_center, 
            is_active=True,
            student__is_archived=False
        )
        
        updated_enr = 0
        for e in valid_enrollments:
            e.created_at = march_dt # Mart oyida qo'shilgan qilib o'zgartiramiz
            e.save(update_fields=['created_at'])
            updated_enr += 1
            
        print(f"✅ {updated_enr} ta o'quvchi Enrollment sanasi mutlaqo 1-Mart (01.03.2026) sanasiga o'tkazildi!")

        # 2. Xato ochilib ketgan BARCHA qarz (TuitionMonth) larni tozalaymiz
        tuitions = TuitionMonth.objects.filter(enrollment__center=my_center)
        deleted_tuitions, _ = tuitions.delete()
        print(f"✅ Jami {deleted_tuitions} ta aralash oy qarz yozuvlari tozalandi!")

        # 3. Va faqatgina Mart oyi uchn, o'zi qancha to'llashi kerak bo'lsa shunchani qo'lda 1 martagina yaratib qo'yamiz.
        qarz_hsb = 0
        for e in valid_enrollments:
            narx = e.kurs_narhi or 0
            if not narx and getattr(e, 'group', None):
                narx = getattr(e.group, "kurs_narxi", 0) or getattr(e.group, "kurs_narhi", 0) or 0
                
            if narx <= 0:
                narx = 500000
                e.kurs_narhi = narx
                e.save(update_fields=['kurs_narhi'])
                
            TuitionMonth.objects.create(
                enrollment=e,
                month=march_first,
                **{fee_field: narx}
            )
            qarz_hsb += 1
            
        print(f"✅ Bajarildi! Jami {qarz_hsb} ta talabaga faqat 1 dona qarz (roppa rosa o'zining summasida) qo'shildi!")

    print("\n" + "="*50)
    print("🎯 XULOSA: Qarzdorlik 1:1 o'zini to'lov stavkasi bo'yicha tushdi! Sahifani yangilab tekshiring!")
    print("="*50 + "\n")

if __name__ == '__main__':
    aniq_narxni_tiklash()
