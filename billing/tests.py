import json
import hashlib
from unittest.mock import ANY, patch
from django.test import TestCase
from django.test import override_settings
from django.test import RequestFactory
from django.utils import timezone
from datetime import date
from django.urls import reverse

from accounts.models import Center, User
from billing.click_views import create_order_and_redirect
from billing.models import (
    CenterSubscription,
    PaymentTransaction,
    SubscriptionPlan,
    Subscription,
    SubscriptionRequest,
)
from billing.services import (
    activate_subscription,
    check_subscription,
    click_transaction_key_for_request,
    get_center_student_limit,
)
from billing.utils import give_subscription


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

    def test_give_subscription_extends_existing_active(self):
        active_sub = Subscription.objects.create(
            user=self.user,
            plan=self.pro_plan,
            start_date=timezone.localdate() - timezone.timedelta(days=3),
            end_date=timezone.localdate() + timezone.timedelta(days=7),
            is_active=True,
        )

        updated = give_subscription(self.user, self.pro_plan)
        active_sub.refresh_from_db()

        self.assertEqual(updated.pk, active_sub.pk)
        self.assertTrue(active_sub.is_active)
        self.assertEqual(
            active_sub.end_date,
            timezone.localdate() + timezone.timedelta(days=7 + self.pro_plan.duration_days),
        )

    def test_give_subscription_creates_new_when_expired(self):
        old_sub = Subscription.objects.create(
            user=self.user,
            plan=self.pro_plan,
            start_date=timezone.localdate() - timezone.timedelta(days=60),
            end_date=timezone.localdate() - timezone.timedelta(days=1),
            is_active=True,
        )

        new_sub = give_subscription(self.user, self.free_plan)
        old_sub.refresh_from_db()
        self.assertFalse(old_sub.is_active)
        self.assertTrue(new_sub.is_active)
        self.assertEqual(new_sub.plan, self.free_plan)


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
            amount=300000,
            price=300000,
            status=SubscriptionRequest.Status.PENDING,
        )
        pending = SubscriptionRequest.objects.filter(
            user=self.user,
            status=SubscriptionRequest.Status.PENDING,
        )
        self.assertEqual(pending.count(), 1)

    def test_manual_approve_is_disabled(self):
        sub_request = SubscriptionRequest.objects.create(
            user=self.user,
            center=self.center,
            plan_name="PRO",
            duration_months=1,
            amount=300000,
            price=300000,
            status=SubscriptionRequest.Status.PENDING,
        )

        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("billing:subscription_request_approve", args=[sub_request.id]))
        self.assertEqual(response.status_code, 302)

        sub_request.refresh_from_db()
        self.assertEqual(sub_request.status, SubscriptionRequest.Status.PENDING)
        self.assertFalse(Subscription.objects.filter(user=self.user, is_active=True).exists())

    def test_manual_reject_is_disabled(self):
        sub_request = SubscriptionRequest.objects.create(
            user=self.user,
            center=self.center,
            plan_name="PRO",
            duration_months=1,
            amount=300000,
            price=300000,
            status=SubscriptionRequest.Status.PENDING,
        )

        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("billing:subscription_request_reject", args=[sub_request.id]))
        self.assertEqual(response.status_code, 302)

        sub_request.refresh_from_db()
        self.assertEqual(sub_request.status, SubscriptionRequest.Status.PENDING)


@override_settings(
    CLICK_SERVICE_ID="36302",
    CLICK_MERCHANT_ID="36302",
    CLICK_SECRET_KEY="test-click-secret",
)
class ClickPrepareCompleteTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Center Click", slug="center-click")
        self.user = User.objects.create_user(
            email="director.click@test.uz",
            password="strong-pass-123",
            role="director",
            ism="Director",
            familya="Click",
            center=self.center,
        )
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
        self.sub_request = SubscriptionRequest.objects.create(
            user=self.user,
            center=self.center,
            plan_name="PRO",
            duration_months=1,
            merchant_trans_id="ORD-TEST-CLICK-2000",
            amount=300000,
            price=300000,
            status=SubscriptionRequest.Status.PENDING,
        )

    @staticmethod
    def _prepare_sign(service_id, secret_key, click_trans_id, merchant_trans_id, amount, action, sign_time):
        payload = f"{click_trans_id}{service_id}{secret_key}{merchant_trans_id}{amount}{action}{sign_time}"
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _complete_sign(
        service_id,
        secret_key,
        click_trans_id,
        merchant_trans_id,
        merchant_prepare_id,
        amount,
        action,
        sign_time,
    ):
        payload = (
            f"{click_trans_id}{service_id}{secret_key}"
            f"{merchant_trans_id}{merchant_prepare_id}{amount}{action}{sign_time}"
        )
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    def test_click_prepare_success(self):
        click_trans_id = "2001"
        merchant_trans_id = self.sub_request.merchant_trans_id
        amount = str(self.sub_request.amount)
        sign_time = "2026-03-18 12:00:00"
        sign_string = self._prepare_sign(
            service_id="36302",
            secret_key="test-click-secret",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            amount=amount,
            action="0",
            sign_time=sign_time,
        )
        response = self.client.post(
            "/click/prepare/",
            data={
                "click_trans_id": click_trans_id,
                "service_id": "36302",
                "merchant_trans_id": merchant_trans_id,
                "transaction_param": str(self.sub_request.id),
                "amount": amount,
                "action": "0",
                "sign_time": sign_time,
                "sign_string": sign_string,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["error"], 0)
        self.assertEqual(payload["merchant_trans_id"], merchant_trans_id)
        self.assertEqual(payload["merchant_prepare_id"], str(self.sub_request.id))

    def test_click_prepare_requires_exact_merchant_trans_id(self):
        click_trans_id = "2001A"
        wrong_merchant_trans_id = str(self.sub_request.id + 999)
        amount = str(self.sub_request.amount)
        sign_time = "2026-03-18 12:00:30"
        sign_string = self._prepare_sign(
            service_id="36302",
            secret_key="test-click-secret",
            click_trans_id=click_trans_id,
            merchant_trans_id=wrong_merchant_trans_id,
            amount=amount,
            action="0",
            sign_time=sign_time,
        )
        response = self.client.post(
            "/click/prepare/",
            data={
                "click_trans_id": click_trans_id,
                "service_id": "36302",
                "merchant_trans_id": wrong_merchant_trans_id,
                "transaction_param": str(self.sub_request.id),
                "amount": amount,
                "action": "0",
                "sign_time": sign_time,
                "sign_string": sign_string,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error"], -5)

    @patch("billing.click_views.send_payment_success_notification")
    def test_click_complete_accepts_legacy_numeric_subscription_request_id(self, mocked_notify):
        legacy_request = SubscriptionRequest.objects.create(
            user=self.user,
            center=self.center,
            plan=self.plan,
            plan_name=self.plan.title,
            duration_months=1,
            merchant_trans_id=None,
            amount=300000,
            price=300000,
            status=SubscriptionRequest.Status.PENDING,
        )

        click_trans_id = "2001LEG"
        merchant_trans_id = str(legacy_request.id)
        merchant_prepare_id = str(legacy_request.id)
        amount = str(legacy_request.amount)
        sign_time = "2026-03-18 12:00:45"
        sign_string = self._complete_sign(
            service_id="36302",
            secret_key="test-click-secret",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            merchant_prepare_id=merchant_prepare_id,
            amount=amount,
            action="1",
            sign_time=sign_time,
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/click/complete/",
                data={
                    "click_trans_id": click_trans_id,
                    "service_id": "36302",
                    "merchant_trans_id": merchant_trans_id,
                    "transaction_param": merchant_prepare_id,
                    "merchant_prepare_id": merchant_prepare_id,
                    "amount": amount,
                    "action": "1",
                    "error": "0",
                    "sign_time": sign_time,
                    "sign_string": sign_string,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["error"], 0)
        legacy_request.refresh_from_db()
        self.assertEqual(legacy_request.status, SubscriptionRequest.Status.PAID)
        self.assertTrue(mocked_notify.called)

    @patch("billing.click_views.send_payment_success_notification")
    def test_click_complete_marks_request_paid(self, mocked_notify):
        click_trans_id = "2002"
        merchant_trans_id = self.sub_request.merchant_trans_id
        merchant_prepare_id = str(self.sub_request.id)
        amount = str(self.sub_request.amount)
        sign_time = "2026-03-18 12:01:00"
        sign_string = self._complete_sign(
            service_id="36302",
            secret_key="test-click-secret",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            merchant_prepare_id=merchant_prepare_id,
            amount=amount,
            action="1",
            sign_time=sign_time,
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/click/complete/",
                data={
                    "click_trans_id": click_trans_id,
                    "service_id": "36302",
                    "merchant_trans_id": merchant_trans_id,
                    "merchant_prepare_id": merchant_prepare_id,
                    "amount": amount,
                    "action": "1",
                    "error": "0",
                    "sign_time": sign_time,
                    "sign_string": sign_string,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["error"], 0)
        self.sub_request.refresh_from_db()
        self.assertEqual(self.sub_request.status, SubscriptionRequest.Status.PAID)
        self.assertTrue(mocked_notify.called)
        mocked_notify.assert_called_once_with(
            user=self.user,
            plan_name=self.plan.name,
            end_date=ANY,
            center_name=self.center.name,
            duration_months=1,
            paid_amount=self.sub_request.amount,
        )

    @patch("billing.click_views.send_payment_success_notification")
    def test_click_complete_extends_center_from_existing_future_end_date(self, mocked_notify):
        now = timezone.now()
        old_end_date = now + timezone.timedelta(days=10)
        active_sub = CenterSubscription.objects.create(
            center=self.center,
            plan=self.plan,
            status=CenterSubscription.Status.ACTIVE,
            started_at=now - timezone.timedelta(days=5),
            expires_at=old_end_date,
        )
        self.center.expires_at = old_end_date
        self.center.plan = self.plan.code
        self.center.save(update_fields=["expires_at", "plan"])

        click_trans_id = "2010"
        merchant_prepare_id = str(self.sub_request.id)
        amount = str(self.sub_request.amount)
        sign_time = "2026-03-18 12:07:00"
        sign_string = self._complete_sign(
            service_id="36302",
            secret_key="test-click-secret",
            click_trans_id=click_trans_id,
            merchant_trans_id=self.sub_request.merchant_trans_id,
            merchant_prepare_id=merchant_prepare_id,
            amount=amount,
            action="1",
            sign_time=sign_time,
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/click/complete/",
                data={
                    "click_trans_id": click_trans_id,
                    "service_id": "36302",
                    "merchant_trans_id": self.sub_request.merchant_trans_id,
                    "merchant_prepare_id": merchant_prepare_id,
                    "amount": amount,
                    "action": "1",
                    "error": "0",
                    "sign_time": sign_time,
                    "sign_string": sign_string,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error"], 0)
        active_sub.refresh_from_db()
        self.center.refresh_from_db()
        expected_end_date = old_end_date + timezone.timedelta(days=self.plan.duration_days)
        self.assertEqual(active_sub.expires_at, expected_end_date)
        self.assertEqual(self.center.expires_at, expected_end_date)
        self.assertTrue(mocked_notify.called)

    @patch("billing.click_views.send_payment_success_notification")
    def test_click_complete_sets_new_period_from_now_when_center_expired(self, mocked_notify):
        now = timezone.now()
        old_end_date = now - timezone.timedelta(days=2)
        active_sub = CenterSubscription.objects.create(
            center=self.center,
            plan=self.plan,
            status=CenterSubscription.Status.ACTIVE,
            started_at=now - timezone.timedelta(days=40),
            expires_at=old_end_date,
        )
        self.center.expires_at = old_end_date
        self.center.plan = self.plan.code
        self.center.save(update_fields=["expires_at", "plan"])

        click_trans_id = "2011"
        merchant_prepare_id = str(self.sub_request.id)
        amount = str(self.sub_request.amount)
        sign_time = "2026-03-18 12:08:00"
        sign_string = self._complete_sign(
            service_id="36302",
            secret_key="test-click-secret",
            click_trans_id=click_trans_id,
            merchant_trans_id=self.sub_request.merchant_trans_id,
            merchant_prepare_id=merchant_prepare_id,
            amount=amount,
            action="1",
            sign_time=sign_time,
        )

        before_call = timezone.now()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/click/complete/",
                data={
                    "click_trans_id": click_trans_id,
                    "service_id": "36302",
                    "merchant_trans_id": self.sub_request.merchant_trans_id,
                    "merchant_prepare_id": merchant_prepare_id,
                    "amount": amount,
                    "action": "1",
                    "error": "0",
                    "sign_time": sign_time,
                    "sign_string": sign_string,
                },
            )
        after_call = timezone.now()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error"], 0)
        active_sub.refresh_from_db()
        self.center.refresh_from_db()

        min_expected = before_call + timezone.timedelta(days=self.plan.duration_days)
        max_expected = after_call + timezone.timedelta(days=self.plan.duration_days)
        self.assertGreaterEqual(active_sub.expires_at, min_expected)
        self.assertLessEqual(active_sub.expires_at, max_expected)
        self.assertEqual(self.center.expires_at, active_sub.expires_at)
        self.assertTrue(mocked_notify.called)

    @patch("billing.click_views.send_payment_success_notification")
    def test_click_complete_is_idempotent_on_duplicate_callback(self, mocked_notify):
        click_trans_id = "2012"
        merchant_prepare_id = str(self.sub_request.id)
        amount = str(self.sub_request.amount)
        sign_time = "2026-03-18 12:09:00"
        sign_string = self._complete_sign(
            service_id="36302",
            secret_key="test-click-secret",
            click_trans_id=click_trans_id,
            merchant_trans_id=self.sub_request.merchant_trans_id,
            merchant_prepare_id=merchant_prepare_id,
            amount=amount,
            action="1",
            sign_time=sign_time,
        )

        with self.captureOnCommitCallbacks(execute=True):
            first_response = self.client.post(
                "/click/complete/",
                data={
                    "click_trans_id": click_trans_id,
                    "service_id": "36302",
                    "merchant_trans_id": self.sub_request.merchant_trans_id,
                    "merchant_prepare_id": merchant_prepare_id,
                    "amount": amount,
                    "action": "1",
                    "error": "0",
                    "sign_time": sign_time,
                    "sign_string": sign_string,
                },
            )
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.json()["error"], 0)

        self.center.refresh_from_db()
        first_end_date = self.center.expires_at

        with self.captureOnCommitCallbacks(execute=True):
            second_response = self.client.post(
                "/click/complete/",
                data={
                    "click_trans_id": click_trans_id,
                    "service_id": "36302",
                    "merchant_trans_id": self.sub_request.merchant_trans_id,
                    "merchant_prepare_id": merchant_prepare_id,
                    "amount": amount,
                    "action": "1",
                    "error": "0",
                    "sign_time": sign_time,
                    "sign_string": sign_string,
                },
            )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["error"], 0)
        self.center.refresh_from_db()
        self.assertEqual(self.center.expires_at, first_end_date)
        self.assertEqual(
            PaymentTransaction.objects.filter(
                transaction_id=click_transaction_key_for_request(self.sub_request.id),
                status=PaymentTransaction.Status.PAID,
            ).count(),
            1,
        )
        self.assertEqual(
            CenterSubscription.objects.filter(
                center=self.center,
                status=CenterSubscription.Status.ACTIVE,
            ).count(),
            1,
        )
        self.assertTrue(mocked_notify.called)

    def test_click_complete_rejects_wrong_amount(self):
        click_trans_id = "2003"
        merchant_trans_id = self.sub_request.merchant_trans_id
        merchant_prepare_id = str(self.sub_request.id)
        amount = "1"
        sign_time = "2026-03-18 12:02:00"
        sign_string = self._complete_sign(
            service_id="36302",
            secret_key="test-click-secret",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            merchant_prepare_id=merchant_prepare_id,
            amount=amount,
            action="1",
            sign_time=sign_time,
        )
        response = self.client.post(
            "/click/complete/",
            data={
                "click_trans_id": click_trans_id,
                "service_id": "36302",
                "merchant_trans_id": merchant_trans_id,
                "merchant_prepare_id": merchant_prepare_id,
                "amount": amount,
                "action": "1",
                "error": "0",
                "sign_time": sign_time,
                "sign_string": sign_string,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["error"], -2)
        self.sub_request.refresh_from_db()
        self.assertEqual(self.sub_request.status, SubscriptionRequest.Status.PENDING)

    def test_click_complete_rejects_fake_sign(self):
        response = self.client.post(
            "/click/complete/",
            data={
                "click_trans_id": "2004",
                "service_id": "36302",
                "merchant_trans_id": self.sub_request.merchant_trans_id,
                "merchant_prepare_id": str(self.sub_request.id),
                "amount": str(self.sub_request.amount),
                "action": "1",
                "error": "0",
                "sign_time": "2026-03-18 12:03:00",
                "sign_string": "fake-sign",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error"], -1)

    @patch("billing.click_views.send_payment_success_notification")
    def test_click_webhook_dispatches_complete(self, mocked_notify):
        click_trans_id = "2005"
        merchant_trans_id = self.sub_request.merchant_trans_id
        merchant_prepare_id = str(self.sub_request.id)
        amount = str(self.sub_request.amount)
        sign_time = "2026-03-18 12:04:00"
        sign_string = self._complete_sign(
            service_id="36302",
            secret_key="test-click-secret",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            merchant_prepare_id=merchant_prepare_id,
            amount=amount,
            action="1",
            sign_time=sign_time,
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/click/webhook/",
                data={
                    "click_trans_id": click_trans_id,
                    "service_id": "36302",
                    "merchant_trans_id": merchant_trans_id,
                    "merchant_prepare_id": merchant_prepare_id,
                    "amount": amount,
                    "action": "1",
                    "error": "0",
                    "sign_time": sign_time,
                    "sign_string": sign_string,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error"], 0)
        self.sub_request.refresh_from_db()
        self.assertEqual(self.sub_request.status, SubscriptionRequest.Status.PAID)
        self.assertTrue(mocked_notify.called)

    def test_click_webhook_rejects_unknown_action(self):
        response = self.client.post(
            "/api/click/webhook/",
            data={
                "click_trans_id": "2006",
                "merchant_trans_id": self.sub_request.merchant_trans_id,
                "action": "9",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error"], -3)

    def test_click_webhook_get_health(self):
        response = self.client.get("/api/click/webhook/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["endpoint"], "/api/click/webhook/")

    @patch("billing.click_views.send_payment_success_notification")
    def test_click_webhook_accepts_json_payload(self, mocked_notify):
        click_trans_id = "2007"
        merchant_trans_id = self.sub_request.merchant_trans_id
        merchant_prepare_id = str(self.sub_request.id)
        amount = str(self.sub_request.amount)
        sign_time = "2026-03-18 12:05:00"
        sign_string = self._complete_sign(
            service_id="36302",
            secret_key="test-click-secret",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            merchant_prepare_id=merchant_prepare_id,
            amount=amount,
            action="1",
            sign_time=sign_time,
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/click/webhook/",
                data=json.dumps(
                    {
                        "click_trans_id": click_trans_id,
                        "service_id": "36302",
                        "merchant_trans_id": merchant_trans_id,
                        "merchant_prepare_id": merchant_prepare_id,
                        "amount": amount,
                        "action": "1",
                        "error": "0",
                        "sign_time": sign_time,
                        "sign_string": sign_string,
                    }
                ),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error"], 0)
        self.assertTrue(mocked_notify.called)

    @patch("billing.click_views.send_payment_success_notification")
    def test_click_webhook_accepts_raw_form_body(self, mocked_notify):
        click_trans_id = "2008"
        merchant_trans_id = self.sub_request.merchant_trans_id
        merchant_prepare_id = str(self.sub_request.id)
        amount = str(self.sub_request.amount)
        sign_time = "2026-03-18 12:06:00"
        sign_string = self._complete_sign(
            service_id="36302",
            secret_key="test-click-secret",
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            merchant_prepare_id=merchant_prepare_id,
            amount=amount,
            action="1",
            sign_time=sign_time,
        )
        body = (
            f"click_trans_id={click_trans_id}"
            f"&service_id=36302"
            f"&merchant_trans_id={merchant_trans_id}"
            f"&merchant_prepare_id={merchant_prepare_id}"
            f"&amount={amount}"
            f"&action=1"
            f"&error=0"
            f"&sign_time={sign_time.replace(' ', '%20')}"
            f"&sign_string={sign_string}"
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.generic(
                "POST",
                "/api/click/webhook/",
                data=body,
                content_type="text/plain",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error"], 0)
        self.assertTrue(mocked_notify.called)


@override_settings(
    CLICK_SERVICE_ID="36302",
    CLICK_MERCHANT_ID="36302",
    CLICK_WEBHOOK_URL="https://example.uz/api/click/webhook/",
)
class ClickPaymentUrlCreateTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.center = Center.objects.create(name="Center URL", slug="center-url")
        self.user = User.objects.create_user(
            email="director.url@test.uz",
            password="strong-pass-123",
            role="director",
            ism="Director",
            familya="URL",
            center=self.center,
        )
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

    def test_click_create_returns_payment_url_and_creates_order(self):
        request = self.factory.post(
            "/hisob/billing/order/click-create/",
            data={"plan": self.plan.code, "months": "1", "promo": ""},
        )
        request.user = self.user
        request.center = self.center

        response = create_order_and_redirect(request)
        self.assertEqual(response.status_code, 200)

        payload = json.loads(response.content.decode("utf-8"))
        self.assertIn("payment_url", payload)
        self.assertIn("https://my.click.uz/services/pay?", payload["payment_url"])
        self.assertIn("service_id=36302", payload["payment_url"])
        self.assertIn("merchant_trans_id=", payload["payment_url"])
        self.assertIn("amount=300000", payload["payment_url"])
        self.assertIn("return_url=", payload["payment_url"])
        self.assertIn("webhook_prepare_url", payload)
        self.assertIn("webhook_complete_url", payload)
        self.assertEqual(payload.get("webhook_url"), "https://example.uz/api/click/webhook/")

        req = SubscriptionRequest.objects.get(pk=payload["order_id"])
        self.assertEqual(req.status, SubscriptionRequest.Status.PENDING)
        self.assertEqual(req.amount, 300000)
        self.assertEqual(req.merchant_trans_id, payload["merchant_trans_id"])
        self.assertEqual(payload["merchant_trans_id"], str(payload["order_id"]))

    def test_payment_status_api_returns_pending_status(self):
        sub_request = SubscriptionRequest.objects.create(
            user=self.user,
            center=self.center,
            plan_name="PRO",
            duration_months=1,
            merchant_trans_id="ORD-STATUS-2000",
            amount=300000,
            price=300000,
            status=SubscriptionRequest.Status.PENDING,
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("billing:payment_status_api"),
            data={"ids": str(sub_request.id)},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("items", payload)
        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        self.assertEqual(item["id"], sub_request.id)
        self.assertEqual(item["status"], SubscriptionRequest.Status.PENDING)
        self.assertGreaterEqual(item["seconds_left"], 0)
        self.assertEqual(item["merchant_trans_id"], sub_request.merchant_trans_id)

    def test_payment_success_redirects_to_cancel_when_status_cancelled(self):
        sub_request = SubscriptionRequest.objects.create(
            user=self.user,
            center=self.center,
            plan_name="PRO",
            duration_months=1,
            merchant_trans_id="ORD-CANCEL-2000",
            amount=300000,
            price=300000,
            status=SubscriptionRequest.Status.CANCELLED,
        )

        response = self.client.get(
            reverse("billing:payment_success"),
            data={"merchant_trans_id": sub_request.merchant_trans_id},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("billing:payment_cancel"), response.url)
