import os
import django
import sys
from django.db.models import Sum

# Django muhitini sozlash
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from education.models import Attendance, TeacherIncome, Enrollment
from django.db import transaction

def recalculate_all_incomes():
    print("--- 🛠 O'QITUVCHI OYLIKLARINI QAYTA HISOBLASH (FIXER V2) BOSHLANDI ---")
    
    # Barcha davomatlarni olamiz
    all_attendances = Attendance.objects.all().select_related('group', 'student', 'teacher', 'group__center')
    total = all_attendances.count()
    
    print(f"Jami {total} ta davomat tekshirilmoqda...")
    
    created_count = 0
    updated_count = 0
    deleted_count = 0
    skipped_count = 0
    
    with transaction.atomic():
        for i, att in enumerate(all_attendances):
            # 1. To'lanadigan holatmi?
            is_billable = att.status == 'present' or att.status == 'absent_unexcused' or getattr(att, 'forced', False) or getattr(att, 'present', False)

            if not is_billable:
                # To'lanmaydigan holatda eskini o'chiradi
                deleted, _ = TeacherIncome.objects.filter(attendance=att).delete()
                if deleted: deleted_count += 1
                continue

            # 2. Enrollmentni topish (is_active shartimas, lekin faollari yuqorida tursin)
            enrollment = Enrollment.objects.filter(
                group=att.group,
                student=att.student
            ).order_by('-is_active', '-created_at').first()

            if not enrollment:
                # Mutlaqo enrollment yo'q bo'lsa daromad bo'lishi mumkin emas
                deleted, _ = TeacherIncome.objects.filter(attendance=att).delete()
                if deleted: deleted_count += 1
                skipped_count += 1
                continue

            # 4. Saqlash (Har doim guruhining asosiy o'qituvchisiga yozamiz)
            teacher = att.group.oqituvchi if att.group else None
            if not teacher:
                skipped_count += 1
                continue

            # 3. Hisoblash
            # MUHIM: Foydalanuvchi talabiga ko'ra, O'qituvchi profildagi foiz MASTER (asosiy) hisoblanadi.
            foiz = getattr(teacher, 'oqituvchi_foizi', 0)
            if foiz is None or foiz == 0:
                foiz = enrollment.oqituvchi_foiz
                
            kurs_narhi = enrollment.kurs_narhi or 0
            
            oy_dars_soni = att.group.oy_dars_soni or 12
            if oy_dars_soni <= 0: oy_dars_soni = 12

            if kurs_narhi > 0 and foiz > 0:
                total_per_lesson = kurs_narhi / oy_dars_soni
                amount = round(total_per_lesson * (foiz / 100))
                center_amount = round(total_per_lesson * ((100 - foiz) / 100))
                total_amount = round(total_per_lesson)
            else:
                amount = 0
                center_amount = 0
                total_amount = 0



            obj, created = TeacherIncome.objects.update_or_create(
                attendance=att,
                defaults={
                    'center': att.center or (att.group.center if att.group else None),
                    'teacher': teacher,
                    'group': att.group,
                    'amount': amount,
                    'center_amount': center_amount,
                    'total_amount': total_amount
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
                
            if i % 100 == 0:
                print(f"Jarayon: {i}/{total}...")

    print("\n" + "="*40)
    print(f"✅ HISOB-KITOB YAKUNLANDI!")
    print(f"Yaratildi: {created_count} ta yangi daromad yozuvi")
    print(f"Yangilandi: {updated_count} ta eski yozuv to'g'irladi")
    print(f"O'chirildi: {deleted_count} ta noto'g'ri yozuv")
    print(f"O'tkazib yuborildi: {skipped_count} ta (Enrollment topilmadi yoki Teacher yo'q)")
    print("="*40)

if __name__ == "__main__":
    recalculate_all_incomes()
