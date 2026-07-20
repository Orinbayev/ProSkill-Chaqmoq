"""Phase 8: subscription enforcement lag — short TTL + invalidation."""
from __future__ import annotations

import time
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Center, User
from billing.models import CenterSubscription, SubscriptionPlan
from core import middleware as mw
from core.middleware import (
    _is_center_blocked,
    _sub_block_cache_ttl,
    _sub_check_interval,
    invalidate_center_cache,
    invalidate_center_tree_cache,
)
from core.test_utils import create_active_center


@override_settings(
    SUBSCRIPTION_CHECK_INTERVAL_SECONDS=120,
    SUBSCRIPTION_BLOCK_CACHE_TTL=15,
    CENTER_CACHE_TTL=15,
)
class SubscriptionLagTests(TestCase):
    def setUp(self):
        mw._CENTER_CACHE.clear()
        mw._SLUG_CACHE.clear()
        mw._SUB_BLOCK_CACHE.clear()
        self.center = create_active_center(name="Lag Center", slug="lag-c")
        self.plan = SubscriptionPlan.objects.filter(code="TEST_ALL").first()
        if self.plan is None:
            self.plan = SubscriptionPlan.objects.create(
                code="TEST_ALL",
                title="Test",
                name="TEST_ALL",
                tier=1,
                max_students=100,
                duration_days=30,
            )

    def test_settings_defaults_are_short(self):
        self.assertEqual(_sub_check_interval(), 120)
        self.assertEqual(_sub_block_cache_ttl(), 15)
        # Must be far below the old 1 hour / 60s defaults
        self.assertLess(_sub_check_interval(), 3600)
        self.assertLess(_sub_block_cache_ttl(), 60)

    def test_block_cache_invalidated_on_manual_block(self):
        # Warm cache as not blocked
        self.assertFalse(_is_center_blocked(self.center))
        self.assertIn(self.center.pk, mw._SUB_BLOCK_CACHE)

        sub = CenterSubscription.objects.filter(
            center=self.center, status=CenterSubscription.Status.ACTIVE
        ).first()
        self.assertIsNotNone(sub)
        sub.manual_block = True
        sub.save(update_fields=["manual_block"])

        # post_save signal should have cleared cache; re-check sees block
        self.assertTrue(_is_center_blocked(self.center))

    def test_invalidate_center_tree_includes_branch(self):
        branch = Center.objects.create(
            name="Branch",
            slug="lag-branch",
            parent_center=self.center,
            status=Center.STATUS_ACTIVE,
        )
        # warm both
        _is_center_blocked(self.center)
        _is_center_blocked(branch)
        self.assertTrue(mw._SUB_BLOCK_CACHE)

        invalidate_center_tree_cache(branch)
        # root key used for block cache
        self.assertNotIn(self.center.pk, mw._SUB_BLOCK_CACHE)

    def test_branch_uses_root_subscription_for_block(self):
        branch = Center.objects.create(
            name="Branch2",
            slug="lag-branch-2",
            parent_center=self.center,
            status=Center.STATUS_ACTIVE,
        )
        sub = CenterSubscription.objects.filter(
            center=self.center, status=CenterSubscription.Status.ACTIVE
        ).first()
        sub.manual_block = True
        sub.save(update_fields=["manual_block"])
        invalidate_center_cache(self.center.pk)

        self.assertTrue(_is_center_blocked(branch))

    def test_block_cache_ttl_respected(self):
        with override_settings(SUBSCRIPTION_BLOCK_CACHE_TTL=1):
            mw._SUB_BLOCK_CACHE.clear()
            self.assertFalse(_is_center_blocked(self.center))
            # force stale cached True without DB flip
            mw._SUB_BLOCK_CACHE[self.center.pk] = (True, time.monotonic())
            self.assertTrue(_is_center_blocked(self.center))
            time.sleep(1.05)
            # TTL expired → re-query → not blocked
            self.assertFalse(_is_center_blocked(self.center))
