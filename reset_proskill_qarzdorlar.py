import os
import django
from datetime import date
from django.db import transaction

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import Center, User
from education.models import Enrollment, TuitionMonth, Payment, Group
from education.services.tuition import tuition_month_fee_field, ensure_tuition_month

def qatiy_tozalash():
    print("\n" + "="*50)
    print("🚀 QAT'IY TOZALASH VA NARXLASH (TOLOVLAR VA QARZLARNI NOLDAN TIKLASH)")
    print("="*50)

    proskill_centers = Center.objects.filter(name__icontains='proskill')
    my_center = None
    max_count = 0
    for c in proskill_centers:
        cnt = User.objects.filter(role='student', is_archived=False, center=c).count()
        if cnt > max_count:
            max_count = cnt
            my_center = c
            
    if not my_center:
        print("❌ PROSKILL markazi topilmadi!")
        return
        
    all_students_count = User.objects.filter(role='student', is_archived=False, center=my_center).count()
    print(f"✅ Markaz aniqlandi: {my_center.name} (ID: {my_center.id})")
    print(f"✅ Barcha o'quvchilar: {all_students_count} ta")

    fee_field = tuition_month_fee_field()
    march = date(2026, 3, 1)

    with transaction.atomic():
        # 1. TOLOVLAR BO'LIMINI UMUAMAN TOZALASH (Faqat PROSKILL uchun)
        print("\n🗑️ TO'LOVLAR BO'LIMI TOZALANMOQDA...")
        payments = Payment.objects.filter(center=my_center)
        deleted_payments, _ = payments.delete()
        print(f"✅ Jami {deleted_payments} ta to'lov yozuvlari tanaffussiz o'chirildi!")

        # 2. QARZDORLAR BO'LIMINI UMUAMAN TOZALASH (Hamma eski qarzlarni o'chirish)
        print("\n🗑️ QARZDORLAR BO'LIMI (ESKI QARZLAR) TOZALANMOQDA...")
        tuitions = TuitionMonth.objects.filter(enrollment__center=my_center)
        deleted_tuitions, _ = tuitions.delete()
        print(f"✅ Jami {deleted_tuitions} ta eski oy qarz yozuvlari o'chirildi!")

        # 3. YONIDA GURUHI BOR BARCHA O'QUVCHILARGA MART OYI UCHUN QARZ YOZAMIZ
        print("\n➕ XAR BIR GURUHGA BIRIKTIRILGAN O'QUVCHI UCHUN MART OYIGA QARZ YOZILMOQDA...")
        enrollments = Enrollment.objects.filter(
            center=my_center, 
            is_active=True,
            student__is_archived=False
        ).select_related('group', 'student')
        
        qarz_hsb = 0
        nol_narx_hsb = 0
        
        for e in enrollments:
            narx = e.kurs_narhi or 0
            if not narx and getattr(e, 'group', None):
                narx = getattr(e.group, "kurs_narxi", 0) or getattr(e.group, "kurs_narhi", 0) or 0
            
            # Agar narx hali ham 0 bo'lsa (Dastur qarzdorga kiritmaydi!), shuni bartaraf qilamiz
            if narx <= 0:
                narx = 500000  # Default majburiy qarz
                e.kurs_narhi = narx
                e.save(update_fields=['kurs_narhi'])
                nol_narx_hsb += 1
                
            # Mart oyi qarzdorligi ob'ektini yaratamiz
            tm_march, _ = TuitionMonth.objects.get_or_create(
                enrollment=e,
                month=march,
                defaults={fee_field: narx}
            )
            # Aniqlik uchun
            if getattr(tm_march, fee_field) != narx:
                setattr(tm_march, fee_field, narx)
                tm_march.save(update_fields=[fee_field])
                
            qarz_hsb += 1
            
        print(f"✅ Bajarildi! Jami {qarz_hsb} ta guruh_oquvchisi hisobiga Mart oyi qarzi qo'shildi! (Endi Qarzdorlar jadvaliga tushishadi).")
        if nol_narx_hsb > 0:
            print(f"ℹ️ {nol_narx_hsb} ta o'quvchining GURUH narxi nol deyilgan ekan, ro'yxatda qarzdor chiqishi uchun default 500,000 narx bilan almashtirdim!")

    print("\n" + "="*50)
    print("🎯 XULOSA: Tizim to'ppa-to'g'ri yangilandi. Iltimos, Veb saytga kirib yangilab tekshirib ko'ring!")
    print("="*50 + "\n")

if __name__ == '__main__':
    qatiy_tozalash()
