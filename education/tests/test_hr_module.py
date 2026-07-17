import json
from datetime import time
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from core.test_utils import activate_center
from education.models import Group, GroupSchedule, StaffProfile, TeacherAvailability
from store.models import LeadGroup, Yonalish


class HrModuleTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(
            name="HR Center",
            slug="hr-center",
            features={"leads": True},
        )
        activate_center(self.center)
        self.other_center = Center.objects.create(
            name="Other Center",
            slug="other-center",
            features={"leads": True},
        )

        self.director = User.objects.create_user(
            email="director@hr.test",
            password="pass12345",
            role="director",
            center=self.center,
            ism="Direktor",
            familya="Bir",
        )
        self.manager = User.objects.create_user(
            email="manager@hr.test",
            password="pass12345",
            role="manager",
            center=self.center,
            ism="Manager",
            familya="Bir",
        )
        self.teacher_busy = User.objects.create_user(
            email="busy@hr.test",
            password="pass12345",
            role="teacher",
            center=self.center,
            ism="Band",
            familya="Ustoz",
            telefon1="+998901111111",
            phone_number="+998901111111",
        )
        self.teacher_free = User.objects.create_user(
            email="free@hr.test",
            password="pass12345",
            role="teacher",
            center=self.center,
            ism="Bosh",
            familya="Ustoz",
            telefon1="+998902222222",
            phone_number="+998902222222",
        )
        self.teacher_other_center = User.objects.create_user(
            email="other@hr.test",
            password="pass12345",
            role="teacher",
            center=self.other_center,
            ism="Boshqa",
            familya="Markaz",
        )
        self.teacher_viewer = User.objects.create_user(
            email="teacher-viewer@hr.test",
            password="pass12345",
            role="teacher",
            center=self.center,
            ism="Oddiy",
            familya="Teacher",
        )

        self.subject_math = Yonalish.objects.create(center=self.center, nom="Matematika")
        self.subject_english = Yonalish.objects.create(center=self.center, nom="English")
        self.other_subject = Yonalish.objects.create(center=self.other_center, nom="Physics")

        self.busy_profile = StaffProfile.objects.create(
            user=self.teacher_busy,
            tenant=self.center,
            full_name=self.teacher_busy.get_full_name(),
            phone=self.teacher_busy.telefon1,
            role=StaffProfile.Role.TEACHER,
            position="Senior IELTS ustoz",
            levels=["IELTS 5.5+", "Foundation"],
            directions=["IELTS", "SAT Math"],
        )
        self.busy_profile.subjects.set([self.subject_math.id])
        StaffProfile.objects.create(
            user=self.teacher_free,
            tenant=self.center,
            full_name=self.teacher_free.get_full_name(),
            phone=self.teacher_free.telefon1,
            role=StaffProfile.Role.TEACHER,
            position="General English ustoz",
            levels=["A1", "A2"],
            directions=["General English"],
        ).subjects.set([self.subject_english.id])

        TeacherAvailability.objects.create(
            tenant=self.center,
            teacher=self.teacher_busy,
            weekday=1,
            start_time=time(8, 0),
            end_time=time(12, 0),
            type=TeacherAvailability.Type.AVAILABLE,
        )
        TeacherAvailability.objects.create(
            tenant=self.center,
            teacher=self.teacher_free,
            weekday=1,
            start_time=time(8, 0),
            end_time=time(12, 0),
            type=TeacherAvailability.Type.AVAILABLE,
        )
        TeacherAvailability.objects.create(
            tenant=self.other_center,
            teacher=self.teacher_other_center,
            weekday=1,
            start_time=time(8, 0),
            end_time=time(12, 0),
            type=TeacherAvailability.Type.AVAILABLE,
        )

        self.busy_group = Group.objects.create(
            center=self.center,
            nom="Busy Group",
            oqituvchi=self.teacher_busy,
            kurs_narxi=500000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        GroupSchedule.objects.bulk_create(
            [
                GroupSchedule(center=self.center, group=self.busy_group, weekday=1, start_time=time(9, 0), end_time=time(10, 30)),
                GroupSchedule(center=self.center, group=self.busy_group, weekday=3, start_time=time(9, 0), end_time=time(10, 30)),
                GroupSchedule(center=self.center, group=self.busy_group, weekday=5, start_time=time(9, 0), end_time=time(10, 30)),
            ]
        )

        self.lead_group = LeadGroup.objects.create(
            center=self.center,
            name="Lead Group One",
            min_students=2,
        )

        self.hr_employees_url = f"/{self.center.slug}/api/hr/employees/"
        self.hr_available_url = f"/{self.center.slug}/api/hr/teachers/available/"

    def _tenant_url(self, name, *args, center=None):
        active_center = center or self.center
        return f"/{active_center.slug}{reverse(name, args=args)}"

    def test_employee_create_api_creates_user_profile_and_subjects(self):
        self.client.force_login(self.director)
        response = self.client.post(
            self.hr_employees_url,
            data=json.dumps(
                {
                    "full_name": "Yangi Ustoz",
                    "phone": "+998903333333",
                    "role": "teacher",
                    "position": "Matematika ustoz",
                    "hire_date": "2026-04-01",
                    "subjects": [self.subject_math.id],
                    "levels": ["A1", "A2"],
                    "directions": ["Olimpiada", "General Math"],
                    "note": "Sinov darslari yaxshi o'tgan",
                    "is_active": True,
                    "availability_slots": [
                        {
                            "weekday": "1",
                            "start_time": "08:00",
                            "end_time": "12:00",
                            "type": "available",
                        }
                    ],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        employee = payload["employee"]
        self.assertEqual(employee["full_name"], "Yangi Ustoz")
        self.assertEqual(employee["role"], "teacher")
        self.assertEqual(employee["subjects"][0]["name"], "Matematika")
        self.assertIn("credentials", payload)

        created_user = User.objects.get(email=payload["credentials"]["email"])
        profile = StaffProfile.objects.get(user=created_user)
        self.assertEqual(profile.tenant, self.center)
        self.assertEqual(profile.levels, ["A1", "A2"])
        self.assertEqual(profile.directions, ["Olimpiada", "General Math"])
        self.assertEqual(list(profile.subjects.values_list("id", flat=True)), [self.subject_math.id])
        self.assertEqual(
            TeacherAvailability.objects.filter(tenant=self.center, teacher=created_user).count(),
            1,
        )

    def test_employee_detail_returns_schedule_and_free_slots(self):
        self.client.force_login(self.manager)
        response = self.client.get(f"{self.hr_employees_url}{self.teacher_busy.id}/")
        self.assertEqual(response.status_code, 200)
        employee = response.json()["employee"]

        monday = next(item for item in employee["weekly_schedule"] if item["weekday"] == 1)
        self.assertEqual(len(employee["current_groups"]), 1)
        self.assertEqual(employee["current_groups"][0]["name"], "Busy Group")
        self.assertEqual(len(monday["groups"]), 1)
        self.assertEqual(monday["groups"][0]["time_range"], "09:00 - 10:30")
        free_ranges = [slot["time_range"] for slot in monday["free_slots"]]
        self.assertIn("08:00 - 09:00", free_ranges)
        self.assertIn("10:30 - 12:00", free_ranges)

    def test_filters_and_deactivate_flow_work(self):
        self.client.force_login(self.director)
        response = self.client.get(
            self.hr_employees_url,
            {
                "role": "teacher",
                "subject": self.subject_math.id,
                "active": "active",
            },
        )
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.teacher_busy.id)

        deactivate = self.client.delete(f"{self.hr_employees_url}{self.teacher_busy.id}/")
        self.assertEqual(deactivate.status_code, 200)
        self.busy_profile.refresh_from_db()
        self.teacher_busy.refresh_from_db()
        self.assertFalse(self.busy_profile.is_active)
        self.assertFalse(self.teacher_busy.is_active)

        inactive_response = self.client.get(self.hr_employees_url, {"active": "inactive"})
        inactive_ids = {row["id"] for row in inactive_response.json()["results"]}
        self.assertIn(self.teacher_busy.id, inactive_ids)

    def test_available_teacher_api_returns_only_free_matching_tenant_teacher(self):
        self.client.force_login(self.manager)
        response = self.client.get(
            self.hr_available_url,
            {
                "day": 1,
                "time": "09:00",
                "end_time": "10:30",
            },
        )
        self.assertEqual(response.status_code, 200)
        result_ids = {item["id"] for item in response.json()["results"]}
        self.assertIn(self.teacher_free.id, result_ids)
        self.assertNotIn(self.teacher_busy.id, result_ids)
        self.assertNotIn(self.teacher_other_center.id, result_ids)

    def test_employees_api_falls_back_when_hr_tables_are_unavailable(self):
        self.client.force_login(self.director)
        storage_state = {
            "profiles": False,
            "availability": False,
            "profile_subjects": False,
        }

        with patch("education.hr_views.hr_data_storage_state", return_value=storage_state), patch(
            "education.services.hr.hr_data_storage_state", return_value=storage_state
        ):
            response = self.client.get(self.hr_employees_url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["meta"]["storage_ready"])
        self.assertGreaterEqual(payload["count"], 2)
        result_ids = {row["id"] for row in payload["results"]}
        self.assertIn(self.teacher_busy.id, result_ids)
        self.assertIn(self.teacher_free.id, result_ids)

    def test_group_create_rejects_busy_teacher(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            self._tenant_url("education:group_create_lang"),
            {
                "nom": "Conflict Group",
                "oqituvchi": self.teacher_busy.id,
                "course_start_date": timezone.localdate().isoformat(),
                "duration_months": 2,
                "max_students": 12,
                "schedule_mode": "odd",
                "schedule_start_time": "09:00",
                "schedule_end_time": "10:30",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("oqituvchi", response.context["form"].errors)
        self.assertFalse(Group.objects.filter(center=self.center, nom="Conflict Group").exists())

    def test_lead_group_convert_rejects_busy_teacher(self):
        self.client.force_login(self.director)
        response = self.client.post(
            self._tenant_url("store:lead_group_convert_api", self.lead_group.id),
            data=json.dumps(
                {
                    "name": "Real Group",
                    "teacher": self.teacher_busy.id,
                    "lesson_days": ["1", "3", "5"],
                    "lesson_time": "09:00",
                    "lesson_end_time": "10:30",
                    "start_date": timezone.localdate().isoformat(),
                    "price": 600000,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("teacher", response.json()["errors"])

    def test_hr_page_forbidden_for_teacher_and_other_tenant_employee_hidden(self):
        self.client.force_login(self.teacher_viewer)
        forbidden = self.client.get(self._tenant_url("education:hr_dashboard"))
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_login(self.manager)
        not_found = self.client.get(f"{self.hr_employees_url}{self.teacher_other_center.id}/")
        self.assertEqual(not_found.status_code, 404)
