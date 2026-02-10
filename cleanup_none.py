import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User

users = User.objects.all()
count = 0
for u in users:
    updated = False
    if u.ism and u.ism.strip().lower() == 'none':
        u.ism = ''
        updated = True
    if u.familya and u.familya.strip().lower() == 'none':
        u.familya = ''
        updated = True
    if u.otchestvo and u.otchestvo.strip().lower() == 'none':
        u.otchestvo = ''
        updated = True
    
    if updated:
        u.save()
        count += 1

print(f"Updated {count} users.")
