import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from billing.models import SubscriptionPlan, SubscriptionRequest
from accounts.models import Center

User = get_user_model()

# 1. Get a user and center
admin_user = User.objects.filter(is_superuser=True).first()
if not admin_user:
    print("No admin user found")
    exit()

center = Center.objects.first()
if not center:
    print("No center found")
    exit()

# 2. Get a plan
plan = SubscriptionPlan.objects.filter(active=True).first()
if not plan:
    print("No active plan found")
    exit()

# 3. Simulate order_create
print(f"Testing order_create with user: {admin_user.email}, center: {center.name}, plan: {plan.title}")
req = SubscriptionRequest.objects.create(
    user=admin_user,
    center=center,
    plan_name=plan.title,
    duration_months=1,
    price=plan.monthly_price,
    status=SubscriptionRequest.Status.PENDING,
)

print(f"Created SubscriptionRequest: {req.id} - Status: {req.status}")

# 4. Check if it appears in pending_orders query used by SuperAdmin
pending = SubscriptionRequest.objects.filter(status=SubscriptionRequest.Status.PENDING)
print(f"Total pending requests in DB: {pending.count()}")
for p in pending:
    print(f" - {p.id}: {p.center.name} - {p.plan_name} - {p.status}")

