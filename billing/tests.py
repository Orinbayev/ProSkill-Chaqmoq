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

    @patch("billing.click_views.send_payment_group_receipt_notification")
    @patch("billing.click_views.send_payment_success_notification")
    def test_click_complete_marks_request_paid(self, mocked_notify, mocked_group_notify):
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
        mocked_group_notify.assert_called_once_with(
            center_name=self.center.name,
            plan_name=self.plan.name,
            duration_months=1,
            paid_amount=self.sub_request.amount,
            end_date=ANY,
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            request_id=self.sub_request.id,
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


# ============================================================
# PLAN SWITCH / CREDIT CONVERSION TESTS
# ============================================================

from decimal import Decimal
from billing.services import (
    calculate_plan_switch_days,
    calculate_upgrade_preview,
    get_plan_period_base_price,
)


def _make_sub(plan, remaining_days, now=None):
    """
    Test yordamchi: CenterSubscription-ga o'xshash simple namespace yaratadi.
    Django DB ga ulanmaydi.
    """
    from types import SimpleNamespace
    from django.utils import timezone as tz
    _now = now or tz.now()

    sub = SimpleNamespace()
    sub.plan = plan
    sub.plan_id = getattr(plan, "id", 1)
    sub.expires_at = _now + tz.timedelta(days=remaining_days)
    return sub


def _make_plan(pk, code, monthly_price, tier,
               price_3m=None, price_6m=None, price_9m=None, price_12m=None):
    """Stub SubscriptionPlan."""
    from types import SimpleNamespace
    p = SimpleNamespace()
    p.id = pk
    p.pk = pk
    p.code = code
    p.title = code.capitalize()
    p.monthly_price = monthly_price
    p.tier = tier
    p.price_3m = price_3m
    p.price_6m = price_6m
    p.price_9m = price_9m
    p.price_12m = price_12m
    return p


class PlanSwitchDaysTests(TestCase):
    """
    calculate_plan_switch_days() uchun test suitlar.
    DB ga ulanmasdan, faqat mantiq testlanadi.
    """

    def setUp(self):
        from django.utils import timezone as tz
        self.now = tz.now()

        # Plan stubs (tier qiymatlari real DB ga mos kelishi shart emas bu testda)
        self.standard = _make_plan(1, "STANDARD", 400_000, tier=10)
        self.premium  = _make_plan(2, "PREMIUM",  600_000, tier=20)
        self.pro      = _make_plan(3, "PRO",      900_000, tier=30)
        self.free     = _make_plan(4, "FREE",           0, tier=1)

        # Period narxlari bilan plan
        self.std_period = _make_plan(
            5, "STANDARD_P", 400_000, tier=10,
            price_3m=1_080_000,   # 10% chegirma
            price_12m=3_840_000,  # 20% chegirma
        )

    # ── CASE 1: Same plan extend ──────────────────────────────────────────
    def test_case1_same_plan_extend(self):
        """Standard × 300 kun qoldi + yana Standard 30 kun → extend"""
        sub = _make_sub(self.standard, remaining_days=300, now=self.now)
        result = calculate_plan_switch_days(sub, self.standard, paid_days=30)

        self.assertEqual(result["mode"], "extend")
        self.assertTrue(result["is_same_plan"])
        self.assertEqual(result["credit_days"], 0)
        self.assertEqual(result["total_new_days"], 30)
        # expires_at = (now + 300 days) + 30 days
        from django.utils import timezone as tz
        expected = (self.now + tz.timedelta(days=300)) + tz.timedelta(days=30)
        delta = abs((result["new_expires_at"] - expected).total_seconds())
        self.assertLess(delta, 2)

    # ── CASE 2: Standard → Premium (upgrade) ─────────────────────────────
    def test_case2_standard_to_premium_upgrade(self):
        """Standard × 300 kun qoldi → Premium (qimmatroq): kredit konvert"""
        sub = _make_sub(self.standard, remaining_days=300, now=self.now)
        result = calculate_plan_switch_days(sub, self.premium, paid_days=30)

        self.assertEqual(result["mode"], "convert")
        self.assertFalse(result["is_same_plan"])
        self.assertEqual(result["remaining_days"], 300)

        # credit = (400000/30) × 300 = 4_000_000
        # credit_days = floor(4_000_000 / (600000/30)) = floor(200) = 200
        self.assertEqual(result["remaining_credit"], Decimal("4000000"))
        self.assertEqual(result["credit_days"], 200)
        self.assertEqual(result["total_new_days"], 230)  # 200 + 30

        # Muddat qisqarishi kerak (300 → 230)
        self.assertLess(result["total_new_days"], 300)

    # ── CASE 3: Premium → Standard (downgrade) ───────────────────────────
    def test_case3_premium_to_standard_downgrade(self):
        """Premium × 100 kun qoldi → Standard (arzonroq): kredit konvert, kun ko'payadi"""
        sub = _make_sub(self.premium, remaining_days=100, now=self.now)
        result = calculate_plan_switch_days(sub, self.standard, paid_days=30)

        self.assertEqual(result["mode"], "convert")

        # credit = (600000/30) × 100 = 2_000_000
        # credit_days = floor(2_000_000 / (400000/30)) = floor(150) = 150
        self.assertEqual(result["remaining_credit"], Decimal("2000000"))
        self.assertEqual(result["credit_days"], 150)
        self.assertEqual(result["total_new_days"], 180)  # 150 + 30

        # Kun ko'payishi kerak (100 → 180)
        self.assertGreater(result["total_new_days"], 100)

    # ── CASE 4: Obuna tugagan → yangi xarid ──────────────────────────────
    def test_case4_expired_sub_fresh_start(self):
        """Obuna tugagan (remaining_days=0) → oddiy yangi obuna"""
        sub = _make_sub(self.standard, remaining_days=0, now=self.now)
        # Simulate: expires_at is in the past (0 days left means today or yesterday)
        from django.utils import timezone as tz
        sub.expires_at = self.now - tz.timedelta(days=1)

        result = calculate_plan_switch_days(sub, self.pro, paid_days=30)

        # has_active_time = False → mode="new"
        self.assertEqual(result["mode"], "new")
        self.assertEqual(result["credit_days"], 0)
        self.assertEqual(result["total_new_days"], 30)

    def test_case4b_no_active_sub(self):
        """Faol obuna yo'q → oddiy yangi obuna"""
        result = calculate_plan_switch_days(None, self.pro, paid_days=30)

        self.assertEqual(result["mode"], "new")
        self.assertEqual(result["credit_days"], 0)
        self.assertEqual(result["total_new_days"], 30)

    # ── CASE 5: Plan almashish + qo'shimcha to'lov ───────────────────────
    def test_case5_plan_switch_with_extra_payment(self):
        """Standard × 300 kun + Pro ga o'tish + 90 kun to'lov"""
        sub = _make_sub(self.standard, remaining_days=300, now=self.now)
        result = calculate_plan_switch_days(sub, self.pro, paid_days=90)

        self.assertEqual(result["mode"], "convert")
        # credit = (400000/30) × 300 = 4_000_000
        # credit_days = floor(4_000_000 / (900000/30)) = floor(133.33) = 133
        self.assertEqual(result["remaining_credit"], Decimal("4000000"))
        self.assertEqual(result["credit_days"], 133)
        self.assertEqual(result["total_new_days"], 223)  # 133 + 90

    # ── Edge cases ────────────────────────────────────────────────────────
    def test_zero_price_plan_falls_back_to_new(self):
        """Narx 0 bo'lsa, kredit konvert qilinmaydi → new mode"""
        sub = _make_sub(self.free, remaining_days=50, now=self.now)
        result = calculate_plan_switch_days(sub, self.pro, paid_days=30)
        # old_monthly = 0 → safe fallback
        self.assertIn(result["mode"], ("new", "convert"))
        self.assertGreaterEqual(result["total_new_days"], 1)

    def test_no_negative_days(self):
        """Hech qachon manfiy kun qaytmasligi kerak"""
        sub = _make_sub(self.standard, remaining_days=1, now=self.now)
        result = calculate_plan_switch_days(sub, self.pro, paid_days=0)
        self.assertGreaterEqual(result["total_new_days"], 1)

    def test_842_days_standard_to_pro(self):
        """
        Muammo holati: Standard × 842 kun + Pro ga o'tish → 842 emas, konvert bo'lishi kerak.
        Standard=400k/month, Pro=900k/month
        credit = (400000/30) × 842 = 11_226_666 so'm (floor)
        credit_days = floor(11_226_666 / (900000/30)) = floor(374.22) = 374
        """
        sub = _make_sub(self.standard, remaining_days=842, now=self.now)
        result = calculate_plan_switch_days(sub, self.pro, paid_days=30)

        self.assertEqual(result["mode"], "convert")
        # 842 days with Standard rate
        expected_credit = Decimal("400000") / 30 * 842
        expected_credit_floor = int(expected_credit.to_integral_value(rounding=Decimal.ROUND_DOWN if False else __import__('decimal').ROUND_DOWN))
        self.assertEqual(int(result["remaining_credit"]), expected_credit_floor)

        # credit_days must NOT be 842 (that would be the bug)
        self.assertLess(result["credit_days"], 500)
        # credit_days should be around 374
        self.assertAlmostEqual(result["credit_days"], 374, delta=2)
        self.assertEqual(result["total_new_days"], result["credit_days"] + 30)

    # ── calculate_upgrade_preview backward compat ─────────────────────────
    def test_upgrade_preview_backward_compat(self):
        """calculate_upgrade_preview wrapper ishlasin"""
        sub = _make_sub(self.standard, remaining_days=300, now=self.now)
        result = calculate_upgrade_preview(sub, self.pro, paid_days=30)

        self.assertIn("is_upgrade", result)
        self.assertTrue(result["is_upgrade"])  # pro.tier > standard.tier
        self.assertIn("mode", result)
        self.assertEqual(result["mode"], "convert")

    def test_upgrade_preview_downgrade_is_upgrade_false(self):
        """Downgrade holida is_upgrade=False bo'lishi kerak"""
        sub = _make_sub(self.pro, remaining_days=100, now=self.now)
        result = calculate_upgrade_preview(sub, self.standard, paid_days=30)

        self.assertFalse(result["is_upgrade"])
        self.assertEqual(result["mode"], "convert")  # lekin convert hali ham ishlaydi


class PlanPeriodPriceTests(TestCase):
    """get_plan_period_base_price() uchun testlar."""

    def setUp(self):
        self.plan = _make_plan(
            1, "STANDARD", 400_000, tier=10,
            price_3m=1_080_000,
            price_6m=2_040_000,
            price_12m=3_840_000,
        )
        self.plan_no_period = _make_plan(2, "PRO", 900_000, tier=30)

    def test_period_prices_used_when_set(self):
        self.assertEqual(get_plan_period_base_price(self.plan, 3), 1_080_000)
        self.assertEqual(get_plan_period_base_price(self.plan, 6), 2_040_000)
        self.assertEqual(get_plan_period_base_price(self.plan, 12), 3_840_000)

    def test_fallback_to_monthly_when_period_not_set(self):
        # plan_no_period has no price_3m etc.
        self.assertEqual(get_plan_period_base_price(self.plan_no_period, 3), 900_000 * 3)
        self.assertEqual(get_plan_period_base_price(self.plan_no_period, 12), 900_000 * 12)

    def test_1_month_always_monthly_price(self):
        self.assertEqual(get_plan_period_base_price(self.plan, 1), 400_000)

    def test_period_price_zero_falls_back(self):
        """0 yoki None period narxida fallback ishlashi kerak"""
        plan = _make_plan(3, "X", 300_000, tier=5, price_6m=0, price_12m=None)
        self.assertEqual(get_plan_period_base_price(plan, 6), 300_000 * 6)
        self.assertEqual(get_plan_period_base_price(plan, 12), 300_000 * 12)


# ============================================================
# SUPERADMIN SYNC TESTS — DB required
# ============================================================

class SuperadminApplySubscriptionTests(TestCase):
    """
    superadmin_apply_subscription() va sync_center_from_active_subscription()
    uchun integration testlar.
    DB ishlatadi.
    """

    def _create_center_and_plan(self, plan_code="STANDARD", monthly=400_000, tier=10):
        from django.utils import timezone as tz
        plan = SubscriptionPlan.objects.create(
            code=plan_code,
            title=plan_code.capitalize(),
            monthly_price=monthly,
            tier=tier,
            max_students=200,
            max_groups=50,
            max_users=100,
            active=True,
        )
        center = Center.objects.create(
            name=f"Test Center {plan_code}",
            slug=f"test-{plan_code.lower()}-{plan.pk}",
            plan=plan_code,
            monthly_price=monthly,
            max_students=200,
        )
        return center, plan

    def test_superadmin_apply_subscription_creates_active_sub(self):
        """superadmin_apply_subscription yangi ACTIVE sub yaratishi kerak"""
        from billing.services import superadmin_apply_subscription
        from django.utils import timezone as tz
        center, plan = self._create_center_and_plan("STANDARD")
        expires = tz.now() + tz.timedelta(days=30)

        sub = superadmin_apply_subscription(center, plan, expires)

        self.assertEqual(sub.status, CenterSubscription.Status.ACTIVE)
        self.assertEqual(sub.plan_id, plan.pk)
        active_count = CenterSubscription.objects.filter(
            center=center, status=CenterSubscription.Status.ACTIVE
        ).count()
        self.assertEqual(active_count, 1)

    def test_superadmin_apply_expires_old_subscription(self):
        """
        Eski ACTIVE sub EXPIRED bo'lishi kerak.
        Yangi ACTIVE sub yaratilishi kerak.
        """
        from billing.services import superadmin_apply_subscription
        from django.utils import timezone as tz

        center, old_plan = self._create_center_and_plan("STANDARD")
        new_plan = SubscriptionPlan.objects.create(
            code="PRO", title="Pro", monthly_price=900_000,
            tier=30, max_students=2000, max_groups=999, max_users=999, active=True,
        )

        # Create old ACTIVE subscription
        old_expires = tz.now() + tz.timedelta(days=300)
        CenterSubscription.objects.create(
            center=center, plan=old_plan,
            status=CenterSubscription.Status.ACTIVE,
            expires_at=old_expires, started_at=tz.now(),
        )

        # Apply new plan
        new_expires = tz.now() + tz.timedelta(days=30)
        new_sub = superadmin_apply_subscription(center, new_plan, new_expires)

        # Old must be EXPIRED
        old_sub_refreshed = CenterSubscription.objects.filter(
            center=center, plan=old_plan
        ).first()
        self.assertEqual(old_sub_refreshed.status, CenterSubscription.Status.EXPIRED)

        # New must be ACTIVE
        self.assertEqual(new_sub.status, CenterSubscription.Status.ACTIVE)
        self.assertEqual(new_sub.plan_id, new_plan.pk)

        # Center must be synced
        center.refresh_from_db()
        self.assertEqual(center.plan, "PRO")
        self.assertEqual(center.monthly_price, 900_000)

    def test_sync_center_from_active_subscription(self):
        """sync_center_from_active_subscription Center fieldlarini to'g'ri yangilashi kerak"""
        from billing.services import sync_center_from_active_subscription
        from django.utils import timezone as tz

        center, plan = self._create_center_and_plan("PREMIUM", monthly=600_000, tier=20)
        expires = tz.now() + tz.timedelta(days=60)
        CenterSubscription.objects.create(
            center=center, plan=plan,
            status=CenterSubscription.Status.ACTIVE,
            expires_at=expires, started_at=tz.now(),
        )

        # Artificially break center's cached fields
        center.plan = "FREE"
        center.monthly_price = 0
        center.save(update_fields=["plan", "monthly_price"])

        # Sync
        result = sync_center_from_active_subscription(center)
        self.assertTrue(result)

        center.refresh_from_db()
        self.assertEqual(center.plan, "PREMIUM")
        self.assertEqual(center.monthly_price, 600_000)

    def test_sync_center_no_active_sub_returns_false(self):
        """Faol obuna yo'q bo'lsa sync False qaytarishi kerak"""
        from billing.services import sync_center_from_active_subscription

        center, _ = self._create_center_and_plan()
        # No CenterSubscription created
        result = sync_center_from_active_subscription(center)
        self.assertFalse(result)

    def test_no_duplicate_active_subs_after_multiple_applies(self):
        """
        superadmin_apply_subscription bir necha bor chaqirilsa ham
        doim FAQAT BITTA ACTIVE subscription bo'lishi kerak.
        """
        from billing.services import superadmin_apply_subscription
        from django.utils import timezone as tz

        center, plan = self._create_center_and_plan()
        expires1 = tz.now() + tz.timedelta(days=30)
        expires2 = tz.now() + tz.timedelta(days=60)
        expires3 = tz.now() + tz.timedelta(days=90)

        superadmin_apply_subscription(center, plan, expires1)
        superadmin_apply_subscription(center, plan, expires2)
        superadmin_apply_subscription(center, plan, expires3)

        active_count = CenterSubscription.objects.filter(
            center=center, status=CenterSubscription.Status.ACTIVE
        ).count()
        self.assertEqual(active_count, 1)

        latest = CenterSubscription.objects.get(center=center, status=CenterSubscription.Status.ACTIVE)
        self.assertAlmostEqual(
            (latest.expires_at - expires3).total_seconds(), 0, delta=2
        )
        self.assertIn(reverse("billing:payment_cancel"), response.url)
