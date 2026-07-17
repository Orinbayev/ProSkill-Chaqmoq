from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from core.test_utils import activate_center
from chaqmoq.models import Ledger
from education.models import (
    Attendance,
    CenterExamSetting,
    DailyLightningRecord,
    Enrollment,
    ExamResult,
    ExamSession,
    Group,
    StudentAcademicSummary,
)
from education.services.ranking_service import build_group_completion_recommendations, build_group_internal_ranking


class PhaseThreeInternalRankingTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Phase3 Center", slug="phase3-center")
        activate_center(self.center)
        self.director = User.objects.create_user(
            email="director.phase3@example.com",
            password="password",
            role="director",
            center=self.center,
            ism="Direk",
            familya="Tor",
        )
        self.teacher = User.objects.create_user(
            email="teacher.phase3@example.com",
            password="password",
            role="teacher",
            center=self.center,
            ism="Teach",
            familya="Er",
        )
        self.s1 = User.objects.create_user(
            email="student1.phase3@example.com",
            password="password",
            role="student",
            center=self.center,
            ism="Ali",
            familya="One",
        )
        self.s2 = User.objects.create_user(
            email="student2.phase3@example.com",
            password="password",
            role="student",
            center=self.center,
            ism="Vali",
            familya="Two",
        )
        self.s3 = User.objects.create_user(
            email="student3.phase3@example.com",
            password="password",
            role="student",
            center=self.center,
            ism="Sardor",
            familya="Three",
        )

        self.group = Group.objects.create(
            center=self.center,
            nom="Phase3 Group",
            oqituvchi=self.teacher,
            kurs_narxi=500000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
            course_start_date=timezone.localdate().replace(day=1),
            duration_months=6,
            lessons_per_week=3,
        )
        Enrollment.objects.create(group=self.group, student=self.s1, center=self.center, is_active=True)
        Enrollment.objects.create(group=self.group, student=self.s2, center=self.center, is_active=True)
        Enrollment.objects.create(group=self.group, student=self.s3, center=self.center, is_active=True)

        CenterExamSetting.objects.create(
            center=self.center,
            exam_system_enabled=True,
            exam_every_n_lessons=12,
            passing_score_percent=60,
        )

        base_date = timezone.localdate()
        lesson_days = [base_date, base_date - timedelta(days=1), base_date - timedelta(days=2), base_date - timedelta(days=3)]
        for d in lesson_days:
            Attendance.objects.create(center=self.center, group=self.group, student=self.s1, teacher=self.teacher, date=d, status="present", present=True)
            Attendance.objects.create(
                center=self.center,
                group=self.group,
                student=self.s2,
                teacher=self.teacher,
                date=d,
                status="present" if d == lesson_days[0] else "absent_unexcused",
                present=(d == lesson_days[0]),
            )
            Attendance.objects.create(
                center=self.center,
                group=self.group,
                student=self.s3,
                teacher=self.teacher,
                date=d,
                status="present" if d != lesson_days[-1] else "absent_excused",
                present=(d != lesson_days[-1]),
            )

        session = ExamSession.objects.create(
            center=self.center,
            group=self.group,
            teacher=self.teacher,
            attendance_date=base_date,
            exam_date=base_date,
            lesson_number_reference=12,
            exam_sequence_number=1,
            teacher_decision=ExamSession.DECISION_YES,
            status=ExamSession.STATUS_COMPLETED,
            created_by=self.teacher,
        )
        ExamResult.objects.create(
            center=self.center,
            session=session,
            group=self.group,
            student=self.s1,
            teacher=self.teacher,
            score=88,
            percent=88,
            passed=True,
            exam_date=base_date,
            lesson_number_reference=12,
            created_by=self.teacher,
        )
        ExamResult.objects.create(
            center=self.center,
            session=session,
            group=self.group,
            student=self.s2,
            teacher=self.teacher,
            score=40,
            percent=40,
            passed=False,
            exam_date=base_date,
            lesson_number_reference=12,
            created_by=self.teacher,
        )
        ExamResult.objects.create(
            center=self.center,
            session=session,
            group=self.group,
            student=self.s3,
            teacher=self.teacher,
            score=70,
            percent=70,
            passed=True,
            exam_date=base_date,
            lesson_number_reference=12,
            created_by=self.teacher,
        )

        DailyLightningRecord.objects.create(center=self.center, group=self.group, student=self.s1, date=base_date, plus_points=40, minus_points=0)
        DailyLightningRecord.objects.create(center=self.center, group=self.group, student=self.s2, date=base_date, plus_points=300, minus_points=0)
        DailyLightningRecord.objects.create(center=self.center, group=self.group, student=self.s3, date=base_date, plus_points=60, minus_points=-10)

        Ledger.objects.create(student=self.s1, beruvchi=self.teacher, group=self.group, ball=40)
        Ledger.objects.create(student=self.s2, beruvchi=self.teacher, group=self.group, ball=1000)
        Ledger.objects.create(student=self.s3, beruvchi=self.teacher, group=self.group, ball=20)

    def test_internal_ranking_not_dominated_by_lightning(self):
        rows = build_group_internal_ranking(group=self.group, actor=self.teacher)
        self.assertEqual(len(rows), 3)
        # s2 has the highest lightning, but weak attendance/exam results should keep it below s1.
        self.assertEqual(rows[0]["student_id"], self.s1.id)

    def test_completion_recommendation_persists_student_summary(self):
        payload = build_group_completion_recommendations(group=self.group, actor=self.director)
        self.assertEqual(len(payload["rows"]), 3)
        self.assertTrue(
            StudentAcademicSummary.objects.filter(group=self.group, student=self.s1, completion_recommendation="eligible").exists()
        )
        self.assertTrue(
            StudentAcademicSummary.objects.filter(group=self.group, student=self.s2, completion_recommendation="not_eligible").exists()
        )

    def test_group_internal_ranking_view_available_for_teacher(self):
        self.client.force_login(self.teacher)
        resp = self.client.get(reverse("education:group_internal_ranking", args=[self.group.id]), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Guruh ichki aktivlik reytingi")

    def test_group_completion_recommendations_view_for_director(self):
        self.client.force_login(self.director)
        resp = self.client.get(reverse("education:group_completion_recommendations", args=[self.group.id]), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Kurs yakuniy tavsiyalari")
