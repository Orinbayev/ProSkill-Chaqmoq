from django.test import TestCase
from django.utils import timezone
from datetime import date
from django.urls import reverse

from accounts.models import Center, User
from billing.models import SubscriptionPlan, Subscription, SubscriptionRequest
from billing.services import (
    activate_subscription,
    check_subscription,
    get_center_student_limit,
)


class UserSubscriptionServiceTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Test Center", slug="test-center")
        self.user = User.objects.create_user(
            email="director@test.uz",
            password="strong-pass-123",
            role="director",
            ism="Ali",
            familya="Valiyev",
            center=self.center,
        )
        self.free_plan = SubscriptionPlan.objects.create(
            code="FREE",
            title="Free",
            name="FREE",
            monthly_price=0,
            price=0,
            duration_days=30,
            max_students=999,
        )
        self.pro_plan = SubscriptionPlan.objects.create(
            code="PRO",
            title="Pro",
            name="PRO",
            monthly_price=120000,
            price=120000,
            duration_days=30,
            max_students=150,
        )

    def test_activate_subscription_deactivates_previous(self):
        start = date(2026, 1, 1)
        first = activate_subscription(self.user, self.pro_plan, start_date=start)
        self.assertTrue(first.is_active)
        self.assertEqual(first.end_date, start + timezone.timedelta(days=30))

        second = activate_subscription(self.user, self.free_plan, start_date=start)
        first.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)
        self.assertEqual(Subscription.objects.filter(user=self.user, is_active=True).count(), 1)

    def test_check_subscription_deactivates_expired(self):
        sub = Subscription.objects.create(
            user=self.user,
            plan=self.pro_plan,
            start_date=timezone.localdate() - timezone.timedelta(days=40),
            end_date=timezone.localdate() - timezone.timedelta(days=1),
            is_active=True,
        )
        self.assertIsNone(check_subscription(self.user))
        sub.refresh_from_db()
        self.assertFalse(sub.is_active)

    def test_student_limit_policy_free_vs_paid(self):
        # No subscription -> FREE limit
        self.assertEqual(get_center_student_limit(self.center, actor=self.user), 50)

        activate_subscription(self.user, self.free_plan)
        self.assertEqual(get_center_student_limit(self.center, actor=self.user), 50)

        activate_subscription(self.user, self.pro_plan)
        self.assertEqual(get_center_student_limit(self.center, actor=self.user), 150)


class SubscriptionRequestFlowTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Center A", slug="center-a")
        self.user = User.objects.create_user(
            email="director.centera@test.uz",
            password="strong-pass-123",
            role="director",
            ism="Director",
            familya="A",
            center=self.center,
        )
        self.superadmin = User.objects.create(
            email="superadmin@test.uz",
            role="director",
            ism="Super",
            familya="Admin",
            is_superuser=True,
            is_staff=True,
        )
        self.superadmin.set_password("super-pass-123")
        self.superadmin.save()

        self.plan = SubscriptionPlan.objects.create(
            code="PRO",
            title="PRO",
            name="PRO",
            monthly_price=300000,
            price=300000,
            duration_days=30,
            max_students=120,
            active=True,
        )

    def test_request_persists_and_user_pending_query(self):
        SubscriptionRequest.objects.create(
            user=self.user,
            center=self.center,
            plan_name="PRO",
            duration_months=1,
            price=300000,
            status=SubscriptionRequest.Status.PENDING,
        )
        pending = SubscriptionRequest.objects.filter(
            user=self.user,
            status=SubscriptionRequest.Status.PENDING,
        )
        self.assertEqual(pending.count(), 1)

    def test_superadmin_approve_activates_subscription(self):
        sub_request = SubscriptionRequest.objects.create(
            user=self.user,
            center=self.center,
            plan_name="PRO",
            duration_months=1,
            price=300000,
            status=SubscriptionRequest.Status.PENDING,
        )

        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("billing:subscription_request_approve", args=[sub_request.id]))
        self.assertEqual(response.status_code, 302)

        sub_request.refresh_from_db()
        self.assertEqual(sub_request.status, SubscriptionRequest.Status.APPROVED)
        self.assertTrue(Subscription.objects.filter(user=self.user, is_active=True).exists())

    def test_superadmin_reject_marks_rejected(self):
        sub_request = SubscriptionRequest.objects.create(
            user=self.user,
            center=self.center,
            plan_name="PRO",
            duration_months=1,
            price=300000,
            status=SubscriptionRequest.Status.PENDING,
        )

        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("billing:subscription_request_reject", args=[sub_request.id]))
        self.assertEqual(response.status_code, 302)

        sub_request.refresh_from_db()
        self.assertEqual(sub_request.status, SubscriptionRequest.Status.REJECTED)
