from datetime import datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from core.models import CenterDailyMetric, StudentDailyMetric, TeacherDailyMetric
from core.dashboard_views import UZ_MONTHS
from core.services.center_ai_context import (
    build_center_ai_context,
    generate_center_alerts,
    get_monthly_stats,
    get_student_full_info,
    get_teacher_full_info,
)
from education.models import Attendance, Category, Enrollment, FinancialMonth, Group, MonthlyFinanceSnapshot, Payment, PaymentAllocation, TeacherIncome, TuitionMonth
from store.models import Expense, Lead, LeadStatus, Manba, Product, PurchaseRequest, Yonalish


class CenterAnalyticsServiceTests(TestCase):
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

    def test_manager_context_masks_phone_details(self):
        self.student_source_a.telefon1 = "+998901234567"
        self.student_source_a.save(update_fields=["telefon1"])
        context = build_center_ai_context(self.center, viewer=self.manager, limit=5)
        student_items = context["students"]["items"]
        self.assertTrue(student_items)
        self.assertEqual(context["students"]["summary"]["privacy_mode"], "limited")
        self.assertIn("*", student_items[0]["phone"])

    def test_student_full_info_returns_real_student_data(self):
        self.student_source_a.telefon1 = "+998901234567"
        self.student_source_a.save(update_fields=["telefon1"])

        result = get_student_full_info(self.center.id, "Aziza", viewer=self.director)
        self.assertEqual(result["count"], 1)
        item = result["items"][0]
        self.assertEqual(item["full_name"], "Aziza One")
        self.assertEqual(item["teacher_name"], "Ali Strong")
        self.assertIn("Strong Group", item["courses"])
        self.assertEqual(item["status"], "active")
        self.assertGreaterEqual(item["total_payment"], 1_500_000)
        self.assertGreaterEqual(item["attendance"]["present"], 1)

    def test_teacher_full_info_returns_real_teacher_data(self):
        self.teacher_strong.telefon1 = "+998901112233"
        self.teacher_strong.save(update_fields=["telefon1"])

        result = get_teacher_full_info(self.center.id, "Ali Strong", viewer=self.director)
        self.assertEqual(result["count"], 1)
        item = result["items"][0]
        self.assertEqual(item["teacher_name"], "Ali Strong")
        self.assertEqual(item["groups_count"], 1)
        self.assertEqual(item["active_groups"], 1)
        self.assertEqual(item["students_count"], 2)
        self.assertEqual(item["total_income"], 2_000_000)

    def test_monthly_stats_returns_growth_percentage(self):
        last_month = self.today.replace(day=1) - timedelta(days=1)
        old_date = timezone.make_aware(datetime.combine(last_month.replace(day=10), time(10, 0)))
        self.student_source_a.date_joined = old_date
        self.student_source_a.save(update_fields=["date_joined"])
        self.student_source_b.date_joined = old_date
        self.student_source_b.save(update_fields=["date_joined"])

        stats = get_monthly_stats(self.center.id, as_of=self.today)
        self.assertEqual(stats["this_month_students"], 1)
        self.assertEqual(stats["last_month_students"], 2)
        self.assertEqual(stats["growth_percentage"], -50.0)

    def test_generate_center_alerts_flags_group_risk(self):
        alerts = generate_center_alerts(self.center.id, as_of=self.today)
        self.assertTrue(alerts)
        self.assertTrue(any(item["code"] == "group_at_risk" for item in alerts))

    def test_boshqaruv_api_includes_legacy_finance_rows_without_center(self):
        last_month_day = self.today.replace(day=1) - timedelta(days=1)
        last_month_date = last_month_day.replace(day=min(12, last_month_day.day))

        Payment.objects.create(
            center=None,
            enrollment=self.enrollment_b,
            student=self.student_source_b,
            group=self.group_weak,
            payment_type="cash",
            cash_amount=700_000,
            paid_date=last_month_date,
            created_by=self.director,
        )
        Expense.objects.create(
            center=None,
            worker=self.manager,
            summa=200_000,
            izoh="Legacy xarajat",
            sana=timezone.make_aware(datetime.combine(last_month_date, time(11, 0))),
        )

        response = self.client.get(
            reverse("core:director_boshqaruv_api"),
            {
                "date_from": last_month_date.replace(day=1).isoformat(),
                "date_to": self.today.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["kpis"]["revenue"], 2_700_000)
        self.assertGreaterEqual(data["kpis"]["expenses"], 500_000)
        self.assertIn(1_200_000, data["charts"]["monthly_turnover"])
        self.assertIn(200_000, data["charts"]["monthly_expenses"])

    def test_boshqaruv_api_counts_legacy_archived_students_in_current_month(self):
        legacy_archived = self._student("legacy.archived@test.com", "Legacy", "Archived")
        legacy_archived.is_archived = True
        legacy_archived.archived_at = None
        legacy_archived.save(update_fields=["is_archived", "archived_at"])

        response = self.client.get(reverse("core:director_boshqaruv_api"))
        self.assertEqual(response.status_code, 200)

        data = response.json()
        current_month_left = data["charts"]["monthly_left"][-1]
        self.assertGreaterEqual(current_month_left, 1)

    def test_boshqaruv_api_monthly_turnover_uses_payment_allocations_for_history(self):
        history_month = (self.today.replace(day=1) - timedelta(days=90)).replace(day=1)
        history_tuition, _ = TuitionMonth.objects.get_or_create(
            center=self.center,
            enrollment=self.enrollment_b,
            month=history_month,
            defaults={"fee_amount": 500_000},
        )
        april_payment = Payment.objects.create(
            center=self.center,
            enrollment=self.enrollment_b,
            student=self.enrollment_b.student,
            group=self.enrollment_b.group,
            payment_type="cash",
            cash_amount=900_000,
            paid_date=self.today,
            created_by=self.director,
        )
        PaymentAllocation.objects.create(
            center=self.center,
            payment=april_payment,
            tuition_month=history_tuition,
            amount=900_000,
        )

        response = self.client.get(reverse("core:director_boshqaruv_api"))
        self.assertEqual(response.status_code, 200)

        data = response.json()
        labels = data["charts"]["monthly_labels"]
        turnover = data["charts"]["monthly_turnover"]
        history_label = UZ_MONTHS[history_month.month]
        current_label = UZ_MONTHS[self.today.month]

        self.assertEqual(turnover[labels.index(current_label)], 1_500_000)
        self.assertGreaterEqual(turnover[labels.index(history_label)], 900_000)

    def test_boshqaruv_api_returns_payment_breakdown_by_category(self):
        language_category = Category.objects.create(center=self.center, name="Language")
        language_group = Group.objects.create(
            center=self.center,
            nom="Language Group",
            category_obj=language_category,
            oqituvchi=self.teacher_weak,
            kurs_narxi=400_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        language_student = self._student("student.language@test.com", "Lola", "Lang")
        language_enrollment = self._enroll(language_student, language_group, 400_000)
        TuitionMonth.objects.create(
            center=self.center,
            enrollment=language_enrollment,
            month=self.today.replace(day=1),
            fee_amount=400_000,
        )

        response = self.client.get(reverse("core:director_boshqaruv_api"))
        self.assertEqual(response.status_code, 200)

        charts = response.json()["charts"]
        self.assertEqual(charts["pay_status_labels"], ["To'lagan", "To'lamagan", "Qisman"])
        self.assertEqual(sum(charts["pay_status_counts"]), 4)

        breakdown = {row["name"]: row for row in charts["pay_category_breakdown"]}
        self.assertEqual(breakdown["Matematika"]["total"], 3)
        self.assertEqual(breakdown["Matematika"]["paid"], 1)
        self.assertEqual(breakdown["Matematika"]["unpaid"], 1)
        self.assertEqual(breakdown["Matematika"]["partial"], 1)
        self.assertEqual(breakdown["Language"]["total"], 1)
        self.assertEqual(breakdown["Language"]["paid"], 0)
        self.assertEqual(breakdown["Language"]["unpaid"], 1)
        self.assertEqual(breakdown["Language"]["partial"], 0)

    def test_boshqaruv_api_reports_converted_lead_sources_and_payment_amounts(self):
        extra_student = self._student("student.extra.source@test.com", "Dilshod", "Source")
        Lead.objects.create(
            center=self.center,
            ism="LeadC",
            familya="Gamma",
            telefon1="+998903333333",
            yosh=20,
            manba=self.source_telegram,
            yonalish=self.direction_maths,
            status=self.lead_registered,
            assigned_manager=self.manager,
            converted_user=extra_student,
            converted_to_student=True,
            converted_at=timezone.now(),
            converted_by=self.director,
            created_by=self.director,
        )

        response = self.client.get(reverse("core:director_boshqaruv_api"))

        self.assertEqual(response.status_code, 200)
        charts = response.json()["charts"]
        self.assertEqual(
            charts["funnel_labels"],
            ["Yangi lid", "Bog'langan", "Trial darsda", "Ro'yxatdan o'tdi"],
        )
        self.assertEqual(charts["funnel"][3], 3)
        self.assertEqual(charts["source_labels"][0], "Telegram")
        self.assertEqual(charts["source_counts"][0], 2)

        payment_amounts = dict(zip(charts["pay_method_labels"], charts["pay_method_amounts"]))
        payment_counts = dict(zip(charts["pay_method_labels"], charts["pay_method_counts"]))
        self.assertEqual(payment_counts["Naqd"], 2)
        self.assertEqual(payment_amounts["Naqd"], 1_500_000)

    def test_boshqaruv_api_uses_monthly_snapshot_when_live_month_is_empty(self):
        history_month = (self.today.replace(day=1) - timedelta(days=150)).replace(day=1)
        financial_month = FinancialMonth.objects.create(
            center=self.center,
            year=history_month.year,
            month=history_month.month,
            is_closed=True,
        )
        MonthlyFinanceSnapshot.objects.create(
            financial_month=financial_month,
            total_income=4_200_000,
            total_expense=1_100_000,
            center_profit=3_100_000,
            student_count=12,
            attendance_rate=87.5,
        )

        response = self.client.get(reverse("core:director_boshqaruv_api"))
        self.assertEqual(response.status_code, 200)

        charts = response.json()["charts"]
        history_label = UZ_MONTHS[history_month.month]
        self.assertGreaterEqual(charts["monthly_turnover"][charts["monthly_labels"].index(history_label)], 4_200_000)
        self.assertGreaterEqual(charts["monthly_expenses"][charts["monthly_labels"].index(history_label)], 1_100_000)

    def test_daily_metric_models_can_be_created(self):
        center_metric = CenterDailyMetric.objects.create(
            center=self.center,
            date=self.today,
            students_count=3,
            teachers_count=2,
            revenue=1_500_000,
        )
        teacher_metric = TeacherDailyMetric.objects.create(
            center=self.center,
            teacher=self.teacher_strong,
            date=self.today,
            students_count=2,
            revenue=2_000_000,
        )
        student_metric = StudentDailyMetric.objects.create(
            center=self.center,
            student=self.student_source_a,
            date=self.today,
            attendance=True,
            payment_status="paid",
        )
        self.assertEqual(center_metric.students_count, 3)
        self.assertEqual(teacher_metric.revenue, 2_000_000)
        self.assertTrue(student_metric.attendance)
