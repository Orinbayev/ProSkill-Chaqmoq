import os
import django
import sys
from datetime import date, timedelta
from django.utils import timezone

# Django muhitini sozlash
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from education.models import Attendance
from django.contrib.auth import get_user_model
from chaqmoq.models import Rule, Ledger
from django.core.management import call_command

User = get_user_model()

def run_test():
    print("--- 🚀 OYLIK QOIDA TESTI BOSHLANDI ---")
    
    # 1. Test o'quvchisi
    from accounts.models import Center
    center, _ = Center.objects.get_or_create(name='Test Center', slug='test-center')
    
    student, _ = User.objects.get_or_create(
        email='test_bot_user@chaqmoq.uz',
        defaults={'role': 'student', 'ism': 'Test', 'familya': 'Robot', 'center': center}
    )
    
    # Guruh majburiy ekan
    from education.models import Group
    group, _ = Group.objects.get_or_create(nom='Test Group', defaults={'center': center})
    
    # 2. Qoida yaratish (3 marta qoldirsa -25 chaqmoq)
    rule, created = Rule.objects.get_or_create(
        tur=Rule.ATTENDANCE_PENALTY,
        absence_limit=3,
        defaults={
            'nom': 'Oylik Jarima Test', 
            'lightning_penalty': -25, 
            'period': 'monthly'
        }
    )
    if not created:
        rule.absence_limit = 3
        rule.lightning_penalty = -25
        rule.save()

    # 3. Fevral oyi uchun davomat (o'tgan oy sifatida)
    # Bugun 11-mart, demak fevral oyini (2026-02) test qilamiz.
    feb_start = date(2026, 2, 1)
    
    # Eskilarini tozalash (toza test uchun)
    Attendance.objects.filter(student=student, date__month=2, date__year=2026).delete()
    Ledger.objects.filter(student=student, rule=rule, sana__month=3).delete()
    
    print(f"O'quvchi '{student.username}' uchun Fevral oyida 4 marta 'SABABSIZ' yaratilmogda...")
    for i in range(4):
        Attendance.objects.create(
            student=student,
            group=group,
            date=feb_start + timedelta(days=i),
            status='absent_unexcused',
            present=False
        )
    
    print("\n'apply_monthly_rules' komandasi ishga tushirilmoqda...")
    print("Simulyatsiya: Bugun 1-Mart va biz fevralni hisoblayapmiz.")
    
    # Bugun 1-mart bo'lsa, komanda avtomatik o'tgan oyni (fevral) hisoblaydi
    call_command('apply_monthly_rules', force_date='2026-03-01')
    
    # 4. Natijani tekshirish
    ledger = Ledger.objects.filter(student=student, rule=rule).first()
    
    if ledger:
        print("\n" + "="*40)
        print(f"✅ MUVAFFAQIYAT: Avtomatik jarima ishga tushdi!")
        print(f"O'quvchi: {student.get_full_name()}")
        print(f"Jarima miqdori: {ledger.ball} ball")
        print(f"Qoida nomi: {ledger.rule_nom}")
        print(f"Sana: {ledger.sana.strftime('%Y-%m-%d %H:%M')}")
        print("="*40)
    else:
        print("\n❌ XATO: Jarima topilmadi. Komanda ishlamagan ko'rinadi.")

if __name__ == "__main__":
    run_test()
