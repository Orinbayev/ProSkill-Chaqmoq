import os
import django
import sys

# Setup environment
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_prod")
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Center
from education.models import Group

User = get_user_model()

print("\n" + "="*60)
print("📊 BAZA STATISTIKASI (RENDER PRODUCTION)")
print("="*60)

# 1. USERLAR (Foydalanuvchilar)
total_users = User.objects.count()
print(f"\n👥 JAMI USERLAR: {total_users}")

if total_users > 0:
    # Rollar bo'yicha
    # Using raw SQL or checking field if 'role' exists
    try:
        roles = User.objects.values_list('role', flat=True)
        role_counts = {}
        for r in roles:
            r_name = r if r else "Role yo'q"
            role_counts[r_name] = role_counts.get(r_name, 0) + 1
        
        for role, count in role_counts.items():
            print(f"   - {role}: {count} ta")
    except Exception as e:
        print(f"   (Role bo'yicha hisoblashda xatolik: {e})")

# 2. MARKAZLAR (Center)
try:
    total_centers = Center.objects.count()
    print(f"\n🏢 JAMI MARKAZLAR: {total_centers}")
    if total_centers > 0:
        for center in Center.objects.all()[:10]: # first 10
            print(f"   - {center.name} (Plan: {getattr(center, 'plan', 'N/A')})")
        if total_centers > 10:
            print(f"   ... va yana {total_centers - 10} ta markaz")
except Exception as e:
    print(f"   (Markazlarni hisoblashda xatolik: {e})")

# 3. GURUHLAR
try:
    total_groups = Group.objects.count()
    print(f"\n📚 JAMI GURUHLAR: {total_groups}")
except Exception as e:
    print(f"   (Guruhlarni hisoblashda xatolik: {e})")

# 4. SUPERUSERLAR (Login uchun)
superusers = User.objects.filter(is_superuser=True)
print(f"\n🔑 SUPERUSERLAR (Login qila oladiganlar):")
if superusers.exists():
    for su in superusers:
        print(f"   - {su.email} (Active: {su.is_active})")
else:
    print("   ❌ HECH QANDAY SUPERUSER TOPILMADI!")

# 5. Admin qidirish
target = "amirxondev@gmail.com"
u = User.objects.filter(email__iexact=target).first()
if u:
    print(f"\n✅ {target} bazada MAVJUD (ID: {u.id})")
else:
    print(f"\n❌ {target} bazada YO'Q")

print("\n" + "="*60)
