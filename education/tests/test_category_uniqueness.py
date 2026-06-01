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

    def test_legacy_category_in_lead_group_form_and_courses(self):
        """Primary center should see and allow selecting legacy/global categories (where center is None)"""
        # Create a global category
        global_cat = Category.objects.create(name="Global Legacy Cat", center=None)

        # Import LeadGroupForm
        from store.forms import LeadGroupForm
        from education.models import CourseTemplate

        # LeadGroupForm initialized with primary center should contain global_cat
        form = LeadGroupForm(center=self.center)
        self.assertIn(global_cat, form.fields["department"].queryset)

        # course_create view should display global_cat and allow using it
        self.client.force_login(self.user)
        url = reverse("education:course_create")
        
        # Verify global category is in context
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(global_cat, response.context["categories"])

        # Try creating a course template associated with global_cat
        post_data = {
            "name": "Global English Course",
            "price": "300000",
            "teacher_percent": "45",
            "lessons_per_month": "12",
            "category_obj": str(global_cat.id),
            "is_active": "on"
        }
        post_response = self.client.post(url, post_data, follow=True)
        self.assertEqual(post_response.status_code, 200)

        # Verify CourseTemplate was created with correct global category
        course = CourseTemplate.objects.filter(name="Global English Course").first()
        self.assertIsNotNone(course)
        self.assertEqual(course.category_obj, global_cat)

    def test_lead_group_conversion_preserves_department(self):
        """Converting a LeadGroup should correctly set the selected Category (department) on the created Group"""
        # Create a LeadGroup
        from store.models import LeadGroup, Yonalish
        from store.crm_views import _convert_lead_group_to_real_group

        subject = Yonalish.objects.create(nom="English", center=self.center)
        lead_group = LeadGroup.objects.create(
            center=self.center,
            name="Test Lead Group",
            subject=subject,
            department=self.existing_cat
        )

        # Create a teacher user
        teacher_user = User.objects.create_user(
            email="teacher_test@example.com", password="password", role="teacher", center=self.center
        )

        # Let's mock the POST payload from the convert modal
        payload = {
            "name": "Converted Group",
            "department": str(self.existing_cat.id),
            "teacher": str(teacher_user.id),
            "lesson_days": ["1", "3", "5"],
            "lesson_time": "09:00",
            "lesson_end_time": "10:30",
            "start_date": "2026-06-01",
            "price": "300000",
            "teacher_share": "45"
        }

        # Run the conversion
        result, errors = _convert_lead_group_to_real_group(
            lead_group=lead_group,
            payload=payload,
            actor=self.user,
            center=self.center
        )

        # Verify no validation errors occurred
        self.assertIsNone(errors)
        self.assertIsNotNone(result)

        # Check if the Group was created
        group = result["group"]
        self.assertIsNotNone(group)
        self.assertEqual(group.nom, "Converted Group")

        # Verify that category_obj is set to the selected department!
        self.assertEqual(group.category_obj, self.existing_cat)
