import json

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta

from accounts.models import Center, User
from education.models import Category, Enrollment, Group, GroupStudent, Student as EducationStudent
from store.forms import LeadForm
from store.lead_services import (
    confirm_lead,
    convert_lead_to_student_safe,
    ensure_default_lead_catalog,
    ensure_default_lead_subjects,
    get_status_by_code,
    send_follow_up_notification_if_due,
)
from store.models import Expense, ExpenseCategory, Lead, LeadGroup, LeadStatus, Manba, Product, PurchaseRequest, TrialLesson, Yonalish
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
        registered_status = get_status_by_code(center=self.center, code=LeadStatus.Code.REGISTERED)
        lead.status = registered_status
        lead.is_confirmed = True
        lead.confirmed_at = timezone.now()
        lead.confirmed_by = self.manager
        lead.save(update_fields=["status", "is_confirmed", "confirmed_at", "confirmed_by", "updated_at"])

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


class LeadApiTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(
            name="Lead API Center",
            slug="lead-api-center",
            features={"leads": True},
        )
        self.manager = User.objects.create_user(
            email="manager@lead-api.test",
            password="Pass12345!",
            role="manager",
            center=self.center,
            ism="Api",
            familya="Manager",
        )
        self.superadmin = User.objects.create_user(
            email="superadmin@lead-api.test",
            password="Pass12345!",
            role="director",
            center=self.center,
            ism="Api",
            familya="Superadmin",
        )
        self.superadmin.is_staff = True
        self.superadmin.is_superuser = True
        self.superadmin.save(update_fields=["is_staff", "is_superuser"])
        self.other_manager = User.objects.create_user(
            email="other-manager@lead-api.test",
            password="Pass12345!",
            role="manager",
            center=self.center,
            ism="Other",
            familya="Manager",
        )
        self.teacher = User.objects.create_user(
            email="teacher@lead-api.test",
            password="Pass12345!",
            role="teacher",
            center=self.center,
            ism="Api",
            familya="Teacher",
        )
        self.teacher.oqituvchi_foizi = 45
        self.teacher.save(update_fields=["oqituvchi_foizi"])
        self.other_center = Center.objects.create(
            name="Other Lead Center",
            slug="other-lead-center",
            features={"leads": True},
        )
        self.other_teacher = User.objects.create_user(
            email="teacher@other-lead-api.test",
            password="Pass12345!",
            role="teacher",
            center=self.other_center,
            ism="Other",
            familya="Teacher",
        )
        self.department = Category.objects.create(center=self.center, name="English")
        self.it_department = Category.objects.create(center=self.center, name="IT")
        self.other_department = Category.objects.create(center=self.other_center, name="Other Department")
        self.group = Group.objects.create(
            center=self.center,
            nom="IELTS Pro",
            oqituvchi=self.teacher,
            kurs_narxi=650_000,
            oqituvchi_foiz=45,
            oy_dars_soni=14,
        )
        self.other_group = Group.objects.create(
            center=self.other_center,
            nom="Other Group",
            oqituvchi=self.other_teacher,
            kurs_narxi=500_000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        ensure_default_lead_catalog(self.center)
        ensure_default_lead_subjects(self.center)
        self.ielts_subject = Yonalish.objects.get(center=self.center, nom="IELTS")
        self.math_subject = Yonalish.objects.get(center=self.center, nom="Matematika")
        self.russian_subject = Yonalish.objects.get(center=self.center, nom="Rus tili")
        self.other_subject = Yonalish.objects.get(center=self.center, nom="Boshqa")
        self.client.force_login(self.manager)

        self.api_url = f"/{self.center.slug}{reverse('store:leads_api')}"
        self.detail_base = f"/{self.center.slug}{reverse('store:lead_api_detail', args=[0])}".removesuffix("0/")
        self.archive_base = f"/{self.center.slug}{reverse('store:lead_api_archive', args=[0])}".removesuffix("0/archive/")
        self.restore_base = f"/{self.center.slug}{reverse('store:lead_api_restore', args=[0])}".removesuffix("0/restore/")
        self.confirm_base = f"/{self.center.slug}{reverse('store:lead_api_confirm', args=[0])}".removesuffix("0/confirm/")
        self.assign_group_base = f"/{self.center.slug}{reverse('store:lead_api_assign_lead_group', args=[0])}".removesuffix("0/assign-lead-group/")
        self.convert_base = f"/{self.center.slug}{reverse('store:lead_api_convert', args=[0])}".removesuffix("0/convert/")
        self.lead_groups_url = f"/{self.center.slug}{reverse('store:lead_groups_api')}"
        self.lead_group_detail_base = f"/{self.center.slug}{reverse('store:lead_group_detail_api', args=[0])}".removesuffix("0/")
        self.lead_group_archive_base = f"/{self.center.slug}{reverse('store:lead_group_archive_api', args=[0])}".removesuffix("0/archive/")
        self.lead_group_restore_base = f"/{self.center.slug}{reverse('store:lead_group_restore_api', args=[0])}".removesuffix("0/restore/")
        self.lead_group_convert_base = f"/{self.center.slug}{reverse('store:lead_group_convert_api', args=[0])}".removesuffix("0/convert-to-group/")
        self.subjects_url = f"/{self.center.slug}{reverse('store:lead_subjects_api')}"
        self.statuses_url = f"/{self.center.slug}{reverse('store:lead_statuses_api')}"

    def _detail_url(self, lead_id: int) -> str:
        return f"{self.detail_base}{lead_id}/"

    def _convert_url(self, lead_id: int) -> str:
        return f"{self.convert_base}{lead_id}/convert/"

    def _archive_url(self, lead_id: int) -> str:
        return f"{self.archive_base}{lead_id}/archive/"

    def _restore_url(self, lead_id: int) -> str:
        return f"{self.restore_base}{lead_id}/restore/"

    def _confirm_url(self, lead_id: int) -> str:
        return f"{self.confirm_base}{lead_id}/confirm/"

    def _assign_group_url(self, lead_id: int) -> str:
        return f"{self.assign_group_base}{lead_id}/assign-lead-group/"

    def _lead_group_detail_url(self, lead_group_id: int) -> str:
        return f"{self.lead_group_detail_base}{lead_group_id}/"

    def _lead_group_archive_url(self, lead_group_id: int) -> str:
        return f"{self.lead_group_archive_base}{lead_group_id}/archive/"

    def _lead_group_restore_url(self, lead_group_id: int) -> str:
        return f"{self.lead_group_restore_base}{lead_group_id}/restore/"

    def _lead_group_convert_url(self, lead_group_id: int) -> str:
        return f"{self.lead_group_convert_base}{lead_group_id}/convert-to-group/"

    def _subject_detail_url(self, subject_id: int) -> str:
        return f"{self.subjects_url}{subject_id}/"

    def _status_detail_url(self, status_id: int) -> str:
        return f"{self.statuses_url}{status_id}/"

    def _make_lead(self, **overrides) -> Lead:
        lead = Lead.objects.create(
            center=self.center,
            ism=overrides.pop("ism", "Lead"),
            familya=overrides.pop("familya", "User"),
            telefon1=overrides.pop("telefon1", "+998901111111"),
            yosh=overrides.pop("yosh", 15),
            assigned_manager=overrides.pop("assigned_manager", self.manager),
            yonalish=overrides.pop("yonalish", self.other_subject),
            **overrides,
        )
        return lead

    def _mark_lead_confirmed(self, lead: Lead, *, actor=None) -> Lead:
        confirm_lead(lead=lead, actor=actor or self.manager)
        lead.refresh_from_db()
        return lead

    def test_create_lead_via_api(self):
        response = self.client.post(
            self.api_url,
            data=json.dumps(
                {
                    "name": "Ali Valiyev",
                    "phone": "90 123 45 67",
                    "subject": str(self.ielts_subject.id),
                    "status": Lead.PipelineStatus.NEW,
                    "note": "Telegram orqali yozgan",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response["Content-Type"], "application/json")
        lead = Lead.objects.get(center=self.center, ism="Ali", familya="Valiyev")
        self.assertEqual(lead.telefon1, "+998901234567")
        self.assertEqual(lead.yonalish_id, self.ielts_subject.id)
        self.assertEqual(lead.pipeline_status, Lead.PipelineStatus.NEW)
        self.assertEqual(lead.assigned_manager_id, self.manager.id)
        self.assertEqual(lead.comment, "Telegram orqali yozgan")

    def test_manager_cannot_override_assigned_manager_on_create(self):
        response = self.client.post(
            self.api_url,
            data=json.dumps(
                {
                    "name": "Override Manager",
                    "phone": "90 555 44 33",
                    "subject": str(self.math_subject.id),
                    "status": Lead.PipelineStatus.NEW,
                    "manager": self.other_manager.id,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        lead = Lead.objects.get(center=self.center, ism="Override", familya="Manager")
        self.assertEqual(lead.assigned_manager_id, self.manager.id)

    def test_director_can_choose_manager_on_create(self):
        self.client.force_login(self.superadmin)

        response = self.client.post(
            self.api_url,
            data=json.dumps(
                {
                    "name": "Director Choice",
                    "phone": "90 888 77 66",
                    "subject": str(self.russian_subject.id),
                    "status": Lead.PipelineStatus.NEW,
                    "manager": self.other_manager.id,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        lead = Lead.objects.get(center=self.center, ism="Director", familya="Choice")
        self.assertEqual(lead.assigned_manager_id, self.other_manager.id)

    def test_leads_api_returns_existing_leads_as_json(self):
        existing = self._make_lead(ism="Existing", telefon1="+998901234568", yonalish=self.ielts_subject)

        response = self.client.get(self.api_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        data = response.json()
        self.assertIn("results", data)
        self.assertIn("count", data)
        self.assertIn("next", data)
        self.assertIn("previous", data)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], existing.id)

    def test_subject_filter_returns_only_matching_leads(self):
        ielts_lead = self._make_lead(ism="Ielts", telefon1="+998901111112", yonalish=self.ielts_subject)
        self._make_lead(ism="Math", telefon1="+998901111113", yonalish=self.math_subject)

        response = self.client.get(self.api_url, {"subjects": [self.ielts_subject.id]})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], ielts_lead.id)
        self.assertEqual(data["results"][0]["subject"], str(self.ielts_subject.id))

    def test_status_filter_returns_only_matching_leads(self):
        contacted_status = get_status_by_code(center=self.center, code=LeadStatus.Code.CONTACTED)
        contacted_lead = self._make_lead(
            ism="Contacted",
            telefon1="+998901111114",
            status=contacted_status,
        )
        self._make_lead(ism="Fresh", telefon1="+998901111115")

        response = self.client.get(self.api_url, {"statuses": [Lead.PipelineStatus.CONTACTED]})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], contacted_lead.id)
        self.assertEqual(data["results"][0]["status"], Lead.PipelineStatus.CONTACTED)

    def test_search_filters_by_name_phone_subject_and_status(self):
        ali = self._make_lead(ism="Ali", familya="Karimov", telefon1="+998909990001")
        custom_status = LeadStatus.objects.create(
            center=self.center,
            nom="Qayta aloqada",
            code="custom_recontact",
            order=195,
            is_active=True,
        )
        subject_lead = self._make_lead(
            ism="Vali",
            familya="Sobirov",
            telefon1="+998909990002",
            yonalish=self.math_subject,
            status=custom_status,
        )

        response = self.client.get(self.api_url, {"q": "9990001"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], ali.id)

        response = self.client.get(self.api_url, {"q": "Ali"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["id"], ali.id)

        response = self.client.get(self.api_url, {"q": "Matematika"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["id"], subject_lead.id)

        response = self.client.get(self.api_url, {"q": "Qayta aloqada"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["id"], subject_lead.id)

    def test_pagination_returns_requested_page_size(self):
        for index in range(25):
            self._make_lead(
                ism=f"Lead{index}",
                telefon1=f"+99890120{index:04d}",
            )

        response = self.client.get(self.api_url, {"page_size": 10, "page": 2})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 10)
        self.assertEqual(data["page"], 2)
        self.assertEqual(data["page_size"], 10)
        self.assertEqual(data["count"], 25)
        self.assertIsNotNone(data["next"])
        self.assertIsNotNone(data["previous"])

    def test_kanban_view_returns_all_filtered_leads_without_pagination(self):
        contacted_status = get_status_by_code(center=self.center, code=LeadStatus.Code.CONTACTED)
        for index in range(25):
            self._make_lead(
                ism=f"Kanban{index}",
                telefon1=f"+99890130{index:04d}",
                status=contacted_status,
            )
        self._make_lead(ism="Fresh", telefon1="+998901309999")

        response = self.client.get(
            self.api_url,
            {
                "view": "kanban",
                "page_size": 10,
                "page": 2,
                "statuses": [Lead.PipelineStatus.CONTACTED],
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 25)
        self.assertEqual(len(data["results"]), 25)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["num_pages"], 1)
        self.assertIsNone(data["next"])
        self.assertIsNone(data["previous"])
        self.assertEqual(data["counts"][Lead.PipelineStatus.CONTACTED], 25)

    def test_kanban_status_move_updates_pipeline_status(self):
        lead = self._make_lead(
            ism="Pipeline",
            telefon1="+998901111116",
            yonalish=Yonalish.objects.get(center=self.center, nom="General English"),
        )

        response = self.client.patch(
            self._detail_url(lead.id),
            data=json.dumps(
                {
                    "name": lead.full_name,
                    "phone": lead.telefon1,
                    "subject": str(lead.yonalish_id),
                    "status": Lead.PipelineStatus.TRIAL,
                    "note": lead.comment or "",
                    "manager": self.manager.id,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.pipeline_status, Lead.PipelineStatus.TRIAL)
        self.assertEqual(lead.status.code, LeadStatus.Code.TRIAL_SCHEDULED)
        self.assertEqual(response.json()["lead"]["status"], Lead.PipelineStatus.TRIAL)

    def test_confirm_endpoint_converts_lead_to_student(self):
        lead = self._make_lead(
            ism="Confirmed",
            familya="Lead",
            telefon1="+998901111117",
            yonalish=self.russian_subject,
        )

        response = self.client.post(
            self._confirm_url(lead.id),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        lead.refresh_from_db()
        self.assertTrue(lead.is_confirmed)
        self.assertTrue(lead.converted_to_student)
        self.assertTrue(lead.is_archived)
        self.assertIsNotNone(lead.confirmed_at)
        self.assertEqual(lead.confirmed_by_id, self.manager.id)
        self.assertIsNotNone(lead.converted_user_id)
        self.assertEqual(lead.status.code, LeadStatus.Code.REGISTERED)
        self.assertTrue(User.objects.filter(id=lead.converted_user_id, role="student").exists())
        self.assertTrue(EducationStudent.objects.filter(user_id=lead.converted_user_id, center=self.center).exists())
        self.assertFalse(Enrollment.objects.filter(student_id=lead.converted_user_id, is_active=True).exists())
        self.assertEqual(response.json()["message"], "Lead o‘quvchiga aylantirildi")
        self.assertEqual(response.json()["student_id"], lead.converted_user_id)
        self.assertTrue(response.json()["student"]["created"])
        self.assertEqual(response.json()["lead"]["status"], Lead.PipelineStatus.CONVERTED)

    def test_confirm_endpoint_allows_same_phone_for_different_student(self):
        User.objects.create_user(
            email="existing-confirmed@student.test",
            password="Pass12345!",
            role="student",
            center=self.center,
            ism="Existing",
            familya="Student",
            telefon1="+998901111171",
            phone_number="+998901111171",
        )
        lead = self._make_lead(
            ism="Duplicate",
            familya="Phone",
            telefon1="+998901111171",
            yonalish=self.ielts_subject,
        )

        response = self.client.post(
            self._confirm_url(lead.id),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Lead o‘quvchiga aylantirildi")
        lead.refresh_from_db()
        self.assertTrue(lead.converted_to_student)
        self.assertTrue(lead.is_archived)
        self.assertIsNotNone(lead.converted_user_id)
        created_student = User.objects.get(pk=lead.converted_user_id)
        self.assertEqual(created_student.telefon1, "+998901111171")
        self.assertEqual(created_student.phone_number or "", "")
        self.assertEqual(
            User.objects.filter(center=self.center, role="student", telefon1="+998901111171").count(),
            2,
        )

    def test_confirm_endpoint_rejects_other_tenant_lead(self):
        other_center_manager = User.objects.create_user(
            email="manager@other-lead-api.test",
            password="Pass12345!",
            role="manager",
            center=self.other_center,
            ism="Other",
            familya="Tenant",
        )
        other_center_lead = Lead.objects.create(
            center=self.other_center,
            ism="Other",
            familya="Lead",
            telefon1="+998901111172",
            yosh=15,
            assigned_manager=other_center_manager,
        )

        response = self.client.post(
            self._confirm_url(other_center_lead.id),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_convert_lead_rejects_unconfirmed_lead(self):
        lead = self._make_lead(
            ism="Unconfirmed",
            familya="Lead",
            telefon1="+998901111118",
            yonalish=self.ielts_subject,
        )

        response = self.client.post(
            self._convert_url(lead.id),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Faqat tasdiqlangan leadlar", response.json()["error"])
        lead.refresh_from_db()
        self.assertFalse(lead.converted_to_student)

    def test_convert_confirmed_lead_creates_student_without_direct_enrollment(self):
        lead = self._make_lead(
            ism="Solo",
            familya="Lead",
            telefon1="+998901111119",
            yonalish=self.ielts_subject,
        )
        self._mark_lead_confirmed(lead)

        response = self.client.post(
            self._convert_url(lead.id),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        lead.refresh_from_db()
        self.assertTrue(lead.converted_to_student)
        self.assertTrue(lead.is_archived)
        self.assertTrue(User.objects.filter(id=lead.converted_user_id, role="student").exists())
        self.assertFalse(Enrollment.objects.filter(student_id=lead.converted_user_id, is_active=True).exists())
        self.assertEqual(response.json()["message"], "Lead o‘quvchiga aylantirildi")
        self.assertNotIn("enrolled_group_id", response.json()["student"])

    def test_convert_endpoint_rejects_already_converted_lead(self):
        lead = self._make_lead(
            ism="Repeat",
            familya="Lead",
            telefon1="+998901111120",
            yonalish=self.russian_subject,
        )
        self._mark_lead_confirmed(lead)
        self.client.post(self._convert_url(lead.id), data=json.dumps({}), content_type="application/json")

        response = self.client.post(
            self._convert_url(lead.id),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("allaqachon", response.json()["error"])

    def test_assign_lead_group_endpoint_updates_lead(self):
        lead = self._make_lead(
            ism="Grouped",
            familya="Lead",
            telefon1="+998901111121",
            yonalish=self.math_subject,
        )
        lead_group = LeadGroup.objects.create(
            center=self.center,
            name="Math Leads",
            subject=self.math_subject,
            department=self.department,
            min_students=5,
            created_by=self.manager,
        )

        response = self.client.post(
            self._assign_group_url(lead.id),
            data=json.dumps({"lead_group_id": lead_group.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        lead.refresh_from_db()
        lead_group.refresh_from_db()
        self.assertEqual(lead.lead_group_id, lead_group.id)
        self.assertIsNotNone(lead.added_to_group_at)
        self.assertEqual(response.json()["lead"]["lead_group_name"], "Math Leads")
        self.assertTrue(response.json()["lead"]["added_to_group_at"])
        self.assertEqual(lead_group.status, LeadGroup.Status.COLLECTING)

    def test_lead_list_template_uses_simplified_lead_group_ui(self):
        response = self.client.get(f"/{self.center.slug}{reverse('store:lead_list')}")

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn('id="leadPageTabs"', content)
        self.assertIn('data-tab-button="leads"', content)
        self.assertIn('data-tab-button="groups"', content)
        self.assertIn('data-tab-button="archive"', content)
        self.assertIn('id="leadTabCount"', content)
        self.assertIn('id="leadGroupsTabCount"', content)
        self.assertIn('id="archiveTabCount"', content)
        self.assertIn('id="leadsTabPanel"', content)
        self.assertIn('id="groupsTabPanel" class="lead-crm__panel-stack lead-hidden"', content)
        self.assertIn('id="archiveTabPanel" class="lead-crm__panel-stack lead-hidden"', content)
        self.assertIn('id="leadGroupDetailModal"', content)
        self.assertIn('id="leadGroupDetailTableBody"', content)
        self.assertIn('id="leadGroupDetailCardList"', content)
        self.assertIn('id="archiveLeadsPanel"', content)
        self.assertIn('id="archiveLeadGroupsPanel" class="lead-hidden"', content)
        self.assertIn('id="restoreConfirmModal"', content)
        self.assertIn("'pushState'", content)
        self.assertIn("overflow-x: auto;", content)
        self.assertEqual(content.count('id="createLeadButton"'), 1)
        self.assertEqual(content.count('id="createLeadGroupButton"'), 1)
        self.assertIn('id="createLeadGroupButton" type="button" class="lead-crm__add lead-hidden"', content)
        self.assertIn('data-lead-group-action="view"', content)
        self.assertIn('data-lead-group-open-card=', content)
        self.assertLess(content.index('id="leadPageTabs"'), content.index('id="leadsTabPanel"'))
        self.assertNotIn('id="convertGroupSubjectInput"', content)
        self.assertNotIn('id="leadGroupSubjectInput"', content)
        self.assertIn('id="convertGroupDaysWrap"', content)
        self.assertIn('id="convertGroupEndTimeInput"', content)
        self.assertNotIn('<th>Min</th>', content)
        self.assertIn('Yaratilgan sana', content)
        self.assertIn('id="leadGroupCardList"', content)
        self.assertIn('"teacher_share_percent": 45', content)
        self.assertLess(content.index('id="leadPageTabs"'), content.index('class="lead-crm__filters"'))
        self.assertLess(content.index('for="convertGroupNameInput"'), content.index('for="convertGroupDepartmentInput"'))
        self.assertLess(content.index('for="convertGroupDepartmentInput"'), content.index('for="convertGroupTeacherInput"'))
        self.assertLess(content.index('for="convertGroupTeacherInput"'), content.index('for="convertGroupStartDateInput"'))
        self.assertLess(content.index('for="convertGroupStartDateInput"'), content.index('for="convertGroupTimeInput"'))
        self.assertLess(content.index('for="convertGroupTimeInput"'), content.index('for="convertGroupEndTimeInput"'))
        self.assertLess(content.index('for="convertGroupEndTimeInput"'), content.index('for="convertGroupPriceInput"'))
        self.assertLess(content.index('for="convertGroupPriceInput"'), content.index('for="convertGroupTeacherShareInput"'))
        self.assertIn('lead-field lead-field--full">\n        <label for="convertGroupTeacherInput"', content)

    def test_lead_groups_api_returns_active_count_and_created_date(self):
        lead_group = LeadGroup.objects.create(
            center=self.center,
            name="Active Leads Group",
            department=self.department,
            min_students=2,
            created_by=self.manager,
        )
        self._make_lead(ism="Active", telefon1="+998901111150", lead_group=lead_group)
        archived_lead = self._make_lead(ism="Archived", telefon1="+998901111151", lead_group=lead_group)
        archived_lead.mark_archived(by_user=self.manager)

        response = self.client.get(self.lead_groups_url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()["results"][0]
        self.assertEqual(payload["lead_count"], 1)
        self.assertEqual(payload["lead_count_label"], "1 ta")
        self.assertRegex(payload["created_at_label"], r"^\d{2}\.\d{2}\.\d{4}$")

    def test_lead_archive_and_restore_endpoints_move_item_between_lists(self):
        lead = self._make_lead(
            ism="Archive",
            familya="Lead",
            telefon1="+998901111153",
            yonalish=self.ielts_subject,
        )

        archive_response = self.client.post(self._archive_url(lead.id), data=json.dumps({}), content_type="application/json")

        self.assertEqual(archive_response.status_code, 200)
        lead.refresh_from_db()
        self.assertTrue(lead.is_archived)
        self.assertIsNotNone(lead.archived_at)
        self.assertEqual(lead.archived_by_id, self.manager.id)
        active_response = self.client.get(self.api_url, {"archived": "false"})
        archived_response = self.client.get(self.api_url, {"archived": "true"})
        self.assertEqual(active_response.json()["count"], 0)
        self.assertEqual(archived_response.json()["count"], 1)
        self.assertEqual(archived_response.json()["results"][0]["archived_at_label"], timezone.localtime(lead.archived_at).strftime("%d.%m.%Y %H:%M"))

        restore_response = self.client.post(self._restore_url(lead.id), data=json.dumps({}), content_type="application/json")

        self.assertEqual(restore_response.status_code, 200)
        lead.refresh_from_db()
        self.assertFalse(lead.is_archived)
        self.assertIsNone(lead.archived_at)
        self.assertIsNone(lead.archived_by_id)
        active_response = self.client.get(self.api_url, {"archived": "false"})
        archived_response = self.client.get(self.api_url, {"archived": "true"})
        self.assertEqual(active_response.json()["count"], 1)
        self.assertEqual(archived_response.json()["count"], 0)

    def test_lead_group_archive_and_restore_endpoints_move_group_between_lists(self):
        lead_group = LeadGroup.objects.create(
            center=self.center,
            name="Archive Group",
            department=self.department,
            min_students=2,
            created_by=self.manager,
        )
        lead = self._make_lead(
            ism="Grouped",
            familya="Archive",
            telefon1="+998901111154",
            yonalish=self.math_subject,
            lead_group=lead_group,
        )

        archive_response = self.client.post(self._lead_group_archive_url(lead_group.id), data=json.dumps({}), content_type="application/json")

        self.assertEqual(archive_response.status_code, 200)
        lead_group.refresh_from_db()
        lead.refresh_from_db()
        self.assertTrue(lead_group.is_archived)
        self.assertIsNotNone(lead_group.archived_at)
        self.assertEqual(lead_group.archived_by_id, self.manager.id)
        self.assertEqual(lead.lead_group_id, lead_group.id)
        active_response = self.client.get(self.lead_groups_url, {"archived": "false"})
        archived_response = self.client.get(self.lead_groups_url, {"archived": "true"})
        self.assertEqual(active_response.json()["count"], 0)
        self.assertEqual(archived_response.json()["count"], 1)
        self.assertEqual(archived_response.json()["results"][0]["lead_count_label"], "1 ta")

        restore_response = self.client.post(self._lead_group_restore_url(lead_group.id), data=json.dumps({}), content_type="application/json")

        self.assertEqual(restore_response.status_code, 200)
        lead_group.refresh_from_db()
        self.assertFalse(lead_group.is_archived)
        self.assertIsNone(lead_group.archived_at)
        self.assertIsNone(lead_group.archived_by_id)
        active_response = self.client.get(self.lead_groups_url, {"archived": "false"})
        archived_response = self.client.get(self.lead_groups_url, {"archived": "true"})
        self.assertEqual(active_response.json()["count"], 1)
        self.assertEqual(archived_response.json()["count"], 0)

    def test_lead_group_detail_api_returns_group_members_with_added_timestamp(self):
        lead_group = LeadGroup.objects.create(
            center=self.center,
            name="Detail Group",
            department=self.department,
            min_students=2,
            created_by=self.manager,
        )
        lead = self._make_lead(
            ism="Detail",
            familya="Member",
            telefon1="+998901111152",
            yonalish=self.math_subject,
            lead_group=lead_group,
            comment="Birinci izoh",
        )
        created_at = timezone.make_aware(datetime(2026, 4, 30, 10, 15), timezone.get_current_timezone())
        added_at = timezone.make_aware(datetime(2026, 4, 30, 14, 25), timezone.get_current_timezone())
        Lead.objects.filter(pk=lead.pk).update(qoshilgan_sana=created_at, added_to_group_at=added_at)

        response = self.client.get(self._lead_group_detail_url(lead_group.id))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["lead_group"]["name"], "Detail Group")
        self.assertEqual(data["lead_group"]["department_name"], self.department.name)
        self.assertEqual(data["lead_group"]["member_count"], 1)
        self.assertEqual(data["lead_group"]["member_count_label"], "1 ta")
        self.assertEqual(len(data["leads"]), 1)
        member = data["leads"][0]
        self.assertEqual(member["name"], "Detail Member")
        self.assertEqual(member["phone"], "+998901111152")
        self.assertEqual(member["subject_label"], self.math_subject.nom)
        self.assertEqual(member["manager"], self.manager.get_full_name() or self.manager.email)
        self.assertEqual(member["note"], "Birinci izoh")
        self.assertEqual(member["added_to_group_at_label"], "30.04.2026 14:25")
        self.assertEqual(member["added_to_group_date_label"], "30.04.2026")
        self.assertEqual(member["added_to_group_time_label"], "14:25")
        self.assertEqual(member["created_at_label"], "30.04.2026 10:15")

    def test_lead_group_detail_api_returns_empty_state_for_group_without_members(self):
        lead_group = LeadGroup.objects.create(
            center=self.center,
            name="Empty Group",
            department=self.department,
            min_students=3,
            created_by=self.manager,
        )

        response = self.client.get(self._lead_group_detail_url(lead_group.id))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["lead_group"]["name"], "Empty Group")
        self.assertEqual(data["lead_group"]["member_count"], 0)
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["leads"], [])

    def test_lead_group_crud_and_convert_to_real_group_only_uses_confirmed_leads(self):
        create_response = self.client.post(
            self.lead_groups_url,
            data=json.dumps(
                {
                    "name": "Kompyuter Savodxonligi",
                    "subject": self.other_subject.id,
                    "department": self.it_department.id,
                    "min_students": 2,
                    "note": "May oyi uchun",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(create_response.status_code, 201)
        lead_group_id = create_response.json()["lead_group"]["id"]
        lead_group = LeadGroup.objects.get(id=lead_group_id)
        self.assertEqual(lead_group.status, LeadGroup.Status.COLLECTING)

        update_response = self.client.patch(
            self._lead_group_detail_url(lead_group_id),
            data=json.dumps({"name": "Kompyuter Savodxonligi Pro", "subject": self.other_subject.id, "department": self.it_department.id, "min_students": 2, "note": "Yangilandi"}),
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)
        lead_group.refresh_from_db()
        self.assertEqual(lead_group.name, "Kompyuter Savodxonligi Pro")

        confirmed_lead = self._make_lead(
            ism="Ready",
            familya="Lead",
            telefon1="+998901111122",
            yonalish=self.other_subject,
        )
        self._mark_lead_confirmed(confirmed_lead)
        pending_lead = self._make_lead(
            ism="Pending",
            familya="Lead",
            telefon1="+998901111123",
            yonalish=self.other_subject,
        )
        self.client.post(self._assign_group_url(confirmed_lead.id), data=json.dumps({"lead_group_id": lead_group_id}), content_type="application/json")
        self.client.post(self._assign_group_url(pending_lead.id), data=json.dumps({"lead_group_id": lead_group_id}), content_type="application/json")

        lead_group.refresh_from_db()
        self.assertEqual(lead_group.status, LeadGroup.Status.READY)

        convert_response = self.client.post(
            self._lead_group_convert_url(lead_group_id),
            data=json.dumps(
                {
                    "name": "IT-01",
                    "department": self.it_department.id,
                    "teacher": self.teacher.id,
                    "lesson_time": "09:00",
                    "start_date": timezone.localdate().isoformat(),
                    "price": 700000,
                    "teacher_share": 99,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(convert_response.status_code, 200)
        lead_group.refresh_from_db()
        confirmed_lead.refresh_from_db()
        pending_lead.refresh_from_db()
        real_group = Group.objects.get(id=lead_group.converted_group_id)
        self.assertEqual(lead_group.status, LeadGroup.Status.CONVERTED)
        self.assertIsNotNone(lead_group.converted_group_id)
        self.assertEqual(real_group.oqituvchi_foiz, 45)
        self.assertTrue(confirmed_lead.converted_to_student)
        self.assertFalse(pending_lead.converted_to_student)
        self.assertTrue(EducationStudent.objects.filter(user_id=confirmed_lead.converted_user_id, center=self.center).exists())
        self.assertTrue(
            Enrollment.objects.filter(
                student_id=confirmed_lead.converted_user_id,
                group_id=lead_group.converted_group_id,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            GroupStudent.objects.filter(
                student_id=confirmed_lead.converted_user_id,
                group_id=lead_group.converted_group_id,
            ).exists()
        )
        self.assertEqual(convert_response.json()["converted_count"], 1)
        self.assertEqual(convert_response.json()["skipped_unconfirmed"], 1)
        self.assertEqual(convert_response.json()["created_student_count"], 1)
        self.assertEqual(convert_response.json()["linked_existing_student_count"], 0)
        self.assertIn("1 ta tasdiqlangan lead o‘quvchiga aylantirildi.", convert_response.json()["message"])
        self.assertIn("1 ta tasdiqlanmagan lead o‘tkazib yuborildi.", convert_response.json()["message"])

    def test_superuser_can_override_teacher_share_on_real_group_conversion(self):
        lead_group = LeadGroup.objects.create(
            center=self.center,
            name="Override Group",
            subject=self.math_subject,
            department=self.department,
            min_students=1,
            created_by=self.manager,
        )
        confirmed_lead = self._make_lead(
            ism="Override",
            familya="Lead",
            telefon1="+998901111130",
            yonalish=self.math_subject,
            lead_group=lead_group,
        )
        self._mark_lead_confirmed(confirmed_lead)
        self.client.force_login(self.superadmin)

        response = self.client.post(
            self._lead_group_convert_url(lead_group.id),
            data=json.dumps(
                {
                    "name": "Math-Superadmin",
                    "department": self.department.id,
                    "teacher": self.teacher.id,
                    "lesson_time": "11:00",
                    "start_date": timezone.localdate().isoformat(),
                    "price": 640000,
                    "teacher_share": 52,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        lead_group.refresh_from_db()
        self.assertEqual(Group.objects.get(id=lead_group.converted_group_id).oqituvchi_foiz, 52)

    def test_lead_group_convert_reuses_existing_student_without_duplicate_creation(self):
        existing_student = User.objects.create_user(
            email="existing-student@lead-api.test",
            password="Pass12345!",
            role="student",
            center=self.center,
            ism="Existing",
            familya="Student",
            telefon1="+998901111131",
            phone_number="+998901111131",
        )
        lead_group = LeadGroup.objects.create(
            center=self.center,
            name="Existing Student Group",
            subject=self.ielts_subject,
            department=self.department,
            min_students=1,
            created_by=self.manager,
        )
        confirmed_lead = self._make_lead(
            ism="Existing",
            familya="Student",
            telefon1="+998901111131",
            yonalish=self.ielts_subject,
            lead_group=lead_group,
        )
        self._mark_lead_confirmed(confirmed_lead)
        before_students = User.objects.filter(center=self.center, role="student").count()

        response = self.client.post(
            self._lead_group_convert_url(lead_group.id),
            data=json.dumps(
                {
                    "name": "Existing-01",
                    "department": self.department.id,
                    "teacher": self.teacher.id,
                    "lesson_time": "08:30",
                    "start_date": timezone.localdate().isoformat(),
                    "price": 600000,
                    "teacher_share": 77,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        confirmed_lead.refresh_from_db()
        lead_group.refresh_from_db()
        after_students = User.objects.filter(center=self.center, role="student").count()
        self.assertEqual(before_students, after_students)
        self.assertEqual(confirmed_lead.converted_user_id, existing_student.id)
        self.assertEqual(response.json()["created_student_count"], 0)
        self.assertEqual(response.json()["linked_existing_student_count"], 1)
        self.assertTrue(
            Enrollment.objects.filter(
                student=existing_student,
                group_id=lead_group.converted_group_id,
                is_active=True,
            ).exists()
        )
        self.assertIn("mavjud studentga bog‘landi", response.json()["message"])

    def test_lead_group_convert_skips_duplicate_student_already_added_to_group(self):
        lead_group = LeadGroup.objects.create(
            center=self.center,
            name="Duplicate Phones",
            subject=self.math_subject,
            department=self.department,
            min_students=2,
            created_by=self.manager,
        )
        first_lead = self._make_lead(
            ism="Duplicate",
            familya="One",
            telefon1="+998901111132",
            yonalish=self.math_subject,
            lead_group=lead_group,
        )
        second_lead = self._make_lead(
            ism="Duplicate",
            familya="One",
            telefon1="+998901111132",
            yonalish=self.math_subject,
            lead_group=lead_group,
        )
        self._mark_lead_confirmed(first_lead)
        self._mark_lead_confirmed(second_lead)

        response = self.client.post(
            self._lead_group_convert_url(lead_group.id),
            data=json.dumps(
                {
                    "name": "Math-Dedup",
                    "department": self.department.id,
                    "teacher": self.teacher.id,
                    "lesson_time": "13:00",
                    "start_date": timezone.localdate().isoformat(),
                    "price": 580000,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        lead_group.refresh_from_db()
        self.assertEqual(response.json()["converted_count"], 2)
        self.assertEqual(response.json()["duplicate_group_membership_count"], 1)
        self.assertEqual(
            Enrollment.objects.filter(group_id=lead_group.converted_group_id, is_active=True).count(),
            1,
        )
        self.assertEqual(
            User.objects.filter(center=self.center, role="student", telefon1="+998901111132").count(),
            1,
        )
        self.assertIn("duplicate student allaqachon shu guruhda bo‘lgani uchun skip qilindi", response.json()["message"])

    def test_lead_group_convert_rejects_other_center_teacher_and_department(self):
        lead_group = LeadGroup.objects.create(
            center=self.center,
            name="Tenant Safe Group",
            subject=self.math_subject,
            department=self.department,
            min_students=1,
            created_by=self.manager,
        )
        confirmed_lead = self._make_lead(
            ism="Tenant",
            familya="Confirmed",
            telefon1="+998901111124",
            yonalish=self.math_subject,
            lead_group=lead_group,
        )
        self._mark_lead_confirmed(confirmed_lead)

        response = self.client.post(
            self._lead_group_convert_url(lead_group.id),
            data=json.dumps(
                {
                    "name": "Bad Group",
                    "department": self.other_department.id,
                    "teacher": self.other_teacher.id,
                    "lesson_time": "10:00",
                    "start_date": timezone.localdate().isoformat(),
                    "price": 500000,
                    "teacher_share": 40,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        lead_group.refresh_from_db()
        self.assertIsNone(lead_group.converted_group_id)

    def test_archive_marks_lead_archived_and_hides_from_list(self):
        lead = self._make_lead(
            ism="Archive",
            familya="Lead",
            telefon1="+998901111121",
            yonalish=self.other_subject,
        )

        delete_response = self.client.delete(self._detail_url(lead.id))

        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(delete_response.json()["success"])
        lead.refresh_from_db()
        self.assertTrue(lead.is_archived)
        self.assertTrue(Lead.objects.filter(id=lead.id).exists())

        list_response = self.client.get(self.api_url)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["count"], 0)

    def test_subject_create_api_adds_new_subject_and_returns_json(self):
        response = self.client.post(
            self.subjects_url,
            data=json.dumps({"name": "Fizika"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response["Content-Type"], "application/json")
        data = response.json()
        self.assertEqual(data["subject"]["label"], "Fizika")
        self.assertTrue(Yonalish.objects.filter(center=self.center, nom="Fizika").exists())

    def test_subject_update_api_renames_existing_subject(self):
        response = self.client.patch(
            self._subject_detail_url(self.math_subject.id),
            data=json.dumps({"name": "Matematika Pro"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.math_subject.refresh_from_db()
        self.assertEqual(self.math_subject.nom, "Matematika Pro")
        self.assertEqual(response.json()["subject"]["label"], "Matematika Pro")

    def test_subject_delete_api_marks_used_subject_inactive_but_keeps_old_lead_visible(self):
        lead = self._make_lead(
            ism="Subject",
            familya="Holder",
            telefon1="+998901111122",
            yonalish=self.math_subject,
        )

        response = self.client.delete(self._subject_detail_url(self.math_subject.id))

        self.assertEqual(response.status_code, 200)
        self.math_subject.refresh_from_db()
        self.assertFalse(self.math_subject.is_active)
        self.assertTrue(Yonalish.objects.filter(pk=self.math_subject.id).exists())
        self.assertNotIn(
            self.math_subject.id,
            [item["id"] for item in self.client.get(self.subjects_url).json()["results"]],
        )

        leads_response = self.client.get(self.api_url)
        self.assertEqual(leads_response.status_code, 200)
        result = next(item for item in leads_response.json()["results"] if item["id"] == lead.id)
        self.assertEqual(result["subject"], str(self.math_subject.id))
        self.assertEqual(result["subject_label"], "Matematika")

    def test_status_create_api_adds_custom_status_and_lead_can_use_it(self):
        status_response = self.client.post(
            self.statuses_url,
            data=json.dumps({"name": "Qayta chaqirish"}),
            content_type="application/json",
        )

        self.assertEqual(status_response.status_code, 201)
        self.assertEqual(status_response["Content-Type"], "application/json")
        status_data = status_response.json()
        self.assertTrue(status_data["status"]["value"].startswith("custom:"))
        created_status = LeadStatus.objects.get(center=self.center, nom="Qayta chaqirish")

        lead_response = self.client.post(
            self.api_url,
            data=json.dumps(
                {
                    "name": "Status Lead",
                    "phone": "90 555 66 77",
                    "subject": str(self.ielts_subject.id),
                    "status": status_data["status"]["value"],
                    "note": "Custom status bilan yaratildi",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(lead_response.status_code, 201)
        lead = Lead.objects.get(center=self.center, ism="Status", familya="Lead")
        self.assertEqual(lead.status_id, created_status.id)
        self.assertEqual(lead_response.json()["lead"]["status"], f"custom:{created_status.id}")

    def test_status_update_api_renames_existing_custom_status(self):
        created_status = LeadStatus.objects.create(
            center=self.center,
            nom="Qayta ko‘rib chiqish",
            code="custom_review",
            order=180,
            is_active=True,
        )

        response = self.client.patch(
            self._status_detail_url(created_status.id),
            data=json.dumps({"name": "Qayta aloqa"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        created_status.refresh_from_db()
        self.assertEqual(created_status.nom, "Qayta aloqa")
        self.assertEqual(response.json()["status"]["label"], "Qayta aloqa")

    def test_status_delete_api_marks_used_status_inactive_but_old_lead_keeps_status_name(self):
        custom_status = LeadStatus.objects.create(
            center=self.center,
            nom="Qayta chaqirish",
            code="custom_recall",
            order=190,
            is_active=True,
        )
        lead = self._make_lead(
            ism="Status",
            familya="Holder",
            telefon1="+998901111123",
            yonalish=self.ielts_subject,
            status=custom_status,
        )

        response = self.client.delete(self._status_detail_url(custom_status.id))

        self.assertEqual(response.status_code, 200)
        custom_status.refresh_from_db()
        self.assertFalse(custom_status.is_active)
        self.assertTrue(LeadStatus.objects.filter(pk=custom_status.id).exists())
        self.assertNotIn(
            custom_status.id,
            [item["id"] for item in self.client.get(self.statuses_url).json()["results"]],
        )

        leads_response = self.client.get(self.api_url)
        self.assertEqual(leads_response.status_code, 200)
        result = next(item for item in leads_response.json()["results"] if item["id"] == lead.id)
        self.assertEqual(result["status"], f"custom:{custom_status.id}")
        self.assertEqual(result["status_label"], "Qayta chaqirish")

    def test_lead_page_uses_uzbek_labels(self):
        response = self.client.get(f"/{self.center.slug}{reverse('store:lead_list')}")

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Jadval", content)
        self.assertIn("Bosqichlar", content)
        self.assertIn("Tozalash", content)
        self.assertIn("Menejer", content)
        self.assertIn("Lead yo‘q", content)
        self.assertIn("Lead holati yangilandi", content)
        self.assertIn("Lead guruhlari", content)
        self.assertIn("Lead guruhi yaratish", content)
        self.assertIn("Tasdiqlash", content)
        self.assertIn("manualOpenKanbanStatuses: []", content)
        self.assertIn("searchOpenKanbanStatuses: []", content)
        self.assertIn("Qidiruv natijasi:", content)
        self.assertIn("Lead topilmadi", content)
        self.assertIn("data-column-toggle", content)
        self.assertIn("fa-lock", content)
        self.assertNotIn("leadThemeToggle", content)
        self.assertNotIn(">Table<", content)
        self.assertNotIn(">Kanban<", content)
        self.assertNotIn(">Bo'sh<", content)

    def test_lead_page_removes_extra_subject_controls_and_color_field(self):
        response = self.client.get(f"/{self.center.slug}{reverse('store:lead_list')}")

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertNotIn("openSubjectCreateButton", content)
        self.assertNotIn("openSubjectFromLeadButton", content)
        self.assertNotIn("subjectColorInput", content)
        self.assertNotIn("window.confirm", content)
        self.assertIn('data-add-subject="true"', content)
        self.assertIn('data-add-status="true"', content)
        self.assertIn("Yangi holat", content)
        self.assertIn("subjectDetailUrl", content)
        self.assertIn("statusDetailUrl", content)
        self.assertIn("data-catalog-edit", content)
        self.assertIn("data-catalog-delete", content)
        self.assertIn("data-catalog-menu-trigger", content)
        self.assertIn("confirmCatalogDeleteButton", content)
        self.assertIn("lead-multi-option__menu-trigger", content)
        self.assertIn("lead-multi-option__menu", content)
        self.assertIn("lead-multi-option__menu-item", content)
        self.assertIn("fa-solid fa-ellipsis", content)
        self.assertNotIn("lead-icon-btn--tiny", content)
        self.assertNotIn("lead-multi-option__actions", content)
        self.assertIn("Fanni o‘chirishni tasdiqlaysizmi?", content)
        self.assertIn("Holatni o‘chirishni tasdiqlaysizmi?", content)
        self.assertIn("event.stopPropagation();", content)
        self.assertIn("Arxivlashni tasdiqlang", content)
        self.assertIn(
            "Bu ma’lumot arxivga yuboriladi. Keyin uni Arxiv bo‘limidan qayta tiklashingiz mumkin.",
            content,
        )
        self.assertIn("O‘quvchiga aylantirishni tasdiqlaysizmi?", content)
        self.assertIn("Bu lead o‘quvchi sifatida saqlanadi va O‘quvchilar bo‘limida ko‘rinadi.", content)
        self.assertIn("const defaultManagerId = ", content)
        self.assertIn("const leadManagerLocked = true;", content)
        self.assertIn("Api Manager", content)
        self.assertIn("confirmLeadModal", content)
        self.assertIn("assignLeadGroupModal", content)
        self.assertIn("leadGroupModal", content)
        self.assertIn("leadLeadGroupInput", content)
        self.assertNotIn("Faqat tasdiqlangan leadlar o‘quvchiga aylantiriladi", content)
        self.assertNotIn('id="confirmLeadButton"', content)
        self.assertNotIn('id="convertLeadButton"', content)
        self.assertNotIn('id="deleteLeadButton"', content)
        self.assertNotIn("leadConvertHint", content)
        self.assertNotIn("leadConvertGroupInput", content)

    def test_lead_page_contains_compact_kanban_and_search_highlight_hooks(self):
        response = self.client.get(f"/{self.center.slug}{reverse('store:lead_list')}")

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn('placeholder="Ism, telefon, fan yoki holat"', content)
        self.assertIn("overflow-x: hidden;", content)
        self.assertIn("align-items: end;", content)
        self.assertIn("lead-filter-field--utility", content)
        self.assertIn("lead-select--page-size", content)
        self.assertIn("lead-table__actions-cell", content)
        self.assertIn(".lead-multi-tags {", content)
        self.assertIn("kanban-wrapper", content)
        self.assertIn("kanban-board", content)
        self.assertIn("overflow-x: auto;", content)
        self.assertIn("min-width: 320px;", content)
        self.assertIn("min-width: 280px;", content)
        self.assertIn("max-height: 420px;", content)
        self.assertIn("grid-template-columns: 40px minmax(0, 1fr) auto;", content)
        self.assertIn("grid-template-columns: minmax(0, 1fr) auto;", content)
        self.assertIn("lead-column__summary", content)
        self.assertIn("text-overflow: ellipsis;", content)
        self.assertIn("is-search-match", content)
        self.assertIn("formatLeadCount", content)
        self.assertIn("updateKanbanSearchState", content)
        self.assertIn("kanbanScrollPrev", content)
        self.assertIn("kanbanScrollNext", content)
        self.assertIn("scrollKanban", content)
        self.assertIn("syncKanbanScrollControls", content)
        self.assertIn('title="${escapeHtml(lead.name)}"', content)
        self.assertIn("lead-kanban-card__actions", content)
        self.assertIn("leadModalConvertButton", content)
        self.assertNotIn('data-action="confirm" data-id="${lead.id}"', content)
        self.assertNotIn('data-action="view" data-id="${lead.id}" title="Ko\'rish"', content)
        self.assertNotIn("#${lead.id}", content)
        self.assertNotIn("ID:", content)

    def test_lead_page_escapes_tenant_api_urls_for_apostrophe_slug(self):
        self.center.slug = "do'kon"
        self.center.save(update_fields=["slug"])

        response = self.client.get(f"/{self.center.slug}{reverse('store:lead_list')}")

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("const apiListUrl =", content)
        self.assertIn("/api/leads/", content)
        self.assertNotIn("/do&#x27;kon/api/leads/", content)


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


class LeadGroupRevertTests(TestCase):
    def setUp(self):
        from accounts.models import Center
        from education.models import Category
        from store.models import Yonalish
        
        self.center = Center.objects.create(
            name="Revert Center",
            slug="revert-center",
            features={"leads": True},
        )
        self.manager = User.objects.create_user(
            email="manager@revert.test",
            password="Pass12345!",
            role="manager",
            center=self.center,
            ism="Revert",
            familya="Manager",
        )
        self.teacher = User.objects.create_user(
            email="teacher@revert.test",
            password="Pass12345!",
            role="teacher",
            center=self.center,
            ism="Revert",
            familya="Teacher",
        )
        self.department = Category.objects.create(center=self.center, name="Matematika")
        self.math_subject = Yonalish.objects.create(center=self.center, nom="Matematika")
        self.client.force_login(self.manager)
        
    def _make_lead(self, **kwargs):
        from store.models import Lead
        defaults = {
            "center": self.center,
            "created_by": self.manager,
            "yosh": 15,
            "assigned_manager": self.manager,
        }
        defaults.update(kwargs)
        return Lead.objects.create(**defaults)
        
    def _mark_lead_confirmed(self, lead):
        from store.lead_services import confirm_lead
        confirm_lead(lead=lead, actor=self.manager)

    def test_revert_converted_lead_group_archives_real_group_and_restores_leads(self):
        from store.models import LeadGroup, Lead
        from education.models import Group, Enrollment, GroupStudent
        
        lead_group = LeadGroup.objects.create(
            center=self.center,
            name="Math Revert Group",
            subject=self.math_subject,
            department=self.department,
            min_students=1,
            created_by=self.manager,
        )
        confirmed_lead = self._make_lead(
            ism="Revertable",
            familya="Lead",
            telefon1="+998901234567",
            yonalish=self.math_subject,
            lead_group=lead_group,
        )
        self._mark_lead_confirmed(confirmed_lead)
        
        # 1. Convert it
        convert_url = f"/{self.center.slug}{reverse('store:lead_group_convert_api', args=[lead_group.id])}"
        response = self.client.post(
            convert_url,
            data=json.dumps({
                "name": "Math-101",
                "department": self.department.id,
                "teacher": self.teacher.id,
                "lesson_time": "14:00",
                "start_date": timezone.localdate().isoformat(),
                "price": 600000,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        
        lead_group.refresh_from_db()
        confirmed_lead.refresh_from_db()
        
        real_group_id = lead_group.converted_group_id
        self.assertIsNotNone(real_group_id)
        self.assertEqual(lead_group.status, LeadGroup.Status.CONVERTED)
        self.assertTrue(confirmed_lead.converted_to_student)
        self.assertTrue(confirmed_lead.is_archived)
        
        # Verify enrollment and group student exist
        self.assertTrue(Enrollment.objects.filter(student_id=confirmed_lead.converted_user_id, group_id=real_group_id).exists())
        self.assertTrue(GroupStudent.objects.filter(student_id=confirmed_lead.converted_user_id, group_id=real_group_id).exists())
        
        # 2. Revert it
        revert_url = f"/{self.center.slug}{reverse('store:lead_group_revert_api', args=[lead_group.id])}"
        revert_response = self.client.post(revert_url, data=json.dumps({}), content_type="application/json")
        self.assertEqual(revert_response.status_code, 200)
        
        # Refresh and assert
        lead_group.refresh_from_db()
        confirmed_lead.refresh_from_db()
        
        self.assertIsNone(lead_group.converted_group_id)
        # Reverted back to ready because the active lead is restored
        self.assertEqual(lead_group.status, LeadGroup.Status.READY)
        
        # Lead is active again
        self.assertFalse(confirmed_lead.converted_to_student)
        self.assertFalse(confirmed_lead.is_archived)
        self.assertIsNone(confirmed_lead.converted_user)
        
        # Real group is soft-deleted
        real_group = Group.all_objects.get(id=real_group_id)
        self.assertTrue(real_group.is_deleted)
        
        # Enrollment is soft-deleted
        self.assertFalse(Enrollment.objects.filter(group_id=real_group_id).exists())
        self.assertTrue(Enrollment.all_objects.filter(group_id=real_group_id, is_deleted=True).exists())
        
        # GroupStudent is hard deleted
        self.assertFalse(GroupStudent.objects.filter(group_id=real_group_id).exists())

    def test_lead_group_convert_with_soft_deleted_user_email_conflict(self):
        from store.models import LeadGroup
        
        # 1. Create a soft-deleted user with the candidate email "r.lead@gmail.com"
        soft_deleted_user = User.objects.create_user(
            email="r.lead@gmail.com",
            password="Pass12345!",
            role="student",
            center=self.center,
            ism="Revertable",
            familya="Lead",
        )
        soft_deleted_user.delete()
        
        lead_group = LeadGroup.objects.create(
            center=self.center,
            name="Math Conflict Group",
            subject=self.math_subject,
            department=self.department,
            min_students=1,
            created_by=self.manager,
        )
        confirmed_lead = self._make_lead(
            ism="Revertable",
            familya="Lead",
            telefon1="+998901234568",
            yonalish=self.math_subject,
            lead_group=lead_group,
        )
        self._mark_lead_confirmed(confirmed_lead)
        
        # Try to convert it
        convert_url = f"/{self.center.slug}{reverse('store:lead_group_convert_api', args=[lead_group.id])}"
        response = self.client.post(
            convert_url,
            data=json.dumps({
                "name": "Math-102",
                "department": self.department.id,
                "teacher": self.teacher.id,
                "lesson_time": "15:00",
                "start_date": timezone.localdate().isoformat(),
                "price": 600000,
            }),
            content_type="application/json",
        )
        # Should succeed with 200 and generate a unique email (e.g. "r.lead1@gmail.com") instead of throwing a UNIQUE IntegrityError!
        self.assertEqual(response.status_code, 200)
        
        lead_group.refresh_from_db()
        confirmed_lead.refresh_from_db()
        self.assertIsNotNone(lead_group.converted_group_id)
        self.assertTrue(confirmed_lead.converted_to_student)
        
        # The new user should have a unique email different from the soft-deleted one
        new_student = User.objects.get(id=confirmed_lead.converted_user_id)
        self.assertNotEqual(new_student.email, "r.lead@gmail.com")
        self.assertEqual(new_student.email, "r.lead1@gmail.com")
