from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, Center
from education.models import Group
from billing.models import SubscriptionPlan

class TenantIsolationTest(TestCase):
    def setUp(self):
        # SubscriptionPlan yaratish (billing uchun kerak)
        self.plan = SubscriptionPlan.objects.create(
            code="START",
            title="Start Plan",
            monthly_price=0,
            active=True
        )

        # Centerlarni yaratish
        self.center_a = Center.objects.create(name="Center A", slug="center-a")
        self.center_b = Center.objects.create(name="Center B", slug="center-b")
        
        # Userlarni yaratish
        self.user_a = User.objects.create_user(
            email="teacher_a@example.com", password="password", role="teacher", center=self.center_a
        )
        self.manager_a = User.objects.create_user(
            email="manager_a@example.com", password="password", role="manager", center=self.center_a
        )

        self.user_b = User.objects.create_user(
            email="teacher_b@example.com", password="password", role="teacher", center=self.center_b
        )
        
        # Guruhlarni yaratish
        self.group_a = Group.objects.create(
            nom="Group A", center=self.center_a, oqituvchi=self.user_a, 
            kurs_narxi=1000, oqituvchi_foiz=50
        )
        self.group_b = Group.objects.create(
            nom="Group B", center=self.center_b, oqituvchi=self.user_b,
            kurs_narxi=1000, oqituvchi_foiz=50
        )

    # def test_group_list_isolation(self):
    #     """User A faqat o‘z centeridagi guruhlarni ko‘rishi kerak"""
    #     self.client.force_login(self.user_a)
    #     response = self.client.get(reverse("education:group_list"))  # 'groups' o'rniga 'group_list'
    #     self.assertEqual(response.status_code, 200)
        
    #     # Context ichida groups bormi?
    #     # Viewsda 'rows' deb berilgan
    #     rows = response.context.get("rows", [])
    #     self.assertIn(self.group_a, rows)
    #     self.assertNotIn(self.group_b, rows)

    def test_group_detail_idor_protection(self):
        """User A boshqa centerdagi guruhga kirsa 404 qaytishi kerak"""
        self.client.force_login(self.user_a)

        # TenantMiddleware /{slug}/... ga redirect qiladi, shuning uchun follow=True
        url_a = reverse("education:group_detail", args=[self.group_a.id])
        resp_a = self.client.get(url_a, follow=True)
        self.assertEqual(resp_a.status_code, 200)

        # Boshqa center guruhi -> 404 Not Found
        url_b = reverse("education:group_detail", args=[self.group_b.id])
        resp_b = self.client.get(url_b, follow=True)
        self.assertEqual(resp_b.status_code, 404)

    def test_create_group_center_assignment(self):
        """Guruh yaratganda center avtomatik user.center bo‘lishi kerak"""
        self.client.force_login(self.manager_a)
        # 'group_create' o‘rniga 'group_create_lang' yoki 'group_create_it' ishlatamiz
        url = reverse("education:group_create_lang") 
        data = {
            "nom": "New Group A",
            "kurs_narxi": 500000,
            "oqituvchi_foiz": 40,
            "oy_dars_soni": 12,
            "oqituvchi": self.user_a.id,
            # center_id yubormaymiz, lekin yuborsak ham ignore qilinishi kerak (viewsga bog‘liq)
        }
        self.client.post(url, data)
        
        # Tekshirish
        new_group = Group.objects.filter(nom="New Group A").first()
        self.assertIsNotNone(new_group)
        self.assertEqual(new_group.center, self.center_a)
