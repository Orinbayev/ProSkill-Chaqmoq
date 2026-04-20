from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta

from accounts.models import Center, User
from education.models import Group
from store.forms import LeadForm
from store.lead_services import (
    convert_lead_to_student_safe,
    ensure_default_lead_catalog,
    get_status_by_code,
    send_follow_up_notification_if_due,
)
from store.models import Expense, ExpenseCategory, Lead, LeadStatus, Manba, Product, PurchaseRequest, TrialLesson, Yonalish
from store.trial_services import handle_trial_created, handle_trial_updated


class LeadCrmServiceTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Test Center", slug="test-center")
        self.manager = User.objects.create_user(
            email="manager@test.uz",
            password="Pass12345!",
            role="manager",
            center=self.center,
            ism="Manager",
            familya="One",
        )
        self.teacher = User.objects.create_user(
            email="teacher@test.uz",
            password="Pass12345!",
            role="teacher",
            center=self.center,
            ism="Teacher",
            familya="One",
        )
        ensure_default_lead_catalog(self.center)

    def test_convert_lead_does_not_create_duplicate_student(self):
        existing_student = User.objects.create_user(
            email="student-existing@test.uz",
            password="Pass12345!",
            role="student",
            center=self.center,
            ism="Ali",
            familya="Valiyev",
            telefon1="+998901112233",
            phone_number="+998901112233",
        )

        lead = Lead.objects.create(
            center=self.center,
            ism="Ali",
            familya="Valiyev",
            telefon1="+998901112233",
            yosh=16,
            assigned_manager=self.manager,
        )

        before_students = User.objects.filter(center=self.center, role="student").count()
        user, password, created = convert_lead_to_student_safe(
            lead=lead,
            converted_by=self.manager,
            target_center=self.center,
        )
        after_students = User.objects.filter(center=self.center, role="student").count()

        self.assertFalse(created)
        self.assertIsNone(password)
        self.assertEqual(user.id, existing_student.id)
        self.assertEqual(before_students, after_students)

        lead.refresh_from_db()
        self.assertTrue(lead.converted_to_student)
        self.assertEqual(lead.converted_user_id, existing_student.id)

    def test_follow_up_notification_is_deduplicated(self):
        lead = Lead.objects.create(
            center=self.center,
            ism="Jamshid",
            familya="Karimov",
            telefon1="+998900000001",
            yosh=15,
            assigned_manager=self.manager,
            next_follow_up_date=timezone.localdate(),
        )

        send_follow_up_notification_if_due(lead)
        send_follow_up_notification_if_due(lead)

        self.assertEqual(
            self.manager.notifications.filter(title="Lead follow-up").count(),
            1,
        )

    def test_trial_converted_result_marks_lead_converted(self):
        lead = Lead.objects.create(
            center=self.center,
            ism="Dilnoza",
            familya="Sobirova",
            telefon1="+998901234560",
            yosh=14,
            assigned_manager=self.manager,
        )
        group = Group.objects.create(
            center=self.center,
            nom="English A1",
            oqituvchi=self.teacher,
        )
        trial = TrialLesson.objects.create(
            center=self.center,
            lead=lead,
            group=group,
            teacher=self.teacher,
            scheduled_at=timezone.now() + timedelta(days=1),
            result_status=TrialLesson.ResultStatus.PENDING,
            created_by=self.manager,
            updated_by=self.manager,
        )
        handle_trial_created(trial=trial, actor=self.manager)

        trial.result_status = TrialLesson.ResultStatus.CONVERTED
        trial.save(update_fields=["result_status", "updated_at"])
        handle_trial_updated(
            trial=trial,
            actor=self.manager,
            previous_result=TrialLesson.ResultStatus.PENDING,
        )

        lead.refresh_from_db()
        trial.refresh_from_db()

        registered_status = get_status_by_code(center=self.center, code="registered")
        self.assertTrue(lead.converted_to_student)
        self.assertIsNotNone(lead.converted_user_id)
        self.assertEqual(lead.status_id, registered_status.id if registered_status else lead.status_id)
        self.assertTrue(trial.registered_after_trial)


class LeadCatalogIsolationTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(
            name="Lead Center A",
            slug="lead-center-a",
            features={"leads": True},
        )
        self.other_center = Center.objects.create(
            name="Lead Center B",
            slug="lead-center-b",
            features={"leads": True},
        )
        self.director = User.objects.create_user(
            email="director@lead-a.test",
            password="Pass12345!",
            role="director",
            center=self.center,
            ism="Lead",
            familya="Director",
        )
        self.manager = User.objects.create_user(
            email="manager@lead-a.test",
            password="Pass12345!",
            role="manager",
            center=self.center,
            ism="Lead",
            familya="Manager",
        )
        self.other_manager = User.objects.create_user(
            email="manager@lead-b.test",
            password="Pass12345!",
            role="manager",
            center=self.other_center,
            ism="Other",
            familya="Manager",
        )
        self.center_manba = Manba.objects.create(center=self.center, nom="Instagram A")
        self.other_manba = Manba.objects.create(center=self.other_center, nom="Instagram B")
        self.center_yonalish = Yonalish.objects.create(center=self.center, nom="IELTS A")
        self.other_yonalish = Yonalish.objects.create(center=self.other_center, nom="IELTS B")
        self.center_status = LeadStatus.objects.create(center=self.center, nom="Yangi A", code="new", is_active=True)
        self.other_status = LeadStatus.objects.create(center=self.other_center, nom="Yangi B", code="new", is_active=True)
        self.client.force_login(self.director)

    def test_form_uses_only_current_center_catalog(self):
        form = LeadForm(center=self.center)

        self.assertEqual(
            list(form.fields["manba"].queryset.values_list("id", flat=True)),
            [self.center_manba.id],
        )
        self.assertEqual(
            list(form.fields["yonalish"].queryset.values_list("id", flat=True)),
            [self.center_yonalish.id],
        )
        self.assertEqual(
            list(form.fields["status"].queryset.values_list("id", flat=True)),
            [self.center_status.id],
        )
        self.assertEqual(
            list(form.fields["assigned_manager"].queryset.values_list("id", flat=True)),
            [self.manager.id],
        )
        self.assertEqual(form.fields["manba"].empty_label, "")
        self.assertEqual(form.fields["yonalish"].empty_label, "")
        self.assertEqual(form.fields["status"].empty_label, "")
        self.assertIsNone(form["manba"].value())
        self.assertIsNone(form["yonalish"].value())
        self.assertIsNone(form["status"].value())

    def test_form_rejects_other_center_catalog_ids(self):
        form = LeadForm(
            data={
                "ism": "Ali",
                "telefon1": "+998901112233",
                "manba": self.other_manba.id,
                "yonalish": self.other_yonalish.id,
                "status": self.other_status.id,
                "assigned_manager": self.other_manager.id,
            },
            center=self.center,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("manba", form.errors)
        self.assertIn("yonalish", form.errors)
        self.assertIn("status", form.errors)
        self.assertIn("assigned_manager", form.errors)

    def test_lead_create_page_does_not_auto_seed_catalog(self):
        Manba.objects.filter(center=self.center).delete()
        Yonalish.objects.filter(center=self.center).delete()
        LeadStatus.objects.filter(center=self.center).delete()

        response = self.client.get(f"/{self.center.slug}{reverse('store:lead_create')}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Manba.objects.filter(center=self.center).count(), 0)
        self.assertEqual(Yonalish.objects.filter(center=self.center).count(), 0)
        self.assertEqual(LeadStatus.objects.filter(center=self.center).count(), 0)
        self.assertEqual(response.context["form"].fields["manba"].queryset.count(), 0)
        self.assertEqual(response.context["form"].fields["yonalish"].queryset.count(), 0)
        self.assertEqual(response.context["form"].fields["status"].queryset.count(), 0)


class ExpensePageSmokeTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Expense Center", slug="expense-center")
        self.manager = User.objects.create_user(
            email="manager@expense.test",
            password="Pass12345!",
            role="manager",
            center=self.center,
            ism="Expense",
            familya="Manager",
        )
        self.category = ExpenseCategory.objects.create(center=self.center, nom="Ofis")
        Expense.objects.create(
            center=self.center,
            summa=320_000,
            izoh="Printer uchun qog'oz",
            category=self.category,
            payment_method="naqd",
            receiver="Hamkor",
            worker=self.manager,
            sana=timezone.make_aware(datetime(2026, 4, 6, 10, 0)),
        )
        self.client.force_login(self.manager)
        self.url = f"/{self.center.slug}{reverse('store:expenses')}"

    def test_expenses_page_renders_summary_and_chart_context(self):
        response = self.client.get(
            self.url,
            {
                "sana_dan": "2026-04-01",
                "sana_gacha": "2026-04-12",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_sum"], 320_000)
        self.assertEqual(response.context["filtered_sum"], 320_000)
        self.assertEqual(len(response.context["items"]), 1)
        self.assertEqual(response.context["chart_kicker"], "Oxirgi 12 oy")
        self.assertEqual(response.context["chart_period_label"], "May dan Aprel gacha")
        self.assertEqual(len(response.context["chart_labels"]), 12)
        self.assertEqual(response.context["chart_labels"][0], "May")
        self.assertEqual(response.context["chart_labels"][-1], "Aprel")
        self.assertTrue(all(value == 0 for value in response.context["chart_data"][:-1]))
        self.assertEqual(response.context["chart_data"][-1], 320_000)
        self.assertContains(response, "Jami xarajat")
        self.assertContains(response, "Xarajatlar grafigi")


class ProductStorePageTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Store Center", slug="store-center")
        self.director = User.objects.create_user(
            email="director@store.test",
            password="Pass12345!",
            role="director",
            center=self.center,
            ism="Store",
            familya="Director",
        )
        self.student = User.objects.create_user(
            email="student@store.test",
            password="Pass12345!",
            role="student",
            center=self.center,
            ism="Store",
            familya="Student",
        )
        self.client.force_login(self.director)
        self.shop_url = f"/{self.center.slug}{reverse('store:products')}"
        self.legacy_products_url = f"/{self.center.slug}{reverse('store:product_list')}"

    def test_legacy_products_url_redirects_to_store_home(self):
        response = self.client.get(self.legacy_products_url)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith("/do'kon/"))

    def test_store_home_renders_premium_empty_state(self):
        response = self.client.get(self.shop_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Do'kon bo'limida hali mahsulot joylanmagan")
        self.assertContains(response, "Birinchi mahsulotni qo'shish")

    def test_store_home_shows_product_card(self):
        product = Product.objects.create(
            center=self.center,
            nom="Planner",
            narx_chaqmoq=120,
            narx_som=45_000,
            sotilgan_soni=4,
        )
        PurchaseRequest.objects.create(
            center=self.center,
            student=self.student,
            product=product,
            qty=1,
            status=PurchaseRequest.PENDING,
        )

        response = self.client.get(self.shop_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Planner")
        self.assertContains(response, "Ko‘rish")
