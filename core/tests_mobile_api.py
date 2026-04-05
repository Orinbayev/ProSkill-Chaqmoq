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

        status_response = self.client.get(self._path("auth/status/"))
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_response.json()["authenticated"])

    def test_mobile_director_dashboard_returns_full_contract(self):
        self.client.force_login(self.director)
        response = self.client.get(
            self._path("dashboard/director/"),
            {
                "date_from": (self.today - timezone.timedelta(days=7)).isoformat(),
                "date_to": self.today.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("overview", payload)
        self.assertIn("executive", payload)
        self.assertIn("groups", payload)
        self.assertIn("marketing", payload)
        self.assertEqual(payload["filters"]["applied"]["branch_ids"], [self.center.id])

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
