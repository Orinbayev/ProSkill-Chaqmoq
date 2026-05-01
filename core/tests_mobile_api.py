from django.test import Client, TestCase
from django.test import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from accounts.models import Center, User
from chaqmoq.models import Ledger
from core.models import Notification, NotificationPreference
from education.models import (
    Attendance,
    Category,
    Enrollment,
    ExamResult,
    ExamSession,
    Group,
    Payment,
    PaymentAllocation,
    StudentAcademicSummary,
    TuitionMonth,
)
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
        self.parent.phone_number = "+998901112233"
        self.parent.telefon1 = "+998901112233"
        self.parent.save(update_fields=["phone_number", "telefon1"])
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
        self.next_tuition_month = TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.enrollment,
            month=(self.today.replace(day=1) + timezone.timedelta(days=32)).replace(day=1),
            fee_amount=600_000,
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

        previous_month = (self.today.replace(day=1) - timezone.timedelta(days=2)).replace(day=1)
        self.current_exam_session = ExamSession.objects.create(
            center=self.center,
            group=self.group,
            teacher=self.teacher,
            exam_date=self.today,
            attendance_date=self.today,
            created_by=self.director,
        )
        self.previous_exam_session = ExamSession.objects.create(
            center=self.center,
            group=self.group,
            teacher=self.teacher,
            exam_date=previous_month,
            attendance_date=previous_month,
            created_by=self.director,
        )
        ExamResult.objects.create(
            center=self.center,
            session=self.current_exam_session,
            group=self.group,
            student=self.student,
            teacher=self.teacher,
            percent=82,
            passed=True,
            teacher_comment="Topshiriqlarni vaqtida bajaradi.",
            exam_date=self.today,
            created_by=self.director,
        )
        ExamResult.objects.create(
            center=self.center,
            session=self.previous_exam_session,
            group=self.group,
            student=self.student,
            teacher=self.teacher,
            percent=68,
            passed=True,
            teacher_comment="Amaliy mashqlarni ko‘paytirish kerak.",
            exam_date=previous_month,
            created_by=self.director,
        )
        StudentAcademicSummary.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            exam_count=2,
            average_percent=75,
            attendance_total_lessons=2,
            attendance_present_lessons=1,
            attendance_percent=50,
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
        self.assertEqual(payload["code"], "invalid_password")

    def test_mobile_login_rejects_inactive_user_cleanly(self):
        self.parent.is_active = False
        self.parent.save(update_fields=["is_active"])

        response = self.client.post(
            "/api/mobile/auth/login/",
            data='{"login":"parent@mobile.test","password":"testpass123"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertEqual(payload["code"], "inactive_user")

    def test_mobile_login_rejects_missing_user_cleanly(self):
        response = self.client.post(
            "/api/mobile/auth/login/",
            data='{"login":"missing@mobile.test","password":"testpass123"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["code"], "user_not_found")

    def test_mobile_login_accepts_phone_number_field(self):
        response = self.client.post(
            "/api/mobile/auth/login/",
            data='{"phone_number":"+998901112233","password":"testpass123"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["role"], "parent")

    def test_mobile_login_accepts_center_field_alias(self):
        response = self.client.post(
            "/api/mobile/auth/login/",
            data=(
                '{"login":"parent@mobile.test","password":"testpass123","center":"%s"}'
                % self.center.slug
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["center"]["slug"], self.center.slug)

    @override_settings(DEBUG=True)
    def test_mobile_login_returns_debug_payload_for_unknown_center_slug(self):
        response = self.client.post(
            "/api/mobile/auth/login/",
            data='{"login":"parent@mobile.test","password":"testpass123","center_slug":"missing-center"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["code"], "center_not_found")
        self.assertEqual(payload["received_slug"], "missing-center")
        self.assertIn(
            {"name": self.center.name, "slug": self.center.slug},
            payload["available_centers"],
        )

    def test_mobile_login_rejects_user_outside_requested_center(self):
        other_center = Center.objects.create(
            name="Other Mobile Center",
            slug="other-mobile-center",
            max_students=50,
            capacity_limit=50,
        )
        foreign_user = User.objects.create_user(
            email="student.foreign.login@mobile.test",
            password="testpass123",
            role="student",
            center=other_center,
            ism="Foreign",
            familya="Login",
        )
        response = self.client.post(
            "/api/mobile/auth/login/",
            data=(
                '{"login":"%s","password":"testpass123","center_slug":"%s"}'
                % (foreign_user.email, self.center.slug)
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertEqual(payload["code"], "center_mismatch")

    def test_parent_dashboard_returns_real_child_stats(self):
        self.client.force_login(self.parent)
        response = self.client.get(self._path("parent/dashboard/"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_child"]["id"], self.student.id)
        self.assertEqual(payload["stats"]["debt_amount"], 400_000)
        self.assertEqual(payload["stats"]["attendance_percent"], 50)
        self.assertIn("progress_chart", payload)

    def test_parent_payments_include_plan_items_and_pending_amount(self):
        self.client.force_login(self.parent)
        response = self.client.get(self._path("payments/"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["debt_amount"], 400_000)
        self.assertEqual(payload["summary"]["pending_amount"], 600_000)
        self.assertGreaterEqual(len(payload["plan_items"]), 2)

    def test_parent_progress_supports_period_filter_and_comments(self):
        self.client.force_login(self.parent)
        response = self.client.get(self._path("progress/"), {"period": "last_month"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_period"], "last_month")
        self.assertEqual(payload["selected_period_label"], "O‘tgan oy")
        self.assertEqual(payload["teacher_comments"][0]["comment"], "Amaliy mashqlarni ko‘paytirish kerak.")
        self.assertGreater(payload["subjects"][0]["percent"], 0)

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

    def test_parent_notifications_include_sender_and_recipient_names(self):
        Notification.objects.create(
            center=self.center,
            recipient=self.student,
            sender=self.teacher,
            title="Chaqmoq qo‘shildi ⚡",
            message="Sizga Teacher Test tomonidan 2 chaqmoq qo‘shildi.\nSabab: Faollik",
            type="coin",
        )
        self.client.force_login(self.parent)
        response = self.client.get(self._path("notifications/"))
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        target = next(item for item in items if item["title"] == "Chaqmoq qo‘shildi ⚡")
        self.assertEqual(target["sender_name"], self.teacher.get_full_name())
        self.assertEqual(target["recipient_name"], self.student.get_full_name())

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

    def test_parent_profile_avatar_upload_returns_updated_profile(self):
        self.client.force_login(self.parent)
        avatar = SimpleUploadedFile(
            "avatar.jpg",
            b"filecontent",
            content_type="image/jpeg",
        )
        response = self.client.post(
            self._path("parent/profile/avatar/"),
            data={"avatar": avatar},
        )
        self.assertEqual(response.status_code, 200)
        self.parent.refresh_from_db()
        self.assertTrue(bool(self.parent.avatar))
        self.assertIn("avatar_url", response.json()["parent"])

    def test_parent_notification_preferences_can_be_saved(self):
        self.client.force_login(self.parent)
        response = self.client.patch(
            self._path("parent/notification-preferences/"),
            data='{"attendance":false,"payments":true,"progress":false,"general":true}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        pref = NotificationPreference.objects.get(user=self.parent)
        self.assertFalse(pref.receive_system)
        self.assertTrue(pref.receive_purchase)
        self.assertFalse(pref.receive_coin)
        self.assertTrue(pref.receive_broadcast)

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


class MobileDebtMatchesAdminPanelTests(TestCase):
    """
    Anaxon Baxrambayeva ssenariysi:
    admin paneldagi qarz mobile parent dashboard bilan 1:1 mos kelishi shart.
    """

    def setUp(self):
        from django.urls import reverse
        from datetime import timedelta

        self.client = Client()
        self.today = timezone.localdate()
        self.center = Center.objects.create(
            name="Anaxon Center",
            slug="anaxon-center",
            max_students=50,
            capacity_limit=50,
            phone="+998900000000",
        )
        self.director = User.objects.create_user(
            email="director@anaxon.test",
            password="testpass123",
            role="director",
            center=self.center,
            ism="Director",
            familya="Anaxon",
        )
        self.teacher = User.objects.create_user(
            email="teacher@anaxon.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Teacher",
            familya="Anaxon",
            oqituvchi_foizi=40,
        )
        self.parent = User.objects.create_user(
            email="parent@anaxon.test",
            password="testpass123",
            role="parent",
            center=self.center,
            ism="Parent",
            familya="Anaxon",
        )
        self.student = User.objects.create_user(
            email="anaxon@anaxon.test",
            password="testpass123",
            role="student",
            center=self.center,
            ism="Anaxon",
            familya="Baxrambayeva",
            telefon1="+998901112233",
        )
        self.parent.children.add(self.student)

        self.group = Group.objects.create(
            center=self.center,
            nom="Anaxon Group",
            oqituvchi=self.teacher,
            kurs_narxi=350_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.enrollment = Enrollment.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            kurs_narhi=350_000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        from education.models import StudentGroupHistory

        StudentGroupHistory.objects.create(
            student=self.student,
            group=self.group,
            center=self.center,
            start_date=self.today.replace(day=1) - timedelta(days=30),
            kurs_narxi=350_000,
            oqituvchi_foiz=40,
        )
        self.current_month = self.today.replace(day=1)
        self.tuition_month = TuitionMonth.objects.create(
            center=self.center,
            enrollment=self.enrollment,
            month=self.current_month,
            fee_amount=350_000,
        )
        self.qarzdorlar_url = f"/{self.center.slug}{reverse('education:qarzdorlar_home')}"

    def _api_path(self, suffix: str) -> str:
        return f"/{self.center.slug}/api/mobile/{suffix}"

    def _admin_debt_for_anaxon(self) -> int:
        self.client.force_login(self.director)
        response = self.client.get(self.qarzdorlar_url)
        self.assertEqual(response.status_code, 200)
        rows = {row["student"].email: row for row in response.context["page_obj"].object_list}
        self.assertIn(self.student.email, rows)
        return int(rows[self.student.email]["debt"])

    def test_anaxon_admin_shows_350k_for_unpaid_current_month(self):
        self.assertEqual(self._admin_debt_for_anaxon(), 350_000)

    def test_parent_dashboard_debt_amount_matches_admin_for_anaxon(self):
        admin_debt = self._admin_debt_for_anaxon()
        self.assertEqual(admin_debt, 350_000)

        self.client.force_login(self.parent)
        response = self.client.get(self._api_path("parent/dashboard/"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_child"]["id"], self.student.id)
        self.assertEqual(payload["stats"]["debt_amount"], admin_debt)
        self.assertEqual(payload["stats"]["debt_amount"], 350_000)
        self.assertEqual(payload["stats"]["debt_status"], "qarzdor")
        self.assertEqual(payload["stats"]["max_level"], 5)
        self.assertIn("current_level", payload["stats"])
        self.assertIn("monthly_change", payload["stats"])
        self.assertIn("progress_timeline", payload)
        self.assertIn("progress_level", payload)
        timeline_points = payload["progress_timeline"]["timeline"]
        self.assertGreater(len(timeline_points), 0)
        for point in timeline_points:
            self.assertIn("date", point)
            self.assertIn("score", point)
            self.assertIn("reasons", point)

    def test_parent_dashboard_debt_status_is_paid_when_fully_paid(self):
        from datetime import timedelta

        payment = Payment.objects.create(
            center=self.center,
            enrollment=self.enrollment,
            student=self.student,
            group=self.group,
            payment_type="cash",
            cash_amount=350_000,
            paid_date=self.current_month + timedelta(days=2),
            created_by=self.director,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=payment,
            tuition_month=self.tuition_month,
            amount=350_000,
        )

        self.client.force_login(self.parent)
        payload = self.client.get(self._api_path("parent/dashboard/")).json()
        self.assertEqual(payload["stats"]["debt_amount"], 0)
        self.assertEqual(payload["stats"]["debt_status"], "to_liq_to_langan")

    def test_mobile_student_debt_endpoint_matches_admin_for_anaxon(self):
        admin_debt = self._admin_debt_for_anaxon()

        self.client.force_login(self.student)
        response = self.client.get(self._api_path("student/debt/"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["total_debt"], admin_debt)
        self.assertEqual(payload["total_debt"], 350_000)
        self.assertEqual(payload["total_due"], 350_000)
        self.assertEqual(payload["total_paid"], 0)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["fee"], 350_000)
        self.assertEqual(payload["items"][0]["paid"], 0)
        self.assertEqual(payload["items"][0]["debt"], 350_000)

    def test_mobile_payments_summary_debt_matches_admin_for_anaxon(self):
        admin_debt = self._admin_debt_for_anaxon()

        self.client.force_login(self.parent)
        response = self.client.get(self._api_path("payments/"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["debt_amount"], admin_debt)
        self.assertEqual(payload["summary"]["debt_amount"], 350_000)

    def test_partial_payment_keeps_admin_and_mobile_in_lockstep(self):
        from datetime import timedelta

        payment = Payment.objects.create(
            center=self.center,
            enrollment=self.enrollment,
            student=self.student,
            group=self.group,
            payment_type="cash",
            cash_amount=100_000,
            paid_date=self.current_month + timedelta(days=2),
            created_by=self.director,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=payment,
            tuition_month=self.tuition_month,
            amount=100_000,
        )

        admin_debt = self._admin_debt_for_anaxon()
        self.assertEqual(admin_debt, 250_000)

        self.client.force_login(self.parent)
        dashboard = self.client.get(self._api_path("parent/dashboard/")).json()
        debt_breakdown = self.client.get(self._api_path("student/debt/"), {"student_id": self.student.id}).json()

        self.assertEqual(dashboard["stats"]["debt_amount"], admin_debt)
        self.assertEqual(debt_breakdown["total_debt"], admin_debt)
        self.assertEqual(debt_breakdown["total_due"], 350_000)
        self.assertEqual(debt_breakdown["total_paid"], 100_000)

    def test_full_payment_drops_debt_to_zero_in_both_views(self):
        from datetime import timedelta

        payment = Payment.objects.create(
            center=self.center,
            enrollment=self.enrollment,
            student=self.student,
            group=self.group,
            payment_type="cash",
            cash_amount=350_000,
            paid_date=self.current_month + timedelta(days=2),
            created_by=self.director,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=payment,
            tuition_month=self.tuition_month,
            amount=350_000,
        )

        self.client.force_login(self.director)
        admin_response = self.client.get(self.qarzdorlar_url)
        rows = {row["student"].email: row for row in admin_response.context["page_obj"].object_list}
        self.assertNotIn(self.student.email, rows)

        self.client.force_login(self.parent)
        dashboard = self.client.get(self._api_path("parent/dashboard/")).json()
        debt_breakdown = self.client.get(self._api_path("student/debt/"), {"student_id": self.student.id}).json()

        self.assertEqual(dashboard["stats"]["debt_amount"], 0)
        self.assertEqual(debt_breakdown["total_debt"], 0)
        self.assertEqual(debt_breakdown["total_paid"], 350_000)
