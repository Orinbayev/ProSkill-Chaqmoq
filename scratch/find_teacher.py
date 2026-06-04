import os
import sys
import django

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Center
User = get_user_model()

print("--- CENTERS MATCHING PROSKILL OR SKILL ---")
centers = Center.objects.filter(name__icontains='Skill') | Center.objects.filter(name__icontains='Pro')
for c in centers:
    print(f"Center ID: {c.id}, Name: {c.name}, Slug/Subdomain: {c.slug}")

print("--- USERS SEARCH ---")
all_users = User.objects.filter(
    django.db.models.Q(ism__icontains='hij') | 
    django.db.models.Q(familya__icontains='hij') |
    django.db.models.Q(ism__icontains='ulug') |
    django.db.models.Q(familya__icontains='ulug') |
    django.db.models.Q(ism__icontains='huj') |
    django.db.models.Q(familya__icontains='huj')
)
for u in all_users:
    print(f"ID: {u.id}, Ism: {u.ism}, Familya: {u.familya}, Role: {u.role}, Center: {u.center.name if u.center else 'None'} (ID: {u.center_id}), IsArchived: {u.is_archived}, IsActive: {u.is_active}")

if centers.exists():
    for c in centers:
        print(f"\n--- ALL USERS FOR CENTER {c.name} (ID: {c.id}) ---")
        qs = User.objects.filter(center=c)
        print(f"Total users: {qs.count()}")
        for u in qs.filter(role__in=['teacher', 'manager', 'director', 'admin']):
            print(f"  ID: {u.id}, Ism: {u.ism}, Familya: {u.familya}, Role: {u.role}, IsArchived: {u.is_archived}, IsActive: {u.is_active}")
