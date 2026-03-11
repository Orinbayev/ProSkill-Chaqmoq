import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User
users = User.objects.all()[:10]
for u in users:
    print(u.phone_number, u.role, getattr(u, 'center_id', 'None'))
