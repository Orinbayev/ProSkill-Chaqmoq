from django.test import TestCase
from django.urls import reverse

from accounts.models import Center, User
from education.models import Group


class AttendanceGroupsSearchTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="ProSkill Matem Markazi", slug="proskill-matem")
        self.manager = User.objects.create_user(
            email="manager@attendance.test",
            password="testpass123",
            role="manager",
            center=self.center,
            ism="Manager",
            familya="User",
        )
        self.teacher = User.objects.create_user(
            email="teacher@attendance.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Amirxon",
            familya="O'rinbayev",
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="Matematika - 01",
            oqituvchi=self.teacher,
            kurs_narxi=150_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.client.force_login(self.manager)
        self.url = f"/{self.center.slug}{reverse('education:attendance_groups')}"

    def test_search_by_group_name_returns_page(self):
        response = self.client.get(self.url, {"q": "Matem"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.group.nom)

    def test_search_by_center_name_returns_page(self):
        response = self.client.get(self.url, {"q": "ProSkill"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.group.nom)
