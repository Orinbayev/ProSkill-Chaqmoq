
import os, django, sys
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import Center, User
from billing.models import CenterSubscription

print("-" * 50)
centers = Center.objects.filter(name__startswith="Laylo") | Center.objects.filter(name__startswith="Leyla")
print(f"Found {centers.count()} centers:")

for c in centers:
    sub = getattr(c, 'subscription', None)
    plan = sub.plan.title if sub else "No Sub"
    code = sub.plan.code if sub else c.plan
    expires = sub.expires_at.strftime("%d.%m.%Y") if sub and sub.expires_at else "No Expiry"
    
    # Get Directors
    directors = User.objects.filter(center=c, role='director')
    director_str = ", ".join([f"{d.email} ({d.get_full_name()})" for d in directors])
    
    print(f"ID: {c.id}")
    print(f"Name: {c.name}")
    print(f"Slug: {c.slug}")
    print(f"Plan Title: {plan}")
    print(f"Plan Code: {code}")
    print(f"Expires: {expires}")
    print(f"Directors: {director_str}")
    print(f"Is Deleted: {c.is_deleted}")
    print("-" * 50)
