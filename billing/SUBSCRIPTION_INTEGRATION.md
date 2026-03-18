# Subscription Integration (Before Click)

## What was added
- `SubscriptionPlan` extended with SaaS fields:
  - `name`, `price`, `duration_days`, `created_at`
- New user-level models:
  - `Subscription`
  - `PaymentTransaction`
- Existing `PromoCode` kept; compatibility aliases:
  - `discount_percent` -> `percent_off`
  - `is_active` -> `active`

## Core services
- `billing.services.activate_subscription(user, plan, start_date=None)`
  - Deactivates old active subscriptions
  - Creates a new active subscription
  - Automatically computes `end_date`
- `billing.services.check_subscription(user)`
  - Returns active subscription
  - Auto-deactivates if expired

## Access control
- New decorator: `billing.decorators.require_pro`
- Example:
  ```python
  from billing.decorators import require_pro

  @login_required
  @require_pro
  def premium_view(request):
      ...
  ```

## Student limit policy
- Implemented in `accounts/student_limit.py`:
  - `FREE` -> limit `50`
  - Paid plans (including `PRO`) -> `plan.max_students`
- Existing student add/import paths now use this policy.

## Auto expiration
- Cron-ready command:
  - `python manage.py expire_subscriptions`
- This command deactivates all expired user subscriptions.

## Frontend-ready endpoints
- Plans list: `GET /hisob/billing/api/plans/`
- Current subscription + billing history: `GET /hisob/billing/api/current-subscription/`

## Typical activation flow (after payment callback in future)
```python
from billing.services import activate_subscription

activate_subscription(user=request.user, plan="PRO")
```
