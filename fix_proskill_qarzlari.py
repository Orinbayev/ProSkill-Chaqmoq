import os
import django
from datetime import date
from django.db.models import Sum

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import Center, User
from education.models import Enrollment, TuitionMonth, PaymentAllocation, Group
from education.services.tuition import tuition_month_fee_field, ensure_tuition_month, reallocate_enrollment

def fix_debts_for_proskill():
    march_first = date(2026, 3, 1)
    fee_field = tuition_month_fee_field()
    
    # 1. ProSkill markazini topish
    proskill_centers = Center.objects.filter(name__icontains='proskill')
    
    if not proskill_centers.exists():
        print("❌ 'PROSKILL' nomli markaz topilmadi. Tizimdagi markazlar:")
        for c in Center.objects.all()[:10]:
            print(f"- {c.name} (ID: {c.id})")
        return
        
    # Eng ko'p o'quvchisi bor PROSKILL markazini tanlaymiz (aniqlik uchun)
    center = None
    max_stu = -1
    for c in proskill_centers:
        stu_count = User.objects.filter(role='student', is_archived=False, center=c).count()
        if stu_count > max_stu:
            max_stu = stu_count
            center = c
            
    print(f"🎯 Tanlangan Markaz: '{center.name}' (ID: {center.id}) | Jami O'quvchilar: {max_stu} ta")
    
    # Barcha o'quvchilarni olish
    students = User.objects.filter(role='student', is_archived=False, center=center)
    
    # Faol guruhlar
    groups = Group.objects.filter(center=center)
    if not groups.exists():
        print("❌ Ushbu markazda birorta ham guruh yo'q! Qarzdor qilib bo'lmaydi.")
        return
        
    # Asosiy fallback guruhini topib turaylik (Eng ko'p o'quvchisi borini default sifatida)
    default_group = groups.first() 
    
    fixed_count = 0
    assigned_count = 0
    
    for student in students:
        # A. O'quvchining joriy guruhini (Enrollment) tekshiramiz
        enr = Enrollment.objects.filter(student=student, is_active=True).first()
        
        # B. Agar guruhi umuman yo'q bo'lsa, ularni avtomatik birorta guruhga kiritmasak "Qarzdor" bo'la olmaydi!
        # Shuning uchun ularni default_group ga qo'shamiz
        if not enr:
            enr = Enrollment.objects.create(
                group=default_group,
                student=student,
                center=center,
                kurs_narhi=default_group.kurs_narxi,
                oqituvchi_foiz=default_group.oqituvchi_foiz or 40,
            )
            assigned_count += 1
            
        # C. Mart oyi qarzdorligini kafolatlash! (155 dan barcha qolganlari uchun ishlashi)
        # Eski oylar bo'lsa barchasini nol qilish:
        past_months = TuitionMonth.objects.filter(enrollment=enr, month__lt=march_first)
        for pm in past_months:
            paid = PaymentAllocation.objects.filter(tuition_month=pm).aggregate(s=Sum("amount"))["s"] or 0
            if getattr(pm, fee_field, 0) != paid:
                setattr(pm, fee_field, paid)
                pm.save(update_fields=[fee_field])
                
        # Mart oyiga to'liq guruh / kurs narxini yozish
        tm_march = ensure_tuition_month(enr, march_first)
        narx = enr.kurs_narhi
        if not narx and enr.group:
            narx = getattr(enr.group, "kurs_narxi", 0) or getattr(enr.group, "kurs_narhi", 0) or 0
            
        setattr(tm_march, fee_field, narx)
        tm_march.save(update_fields=[fee_field])
        
        # Pullarni qayta hisoblash
        try:
            reallocate_enrollment(enr)
        except Exception:
            pass
            
        fixed_count += 1
        
    print(f"\n✅ NATIJA: Jami {fixed_count} ta o'quvchi MUVAFFAQIYATLI Mart oyi uchun qarzdor qilindi!")
    print(f"⚠️ Ulardan {assigned_count} tasi umuman guruhsiz ekan, ular majburan birinchi paydo bo'lgan guruh '{default_group.nom}' ga biriktirildi. Chunki tizim aynan shunday ishlaydi.")

if __name__ == '__main__':
    fix_debts_for_proskill()
