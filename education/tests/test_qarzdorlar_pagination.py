from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from core.test_utils import activate_center
from education.models import Enrollment, Group, StudentGroupHistory


class QarzdorlarPaginationTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Debt Center", slug="debt-center")
        activate_center(self.center)
        self.manager = User.objects.create_user(
            email="manager@debt.test",
            password="testpass123",
            role="manager",
            center=self.center,
            ism="Debt",
            familya="Manager",
        )
        self.teacher = User.objects.create_user(
            email="teacher@debt.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Debt",
            familya="Teacher",
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="Debtors Group",
            oqituvchi=self.teacher,
            kurs_narxi=150_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        history_start = date(2026, 4, 1)

        for idx in range(25):
            student = User.objects.create_user(
                email=f"student{idx}@debt.test",
                password="testpass123",
                role="student",
                center=self.center,
                ism=f"Student {idx}",
                familya="Debtor",
                telefon1=f"+99890123{idx:04d}",
            )
            Enrollment.objects.create(
                center=self.center,
                group=self.group,
                student=student,
                kurs_narhi=150_000,
                oqituvchi_foiz=40,
                is_active=True,
            )
            StudentGroupHistory.objects.create(
                student=student,
                group=self.group,
                center=self.center,
                start_date=history_start,
                kurs_narxi=150_000,
                oqituvchi_foiz=40,
            )
        self.client.force_login(self.manager)
        self.url = f"/{self.center.slug}{reverse('education:qarzdorlar_home')}"

    def test_qarzdorlar_page_uses_default_per_page(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["per_page"], 10)
        self.assertEqual(response.context["page_obj"].paginator.per_page, 10)
        self.assertEqual(len(response.context["page_obj"].object_list), 10)
        self.assertContains(response, 'value="10" selected')
        self.assertContains(response, "?page=2&per_page=10")

    def test_qarzdorlar_page_preserves_custom_per_page_in_ui_and_links(self):
        response = self.client.get(self.url, {"per_page": "20"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["per_page"], 20)
        self.assertEqual(response.context["page_obj"].paginator.per_page, 20)
        self.assertEqual(len(response.context["page_obj"].object_list), 20)
        self.assertContains(response, 'value="20" selected')
        self.assertContains(response, "?page=2&per_page=20")

    def test_qarzdorlar_chart_shows_last_12_months(self):
        response = self.client.get(
            self.url,
            {
                "date_from": "2026-04-01",
                "date_to": "2026-04-12",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["chart_kicker"], "Oxirgi 12 oy")
        self.assertEqual(response.context["chart_period_label"], "May dan Aprel gacha")
        self.assertEqual(len(response.context["chart_labels"]), 12)
        self.assertEqual(response.context["chart_labels"][0], "May")
        self.assertEqual(response.context["chart_labels"][-1], "Aprel")
        self.assertTrue(all(value == 0 for value in response.context["chart_data"][:-1]))
        self.assertEqual(response.context["chart_data"][-1], 3_750_000)
