from django.test import TestCase
from django.urls import reverse
from accounts.models import User, Center
from education.models import Category
from education.views import CategoryForm
from billing.models import SubscriptionPlan

class CategoryUniquenessTest(TestCase):
    def setUp(self):
        # Create SubscriptionPlan
        self.plan = SubscriptionPlan.objects.create(
            code="START",
            title="Start Plan",
            monthly_price=0,
            active=True
        )

        # Create Center
        self.center = Center.objects.create(name="ProSkill Center", slug="proskill")
        
        # Create User (Director role to access views)
        self.user = User.objects.create_user(
            email="director@example.com", password="password", role="director", center=self.center
        )

        # Create an initial Category
        self.existing_cat = Category.objects.create(
            name="Dizayn",
            center=self.center
        )

    def test_category_form_unique_validation(self):
        """CategoryForm should fail when a duplicate name is used in the same center (case-insensitive)"""
        # Exact match
        form = CategoryForm(data={"name": "Dizayn"}, center=self.center)
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertEqual(form.errors["name"][0], "Ushbu nomdagi bo'lim allaqachon mavjud!")

        # Case-insensitive match
        form_ci = CategoryForm(data={"name": "  dIzAyN  "}, center=self.center)
        self.assertFalse(form_ci.is_valid())
        self.assertIn("name", form_ci.errors)
        self.assertEqual(form_ci.errors["name"][0], "Ushbu nomdagi bo'lim allaqachon mavjud!")

        # Unique name in same center
        form_ok = CategoryForm(data={"name": "Dasturlash"}, center=self.center)
        self.assertTrue(form_ok.is_valid())

    def test_category_form_unique_with_soft_deleted(self):
        """CategoryForm uniqueness validation should also check soft-deleted categories"""
        # Soft delete the existing category
        self.existing_cat.delete()
        self.assertTrue(self.existing_cat.is_deleted)

        # Form should still fail due to database unique constraint collision with soft-deleted rows
        form = CategoryForm(data={"name": "Dizayn"}, center=self.center)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["name"][0], "Ushbu nomdagi bo'lim allaqachon mavjud!")

    def test_add_category_view_validation(self):
        """The add_category view should show validation error for duplicate category names"""
        self.client.force_login(self.user)
        url = reverse("education:add_category")
        
        # Post duplicate name
        response = self.client.post(url, {"name": "DIZAYN"}, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify the form errors in context
        form = response.context.get("form")
        self.assertIsNotNone(form)
        self.assertIn("name", form.errors)

    def test_edit_category_view_validation(self):
        """The edit_category view should reject duplicate name updates and display an error message"""
        self.client.force_login(self.user)
        
        # Create a second category
        second_cat = Category.objects.create(name="Marketing", center=self.center)
        
        url = reverse("education:edit_category", args=[second_cat.id])
        
        # Try to rename "Marketing" to "dizayn" (which is used by self.existing_cat)
        response = self.client.post(url, {"name": "dizayn", "description": "some info"}, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify error message
        messages = list(response.context.get("messages", []))
        message_texts = [m.message for m in messages]
        self.assertIn("Ushbu nomdagi bo'lim allaqachon mavjud!", message_texts)
        
        # Verify category name was not changed in DB
        second_cat.refresh_from_db()
        self.assertEqual(second_cat.name, "Marketing")
