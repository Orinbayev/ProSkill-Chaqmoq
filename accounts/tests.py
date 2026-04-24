import json
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import BranchRequest, Center, DirectorCenterAccess, User
from accounts.student_limit import check_student_limit
from billing.models import CenterSubscription, SubscriptionOrder, SubscriptionPlan
from education.models import Enrollment, Group, StudentGroupHistory


@override_settings(TIME_ZONE="Asia/Tashkent", USE_TZ=True)
class SuperadminPaymentHistoryApiTests(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_superuser(
            email="superadmin.payment@test.uz",
            password="strong-pass-123",
        )
        self.client.force_login(self.superadmin)

        self.center = Center.objects.create(name="Pay Center", slug="pay-center")
        self.plan = SubscriptionPlan.objects.create(
            code="PRO",
            title="PRO",
            name="PRO",
            monthly_price=100000,
            price=100000,
            duration_days=30,
            max_students=100,
            active=True,
        )

    def _create_paid_order(self, paid_at, *, amount=1000):
        return SubscriptionOrder.objects.create(
            center=self.center,
            plan=self.plan,
            duration_months=1,
            base_price=amount,
            discount_percent=0,
            final_price=amount,
            status=SubscriptionOrder.Status.PAID,
            paid_at=paid_at,
        )

    def test_payment_history_api_supports_pagination_and_page_size(self):
        now = timezone.now()
        for i in range(25):
            self._create_paid_order(now - timedelta(minutes=i), amount=1000 + i)

        response = self.client.get("/platform/api/finance/payments/?per_page=10&page=2")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("payments", payload)
        self.assertEqual(len(payload["payments"]), 10)
        self.assertIn("pagination", payload)
        self.assertEqual(payload["pagination"]["per_page"], 10)
        self.assertEqual(payload["pagination"]["page"], 2)
        self.assertEqual(payload["pagination"]["total_pages"], 3)
        self.assertEqual(payload["pagination"]["total_count"], 25)
        self.assertTrue(payload["pagination"]["has_previous"])
        self.assertTrue(payload["pagination"]["has_next"])

    def test_payment_history_api_returns_local_time_string(self):
        paid_at_utc = datetime(2026, 3, 24, 16, 55, tzinfo=dt_timezone.utc)
        order = self._create_paid_order(paid_at_utc, amount=1200)

        response = self.client.get("/platform/api/finance/payments/?per_page=10&page=1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["payments"])

        row = next((item for item in payload["payments"] if item["id"] == order.id), None)
        self.assertIsNotNone(row)

        expected_local = timezone.localtime(paid_at_utc).strftime("%d.%m.%Y %H:%M")
        self.assertEqual(row["paid_at"], expected_local)

    def test_superadmin_dashboard_shows_paginated_payment_history_and_local_time(self):
        now = timezone.now()
        for i in range(12):
            self._create_paid_order(now - timedelta(minutes=i), amount=2000 + i)

        paid_at_utc = datetime(2026, 3, 24, 16, 55, tzinfo=dt_timezone.utc)
        self._create_paid_order(paid_at_utc, amount=7777)

        response = self.client.get("/platform/?payments_per_page=50&payments_page=1")
        self.assertEqual(response.status_code, 200)

        html = response.content.decode("utf-8")
        self.assertIn("Sahifa 1 / 1", html)
        self.assertIn("50 ta", html)
        self.assertIn("To'lovlar Tarixi", html)

        expected_local = timezone.localtime(paid_at_utc).strftime("%d.%m.%Y %H:%M")
        self.assertIn(expected_local, html)


class CenterUiFeatureToggleTests(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_superuser(
            email="superadmin.features@test.uz",
            password="strong-pass-123",
        )
        self.client.force_login(self.superadmin)
        self.center = Center.objects.create(
            name="Feature Center",
            slug="feature-center",
            features={},
        )

    def test_superadmin_can_toggle_center_ui_feature(self):
        response = self.client.post(
            reverse("platform_global:toggle_center_ui_feature", args=[self.center.id]),
            data='{"feature":"ui_weekly_schedule","enabled":false}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"ok": True, "feature": "ui_weekly_schedule", "enabled": False},
        )

        self.center.refresh_from_db()
        self.assertEqual(self.center.features["ui_weekly_schedule"], False)

    def test_unknown_feature_returns_400(self):
        response = self.client.post(
            reverse("platform_global:toggle_center_ui_feature", args=[self.center.id]),
            data='{"feature":"ui_unknown","enabled":true}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["ok"], False)
        self.assertEqual(response.json()["error"], "Unknown feature")

    def test_center_manage_page_renders_feature_toggle_section(self):
        self.center.features = {"ui_weekly_schedule": False}
        self.center.save(update_fields=["features"])

        response = self.client.get(
            reverse("platform_global:center_manage", args=[self.center.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UI Funksiyalarini Boshqarish")
        self.assertContains(response, 'id="toggle-ui_weekly_schedule"')
        self.assertContains(response, 'id="feat-card-ui_weekly_schedule"')

    def test_center_manage_assign_existing_redirects_back_to_platform_center_manage(self):
        director = User.objects.create_user(
            email="assign-existing@test.uz",
            password="strong-pass-123",
            role="director",
            ism="Assign",
            familya="Director",
            center=None,
        )

        response = self.client.post(
            reverse("platform_global:center_manage", args=[self.center.id]),
            {
                "action": "assign_existing",
                "director_id": str(director.id),
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("platform_global:center_manage", args=[self.center.id]),
        )

        director.refresh_from_db()
        self.assertEqual(director.center_id, self.center.id)


class SuperadminCenterCreateTests(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_superuser(
            email="superadmin.centercreate@test.uz",
            password="strong-pass-123",
        )
        self.client.force_login(self.superadmin)
        self.plan = SubscriptionPlan.objects.create(
            code="CREATE_PRO",
            title="Create PRO",
            name="Create PRO",
            monthly_price=250000,
            price=250000,
            duration_days=30,
            max_students=180,
            active=True,
        )

    def test_center_create_post_succeeds_without_js_synced_capacity_limit(self):
        response = self.client.post(
            reverse("platform_global:center_create"),
            {
                "name": "Render Create Center",
                "slug": "render-create-center",
                "address": "Yunusobod",
                "plan": self.plan.code,
                "status": Center.STATUS_ACTIVE,
                "ism": "Ali",
                "familya": "Director",
                "email": "ali.director.centercreate@test.uz",
                "telefon1": "+998901234567",
                "password": "strong-pass-123",
                "duration": "1",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("platform_global:superadmin_dashboard"))

        center = Center.objects.get(slug="render-create-center")
        self.assertEqual(center.capacity_limit, self.plan.max_students)
        self.assertTrue(center.features.get("dashboard"))
        self.assertTrue(center.features.get("ui_exam_sessions"))
        self.assertTrue(
            User.objects.filter(
                email="ali.director.centercreate@test.uz",
                role="director",
                center=center,
            ).exists()
        )

    @patch("billing.services.superadmin_apply_subscription", side_effect=RuntimeError("sync failed"))
    def test_center_create_still_succeeds_when_subscription_sync_fails(self, _subscription_mock):
        response = self.client.post(
            reverse("platform_global:center_create"),
            {
                "name": "Fallback Create Center",
                "slug": "fallback-create-center",
                "address": "Chilonzor",
                "plan": self.plan.code,
                "status": Center.STATUS_ACTIVE,
                "ism": "Vali",
                "familya": "Director",
                "email": "vali.director.centercreate@test.uz",
                "telefon1": "+998907654321",
                "password": "strong-pass-123",
                "duration": "3",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("platform_global:superadmin_dashboard"))

        center = Center.objects.get(slug="fallback-create-center")
        self.assertEqual(center.plan, self.plan.code)
        self.assertEqual(center.monthly_price, self.plan.monthly_price)
        self.assertEqual(center.max_students, self.plan.max_students)
        self.assertTrue(center.expires_at is not None)
        self.assertTrue(
            User.objects.filter(
                email="vali.director.centercreate@test.uz",
                role="director",
                center=center,
            ).exists()
        )


class StudentLimitResolutionTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(
            name="Limit Center",
            slug="limit-center",
            capacity_limit=200,
            max_students=2000,
        )
        self.director = User.objects.create_user(
            email="director.limit@test.uz",
            password="strong-pass-123",
            role="director",
            ism="Limit",
            familya="Director",
            center=self.center,
        )
        self.plan = SubscriptionPlan.objects.create(
            code="LIMIT_2000",
            title="Limit 2000",
            name="LIMIT_2000",
            monthly_price=500000,
            price=500000,
            duration_days=30,
            max_students=2000,
            active=True,
        )
        CenterSubscription.objects.create(
            center=self.center,
            plan=self.plan,
            status=CenterSubscription.Status.ACTIVE,
            expires_at=timezone.now() + timedelta(days=30),
        )

    def _bulk_students(self, count: int):
        User.objects.bulk_create([
            User(
                email=f"student-limit-{idx}@test.uz",
                role="student",
                ism=f"Student{idx}",
                familya="Limit",
                center=self.center,
            )
            for idx in range(count)
        ])

    def test_check_student_limit_allows_261_of_2000(self):
        self._bulk_students(261)

        state = check_student_limit(self.center, raise_error=False, actor=self.director)

        self.assertFalse(state["is_at_limit"])
        self.assertEqual(state["current_count"], 261)
        self.assertEqual(state["limit"], 2000)
        self.assertIn(
            state["limit_source"],
            {"active_center_subscription.plan.max_students", "center.max_students"},
        )

    def test_check_student_limit_blocks_after_2000(self):
        self._bulk_students(2000)

        with self.assertRaises(ValidationError):
            check_student_limit(self.center, raise_error=True, actor=self.director)


class TenantRedirectRegressionTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Redirect Center", slug="redirect-center")
        self.director = User.objects.create_user(
            email="director.redirect@test.uz",
            password="strong-pass-123",
            role="director",
            ism="Redirect",
            familya="Director",
            center=self.center,
        )
        self.client.force_login(self.director)

    def test_core_home_reverse_points_to_web_dashboard(self):
        self.assertEqual(reverse("core:home"), "/")
        self.assertEqual(reverse("core:notifications"), "/notifications/")

    def test_add_user_redirects_back_to_web_home_after_save(self):
        response = self.client.post(
            reverse("accounts:add_user"),
            {
                "ism": "Ali",
                "familya": "Teacher",
                "otchestvo": "",
                "telefon1": "",
                "telefon2": "",
                "center": str(self.center.id),
                "role": "teacher",
                "email": "ali.teacher@test.uz",
                "password": "strong-pass-123",
                "oqituvchi_foizi": "45",
                "birth_date": "",
                "gender": "",
                "passport_id": "",
                "jshr": "",
                "address": "",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("core:home"))
        self.assertFalse(response["Location"].startswith("/api/mobile/"))
        self.assertTrue(User.objects.filter(email="ali.teacher@test.uz", role="teacher").exists())

    def test_add_user_redirects_to_next_when_provided(self):
        response = self.client.post(
            reverse("accounts:add_user") + "?role=student&next=/redirect-center/stat/students/",
            {
                "next": "/redirect-center/stat/students/",
                "ism": "Vali",
                "familya": "Student",
                "otchestvo": "",
                "telefon1": "",
                "telefon2": "",
                "center": str(self.center.id),
                "role": "student",
                "email": "vali.student@test.uz",
                "password": "strong-pass-123",
                "oqituvchi_foizi": "",
                "birth_date": "2010-01-01",
                "gender": "male",
                "passport_id": "",
                "jshr": "",
                "address": "",
                "group": "",
                "kurs_narhi": "",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/redirect-center/stat/students/")
        self.assertTrue(User.objects.filter(email="vali.student@test.uz", role="student").exists())

    def test_add_user_enrolls_student_into_selected_group(self):
        group = Group.objects.create(
            center=self.center,
            nom="English N1",
            kurs_narxi=650000,
            oqituvchi_foiz=45,
        )
        start_date = timezone.localdate()

        response = self.client.post(
            reverse("accounts:add_user") + "?role=student&drawer=1&next=/redirect-center/stat/students/",
            {
                "next": "/redirect-center/stat/students/",
                "ism": "Gulnoza",
                "familya": "Student",
                "otchestvo": "",
                "telefon1": "",
                "telefon2": "",
                "center": str(self.center.id),
                "role": "student",
                "email": "gulnoza.student@test.uz",
                "password": "strong-pass-123",
                "oqituvchi_foizi": "",
                "birth_date": "2010-01-01",
                "gender": "female",
                "passport_id": "",
                "jshr": "",
                "address": "",
                "group": str(group.id),
                "kurs_narhi": "",
                "group_start_date": start_date.isoformat(),
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "ok": True,
                "user": {
                    "id": User.objects.get(email="gulnoza.student@test.uz").id,
                    "full_name": "Gulnoza Student",
                    "email": "gulnoza.student@test.uz",
                },
            },
        )

        student = User.objects.get(email="gulnoza.student@test.uz")
        self.assertTrue(
            Enrollment.objects.filter(
                student=student,
                group=group,
                kurs_narhi=group.kurs_narxi,
                oqituvchi_foiz=group.oqituvchi_foiz,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            StudentGroupHistory.objects.filter(
                student=student,
                group=group,
                start_date=start_date,
                kurs_narxi=group.kurs_narxi,
                oqituvchi_foiz=group.oqituvchi_foiz,
            ).exists()
        )

    def test_add_user_enrolls_student_into_multiple_groups_from_group_assignments(self):
        odd_group = Group.objects.create(
            center=self.center,
            nom="Matematika",
            kurs_narxi=700000,
            oqituvchi_foiz=45,
            oy_dars_soni=12,
        )
        even_group = Group.objects.create(
            center=self.center,
            nom="Fizika",
            kurs_narxi=500000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )

        response = self.client.post(
            reverse("accounts:add_user") + "?role=student&drawer=1&next=/redirect-center/stat/students/",
            {
                "next": "/redirect-center/stat/students/",
                "ism": "Mehribon",
                "familya": "Student",
                "otchestvo": "",
                "telefon1": "",
                "telefon2": "",
                "center": str(self.center.id),
                "role": "student",
                "email": "mehribon.student@test.uz",
                "password": "strong-pass-123",
                "oqituvchi_foizi": "",
                "birth_date": "2011-01-01",
                "gender": "female",
                "passport_id": "",
                "jshr": "",
                "address": "",
                "group": "",
                "kurs_narhi": "",
                "group_start_date": "",
                "group_assignments": json.dumps([
                    {
                        "group_id": odd_group.id,
                        "start_date": "2026-04-24",
                        "lesson_pattern": "odd",
                        "course_price": 720000,
                        "teacher_percent": 50,
                        "monthly_lessons": 12,
                    },
                    {
                        "group_id": even_group.id,
                        "start_date": "2026-04-25",
                        "lesson_pattern": "even",
                        "course_price": 480000,
                        "teacher_percent": 35,
                        "monthly_lessons": 12,
                    },
                ]),
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 200)
        student = User.objects.get(email="mehribon.student@test.uz")

        odd_enrollment = Enrollment.objects.get(student=student, group=odd_group)
        even_enrollment = Enrollment.objects.get(student=student, group=even_group)

        self.assertEqual(odd_enrollment.joined_at.isoformat(), "2026-04-24")
        self.assertEqual(odd_enrollment.lesson_pattern, Enrollment.LESSON_PATTERN_ODD)
        self.assertEqual(odd_enrollment.kurs_narhi, 720000)
        self.assertEqual(odd_enrollment.oqituvchi_foiz, 50)

        self.assertEqual(even_enrollment.joined_at.isoformat(), "2026-04-25")
        self.assertEqual(even_enrollment.lesson_pattern, Enrollment.LESSON_PATTERN_EVEN)
        self.assertEqual(even_enrollment.kurs_narhi, 480000)
        self.assertEqual(even_enrollment.oqituvchi_foiz, 35)

        self.assertTrue(
            StudentGroupHistory.objects.filter(
                student=student,
                group=odd_group,
                start_date="2026-04-24",
            ).exists()
        )
        self.assertTrue(
            StudentGroupHistory.objects.filter(
                student=student,
                group=even_group,
                start_date="2026-04-25",
            ).exists()
        )

    def test_director_can_open_tenant_add_user_page(self):
        response = self.client.get(reverse("accounts:add_user") + "?role=student")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student Anketasi")


class DirectorMultiCenterTests(TestCase):
    def setUp(self):
        self.primary_center = Center.objects.create(name="Asosiy Center", slug="asosiy-center")
        self.extra_center = Center.objects.create(name="Qo'shimcha Center", slug="qoshimcha-center")
        self.other_center = Center.objects.create(name="Begona Center", slug="begona-center")
        self.director = User.objects.create_user(
            email="director.multicenter@test.uz",
            password="strong-pass-123",
            role="director",
            ism="Multi",
            familya="Director",
            center=self.primary_center,
        )
        DirectorCenterAccess.objects.create(
            director=self.director,
            center=self.extra_center,
            is_active=True,
        )
        self.client.force_login(self.director)

    def test_my_centers_returns_primary_extra_and_pending_requests(self):
        pending_request = BranchRequest.objects.create(
            requester=self.director,
            parent_center=self.primary_center,
            name="Yangi Sergeli",
            status=BranchRequest.Status.PENDING,
        )
        BranchRequest.objects.create(
            requester=self.director,
            parent_center=self.primary_center,
            name="Eski Yunusobod",
            status=BranchRequest.Status.APPROVED,
        )

        response = self.client.get(reverse("accounts:my_centers"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["centers"]), 2)
        self.assertEqual(
            {item["id"] for item in payload["centers"]},
            {self.primary_center.id, self.extra_center.id},
        )
        primary_row = next(item for item in payload["centers"] if item["id"] == self.primary_center.id)
        extra_row = next(item for item in payload["centers"] if item["id"] == self.extra_center.id)
        self.assertTrue(primary_row["is_primary"])
        self.assertTrue(primary_row["is_current"])
        self.assertFalse(extra_row["is_primary"])
        self.assertEqual(len(payload["pending_requests"]), 1)
        self.assertEqual(payload["pending_requests"][0]["id"], pending_request.id)

    def test_director_switch_center_sets_session_and_redirects_new_slug(self):
        response = self.client.post(
            reverse("accounts:director_switch_center"),
            data=json.dumps({"center_id": self.extra_center.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(self.client.session["active_center_id"], self.extra_center.id)
        self.assertEqual(payload["redirect_url"], f"/{self.extra_center.slug}/boshqaruv/")

        dashboard_response = self.client.get(reverse("core:director_boshqaruv"), follow=False)
        self.assertEqual(dashboard_response.status_code, 302)
        self.assertEqual(
            dashboard_response["Location"],
            f"/{self.extra_center.slug}/boshqaruv/",
        )

    def test_director_cannot_switch_to_unassigned_center(self):
        response = self.client.post(
            reverse("accounts:director_switch_center"),
            data=json.dumps({"center_id": self.other_center.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "Bu markazga ruxsat yo'q")

    @patch("accounts.views._send_branch_request_to_telegram", return_value="777")
    def test_branch_request_creates_record_and_saves_telegram_message_id(self, telegram_mock):
        response = self.client.post(
            reverse("accounts:branch_request"),
            data=json.dumps({
                "name": "Yangi Filial",
                "address": "Chilonzor 10",
                "phone": "+998901112233",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        created = BranchRequest.objects.get(pk=payload["request_id"])
        self.assertEqual(created.requester, self.director)
        self.assertEqual(created.parent_center, self.primary_center)
        self.assertEqual(created.telegram_message_id, "777")
        telegram_mock.assert_called_once()
