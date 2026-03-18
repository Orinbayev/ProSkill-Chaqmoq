import os
import django
import time
import hashlib
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from accounts.models import Center
from billing.models import SubscriptionPlan, SubscriptionRequest
from billing.click_views import click_webhook
from billing.utils import _sign_payload

User = get_user_model()
admin_user = User.objects.filter(is_superuser=True).first()
center = Center.objects.first()
plan = SubscriptionPlan.objects.filter(active=True).first()

if not admin_user or not center or not plan:
    print("Cannot run mock: Missing data")
    exit()

# Set up test config
settings.CLICK_SERVICE_ID = "12345"
settings.CLICK_MERCHANT_ID = "67890"
settings.CLICK_SECRET_KEY = "test_key"

req = SubscriptionRequest.objects.create(
    user=admin_user,
    center=center,
    plan_name=plan.title,
    duration_months=3,
    amount=plan.monthly_price * 3,
    price=plan.monthly_price * 3,
    status=SubscriptionRequest.Status.PENDING,
)
req.merchant_trans_id = f"TEST-{req.id}"
req.save()

factory = RequestFactory()

# Mock Prepare
prepare_payload = {
    "click_trans_id": "999999",
    "service_id": settings.CLICK_SERVICE_ID,
    "merchant_id": settings.CLICK_MERCHANT_ID,
    "merchant_trans_id": req.merchant_trans_id,
    "transaction_param": str(req.id),
    "amount": str(float(req.amount)),
    "action": "0",
    "error": "0",
    "error_note": "Success",
    "sign_time": "2023-10-01 12:00:00",
}

sign_str = _sign_payload(
    prepare_payload["click_trans_id"],
    prepare_payload["service_id"],
    settings.CLICK_SECRET_KEY,
    prepare_payload["merchant_trans_id"],
    prepare_payload["amount"],
    prepare_payload["action"],
    prepare_payload["sign_time"],
)
prepare_payload["sign_string"] = hashlib.md5(sign_str.encode("utf-8")).hexdigest()

request = factory.post("/api/click/webhook/", prepare_payload)
response = click_webhook(request)
print("PREPARE RES:", response.content.decode("utf-8"))

# Mock Complete
complete_payload = {
    "click_trans_id": "999999",
    "service_id": settings.CLICK_SERVICE_ID,
    "merchant_id": settings.CLICK_MERCHANT_ID,
    "merchant_trans_id": req.merchant_trans_id,
    "merchant_prepare_id": str(req.id), # Expected prepare id
    "transaction_param": str(req.id),
    "amount": str(float(req.amount)),
    "action": "1",
    "error": "0",
    "error_note": "Success",
    "sign_time": "2023-10-01 12:05:00",
}

comp_sign_str = _sign_payload(
    complete_payload["click_trans_id"],
    complete_payload["service_id"],
    settings.CLICK_SECRET_KEY,
    complete_payload["merchant_trans_id"],
    complete_payload["amount"],
    complete_payload["action"],
    complete_payload["sign_time"],
    complete_payload["merchant_prepare_id"],
)
complete_payload["sign_string"] = hashlib.md5(comp_sign_str.encode("utf-8")).hexdigest()

comp_request = factory.post("/api/click/webhook/", complete_payload)
comp_response = click_webhook(comp_request)
print("COMPLETE RES:", comp_response.content.decode("utf-8"))

req.refresh_from_db()
print("Final Status:", req.status)
