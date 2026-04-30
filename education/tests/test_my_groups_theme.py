from django.test import TestCase
from django.urls import reverse

from accounts.models import Center, User
from education.models import Group


class MyGroupsThemeTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="ProSkill", slug="proskill")
        self.teacher = User.objects.create_user(
            email="teacher@mygroups.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Ali",
            familya="Karimov",
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="English Pro",
            oqituvchi=self.teacher,
            kurs_narxi=200_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.client.force_login(self.teacher)
        self.url = f"/{self.center.slug}{reverse('education:men_guruhlarim')}"

    def test_my_groups_page_uses_global_theme_variables(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "teacher-my-groups-page")
        self.assertContains(response, "my-groups-surface")
        self.assertContains(response, "html[data-role-theme=\"light\"] body.teacher-my-groups-page")
        self.assertContains(response, "html[data-theme=\"light\"] body.teacher-my-groups-page")
        self.assertContains(response, "--card-bg: var(--panel);")
        self.assertContains(response, "--input-bg: var(--panel2);")
        self.assertContains(response, self.group.nom)
