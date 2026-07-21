from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import Center, User
from core.test_utils import activate_center
from education.models import (
    Attendance,
    CenterExamSetting,
    Enrollment,
    ExamReminderLog,
    Group,
)
from education.services.exam_service import (
    get_exam_reminder_state,
    notify_teacher_exam_due,
    scan_and_notify_due_exams,
)


class ExamTelegramReminderTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="TG Exam Center", slug="tg-exam-center")
        activate_center(self.center)
        self.teacher = User.objects.create_user(
            email="teacher.tgexam@example.com",
            password="password",
            role="teacher",
            center=self.center,
            ism="Teach",
            familya="Er",
            telegram_id="999001",
            is_telegram_linked=True,
        )
        self.student = User.objects.create_user(
            email="student.tgexam@example.com",
            password="password",
            role="student",
            center=self.center,
            ism="Stud",
            familya="Ent",
        )
        self.group = Group.objects.create(
            center=self.center,
            nom="TG Exam Group",
            oqituvchi=self.teacher,
            kurs_narxi=500000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
        )
        Enrollment.objects.create(
            group=self.group,
            student=self.student,
            center=self.center,
            kurs_narhi=500000,
            oqituvchi_foiz=40,
            is_active=True,
        )
        CenterExamSetting.objects.create(
            center=self.center,
            exam_system_enabled=True,
            exam_every_n_lessons=3,
        )

    def _seed_lessons(self, count: int):
        today = timezone.localdate()
        for i in range(count):
            Attendance.objects.create(
                center=self.center,
                group=self.group,
                student=self.student,
                teacher=self.teacher,
                date=today - timedelta(days=count - i),
                status="present",
                present=True,
            )

    @patch("accounts.utils_bot.send_telegram_message_async")
    def test_notify_teacher_when_checkpoint_due(self, mock_tg):
        self._seed_lessons(3)
        state = get_exam_reminder_state(group=self.group)
        self.assertTrue(state["due"])
        self.assertEqual(state["target_lesson_number"], 3)

        result = notify_teacher_exam_due(group=self.group)
        self.assertTrue(result["sent"])
        self.assertTrue(result["telegram"])
        mock_tg.assert_called_once()
        args, _kwargs = mock_tg.call_args
        self.assertEqual(str(args[0]), "999001")
        self.assertIn("Imtihon", args[1])

        self.assertTrue(
            ExamReminderLog.objects.filter(
                group=self.group,
                action=ExamReminderLog.ACTION_TELEGRAM,
                lesson_number_reference=3,
            ).exists()
        )

        # Dedupe: second call must not re-send
        mock_tg.reset_mock()
        result2 = notify_teacher_exam_due(group=self.group)
        self.assertFalse(result2["sent"])
        self.assertEqual(result2["reason"], "already_notified")
        mock_tg.assert_not_called()

    @patch("accounts.utils_bot.send_telegram_message_async")
    def test_attendance_signal_triggers_notify(self, mock_tg):
        # 2 dars oldindan
        today = timezone.localdate()
        for i in range(2):
            Attendance.objects.create(
                center=self.center,
                group=self.group,
                student=self.student,
                teacher=self.teacher,
                date=today - timedelta(days=3 - i),
                status="present",
                present=True,
            )
        mock_tg.reset_mock()

        # 3-dars — signal on_commit ishlashi kerak (TestCase wraps in transaction;
        # captureOnCommitCallbacks bilan ishga tushiramiz)
        with self.captureOnCommitCallbacks(execute=True):
            Attendance.objects.create(
                center=self.center,
                group=self.group,
                student=self.student,
                teacher=self.teacher,
                date=today,
                status="present",
                present=True,
            )

        self.assertTrue(
            ExamReminderLog.objects.filter(
                group=self.group,
                action=ExamReminderLog.ACTION_TELEGRAM,
            ).exists()
        )
        mock_tg.assert_called()

    @patch("accounts.utils_bot.send_telegram_message_async")
    def test_scan_command_path_sends_for_due_groups(self, mock_tg):
        self._seed_lessons(3)
        result = scan_and_notify_due_exams(center=self.center)
        self.assertEqual(result["sent"], 1)
        mock_tg.assert_called_once()

    @patch("accounts.utils_bot.send_telegram_message_async")
    def test_disabled_exam_system_skips(self, mock_tg):
        CenterExamSetting.objects.filter(center=self.center).update(exam_system_enabled=False)
        self._seed_lessons(3)
        result = notify_teacher_exam_due(group=self.group)
        self.assertFalse(result["sent"])
        self.assertEqual(result["reason"], "disabled")
        mock_tg.assert_not_called()
