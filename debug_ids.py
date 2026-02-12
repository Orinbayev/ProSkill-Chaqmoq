
import os, django, sys
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import Center, User

def print_center(c):
    sub = getattr(c, 'subscription', None)
    plan = sub.plan.title if sub else "No Sub"
    expires = sub.expires_at.strftime("%d.%m.%Y") if sub and sub.expires_at else "No Expiry"
    directors = list(c.user_set.filter(role='director').values_list('email', flat=True))
    
    print(f"ID: {c.id}")
    print(f"Name: '{c.name}'")
    print(f"Slug: '{c.slug}'")
    print(f"Plan: {plan}")
    print(f"Expires: {expires}")
    print(f"Directors: {directors}")
    print("-" * 30)

c22 = Center.objects.filter(id=22).first()
if c22: print_center(c22)

c27 = Center.objects.filter(id=27).first()
if c27: print_center(c27)
