import os
import django
import sys

# Django muhitini sozlash
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from chaqmoq.models import Rule, Ledger
from accounts.models import Center
from django.db.models import Sum, Q

User = get_user_model()

def smoke_test_chaqmoq_consistency():
    print("--- CHAQMOQ SMOKE TEST START ---")
    
    student = User.objects.filter(id=42).first()
    if not student:
        print("FAIL: Test uchun student topilmadi (ID 42).")
        return
    
    center = student.center or Center.objects.first()
    if not center:
        print("FAIL: Markaz topilmadi.")
        return

    print(f"Test Student: {student.get_full_name()} (ID: {student.id})")
    print(f"Test Center: {center.nom} (ID: {center.id})")

    # 2. Mavjud Ledgerlarni tozalash (ixtiyoriy, lekin test aniqligi uchun yaxshi)
    # Ledger.objects.filter(student=student).delete()

    # 3. Global va Center-specific qoidalar yaratish/olish
    global_rule = Rule.objects.filter(center__isnull=True, tur='plus').first()
    if not global_rule:
        global_rule = Rule.objects.create(nom="Global Test Rule", tur='plus', min_baho=1, max_baho=100, center=None)
    
    center_rule = Rule.objects.filter(center=center, tur='plus').first()
    if not center_rule:
        center_rule = Rule.objects.create(nom="Center Test Rule", tur='plus', min_baho=1, max_baho=100, center=center)

    # 4. Chaqmoqlar berish
    # a) Global ball
    Ledger.objects.create(student=student, ball=10, rule=global_rule, sana=django.utils.timezone.now())
    # b) Center ball
    Ledger.objects.create(student=student, ball=20, rule=center_rule, sana=django.utils.timezone.now())
    # c) Boshqa center ball (hisobga olinmasligi kerak)
    other_center = Center.objects.exclude(id=center.id).first()
    if other_center:
        other_rule = Rule.objects.create(nom="Other Center Rule", tur='plus', min_baho=1, max_baho=100, center=other_center)
        Ledger.objects.create(student=student, ball=100, rule=other_rule, sana=django.utils.timezone.now())

    # 5. Balanslarni tekshirish
    expected_balance = 10 + 20 # global + center
    
    # Method 1: student_balansi (Yangi mantiq)
    method_balance = Ledger.student_balansi(student.id, center=center)
    
    # Method 2: Manual query (Xuddi views'lardagi kabi)
    qs = Ledger.objects.filter(student=student)
    qs = qs.filter(Q(group__center=center) | Q(rule__center=center) | Q(rule__center__isnull=True))
    manual_balance = qs.aggregate(Sum('ball'))['ball__sum'] or 0

    print(f"Expected: {expected_balance} (kamida)")
    print(f"Method Balance: {method_balance}")
    print(f"Manual Balance: {manual_balance}")

    if method_balance >= expected_balance and method_balance == manual_balance:
        print("✅ SUCCESS: Balanslar mos keldi (Global + Center)!")
    else:
        print("❌ FAIL: Balanslarda farq bor!")

    print("--- CHAQMOQ SMOKE TEST END ---")

if __name__ == "__main__":
    smoke_test_chaqmoq_consistency()
