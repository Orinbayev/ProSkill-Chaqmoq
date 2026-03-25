from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from education.models import (
    Attendance,
    CenterExamSetting,
    Enrollment,
    ExamReminderLog,
    ExamResult,
    ExamResultFile,
    ExamSession,
    Group,
)
from education.services.group_schedule_service import calculate_estimated_end_date


class PhaseOneExamFoundationTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Center X", slug="center-x")
        self.teacher = User.objects.create_user(
            email="teacher.phase1@example.com",
            password="password",
            role="teacher",
            center=self.center,
            ism="Teach",
            familya="Er",
        )
        self.director = User.objects.create_user(
            email="director.phase1@example.com",
            password="password",
            role="director",
            center=self.center,
            ism="Direk",
            familya="Tor",
        )
        self.student = User.objects.create_user(
            email="student.phase1@example.com",
            password="password",
            role="student",
            center=self.center,
            ism="Stud",
            familya="Ent",
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="Phase1 Group",
            oqituvchi=self.teacher,
            kurs_narxi=500000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
            course_start_date=timezone.localdate(),
            duration_months=6,
            lessons_per_week=3,
            estimated_end_date=calculate_estimated_end_date(
                course_start_date=timezone.localdate(),
                duration_months=6,
                lessons_per_week=3,
            ),
        )
        self.enrollment = Enrollment.objects.create(
            group=self.group,
            student=self.student,
            center=self.center,
            kurs_narhi=500000,
            oqituvchi_foiz=40,
            is_active=True,
        )

    def test_group_duration_estimation_fields_saved(self):
        self.assertEqual(self.group.lessons_per_week, 3)
        self.assertIsNotNone(self.group.course_start_date)
        self.assertIsNotNone(self.group.estimated_end_date)
        self.assertGreater(self.group.estimated_end_date, self.group.course_start_date)

    def test_exam_settings_permissions(self):
        self.client.force_login(self.director)
        resp = self.client.post(
            reverse("education:exam_settings"),
            {
                "exam_system_enabled": "on",
                "exam_every_n_lessons": 10,
                "passing_score_percent": 65,
                "exam_file_upload_enabled": "on",
                "exam_result_required": "on",
                "optional_task_upload_prompt_enabled": "on",
            },
        )
        self.assertEqual(resp.status_code, 302)

        settings_obj = CenterExamSetting.objects.get(center=self.center)
        self.assertEqual(settings_obj.exam_every_n_lessons, 10)
        self.assertEqual(settings_obj.passing_score_percent, 65)

        self.client.force_login(self.teacher)
        get_resp = self.client.get(reverse("education:exam_settings"))
        self.assertIn(get_resp.status_code, (200, 302))
        post_resp = self.client.post(
            reverse("education:exam_settings"),
            {
                "exam_system_enabled": "on",
                "exam_every_n_lessons": 8,
                "passing_score_percent": 55,
            },
        )
        self.assertIn(post_resp.status_code, (302, 403))
        settings_obj.refresh_from_db()
        self.assertEqual(settings_obj.exam_every_n_lessons, 10)

    def test_exam_reminder_later_logged_without_creating_session(self):
        CenterExamSetting.objects.create(center=self.center, exam_system_enabled=True, exam_every_n_lessons=1)
        Attendance.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            teacher=self.teacher,
            date=timezone.localdate(),
            status="present",
            present=True,
        )

        self.client.force_login(self.teacher)
        resp = self.client.post(
            reverse("education:exam_reminder_action", args=[self.group.id]),
            {"action": "later", "date": timezone.localdate().isoformat()},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            ExamReminderLog.objects.filter(group=self.group, teacher=self.teacher, action=ExamReminderLog.ACTION_LATER).exists()
        )
        self.assertFalse(ExamSession.objects.filter(group=self.group).exists())

    def test_exam_reminder_yes_creates_session_with_teacher_decision(self):
        CenterExamSetting.objects.create(center=self.center, exam_system_enabled=True, exam_every_n_lessons=1)
        Attendance.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            teacher=self.teacher,
            date=timezone.localdate(),
            status="present",
            present=True,
        )

        self.client.force_login(self.teacher)
        resp = self.client.post(
            reverse("education:exam_reminder_action", args=[self.group.id]),
            {"action": "yes", "date": timezone.localdate().isoformat(), "note": "today exam"},
        )
        self.assertEqual(resp.status_code, 302)

        session = ExamSession.objects.filter(group=self.group).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.teacher_decision, ExamSession.DECISION_YES)

    def test_exam_session_entry_saves_results_and_files(self):
        CenterExamSetting.objects.create(
            center=self.center,
            exam_system_enabled=True,
            exam_every_n_lessons=1,
            passing_score_percent=60,
            exam_file_upload_enabled=True,
            exam_result_required=True,
            optional_task_upload_prompt_enabled=True,
        )
        session = ExamSession.objects.create(
            center=self.center,
            group=self.group,
            teacher=self.teacher,
            attendance_date=timezone.localdate(),
            exam_date=timezone.localdate(),
            lesson_number_reference=1,
            exam_sequence_number=1,
            teacher_decision=ExamSession.DECISION_YES,
            status=ExamSession.STATUS_DRAFT,
            created_by=self.teacher,
        )

        self.client.force_login(self.teacher)
        resp = self.client.post(
            reverse("education:exam_session_entry", args=[session.id]),
            {
                f"score_{self.student.id}": "75",
                f"percent_{self.student.id}": "75",
                f"teacher_comment_{self.student.id}": "Good",
                f"assignment_description_{self.student.id}": "Optional task",
                f"work_files_{self.student.id}": SimpleUploadedFile("work.pdf", b"fake-pdf", content_type="application/pdf"),
                f"task_files_{self.student.id}": SimpleUploadedFile("task.pdf", b"fake-pdf", content_type="application/pdf"),
            },
        )
        self.assertEqual(resp.status_code, 302)

        result = ExamResult.objects.get(session=session, student=self.student)
        self.assertTrue(result.passed)
        self.assertEqual(result.percent, 75)
        self.assertEqual(result.teacher_comment, "Good")
        self.assertEqual(ExamResultFile.objects.filter(result=result).count(), 2)

    def test_group_detail_renders_with_exam_reminder_block(self):
        CenterExamSetting.objects.create(
            center=self.center,
            exam_system_enabled=True,
            exam_every_n_lessons=1,
        )
        Attendance.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            teacher=self.teacher,
            date=timezone.localdate(),
            status="present",
            present=True,
        )
        self.client.force_login(self.teacher)
        resp = self.client.get(
            reverse("education:group_detail", args=[self.group.id]),
            {"date": timezone.localdate().isoformat()},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Imtihon", status_code=200)
