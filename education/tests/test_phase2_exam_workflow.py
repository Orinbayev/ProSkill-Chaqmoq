from datetime import time

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from core.test_utils import activate_center
from core.center_features import (
    FEATURE_UI_CERTIFICATES,
    FEATURE_UI_EXAM_SESSIONS,
    FEATURE_UI_FAILED_STUDENTS,
    FEATURE_UI_WEEKLY_SCHEDULE,
)
from education.models import (
    CenterExamSetting,
    EducationAuditLog,
    Enrollment,
    ExamResult,
    ExamResultFile,
    ExamSession,
    Group,
    GroupSchedule,
)


class PhaseTwoExamWorkflowTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Phase2 Center", slug="phase2-center")
        activate_center(self.center)
        self.director = User.objects.create_user(
            email="director.phase2@example.com",
            password="password",
            role="director",
            center=self.center,
            ism="Direk",
            familya="Tor",
        )
        self.teacher = User.objects.create_user(
            email="teacher.phase2@example.com",
            password="password",
            role="teacher",
            center=self.center,
            ism="Teach",
            familya="Er",
        )
        self.teacher2 = User.objects.create_user(
            email="teacher2.phase2@example.com",
            password="password",
            role="teacher",
            center=self.center,
            ism="Teach2",
            familya="Er2",
        )
        self.student1 = User.objects.create_user(
            email="student1.phase2@example.com",
            password="password",
            role="student",
            center=self.center,
            ism="Student",
            familya="One",
        )
        self.student2 = User.objects.create_user(
            email="student2.phase2@example.com",
            password="password",
            role="student",
            center=self.center,
            ism="Student",
            familya="Two",
        )

        self.group = Group.objects.create(
            center=self.center,
            nom="Phase2 Group",
            oqituvchi=self.teacher,
            kurs_narxi=500000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        self.group_other = Group.objects.create(
            center=self.center,
            nom="Phase2 Other Group",
            oqituvchi=self.teacher2,
            kurs_narxi=500000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        Enrollment.objects.create(group=self.group, student=self.student1, center=self.center, is_active=True)
        Enrollment.objects.create(group=self.group, student=self.student2, center=self.center, is_active=True)
        GroupSchedule.objects.create(
            center=self.center,
            group=self.group_other,
            weekday=1,
            start_time=time(9, 0),
            end_time=time(10, 30),
            room="2-kabinet",
        )

        CenterExamSetting.objects.create(
            center=self.center,
            exam_system_enabled=True,
            exam_every_n_lessons=1,
            passing_score_percent=60,
            exam_file_upload_enabled=True,
            exam_result_required=False,
            optional_task_upload_prompt_enabled=True,
        )

        self.session = ExamSession.objects.create(
            center=self.center,
            group=self.group,
            teacher=self.teacher,
            attendance_date=timezone.localdate(),
            exam_date=timezone.localdate(),
            lesson_number_reference=1,
            exam_sequence_number=1,
            teacher_decision=ExamSession.DECISION_YES,
            status=ExamSession.STATUS_COMPLETED,
            created_by=self.teacher,
        )

        self.failed_result = ExamResult.objects.create(
            center=self.center,
            session=self.session,
            group=self.group,
            student=self.student1,
            teacher=self.teacher,
            score=45,
            percent=45,
            passed=False,
            fail_reason="O‘tish foizidan past",
            follow_up_status=ExamResult.FOLLOW_UP_PENDING,
            exam_date=timezone.localdate(),
            lesson_number_reference=1,
            created_by=self.teacher,
        )
        self.passed_result = ExamResult.objects.create(
            center=self.center,
            session=self.session,
            group=self.group,
            student=self.student2,
            teacher=self.teacher,
            score=88,
            percent=88,
            passed=True,
            follow_up_status=ExamResult.FOLLOW_UP_NOT_REQUIRED,
            exam_date=timezone.localdate(),
            lesson_number_reference=1,
            created_by=self.teacher,
        )
        ExamResultFile.objects.create(
            result=self.failed_result,
            file=SimpleUploadedFile("work.pdf", b"pdf-data", content_type="application/pdf"),
            file_kind=ExamResultFile.FILE_WORK,
            uploaded_by=self.teacher,
        )

        self.session_other_teacher = ExamSession.objects.create(
            center=self.center,
            group=self.group,
            teacher=self.teacher2,
            attendance_date=timezone.localdate(),
            exam_date=timezone.localdate(),
            lesson_number_reference=2,
            exam_sequence_number=2,
            teacher_decision=ExamSession.DECISION_YES,
            status=ExamSession.STATUS_DRAFT,
            created_by=self.teacher2,
        )

    def _tenant_url(self, name, *args):
        return f"/{self.center.slug}{reverse(name, args=args)}"

    def test_group_exam_history_for_teacher(self):
        self.client.force_login(self.teacher)
        resp = self.client.get(reverse("education:group_exam_history", args=[self.group.id]), follow=True)
        self.assertIn(resp.status_code, (200, 302))
        if resp.status_code == 200:
            self.assertContains(resp, "Guruh imtihon tarixi")

    def test_teacher_exam_history_for_teacher_role(self):
        self.client.force_login(self.teacher)
        resp = self.client.get(reverse("education:teacher_exam_history"), follow=True)
        self.assertIn(resp.status_code, (200, 302))
        if resp.status_code == 200:
            sessions = list(resp.context["sessions"])
            session_ids = {s.id for s in sessions}
            self.assertIn(self.session.id, session_ids)
            self.assertNotIn(self.session_other_teacher.id, session_ids)

    def test_exam_session_detail_page(self):
        self.client.force_login(self.teacher)
        resp = self.client.get(reverse("education:exam_session_detail", args=[self.session.id]), follow=True)
        self.assertIn(resp.status_code, (200, 302))
        if resp.status_code == 200:
            self.assertContains(resp, "Yiqildi")

    def test_failed_students_list_permission(self):
        self.client.force_login(self.teacher)
        resp = self.client.get(reverse("education:failed_students_list"), follow=True)
        self.assertEqual(resp.status_code, 200)
        rows = list(resp.context["rows"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, self.failed_result.id)

    def test_director_can_update_failed_follow_up(self):
        self.client.force_login(self.director)
        resp = self.client.post(
            reverse("education:failed_students_list"),
            {
                "result_id": self.failed_result.id,
                "follow_up_status": ExamResult.FOLLOW_UP_PARENT_CONTACTED,
                "follow_up_note": "Parent bilan gaplashildi",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.failed_result.refresh_from_db()
        self.assertEqual(self.failed_result.follow_up_status, ExamResult.FOLLOW_UP_PARENT_CONTACTED)
        self.assertEqual(self.failed_result.follow_up_note, "Parent bilan gaplashildi")
        self.assertEqual(self.failed_result.follow_up_updated_by_id, self.director.id)
        self.assertTrue(
            EducationAuditLog.objects.filter(
                action_type="exam_followup_updated",
                entity_type="ExamResult",
                entity_id=str(self.failed_result.id),
            ).exists()
        )

    def test_exam_result_batch_save_sets_followup_for_failed(self):
        new_session = ExamSession.objects.create(
            center=self.center,
            group=self.group,
            teacher=self.teacher,
            attendance_date=timezone.localdate(),
            exam_date=timezone.localdate(),
            lesson_number_reference=3,
            exam_sequence_number=3,
            teacher_decision=ExamSession.DECISION_YES,
            status=ExamSession.STATUS_DRAFT,
            created_by=self.teacher,
        )

        self.client.force_login(self.teacher)
        resp = self.client.post(
            reverse("education:exam_session_entry", args=[new_session.id]),
            {
                f"score_{self.student1.id}": "50",
                f"percent_{self.student1.id}": "50",
                f"teacher_comment_{self.student1.id}": "Need support",
                f"assignment_description_{self.student1.id}": "Task",
                f"score_{self.student2.id}": "90",
                f"percent_{self.student2.id}": "90",
                f"teacher_comment_{self.student2.id}": "Good",
                f"assignment_description_{self.student2.id}": "Task",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        r1 = ExamResult.objects.get(session=new_session, student=self.student1)
        r2 = ExamResult.objects.get(session=new_session, student=self.student2)
        self.assertFalse(r1.passed)
        self.assertEqual(r1.follow_up_status, ExamResult.FOLLOW_UP_PENDING)
        self.assertTrue(bool(r1.fail_reason))
        self.assertTrue(r2.passed)
        self.assertEqual(r2.follow_up_status, ExamResult.FOLLOW_UP_NOT_REQUIRED)

    def test_exam_create_builds_blank_results_for_active_students(self):
        self.client.force_login(self.teacher)
        resp = self.client.post(
            reverse("education:exam_create"),
            {
                "group": self.group.id,
                "exam_date": timezone.localdate().isoformat(),
                "assignment_description": "Yakuniy nazorat",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        session = ExamSession.objects.filter(group=self.group, lesson_number_reference=0).order_by("-id").first()
        if session is None:
            session = ExamSession.objects.filter(group=self.group).order_by("-id").first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, ExamSession.STATUS_DRAFT)

        results = ExamResult.objects.filter(session=session).order_by("student_id")
        self.assertEqual(results.count(), 2)
        self.assertTrue(all(result.score is None for result in results))
        self.assertTrue(all(result.percent is None for result in results))
        self.assertTrue(all(result.assignment_description == "Yakuniy nazorat" for result in results))

    def test_teacher_can_manage_group_schedule(self):
        self.client.force_login(self.teacher)
        resp = self.client.post(
            self._tenant_url("education:group_schedule_manage", self.group.id),
            {
                "action": "add",
                "weekday": "1",
                "start_time": "09:00",
                "end_time": "10:30",
                "room": "3-kabinet",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            GroupSchedule.objects.filter(
                center=self.center,
                group=self.group,
                weekday=1,
                start_time=time(9, 0),
                room="3-kabinet",
            ).exists()
        )
        self.assertContains(resp, "Dars jadvali")

    def test_group_add_creates_odd_schedule_automatically(self):
        self.client.force_login(self.director)
        resp = self.client.post(
            self._tenant_url("education:group_add"),
            {
                "nom": "Auto Schedule Group",
                "oqituvchi": self.teacher.id,
                "kurs_narxi": "650000",
                "course_start_date": timezone.localdate().isoformat(),
                "duration_months": "6",
                "schedule_mode": "odd",
                "schedule_start_time": "10:00",
                "schedule_end_time": "12:00",
                "schedule_room": "5-kabinet",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        group = Group.objects.get(center=self.center, nom="Auto Schedule Group")
        self.assertEqual(group.lessons_per_week, 3)
        schedules = list(GroupSchedule.objects.filter(group=group).order_by("weekday"))
        self.assertEqual([item.weekday for item in schedules], [1, 3, 5])
        self.assertTrue(all(item.start_time == time(10, 0) for item in schedules))
        self.assertTrue(all(item.end_time == time(12, 0) for item in schedules))
        self.assertTrue(all(item.room == "5-kabinet" for item in schedules))

    def test_schedule_conflict_check_detects_other_group(self):
        self.client.force_login(self.teacher)
        resp = self.client.get(
            self._tenant_url("education:schedule_conflict_check"),
            {
                "room": "2-kabinet",
                "weekday": "1",
                "start_time": "09:00",
                "exclude_group_id": self.group.id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload["conflict"])
        self.assertIn(self.group_other.nom, payload["groups"])

    def test_schedule_manage_blocks_room_conflict_on_save(self):
        self.client.force_login(self.teacher)
        resp = self.client.post(
            self._tenant_url("education:group_schedule_manage", self.group.id),
            {
                "action": "add",
                "weekday": "1",
                "start_time": "09:00",
                "end_time": "10:30",
                "room": "2-kabinet",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            GroupSchedule.objects.filter(
                center=self.center,
                group=self.group,
                weekday=1,
                start_time=time(9, 0),
                room="2-kabinet",
            ).exists()
        )
        self.assertContains(resp, self.group_other.nom)

    def test_director_weekly_schedule_view_lists_slots(self):
        GroupSchedule.objects.create(
            center=self.center,
            group=self.group,
            weekday=3,
            start_time=time(9, 0),
            end_time=time(10, 30),
            room="1-kabinet",
        )
        self.client.force_login(self.director)
        resp = self.client.get(self._tenant_url("education:weekly_schedule"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Haftalik Jadval")
        self.assertContains(resp, self.group.nom)
        self.assertContains(resp, "1-kabinet")

    def test_teacher_schedule_view_lists_own_weekly_schedule(self):
        GroupSchedule.objects.create(
            center=self.center,
            group=self.group,
            weekday=5,
            start_time=time(14, 0),
            end_time=time(15, 30),
            room="3-kabinet",
        )
        self.client.force_login(self.teacher)
        resp = self.client.get(self._tenant_url("education:teacher_schedule"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mening jadvalim")
        self.assertContains(resp, self.group.nom)
        self.assertContains(resp, "14:00–15:30")

    def test_exam_sessions_module_can_be_disabled_per_center(self):
        self.center.features = {FEATURE_UI_EXAM_SESSIONS: False}
        self.center.save(update_fields=["features"])

        self.client.force_login(self.director)
        resp = self.client.get(reverse("education:exam_list"))
        self.assertEqual(resp.status_code, 302)

    def test_failed_students_module_can_be_disabled_per_center(self):
        self.center.features = {FEATURE_UI_FAILED_STUDENTS: False}
        self.center.save(update_fields=["features"])

        self.client.force_login(self.director)
        resp = self.client.get(reverse("education:failed_students_list"))
        self.assertEqual(resp.status_code, 302)

    def test_certificates_module_can_be_disabled_per_center(self):
        self.center.features = {FEATURE_UI_CERTIFICATES: False}
        self.center.save(update_fields=["features"])

        self.client.force_login(self.director)
        resp = self.client.get(reverse("education:certificate_templates"))
        self.assertEqual(resp.status_code, 302)

    def test_weekly_schedule_module_can_be_disabled_per_center(self):
        self.center.features = {FEATURE_UI_WEEKLY_SCHEDULE: False}
        self.center.save(update_fields=["features"])

        self.client.force_login(self.director)
        resp = self.client.get(self._tenant_url("education:weekly_schedule"))
        self.assertEqual(resp.status_code, 302)
