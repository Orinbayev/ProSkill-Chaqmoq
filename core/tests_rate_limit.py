"""
core/tests_rate_limit.py

Rate limiting decorator uchun testlar.
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from accounts.models import User, Center
from billing.models import SubscriptionPlan
from core.rate_limit import rate_limit, _build_cache_key


def _make_view(max_calls=3, period=60, key="ip"):
    """Test uchun oddiy view funksiyasi."""
    from django.http import HttpResponse

    @rate_limit(max_calls=max_calls, period=period, key=key, block=True)
    def my_view(request):
        return HttpResponse("OK")

    return my_view


class RateLimitDecoratorTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.plan = SubscriptionPlan.objects.create(
            code="TEST", title="Test", monthly_price=0, active=True
        )
        self.center = Center.objects.create(name="Test Center", slug="test-center")
        self.user = User.objects.create_user(
            email="ratelimit@example.com",
            password="pass",
            role="teacher",
            center=self.center,
        )
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _make_request(self, ip="127.0.0.1"):
        request = self.factory.get("/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = ip
        return request

    def test_allows_within_limit(self):
        """Limit ichidagi so'rovlar o'tishi kerak."""
        view = _make_view(max_calls=3, period=60, key="ip")
        request = self._make_request()
        for _ in range(3):
            resp = view(request)
            self.assertEqual(resp.status_code, 200)

    def test_blocks_over_limit(self):
        """Limitdan oshganda 429 qaytishi kerak."""
        view = _make_view(max_calls=2, period=60, key="ip")
        request = self._make_request(ip="10.0.0.1")
        view(request)
        view(request)
        resp = view(request)
        self.assertEqual(resp.status_code, 429)

    def test_superuser_bypasses_limit(self):
        """Superuser rate limit tekshiruviga kirmaydi."""
        self.user.is_superuser = True
        self.user.save()
        view = _make_view(max_calls=1, period=60, key="ip")
        request = self._make_request()
        for _ in range(5):
            resp = view(request)
            self.assertEqual(resp.status_code, 200)

    def test_different_ips_tracked_separately(self):
        """Turli IP lar uchun alohida limit hisoblanadi."""
        view = _make_view(max_calls=1, period=60, key="ip")
        req1 = self._make_request(ip="192.168.1.1")
        req2 = self._make_request(ip="192.168.1.2")

        resp1 = view(req1)
        self.assertEqual(resp1.status_code, 200)

        resp1_blocked = view(req1)
        self.assertEqual(resp1_blocked.status_code, 429)

        # Boshqa IP hali ham o'ta oladi
        resp2 = view(req2)
        self.assertEqual(resp2.status_code, 200)


class UserImportServiceTest(TestCase):
    """core/services/user_import_service.py testlari."""

    def test_normalize_header(self):
        from core.services.user_import_service import normalize_header
        self.assertEqual(normalize_header("  Ism  "), "ism")
        self.assertEqual(normalize_header("Phone Number"), "phonenumber")
        self.assertEqual(normalize_header("O'quvchi_ismi"), "oquvchiismi")

    def test_cell_to_str(self):
        from core.services.user_import_service import cell_to_str
        self.assertEqual(cell_to_str(None), "")
        self.assertEqual(cell_to_str(3.0), "3")
        self.assertEqual(cell_to_str("  hello  "), "hello")

    def test_normalize_phone(self):
        from core.services.user_import_service import normalize_phone
        self.assertEqual(normalize_phone("+998 90 123 45 67"), "998901234567")
        self.assertEqual(normalize_phone(""), "")
        self.assertEqual(normalize_phone(None), "")

    def test_normalize_gender(self):
        from core.services.user_import_service import normalize_gender
        self.assertEqual(normalize_gender("erkak"), "male")
        self.assertEqual(normalize_gender("ayol"), "female")
        self.assertEqual(normalize_gender("MALE"), "male")
        self.assertIsNone(normalize_gender(None))
        self.assertIsNone(normalize_gender("noma'lum"))

    def test_gen_default_password_length(self):
        from core.services.user_import_service import gen_default_password
        pwd = gen_default_password()
        self.assertEqual(len(pwd), 10)
        pwd_custom = gen_default_password(length=16)
        self.assertEqual(len(pwd_custom), 16)


class AttendanceServiceTest(TestCase):
    """education/services/attendance_service.py testlari."""

    def setUp(self):
        self.plan = SubscriptionPlan.objects.create(
            code="ATT", title="Att Plan", monthly_price=0, active=True
        )
        self.center = Center.objects.create(name="Att Center", slug="att-center")
        self.teacher = User.objects.create_user(
            email="teacher@att.com", password="pass", role="teacher", center=self.center
        )
        self.student = User.objects.create_user(
            email="student@att.com", password="pass", role="student", center=self.center
        )
        from education.models import Group
        self.group = Group.objects.create(
            nom="Test Group",
            center=self.center,
            oqituvchi=self.teacher,
            kurs_narxi=1000,
            oqituvchi_foiz=50,
        )

    def test_toggle_none_to_present(self):
        """none → present"""
        from education.services.attendance_service import toggle_attendance
        from datetime import date
        result = toggle_attendance(
            group=self.group,
            student=self.student,
            date_value=date.today(),
            current_status="none",
        )
        self.assertEqual(result, "present")

    def test_toggle_present_to_absent(self):
        """present → absent"""
        from education.services.attendance_service import toggle_attendance
        from datetime import date
        today = date.today()
        # Birinchi "present" qilish
        toggle_attendance(group=self.group, student=self.student, date_value=today, current_status="none")
        # "absent" qilish
        result = toggle_attendance(group=self.group, student=self.student, date_value=today, current_status="present")
        self.assertEqual(result, "absent")

    def test_direct_set_excused(self):
        """target_status='excused' → absent_excused"""
        from education.services.attendance_service import toggle_attendance
        from datetime import date
        result = toggle_attendance(
            group=self.group,
            student=self.student,
            date_value=date.today(),
            target_status="excused",
        )
        self.assertEqual(result, "absent_excused")

    def test_direct_set_none_deletes_record(self):
        """target_status='none' mavjud yozuvni o'chirishi kerak"""
        from education.services.attendance_service import toggle_attendance
        from education.models import Attendance
        from datetime import date
        today = date.today()
        # Avval yaratamiz
        toggle_attendance(group=self.group, student=self.student, date_value=today, current_status="none")
        self.assertEqual(Attendance.objects.filter(group=self.group, student=self.student, date=today).count(), 1)
        # O'chiramiz
        result = toggle_attendance(group=self.group, student=self.student, date_value=today, target_status="none")
        self.assertEqual(result, "none")
        self.assertEqual(Attendance.objects.filter(group=self.group, student=self.student, date=today).count(), 0)
