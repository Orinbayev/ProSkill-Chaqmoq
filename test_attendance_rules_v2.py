import os
import django
import sys
from datetime import date, timedelta
from django.utils import timezone

# Django muhitini sozlash
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from education.models import Attendance, Group
from django.contrib.auth import get_user_model
from chaqmoq.models import Rule, Ledger
from accounts.models import Center
from django.core.management import call_command

User = get_user_model()

def run_test():
    print("--- 🚀 OYLIK QOIDA TESTI (V2) BOSHLANDI ---")
    
    # 1. Markaz va Guruh
    center, _ = Center.objects.get_or_create(name='Test Center', slug='test-center-unique')
    group, _ = Group.objects.get_or_create(nom='Test Group Monthly', center=center)
    
    # 2. Test o'quvchisi
    student, _ = User.objects.get_or_create(
        email='test_bot_monthly@chaqmoq.uz',
        defaults={'role': 'student', 'ism': 'Oybek', 'familya': 'Monthly', 'center': center}
    )
    # Markaz bog'langaniga ishonch hosil qilish
    student.center = center
    student.save()
    
    # 3. Qoida yaratish (3 marta qoldirsa -30 chaqmoq)
    rule, _ = Rule.objects.get_or_create(
        tur=Rule.ATTENDANCE_PENALTY,
        center=center, # Markazga bog'ladik
        defaults={
            'nom': 'Oylik Jarima Test V2', 
            'lightning_penalty': -30, 
            'absence_limit': 3,
            'period': 'monthly'
        }
    )
    rule.absence_limit = 3
    rule.lightning_penalty = -30
    rule.save()

    # 4. Fevral oyi uchun davomat
    feb_start = date(2026, 2, 1)
    Attendance.objects.filter(student=student, date__month=2, date__year=2026).delete()
    Ledger.objects.filter(student=student, rule=rule).delete()
    
    print(f"O'quvchi uchun fevralga 4 ta SABABSIZ yo'qlik yozilmoqda...")
    for i in range(4):
        Attendance.objects.create(
            student=student,
            group=group,
            date=feb_start + timedelta(days=i),
            status='absent_unexcused',
            present=False,
            center=center
        )
    
    # Tekshiruv: bazada davomatlar bormi?
    att_count = Attendance.objects.filter(student=student, status='absent_unexcused', date__month=2).count()
    print(f"Bazada o'quvchi uchun {att_count} ta davomat bor.")

    print("\nKomanda ishga tushirilyapti: 'python manage.py apply_monthly_rules --force-date=2026-03-01'")
    call_command('apply_monthly_rules', force_date='2026-03-01')
    
    # 5. Natijani tekshirish
    ledger = Ledger.objects.filter(student=student, rule=rule).first()
    
    if ledger:
        print("\n" + "✅"*20)
        print(f"MUVAFFAQIYAT! Tizim o'tgan oyni hisobladi.")
        print(f"Jarima: {ledger.ball} ball. Qoida: {ledger.rule_nom}")
        print("✅"*20)
    else:
        print("\n❌ XATO: Jarima haligacha topilmadi.")

if __name__ == "__main__":
    run_test()
