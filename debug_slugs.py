import os
import django
import sys

# Add project root to path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import Center

print("-" * 60)
print(f"{'ID':<5} | {'Name':<20} | {'Slug (URL)':<20} | {'Status':<10}")
print("-" * 60)

for c in Center.objects.all():
    print(f"{c.id:<5} | {c.name:<20} | {c.slug:<20} | {c.status:<10}")

print("-" * 60)
