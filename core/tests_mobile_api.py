from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import Center, User
from chaqmoq.models import Ledger
from core.models import Notification
from education.models import Attendance, Category, Enrollment, Group, Payment, PaymentAllocation, TuitionMonth
from store.models import Lead, LeadStatus, Manba, Product, PurchaseRequest


class MobileAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.today = timezone.localdate()
        self.center = Center.objects.create(
            name="Mobile Center",
            slug="mobile-center",
            max_students=100,
            capacity_limit=100,
            phone="+998901234567",
        )
        self.category = Category.objects.create(center=self.center, name="IT")

        self.director = User.objects.create_user(
            email="director@mobile.test",
            password="testpass123",
            role="director",
            center=self.center,
            ism="Director",
            familya="Mobile",
        )
        self.teacher = User.objects.create_user(
            email="teacher@mobile.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Teacher",
            familya="One",
        )
        self.student = User.objects.create_user(
            email="student@mobile.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Student",
            familya="One",
        )
        self.parent = User.objects.create_user(
            email="parent@mobile.test",
            password="testpass123",
            role="parent",
            center=self.center,
            ism="Parent",
            familya="One",
        )
        self.parent.children.add(self.student)
        self.assertTrue(self.student.child_code)

        self.group = Group.objects.create(
            center=self.center,
            nom="Flutter Group",
            category_obj=self.category,
            oqituvchi=self.teacher,
            kurs_narxi=600_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            kurs_narhi=600_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        self.tuition_month = TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.enrollment,
            month=self.today.replace(day=1),
            fee_amount=600_000,
        )
        self.payment = Payment.objects.create(
            center=self.center,
            enrollment=self.enrollment,
            student=self.student,
            group=self.group,
            payment_type="cash",
            cash_amount=200_000,
            paid_date=self.today,
            created_by=self.director,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=self.payment,
            tuition_month=self.tuition_month,
            amount=200_000,
        )

        Attendance.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            teacher=self.teacher,
            date=self.today,
            status="present",
            present=True,
        )
        Attendance.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            teacher=self.teacher,
            date=self.today - timezone.timedelta(days=1),
            status="absent_unexcused",
            present=False,
        )

        Ledger.objects.create(
            student=self.student,
            beruvchi=self.teacher,
            group=self.group,
            rule_nom="Bonus",
            rule_tur="plus",
            ball=15,
        )
        Ledger.objects.create(
            student=self.student,
            beruvchi=self.teacher,
            group=self.group,
            rule_nom="Jarima",
            rule_tur="minus",
            ball=-5,
        )

        Notification.objects.create(
            center=self.center,
            recipient=self.student,
            sender=self.director,
            title="Test notification",
            message="Mobile test",
            type="system",
        )

        self.source = Manba.objects.create(center=self.center, nom="Instagram")
        self.status = LeadStatus.objects.create(center=self.center, nom="Yangi", code=LeadStatus.Code.NEW)
        Lead.objects.create(
            center=self.center,
            ism="Lead",
            familya="One",
            telefon1="+998901111111",
            yosh=17,
            manba=self.source,
            status=self.status,
            created_by=self.director,
        )

        self.product = Product.objects.create(
            center=self.center,
            nom="Headphones",
            narx_chaqmoq=50,
            narx_som=100_000,
            izoh="Store product",
        )

    def _path(self, suffix: str) -> str:
        return f"/{self.center.slug}/api/mobile/{suffix}"

    def test_auth_login_and_status_return_session_payload(self):
        response = self.client.post(
            self._path("auth/login/"),
            data='{"username":"director@mobile.test","password":"testpass123"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["user"]["role"], "director")
        self.assertEqual(payload["user"]["center"]["slug"], self.center.slug)
        self.assertFalse(payload["user"]["permissions"]["can_view_director_dashboard"])

        status_response = self.client.get(self._path("auth/status/"))
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_response.json()["authenticated"])

    def test_mobile_login_returns_bearer_token_and_me_accepts_it(self):
        response = self.client.post(
            "/api/mobile/auth/login/",
            data='{"login":"parent@mobile.test","password":"testpass123"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["role"], "parent")
        self.assertEqual(payload["center"]["slug"], self.center.slug)
        self.assertEqual(payload["token"], payload["access_token"])
        token = payload["access_token"]
        me_response = self.client.get(
            "/api/mobile/me/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["user"]["role"], "parent")

    def test_mobile_login_is_csrf_exempt_for_native_parent_and_student(self):
        csrf_client = Client(enforce_csrf_checks=True)
        for login, expected_role in (
            ("parent@mobile.test", "parent"),
            ("student@mobile.test", "student"),
        ):
            response = csrf_client.post(
                "/api/mobile/auth/login/",
                data=(
                    '{"login":"%s","password":"testpass123","center_slug":"%s"}'
                    % (login, self.center.slug)
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["role"], expected_role)

    def test_mobile_login_rejects_wrong_password_cleanly(self):
        response = self.client.post(
            "/api/mobile/auth/login/",
            data='{"login":"parent@mobile.test","password":"wrong"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        payload = response.json()
        self.assertEqual(payload["code"], "invalid_credentials")

    def test_parent_dashboard_returns_real_child_stats(self):
        self.client.force_login(self.parent)
        response = self.client.get(self._path("parent/dashboard/"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_child"]["id"], self.student.id)
        self.assertEqual(payload["stats"]["debt_amount"], 400_000)
        self.assertEqual(payload["stats"]["attendance_percent"], 50)
        self.assertIn("progress_chart", payload)

    def test_student_home_contains_debt_balance_groups_and_payments(self):
        self.client.force_login(self.student)
        response = self.client.get(self._path("student/home/"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()["student"]
        self.assertEqual(payload["balance"], 10)
        self.assertEqual(payload["debt"], 400_000)
        self.assertEqual(payload["groups"][0]["name"], "Flutter Group")
        self.assertEqual(payload["payments"][0]["amount"], 200_000)

    def test_parent_home_only_returns_own_children(self):
        self.client.force_login(self.parent)
        response = self.client.get(self._path("parent/home/"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["children"]), 1)
        self.assertEqual(payload["children"][0]["id"], self.student.id)

    def test_notifications_read_all_marks_unread_records(self):
        self.client.force_login(self.student)
        response = self.client.post(self._path("notifications/read-all/"))
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["updated_count"], 1)
        Notification.objects.filter(recipient=self.student).update(is_read=True)
        latest = Notification.objects.filter(recipient=self.student).order_by("-id").first()
        self.assertIsNotNone(latest)
        self.assertTrue(latest.is_read)

    def test_store_purchase_request_create_and_list(self):
        self.client.force_login(self.student)
        create_response = self.client.post(
            self._path("store/purchase-requests/create/"),
            data=f'{{"product_id": {self.product.id}, "qty": 2}}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(PurchaseRequest.objects.filter(student=self.student).count(), 1)

        list_response = self.client.get(self._path("store/purchase-requests/"))
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["items"][0]["qty"], 2)

    def test_parent_profile_patch_updates_name_phone_and_email(self):
        self.client.force_login(self.parent)
        response = self.client.patch(
            self._path("parent/profile/"),
            data='{"full_name":"Yangi Ota-ona Test","phone":"+998901112233","email":"parent.updated@mobile.test"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.get_full_name(), "Yangi Ota-ona Test")
        self.assertEqual(self.parent.telefon1, "+998901112233")
        self.assertEqual(self.parent.email, "parent.updated@mobile.test")
        self.assertEqual(response.json()["parent"]["phone"], "+998901112233")

    def test_change_password_endpoint_updates_parent_password(self):
        self.client.force_login(self.parent)
        response = self.client.post(
            self._path("auth/change-password/"),
            data='{"current_password":"testpass123","new_password":"newpass123","confirm_password":"newpass123"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.parent.refresh_from_db()
        self.assertTrue(self.parent.check_password("newpass123"))

    def test_parent_children_add_links_student_from_same_center(self):
        extra_student = User.objects.create_user(
            email="student.extra@mobile.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Extra",
            familya="Student",
        )
        self.client.force_login(self.parent)
        response = self.client.post(
            self._path("parent/children/add/"),
            data=f'{{"child_code":"{extra_student.child_code}"}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["success"])
        self.assertTrue(self.parent.children.filter(pk=extra_student.pk).exists())
        self.assertEqual(response.json()["child"]["id"], extra_student.id)
        self.assertEqual(response.json()["child"]["child_code"], extra_student.child_code)

    def test_parent_children_add_rejects_existing_child_link(self):
        self.client.force_login(self.parent)
        response = self.client.post(
            self._path("parent/children/add/"),
            data=f'{{"child_code":"{self.student.child_code}"}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "already_linked")

    def test_parent_children_add_rejects_student_from_other_center(self):
        other_center = Center.objects.create(
            name="Other Center",
            slug="other-center",
            max_students=50,
            capacity_limit=50,
        )
        foreign_student = User.objects.create_user(
            email="student.foreign@mobile.test",
            password="testpass123",
            role="student",
            center=other_center,
            ism="Foreign",
            familya="Student",
        )
        self.client.force_login(self.parent)
        response = self.client.post(
            self._path("parent/children/add/"),
            data=f'{{"child_code":"{foreign_student.child_code}"}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "center_mismatch")
        self.assertFalse(self.parent.children.filter(pk=foreign_student.pk).exists())
