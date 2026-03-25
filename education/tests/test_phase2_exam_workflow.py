from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from education.models import (
    CenterExamSetting,
    EducationAuditLog,
    Enrollment,
    ExamResult,
    ExamResultFile,
    ExamSession,
    Group,
)


class PhaseTwoExamWorkflowTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Phase2 Center", slug="phase2-center")
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
        Enrollment.objects.create(group=self.group, student=self.student1, center=self.center, is_active=True)
        Enrollment.objects.create(group=self.group, student=self.student2, center=self.center, is_active=True)

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
        resp = self.client.get(reverse("education:failed_students_list"))
        self.assertIn(resp.status_code, (302, 403))

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
