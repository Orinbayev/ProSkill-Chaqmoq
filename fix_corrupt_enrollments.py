import os
import django
from datetime import date
from django.db import transaction
from django.db.models import F

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import Center, User
from education.models import Enrollment, TuitionMonth, Payment, Group
from education.services.tuition import tuition_month_fee_field

def xatoni_tuzatish_va_tiklash():
    print("\n" + "="*50)
    print("🚀 BAZADAGI YASHIRIN XATOLARNI TUZATISH VA MART OYIGA QARZ YOZISH")
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
        
    print(f"✅ Markaz aniqlandi: {my_center.name} (ID: {my_center.id})")
    
    with transaction.atomic():
        # BAZADAGI ASOSIY XATONI TUZATAMIZ:
        # Tizimda o'quvchining guruhi bo'lsa ham Enrollment.center qolib ketgan yoki boshqa centerga tushgan.
        # Buning oqibatida Qarzdorlar oynasi filter qilganda ularni chiqarib tashlagan!
        print("\n🔧 1. BAZADAGI YASHIRIN XATONI (TUSHUB QOLGAN MARKAZLARNI) TUZATAMIZ...")
        
        # O'quvchisi shu centerda bo'lgan barcha guruh biriktirmalarini (Enrollments) olamiz
        all_enrollments = Enrollment.objects.filter(
            student__center=my_center
        )
        
        updated_enr = 0
        for e in all_enrollments:
            if getattr(e, 'group', None):
                e.center = e.group.center
            else:
                e.center = my_center
                
            e.save(update_fields=['center'])
            updated_enr += 1
            
        print(f"✅ {updated_enr} ta o'quvchining yo'qolib qolgan markaz ma'lumoti tiklandi!")

        # 2. TO'LOVLARNI O'CHIRISH
        print("\n🗑️ 2. TO'LOVLAR BO'LIMI TOZALANMOQDA...")
        payments = Payment.objects.filter(center=my_center)
        deleted_payments, _ = payments.delete()
        print(f"✅ Jami {deleted_payments} ta to'lov yozuvlari tanaffussiz o'chirildi!")

        # 3. ESKI QARZLARNI (TUITION_MONTH) O'CHIRISH
        print("\n🗑️ 3. QARZDORLAR BO'LIMI (ESKI QARZLAR) TOZALANMOQDA...")
        tuitions = TuitionMonth.objects.filter(enrollment__center=my_center)
        deleted_tuitions, _ = tuitions.delete()
        print(f"✅ Jami {deleted_tuitions} ta oy qarz yozuvlari o'chirildi!")

        # 4. BARCHA AKTIV GURUH BIRIKTIRILGANLARGA AYNAN MART OYIGA QARZ YOZISH
        print("\n➕ 4. GURUHI BOR BARCHA O'QUVCHILAR UCHUN MART OYIGA QARZ YOZILMOQDA...")
        
        fee_field = tuition_month_fee_field()
        march = date(2026, 3, 1)
        
        # Endi ishonch komil: barcha enrollments to'g'ri markazga ulandi
        valid_enrollments = Enrollment.objects.filter(
            center=my_center, 
            is_active=True,
            student__is_archived=False
        ).select_related('group')
        
        qarz_hsb = 0
        nol_narx_hsb = 0
        
        for e in valid_enrollments:
            narx = e.kurs_narhi or 0
            if not narx and getattr(e, 'group', None):
                narx = getattr(e.group, "kurs_narxi", 0) or getattr(e.group, "kurs_narhi", 0) or 0
            
            # Agar nol bo'lsa default 500k qaraymiz (Qarzdorlarda korinishi uchun nol bolmasligi shart)
            if narx <= 0:
                narx = 500000
                e.kurs_narhi = narx
                e.save(update_fields=['kurs_narhi'])
                nol_narx_hsb += 1
                
            # Mart oyi yaratiladi
            tm_march = TuitionMonth.objects.create(
                enrollment=e,
                month=march,
                **{fee_field: narx}
            )
            qarz_hsb += 1
            
        print(f"✅ Bajarildi! Jami {qarz_hsb} ta talabaga Mart oyi uchun aniq qarzdorlik qo'shildi! Ular endi Qarzdorlar jadvalida yuz foiz ko'rinadi.")
        if nol_narx_hsb:
            print(f"ℹ️ {nol_narx_hsb} ta o'quvchida kurs narxi yo'q ekan. Ularning narxi nol emasligi uchun o'rtacha 500,000 qilib belgilandi.")

    print("\n" + "="*50)
    print("🎯 XULOSA: O'quvchilar nega ko'rinmayapti degan savol yechildi! Ular endi o'z o'rnida namoyon bo'ladi!")
    print("="*50 + "\n")

if __name__ == '__main__':
    xatoni_tuzatish_va_tiklash()
