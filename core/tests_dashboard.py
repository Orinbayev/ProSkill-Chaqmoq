import json
from datetime import datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum

from accounts.models import Center, User
from core.models import DirectorAIChatMessage, DirectorAIChatSession
from core.views import _director_ai_request_params
from education.models import Attendance, Category, Enrollment, Group, Payment, TeacherIncome, TuitionMonth
from store.models import Expense, Lead, LeadStatus, Manba, Product, PurchaseRequest, Yonalish


class DirectorDashboardAPITests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.now = timezone.make_aware(datetime.combine(self.today, time(10, 0)))

        self.center = Center.objects.create(
            name="Insight Center",
            slug="insight-center",
            max_students=100,
            capacity_limit=100,
        )
        self.category = Category.objects.create(center=self.center, name="Matematika")

        self.director = User.objects.create_user(
            email="director@test.com",
            password="testpass123",
            role="director",
            center=self.center,
            ism="Direktor",
            familya="Test",
        )
        self.teacher_strong = User.objects.create_user(
            email="teacher.strong@test.com",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Ali",
            familya="Strong",
        )
        self.teacher_weak = User.objects.create_user(
            email="teacher.weak@test.com",
            password="testpass123",
            role="teacher",
            center=self.center,
            ism="Vali",
            familya="Weak",
        )
        self.manager = User.objects.create_user(
            email="manager@test.com",
            password="testpass123",
            role="manager",
            center=self.center,
            ism="Madina",
            familya="Manager",
        )

        self.student_source_a = self._student("student.a@test.com", "Aziza", "One")
        self.student_source_b = self._student("student.b@test.com", "Bekzod", "Two")
        self.student_no_lead = self._student("student.c@test.com", "Sarvar", "Three")

        self.group_strong = Group.objects.create(
            center=self.center,
            nom="Strong Group",
            category_obj=self.category,
            oqituvchi=self.teacher_strong,
            kurs_narxi=600_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.group_weak = Group.objects.create(
            center=self.center,
            nom="Weak Group",
            category_obj=self.category,
            oqituvchi=self.teacher_weak,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )

        self.enrollment_a = self._enroll(self.student_source_a, self.group_strong, 600_000)
        self.enrollment_b = self._enroll(self.student_source_b, self.group_weak, 500_000)
        self.enrollment_c = self._enroll(self.student_no_lead, self.group_strong, 600_000)

        TuitionMonth.objects.create(center=self.center, enrollment=self.enrollment_a, month=self.today.replace(day=1), fee_amount=600_000)
        TuitionMonth.objects.create(center=self.center, enrollment=self.enrollment_b, month=self.today.replace(day=1), fee_amount=500_000)
        TuitionMonth.objects.create(center=self.center, enrollment=self.enrollment_c, month=self.today.replace(day=1), fee_amount=600_000)

        self._payment(self.enrollment_a, 1_000_000)
        self._payment(self.enrollment_c, 500_000)
        self._payment(self.enrollment_a, 500_000, paid_date=self.today - timedelta(days=35))

        for day_offset in range(10):
            lesson_date = self.today - timedelta(days=day_offset)
            Attendance.objects.create(
                center=self.center,
                group=self.group_strong,
                student=self.student_source_a,
                teacher=self.teacher_strong,
                date=lesson_date,
                present=True,
                status="present",
            )
            Attendance.objects.create(
                center=self.center,
                group=self.group_strong,
                student=self.student_no_lead,
                teacher=self.teacher_strong,
                date=lesson_date,
                present=True,
                status="present",
            )

        for day_offset in range(3):
            Attendance.objects.create(
                center=self.center,
                group=self.group_weak,
                student=self.student_source_b,
                teacher=self.teacher_weak,
                date=self.today - timedelta(days=day_offset),
                present=False,
                status="absent_unexcused",
            )

        Expense.objects.create(center=self.center, summa=300_000, izoh="Ijara", sana=self.now)

        self.source_telegram = Manba.objects.create(center=self.center, nom="Telegram")
        self.source_instagram = Manba.objects.create(center=self.center, nom="Instagram")
        self.direction_maths = Yonalish.objects.create(center=self.center, nom="Matematika Pro")
        self.direction_it = Yonalish.objects.create(center=self.center, nom="IT Foundation")
        self.lead_registered = LeadStatus.objects.create(center=self.center, nom="Registered", code=LeadStatus.Code.REGISTERED)

        Lead.objects.create(
            center=self.center,
            ism="LeadA",
            familya="Alpha",
            telefon1="+998901111111",
            yosh=18,
            manba=self.source_telegram,
            yonalish=self.direction_maths,
            status=self.lead_registered,
            assigned_manager=self.manager,
            converted_user=self.student_source_a,
            converted_to_student=True,
            converted_at=timezone.now(),
            converted_by=self.director,
            created_by=self.director,
        )
        Lead.objects.create(
            center=self.center,
            ism="LeadB",
            familya="Beta",
            telefon1="+998902222222",
            yosh=19,
            manba=self.source_instagram,
            yonalish=self.direction_it,
            status=self.lead_registered,
            assigned_manager=self.manager,
            converted_user=self.student_source_b,
            converted_to_student=True,
            converted_at=timezone.now(),
            converted_by=self.director,
            created_by=self.director,
        )
        self.product = Product.objects.create(center=self.center, nom="Notebook", narx_chaqmoq=120, narx_som=45_000)
        PurchaseRequest.objects.create(
            center=self.center,
            student=self.student_source_a,
            product=self.product,
            qty=2,
            manager=self.manager,
        )

        self.client.force_login(self.director)

    def _student(self, email, ism, familya):
        return User.objects.create_user(
            email=email,
            password="testpass123",
            role="student",
            center=self.center,
            ism=ism,
            familya=familya,
            date_joined=timezone.now(),
        )

    def _enroll(self, student, group, fee):
        return Enrollment.objects.create(
            center=self.center,
            student=student,
            group=group,
            kurs_narhi=fee,
            oqituvchi_foiz=group.oqituvchi_foiz,
            is_active=True,
        )

    def _payment(self, enrollment, amount, paid_date=None):
        return Payment.objects.create(
            center=self.center,
            enrollment=enrollment,
            student=enrollment.student,
            group=enrollment.group,
            payment_type="cash",
            cash_amount=amount,
            paid_date=paid_date or self.today,
            created_by=self.director,
        )

    def _get_dashboard(self, **params):
        base_params = {
            "date_from": (self.today - timedelta(days=29)).isoformat(),
            "date_to": self.today.isoformat(),
        }
        base_params.update(params)
        return self.client.get(reverse("core:director_dashboard_api"), base_params)

    def test_dashboard_api_returns_real_payload_and_no_join_duplication(self):
        response = self._get_dashboard()
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("overview", payload)
        self.assertIn("executive", payload)
        self.assertIn("groups", payload)
        self.assertIn("marketing", payload)
        self.assertEqual(payload["finance"]["income"], 1_500_000)
        self.assertEqual(payload["groups"]["top_profitable"][0]["group_name"], "Strong Group")
        self.assertEqual(payload["groups"]["top_profitable"][0]["revenue"], 1_500_000)
        self.assertEqual(payload["teachers"]["ranking"][0]["teacher_name"], "Ali Strong")
        self.assertEqual(payload["teachers"]["ranking"][0]["revenue"], 1_500_000)
        self.assertEqual(payload["teachers"]["ranking"][0]["revenue_previous"], 500_000)
        self.assertEqual(payload["teachers"]["ranking"][0]["revenue_growth"], 200.0)
        self.assertEqual(payload["marketing"]["conversion_rate"], 50.0)
        self.assertEqual(payload["marketing"]["all_time_leads"], 2)
        self.assertEqual(payload["marketing"]["all_time_converted_students"], 2)
        self.assertEqual(payload["marketing"]["all_time_active_students"], 2)
        self.assertEqual(payload["marketing"]["sources_overall"][0]["count"], 1)
        self.assertEqual(payload["marketing"]["sources_overall"][0]["student_conversion"], 100.0)
        self.assertEqual(payload["marketing"]["directions"][0]["name"], "Matematika Pro")
        self.assertEqual(payload["marketing"]["directions"][0]["active_students"], 1)
        self.assertEqual(payload["marketing"]["directions_overall"][0]["name"], "Matematika Pro")
        self.assertEqual(payload["finance"]["payment_completion_rate"], 33.3)
        self.assertEqual(len(payload["executive"]["today_strip"]), 4)
        self.assertEqual(payload["executive"]["trend_signal"]["title"], "Qarzdorlik bosimi oshgan")
        self.assertIn("managers", payload)
        self.assertIn("requests", payload)
        self.assertEqual(payload["managers"]["total_count"], 1)
        self.assertEqual(payload["managers"]["ranking"][0]["manager_name"], "Madina Manager")
        self.assertEqual(len(payload["students"]["roster"]), 3)
        self.assertEqual(
            sorted(item["name"] for item in payload["students"]["roster"]),
            ["Aziza One", "Bekzod Two", "Sarvar Three"],
        )
        self.assertEqual(payload["requests"]["total_count"], 1)
        self.assertEqual(payload["requests"]["all_requests_count"], 1)
        self.assertEqual(payload["requests"]["products_count"], 1)
        self.assertEqual(payload["requests"]["items"][0]["product_name"], "Notebook")

    def test_source_filter_scopes_finance_to_converted_students(self):
        response = self._get_dashboard(source=str(self.source_telegram.id))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["finance"]["income"], 1_000_000)
        self.assertEqual(payload["students"]["active_students"], 1)
        self.assertEqual(payload["filters"]["applied"]["source_ids"], [self.source_telegram.id])

    def test_group_close_candidate_is_flagged(self):
        response = self._get_dashboard()
        payload = response.json()

        close_candidates = payload["groups"]["close_candidates"]
        self.assertTrue(close_candidates)
        self.assertEqual(close_candidates[0]["group_name"], "Weak Group")
        self.assertEqual(close_candidates[0]["primary_action"], "Yopish tavsiya etiladi")

    def test_request_payload_returns_all_filtered_items(self):
        for idx in range(25):
            PurchaseRequest.objects.create(
                center=self.center,
                student=self.student_source_a if idx % 2 == 0 else self.student_source_b,
                product=self.product,
                qty=1,
                manager=self.manager,
            )

        response = self._get_dashboard()
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["requests"]["total_count"], 26)
        self.assertEqual(payload["requests"]["all_requests_count"], 26)
        self.assertEqual(payload["requests"]["products_count"], 1)
        self.assertEqual(len(payload["requests"]["items"]), 26)

    def test_dashboard_teacher_shares_follow_teacher_income_rows(self):
        response = self._get_dashboard()
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        expected_teacher_shares = (
            TeacherIncome.objects.filter(
                center=self.center,
                attendance__date__range=(self.today - timedelta(days=29), self.today),
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        self.assertEqual(payload["finance"]["teacher_shares"], expected_teacher_shares)

    def test_rate_change_recalculates_future_month_attendance(self):
        future_date = self.today.replace(day=1) + timedelta(days=32)
        future_date = future_date.replace(day=5)

        future_attendance = Attendance.objects.create(
            center=self.center,
            group=self.group_strong,
            student=self.student_source_a,
            teacher=self.teacher_strong,
            date=future_date,
            present=True,
            status="present",
        )

        future_income = TeacherIncome.objects.get(attendance=future_attendance)
        self.assertEqual(future_income.amount, 20_000)

        self.teacher_strong.oqituvchi_foizi = 50
        self.teacher_strong.save()

        future_income.refresh_from_db()
        self.assertEqual(future_income.amount, 25_000)

    def test_director_home_uses_new_dashboard_template(self):
        response = self.client.get(f"/{self.center.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DIREKTOR PANELI")
        self.assertContains(response, "Bildirishnomalar")
        self.assertContains(response, 'id="profile-dd"')
        self.assertContains(response, 'id="kpi-grid"')
        self.assertContains(response, 'id="rev-chart"')
        self.assertContains(response, 'id="donut-chart"')
        self.assertContains(response, 'id="finance-section"')
        self.assertContains(response, 'id="payments-section"')
        self.assertContains(response, 'id="modal-detail-btn"')
        self.assertContains(response, 'id="dateFromInput"')
        self.assertContains(response, 'id="dateToInput"')
        self.assertContains(response, 'id="branchSelect"')
        self.assertContains(response, 'id="churn-risk-list"')
        self.assertContains(response, 'id="forecast-chart"')
        self.assertContains(response, 'id="directorAiChatLauncher"')
        self.assertContains(response, 'id="directorAiChatHeaderBtn"')
        self.assertContains(response, 'id="directorAiChatPanel"')
        self.assertContains(response, 'id="directorAiChatForm"')
        self.assertContains(response, 'id="directorAiChatMessages"')
        self.assertContains(response, 'id="directorAiChatReset"')
        self.assertContains(response, 'id="tab-count-manager"')
        self.assertContains(response, 'id="tab-count-products"')
        self.assertContains(response, "Mahsulotlar")
        self.assertContains(response, 'Trend ustuni o‘tgan oyga nisbatan ko‘rsatiladi')
        self.assertNotContains(response, "Konversiya voronkasi")
        self.assertNotContains(response, 'id="aiAskForm"')
        self.assertNotContains(response, 'id="ai-answer-modal"')

    def test_ai_question_period_keywords_override_dashboard_dates(self):
        params = {
            "preset": "custom",
            "date_from": (self.today - timedelta(days=7)).isoformat(),
            "date_to": self.today.isoformat(),
        }

        resolved_today = _director_ai_request_params("Bugungi foyda qancha bo'ldi?", params)
        self.assertEqual(resolved_today["preset"], "today")
        self.assertNotIn("date_from", resolved_today)
        self.assertNotIn("date_to", resolved_today)

        resolved_last_month = _director_ai_request_params("O'tgan oy daromad qancha edi?", params)
        self.assertEqual(resolved_last_month["preset"], "last_month")

        resolved_last_month_typo = _director_ai_request_params("O'tkan oydagi fodya qancha?", params)
        self.assertEqual(resolved_last_month_typo["preset"], "last_month")

        resolved_exact_day = _director_ai_request_params("8 aprel foyda qancha bo'ldi?", params)
        self.assertEqual(resolved_exact_day["preset"], "custom")
        self.assertEqual(resolved_exact_day["date_from"], f"{self.today.year}-04-08")
        self.assertEqual(resolved_exact_day["date_to"], f"{self.today.year}-04-08")

    def test_ai_endpoints_return_payload(self):
        params = {
            "date_from": (self.today - timedelta(days=29)).isoformat(),
            "date_to": self.today.isoformat(),
        }

        insights_response = self.client.get(reverse("core:director_ai_insights_api"), params)
        self.assertEqual(insights_response.status_code, 200)
        insights_payload = insights_response.json()
        self.assertIn("insights", insights_payload)
        self.assertTrue(insights_payload["insights"])

        churn_response = self.client.get(reverse("core:director_ai_churn_risk_api"), params)
        self.assertEqual(churn_response.status_code, 200)
        churn_payload = churn_response.json()
        self.assertIn("items", churn_payload)
        self.assertIn("summary", churn_payload)
        self.assertIn("average_score", churn_payload["summary"])

        forecast_response = self.client.get(reverse("core:director_ai_forecast_api"), params)
        self.assertEqual(forecast_response.status_code, 200)
        forecast_payload = forecast_response.json()
        self.assertEqual(len(forecast_payload["items"]), 9)
        self.assertTrue(any(item["is_forecast"] for item in forecast_payload["items"]))

        ask_response = self.client.post(
            reverse("core:director_ai_ask_api") + f"?date_from={params['date_from']}&date_to={params['date_to']}",
            data=json.dumps({"question": "Eng kuchli ustoz kim?"}),
            content_type="application/json",
        )
        self.assertEqual(ask_response.status_code, 200)
        ask_payload = ask_response.json()
        self.assertIn("answer", ask_payload)
        self.assertTrue(ask_payload["answer"])

        site_ask_response = self.client.post(
            reverse("core:director_ai_ask_api") + f"?date_from={params['date_from']}&date_to={params['date_to']}",
            data=json.dumps({"question": "Saytimda nima bor?"}),
            content_type="application/json",
        )
        self.assertEqual(site_ask_response.status_code, 200)
        self.assertIn("ChaqmoqApp direktor panelida", site_ask_response.json()["answer"])

        active_student_response = self.client.post(
            reverse("core:director_ai_ask_api") + f"?date_from={params['date_from']}&date_to={params['date_to']}",
            data=json.dumps({"question": "Eng faol o'quvchi kim?"}),
            content_type="application/json",
        )
        self.assertEqual(active_student_response.status_code, 200)
        self.assertIn("eng faol o'quvchi", active_student_response.json()["answer"].lower())

        typo_profit_response = self.client.post(
            reverse("core:director_ai_ask_api") + f"?date_from={params['date_from']}&date_to={params['date_to']}",
            data=json.dumps({"question": "O'tkan oydagi fodya qancha?"}),
            content_type="application/json",
        )
        self.assertEqual(typo_profit_response.status_code, 200)
        typo_answer = typo_profit_response.json()["answer"].lower()
        self.assertIn("foyda", typo_answer)
        self.assertNotIn("daromad rejasi", typo_answer)

        today_profit_response = self.client.post(
            reverse("core:director_ai_ask_api") + f"?date_from={params['date_from']}&date_to={params['date_to']}",
            data=json.dumps({"question": "Bugungi foyda qancha bo'ldi?"}),
            content_type="application/json",
        )
        self.assertEqual(today_profit_response.status_code, 200)
        today_profit_answer = today_profit_response.json()["answer"].lower()
        self.assertIn("foyda", today_profit_answer)
        self.assertNotIn("chaqmoqapp direktor panelida", today_profit_answer)

        student_total_response = self.client.post(
            reverse("core:director_ai_ask_api") + f"?date_from={params['date_from']}&date_to={params['date_to']}",
            data=json.dumps({"question": "O'quv markazda nechta o'quvchi bor?"}),
            content_type="application/json",
        )
        self.assertEqual(student_total_response.status_code, 200)
        student_total_answer = student_total_response.json()["answer"].lower()
        self.assertIn("o'quvchi", student_total_answer)
        self.assertIn(str(User.objects.filter(center=self.center, role="student", is_archived=False).count()), student_total_answer)
        self.assertNotIn("eng kuchli ustoz", student_total_answer)

        forecast_question_response = self.client.post(
            reverse("core:director_ai_ask_api") + f"?date_from={params['date_from']}&date_to={params['date_to']}",
            data=json.dumps({"question": "Kelasi oy qancha daromad ko'rishimiz mumkin?"}),
            content_type="application/json",
        )
        self.assertEqual(forecast_question_response.status_code, 200)
        forecast_answer = forecast_question_response.json()["answer"].lower()
        self.assertTrue(
            any(keyword in forecast_answer for keyword in ["prognoz", "taxminan", "weighted moving average"])
        )
        self.assertNotIn("eng kuchli ustoz", forecast_answer)

        chat_response = self.client.get(reverse("core:director_ai_chat_api"), params)
        self.assertEqual(chat_response.status_code, 200)
        chat_payload = chat_response.json()
        self.assertIn("session", chat_payload)
        self.assertEqual(chat_payload["messages"], [])

        chat_ask_response = self.client.post(
            reverse("core:director_ai_chat_ask_api") + f"?date_from={params['date_from']}&date_to={params['date_to']}",
            data=json.dumps({"question": "Eng qarzdor guruh qaysi?"}),
            content_type="application/json",
        )
        self.assertEqual(chat_ask_response.status_code, 200)
        chat_ask_payload = chat_ask_response.json()
        self.assertIn("assistant_message", chat_ask_payload)
        self.assertTrue(chat_ask_payload["assistant_message"]["content"])
        session = DirectorAIChatSession.objects.get(pk=chat_ask_payload["session"]["id"])
        self.assertEqual(session.messages.count(), 2)
        self.assertEqual(
            list(session.messages.values_list("role", flat=True)),
            [DirectorAIChatMessage.Role.USER, DirectorAIChatMessage.Role.ASSISTANT],
        )

        followup_greeting_response = self.client.post(
            reverse("core:director_ai_chat_ask_api") + f"?date_from={params['date_from']}&date_to={params['date_to']}",
            data=json.dumps({"question": "Salom"}),
            content_type="application/json",
        )
        self.assertEqual(followup_greeting_response.status_code, 200)
        greeting_answer = followup_greeting_response.json()["assistant_message"]["content"].lower()
        self.assertIn("salom", greeting_answer)
        self.assertNotIn("qarzdor guruh", greeting_answer)

        position_response = self.client.post(
            reverse("core:director_ai_chat_position_api"),
            data=json.dumps({"position": {"x": 160, "y": 280}}),
            content_type="application/json",
        )
        self.assertEqual(position_response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.launcher_position, {"x": 160, "y": 280})

        reset_response = self.client.post(
            reverse("core:director_ai_chat_reset_api"),
            data=json.dumps({"reset": True}),
            content_type="application/json",
        )
        self.assertEqual(reset_response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.messages.count(), 0)
