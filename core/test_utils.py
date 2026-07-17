"""Shared test helpers for provisioning a fully-active tenant center.

Most view-level test failures in this project are **not** product bugs — they
happen because the test center lacks the state that production centers always
have: an active subscription and the plan-features that ``@require_feature(...)``
and the subscription middleware expect. A bare ``Center.objects.create(...)``
center is gated out of finance/exam/certificate/HR/etc. pages, so requests get
redirected to ``billing:plans`` (302) and assertions on the real page fail.

Use :func:`create_active_center` (or :class:`ActiveCenterTestCase`) in ``setUp``
to get a center that passes every gate.

    from core.test_utils import create_active_center

    class MyTests(TestCase):
        def setUp(self):
            self.center = create_active_center(slug="my-center")

Keep :data:`REQUIRE_FEATURE_CODES` in sync with the codebase::

    grep -rhoE 'require_feature\\("[^"]+"' --include='*.py' .
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

# Every feature code guarded by @require_feature(...) across the codebase.
REQUIRE_FEATURE_CODES = (
    "analytics",
    "finance",
    "hr",
    "imtihon",
    "leads",
    "sertifikat",
    "store",
    "xarajatlar",
)

# Center-level UI module flags. These already default to True in
# core.center_features, but listing them keeps the helper self-documenting and
# robust if a default ever flips to False.
UI_FEATURE_CODES = (
    "ui_exam_sessions",
    "ui_failed_students",
    "ui_certificates",
    "ui_weekly_schedule",
)

ALL_FEATURE_CODES = REQUIRE_FEATURE_CODES + UI_FEATURE_CODES


def activate_center(center, *, features=None, max_students: int = 100_000, subscription_days: int = 365):
    """Turn an **already-created** center into a live, paid tenant in place.

    This is the one-line migration path for existing tests: keep your current
    ``Center.objects.create(...)`` and add ``activate_center(self.center)`` at
    the end of ``setUp``. Enables all ``@require_feature`` flags, attaches an
    ACTIVE subscription, and raises student/capacity limits.

    Returns the same ``center`` (saved).
    """
    from billing.models import CenterSubscription, SubscriptionPlan

    codes = tuple(features) if features is not None else ALL_FEATURE_CODES

    # Legacy JSON path in billing.services.get_feature_flags() adds every truthy
    # key here to the effective feature set — this un-gates @require_feature(...)
    # without needing PlanFeature catalog rows.
    merged = dict(getattr(center, "features", None) or {})
    merged.update({code: True for code in codes})
    center.features = merged

    changed = ["features"]
    for attr, value in (("status", getattr(center, "STATUS_ACTIVE", "ACTIVE")),
                        ("max_students", max_students),
                        ("capacity_limit", max_students)):
        if hasattr(center, attr):
            setattr(center, attr, value)
            changed.append(attr)
    center.save(update_fields=changed)

    # One shared plan across centers (code is unique, not per-center).
    plan, _ = SubscriptionPlan.objects.update_or_create(
        code="TEST_ALL",
        defaults={
            "title": "Test All",
            "name": "TEST_ALL",
            "tier": 99,
            "max_students": max_students,
            "duration_days": subscription_days,
        },
    )

    # unique_active_center_sub allows exactly one ACTIVE sub per center. Reuse an
    # existing active one if the test already made it, otherwise create it.
    CenterSubscription.objects.update_or_create(
        center=center,
        status=CenterSubscription.Status.ACTIVE,
        defaults={
            "plan": plan,
            "expires_at": timezone.now() + timezone.timedelta(days=subscription_days),
        },
    )

    # get_feature_flags() caches per-center for 60s; drop this center's key.
    cache.delete(f"billing:features:v4:{center.id}")
    return center


def create_active_center(
    name: str = "Test Center",
    slug: str = "test-center",
    *,
    features=None,
    max_students: int = 100_000,
    subscription_days: int = 365,
    **center_kwargs,
):
    """Create a :class:`Center` that behaves like a live, paid tenant.

    The center gets:

    * every ``@require_feature(...)`` flag enabled (via the legacy
      ``center.features`` JSON path that ``billing.services.get_feature_flags``
      reads), so finance/exam/certificate/HR/store pages are reachable;
    * an ACTIVE, non-expired :class:`CenterSubscription`, so the subscription
      middleware block check and ``@require_active_subscription`` both pass;
    * generous student/capacity limits so per-plan caps never trip a test.

    Args:
        name / slug: center identity.
        features: iterable of feature codes to enable. ``None`` enables all
            known codes (recommended default). Pass a subset to test gating.
        max_students: student + capacity limit to set on both center and plan.
        subscription_days: how far in the future the subscription expires.
        **center_kwargs: extra fields forwarded to ``Center.objects.create``.

    Returns:
        The saved ``Center`` instance.
    """
    from accounts.models import Center

    center = Center.objects.create(name=name, slug=slug, **center_kwargs)
    return activate_center(
        center,
        features=features,
        max_students=max_students,
        subscription_days=subscription_days,
    )


class ActiveCenterTestCase(TestCase):
    """``TestCase`` whose ``setUp`` provisions ``self.center`` as a live tenant.

    Subclass and override the class attributes as needed, then call
    ``super().setUp()`` first::

        class MyTests(ActiveCenterTestCase):
            center_slug = "my-center"

            def setUp(self):
                super().setUp()
                self.user = User.objects.create_user(..., center=self.center)
    """

    center_name = "Test Center"
    center_slug = "test-center"
    center_features = None  # None -> all features enabled

    def setUp(self):
        super().setUp()
        self.center = create_active_center(
            name=self.center_name,
            slug=self.center_slug,
            features=self.center_features,
        )
