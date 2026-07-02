from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import Center, User
from education.models import Enrollment, Group, Payment, PaymentAllocation, TuitionMonth


class TolovlarPaginationTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Payments Center", slug="payments-center")
        self.manager = User.objects.create_user(
            email="manager@payments.test",
            password="testpass123",
            role="manager",
            center=self.center,
            ism="Payments",
            familya="Manager",
        )
        self.teacher = User.objects.create_user(
            email="teacher@payments.test",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Payments",
            familya="Teacher",
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="Payments Group",
            oqituvchi=self.teacher,
            kurs_narxi=200_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )

        self.first_student = None
        for idx in range(25):
            is_search_match = idx < 15
            student = User.objects.create_user(
                email=f"student{idx}@payments.test",
                password="testpass123",
                role="student",
                center=self.center,
                ism=f"{'Alpha' if is_search_match else 'Beta'} {idx}",
                familya="Student",
                telefon1=f"+99890111{idx:04d}",
                gmail=f"student{idx}@school.test",
            )
            if idx == 0:
                self.first_student = student
            Payment.objects.create(
                center=self.center,
                student=student,
                group=self.group,
                payment_type="cash",
                cash_amount=50_000 + idx,
                paid_date=date(2026, 4, min(idx + 1, 28)),
                created_by=self.manager,
            )

        Payment.objects.create(
            center=self.center,
            student=self.first_student,
            group=self.group,
            payment_type="cash",
            cash_amount=75_000,
            paid_date=date(2026, 4, 29),
            created_by=self.manager,
        )

        self.first_enrollment = Enrollment.objects.create(
            group=self.group,
            student=self.first_student,
            center=self.center,
            kurs_narhi=200_000,
            oqituvchi_foiz=40,
        )

        self.split_payment = Payment.objects.create(
            enrollment=self.first_enrollment,
            center=self.center,
            student=self.first_student,
            group=self.group,
            payment_type="cash",
            cash_amount=125_000,
            paid_date=date(2026, 4, 30),
            created_by=self.manager,
        )
        self.tuition_month_1 = TuitionMonth.objects.create(
            enrollment=self.first_enrollment,
            center=self.center,
            month=date(2026, 4, 1),
            fee_amount=100_000,
        )
        self.tuition_month_2 = TuitionMonth.objects.create(
            enrollment=self.first_enrollment,
            center=self.center,
            month=date(2026, 5, 1),
            fee_amount=100_000,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=self.split_payment,
            tuition_month=self.tuition_month_1,
            amount=100_000,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=self.split_payment,
            tuition_month=self.tuition_month_2,
            amount=25_000,
        )

        self.client.force_login(self.manager)
        self.url = f"/{self.center.slug}{reverse('education:tolovlar_home')}"
        self.full_range = {
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
        }

    def test_tolovlar_page_uses_default_per_page(self):
        response = self.client.get(self.url, self.full_range)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["per_page"], 10)
        self.assertEqual(response.context["page_obj"].paginator.per_page, 10)
        self.assertEqual(len(response.context["page_obj"].object_list), 10)
        self.assertEqual(response.context["page_obj"].paginator.count, 25)
        self.assertEqual(response.context["payment_record_count"], 27)
        self.assertContains(response, 'value="10" selected')
        self.assertContains(response, "page=2")
        self.assertContains(response, "per_page=10")

    def test_tolovlar_page_preserves_search_and_per_page_in_links(self):
        response = self.client.get(
            self.url,
            {"q": "Alpha", "per_page": "10", **self.full_range},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["per_page"], 10)
        self.assertEqual(response.context["page_obj"].paginator.count, 15)
        self.assertEqual(len(response.context["page_obj"].object_list), 10)
        self.assertTrue(
            all("Alpha" in row["student"].ism for row in response.context["page_obj"].object_list)
        )
        self.assertContains(response, 'name="q" value="Alpha"')
        self.assertContains(response, "page=2")
        self.assertContains(response, "q=Alpha")
        self.assertContains(response, "per_page=10")

    def test_tolovlar_page_groups_multiple_payments_by_student(self):
        response = self.client.get(self.url, {"q": "Alpha 0", **self.full_range})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        row = response.context["page_obj"].object_list[0]

        self.assertEqual(row["student"].id, self.first_student.id)
        self.assertEqual(row["payment_count"], 3)
        self.assertEqual(row["total_sum"], 250_000)

    def test_tolovlar_chart_shows_last_12_months(self):
        response = self.client.get(self.url, self.full_range)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["chart_kicker"], "Oxirgi 12 oy")
        self.assertEqual(response.context["chart_period_label"], "May dan Aprel gacha")
        self.assertEqual(len(response.context["chart_labels"]), 12)
        self.assertEqual(response.context["chart_labels"][0], "May")
        self.assertEqual(response.context["chart_labels"][-1], "Aprel")
        # Diagramma QAYSI OY UCHUN to'langani bo'yicha (allocation oyi):
        # split_payment ning 25 000 so'mi 2026-may uchun yozilgan — u aprel
        # ustunida EMAS (may oynadan tashqarida). 1 450 300 - 25 000:
        self.assertEqual(response.context["chart_data"][-1], 1_425_300)
        self.assertTrue(all(value == 0 for value in response.context["chart_data"][:-1]))
        self.assertEqual(response.context["chart_payment_record_count"], 27)
        self.assertEqual(response.context["chart_unique_payers_count"], 25)

    def test_ajax_delete_soft_deletes_split_payment_and_allocations(self):
        delete_url = f"/{self.center.slug}{reverse('education:payment_delete', args=[self.split_payment.id])}"

        response = self.client.post(
            delete_url,
            {"next": self.url},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {"ok": True, "redirect_url": self.url},
        )
        self.assertFalse(Payment.objects.filter(id=self.split_payment.id).exists())
        self.assertEqual(
            PaymentAllocation.objects.filter(payment_id=self.split_payment.id).count(),
            0,
        )
        self.assertTrue(Payment.all_objects.filter(id=self.split_payment.id, is_deleted=True).exists())
