from django.test import Client, TestCase

from .models import DemoLead, SupportCard


class MarketingViewsTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_public_pages_status(self):
        urls = ["/", "/pricing/", "/demo/", "/support/", "/vacancies/", "/privacy/", "/terms/"]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_demo_post_creates_lead(self):
        before_count = DemoLead.objects.count()
        response = self.client.post(
            "/demo/",
            {
                "full_name": "Test User",
                "center_name": "Test Center",
                "phone": "+998901234567",
                "consent": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DemoLead.objects.count(), before_count + 1)

    def test_unprefixed_pages_force_uz_default(self):
        response = self.client.get("/support/", HTTP_ACCEPT_LANGUAGE="ru")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_lang"], "uz")

    def test_prefixed_language_switch_preserves_path_and_query(self):
        response = self.client.get("/ru/support/?source=ad")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_lang"], "ru")

        links = {item["code"]: item["url"] for item in response.context["lang_links"]}
        self.assertEqual(links["uz"], "/support/?source=ad")
        self.assertEqual(links["ru"], "/ru/support/?source=ad")
        self.assertEqual(links["en"], "/en/support/?source=ad")

    def test_support_content_is_localized(self):
        SupportCard.objects.create(
            title="Основной заголовок",
            title_uz="Yordam markazi",
            title_ru="Центр поддержки",
            title_en="Support Center",
            description="Base",
            description_uz="O'zbekcha tavsif",
            description_ru="Русское описание",
            description_en="English description",
            button_text="Ko'rish",
            button_text_uz="Ko'rish",
            button_text_ru="Открыть",
            button_text_en="Open",
            button_url="https://example.com",
            is_active=True,
        )

        uz_response = self.client.get("/support/")
        ru_response = self.client.get("/ru/support/")

        self.assertContains(uz_response, "Yordam markazi")
        self.assertContains(ru_response, "Центр поддержки")
