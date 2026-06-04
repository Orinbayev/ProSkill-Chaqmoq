import os
import sys
import django

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Center
User = get_user_model()

print("--- CENTER SEARCH ---")
all_centers = Center.objects.all()
for c in all_centers:
    if "skill" in c.name.lower() or "pro" in c.name.lower():
        print(f"MATCHED CENTER: ID={c.id}, Name='{c.name}', Slug='{c.slug}', is_deleted={c.is_deleted}")
    else:
        # Just count them or print basic
        pass
print(f"Total Centers in DB: {all_centers.count()}")

print("\n--- USER SEARCH ---")
hijronoy_users = User.objects.filter(ism__icontains="Hijronoy") | User.objects.filter(familya__icontains="Hijronoy") | User.objects.filter(ism__icontains="Ulug'bekova") | User.objects.filter(familya__icontains="Ulug'bekova")
print(f"Total matching Hijronoy/Ulug'bekova: {hijronoy_users.count()}")
for u in hijronoy_users:
    print(f"ID={u.id}, Ism='{u.ism}', Familya='{u.familya}', Role='{u.role}', Center='{u.center.name if u.center else 'None'}' (ID={u.center_id}), IsArchived={u.is_archived}, IsActive={u.is_active}")
