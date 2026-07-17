from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Center, User
from core.test_utils import activate_center
from core.models import Notification
from education.models import (
    Attendance,
    CertificateRecord,
    CertificateTemplate,
    CertificateVerificationLog,
    CenterExamSetting,
    Enrollment,
    ExamResult,
    ExamSession,
    Group,
    GroupClosureWorkflow,
)
from education.services.ranking_service import build_group_completion_recommendations


class PhaseFourCertificateClosureTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Phase4 Center", slug="phase4-center")
        activate_center(self.center)
        self.director = User.objects.create_user(
            email="director.phase4@example.com",
            password="password",
            role="director",
            center=self.center,
            ism="Direk",
            familya="Tor",
        )
        self.teacher = User.objects.create_user(
            email="teacher.phase4@example.com",
            password="password",
            role="teacher",
            center=self.center,
            ism="Teach",
            familya="Er",
        )
        self.student = User.objects.create_user(
            email="student.phase4@example.com",
            password="password",
            role="student",
            center=self.center,
            ism="Ali",
            familya="Valiyev",
        )

        start_date = timezone.localdate() - timedelta(days=180)
        self.group = Group.objects.create(
            center=self.center,
            nom="Phase4 Group",
            oqituvchi=self.teacher,
            kurs_narxi=500000,
            oqituvchi_foiz=40,
            oy_dars_soni=12,
            course_start_date=start_date,
            duration_months=6,
            lessons_per_week=3,
            estimated_end_date=timezone.localdate(),
        )
        Enrollment.objects.create(group=self.group, student=self.student, center=self.center, is_active=True)

        CenterExamSetting.objects.create(
            center=self.center,
            exam_system_enabled=True,
            exam_every_n_lessons=12,
            passing_score_percent=60,
        )

        for i in range(1, 5):
            Attendance.objects.create(
                center=self.center,
                group=self.group,
                student=self.student,
                teacher=self.teacher,
                date=timezone.localdate() - timedelta(days=i),
                status="present",
                present=True,
            )

        session = ExamSession.objects.create(
            center=self.center,
            group=self.group,
            teacher=self.teacher,
            attendance_date=timezone.localdate(),
            exam_date=timezone.localdate(),
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
            student=self.student,
            teacher=self.teacher,
            score=85,
            percent=85,
            passed=True,
            exam_date=timezone.localdate(),
            lesson_number_reference=12,
            created_by=self.teacher,
        )

    def test_director_can_upload_certificate_template(self):
        self.client.force_login(self.director)
        resp = self.client.post(
            reverse("education:certificate_templates"),
            {
                "name": "Main cert",
                "template_type": "certificate",
                "template_file": SimpleUploadedFile("tmpl.png", b"fake-image-bytes", content_type="image/png"),
                "is_active": "on",
                "note": "Primary",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            CertificateTemplate.objects.filter(center=self.center, name="Main cert", template_type="certificate").exists()
        )

    def test_issue_certificate_and_verify_page(self):
        build_group_completion_recommendations(group=self.group, actor=self.director, persist=True)

        self.client.force_login(self.director)
        resp = self.client.post(
            reverse("education:issue_certificate_action", args=[self.group.id, self.student.id]),
            {"certificate_type": "certificate", "note": "Approved by director"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        cert = CertificateRecord.objects.get(group=self.group, student=self.student)
        self.assertEqual(cert.status, CertificateRecord.STATUS_ISSUED)
        self.assertTrue(cert.certificate_number.startswith("CHQ-"))
        self.assertTrue(bool(cert.pdf_file))

        pdf_resp = self.client.get(reverse("education:certificate_download_pdf", args=[cert.id]))
        self.assertIn(pdf_resp.status_code, (200, 302))
        if pdf_resp.status_code == 200:
            self.assertEqual(pdf_resp["Content-Type"], "application/pdf")

        self.client.force_login(self.director)
        verify_resp = self.client.get(reverse("education:certificate_verify", args=[cert.certificate_number]), follow=True)
        self.assertEqual(verify_resp.status_code, 200)
        self.assertTrue(
            CertificateVerificationLog.objects.filter(certificate=cert).exists()
        )

    def test_finalize_session_creates_notifications_and_draft_certificate(self):
        CertificateTemplate.objects.create(
            center=self.center,
            name="Auto cert",
            template_type="certificate",
            template_file=SimpleUploadedFile("tmpl.png", b"fake-image-bytes", content_type="image/png"),
            is_active=True,
            uploaded_by=self.director,
        )

        session = ExamSession.objects.create(
            center=self.center,
            group=self.group,
            teacher=self.teacher,
            attendance_date=timezone.localdate(),
            exam_date=timezone.localdate(),
            lesson_number_reference=24,
            exam_sequence_number=2,
            teacher_decision=ExamSession.DECISION_LATER,
            status=ExamSession.STATUS_DRAFT,
            created_by=self.teacher,
        )
        ExamResult.objects.create(
            center=self.center,
            session=session,
            group=self.group,
            student=self.student,
            teacher=self.teacher,
            assignment_description="Yakuniy nazorat",
            exam_date=timezone.localdate(),
            lesson_number_reference=24,
            created_by=self.teacher,
        )

        self.client.force_login(self.teacher)
        resp = self.client.post(
            reverse("education:exam_session_entry", args=[session.id]),
            {
                "action": "finalize",
                "max_score": "100",
                f"score_{self.student.id}": "90",
                f"percent_{self.student.id}": "90",
                f"teacher_comment_{self.student.id}": "A'lo",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        session.refresh_from_db()
        self.assertEqual(session.status, ExamSession.STATUS_COMPLETED)
        self.assertTrue(Notification.objects.filter(recipient=self.student, title="Imtihon natijasi").exists())
        self.assertTrue(Notification.objects.filter(recipient=self.director, title="Imtihon hisoboti").exists())
        self.assertTrue(Notification.objects.filter(recipient=self.director, title="Sertifikatlar tayyor").exists())

        draft_cert = CertificateRecord.objects.get(group=self.group, student=self.student, status=CertificateRecord.STATUS_DRAFT)
        self.assertEqual(draft_cert.certificate_type, CertificateRecord.TYPE_CERTIFICATE)
        self.assertFalse(bool(draft_cert.pdf_file))

    def test_issue_certificate_action_promotes_existing_draft(self):
        template = CertificateTemplate.objects.create(
            center=self.center,
            name="Draft cert",
            template_type="certificate",
            template_file=SimpleUploadedFile("tmpl2.png", b"fake-image-bytes", content_type="image/png"),
            is_active=True,
            uploaded_by=self.director,
        )
        draft = CertificateRecord.objects.create(
            center=self.center,
            group=self.group,
            student=self.student,
            template=template,
            certificate_type=CertificateRecord.TYPE_CERTIFICATE,
            certificate_number="CERT-1-ABCDEFGH",
            status=CertificateRecord.STATUS_DRAFT,
            note="Auto draft",
        )

        self.client.force_login(self.director)
        resp = self.client.post(
            reverse("education:issue_certificate_action", args=[self.group.id, self.student.id]),
            {"certificate_type": "certificate", "note": "Tasdiqlandi"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        draft.refresh_from_db()
        self.assertEqual(draft.status, CertificateRecord.STATUS_ISSUED)
        self.assertTrue(draft.certificate_number.startswith("CHQ-"))
        self.assertTrue(bool(draft.pdf_file))

    def test_exam_api_summary_returns_exam_metrics(self):
        self.client.force_login(self.director)
        resp = self.client.get(reverse("core:exam_api_summary"))
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertGreaterEqual(payload["total_sessions"], 1)
        self.assertGreaterEqual(payload["this_month_completed"], 1)
        self.assertGreaterEqual(payload["avg_percent"], 0)
        self.assertEqual(payload["pending_certificates"], 0)

    def test_group_closure_no_then_yes_keeps_group_history_safe(self):
        self.client.force_login(self.teacher)
        no_resp = self.client.post(
            reverse("education:group_closure_action", args=[self.group.id]),
            {"action": "no", "date": timezone.localdate().isoformat()},
        )
        self.assertEqual(no_resp.status_code, 302)

        workflow = GroupClosureWorkflow.objects.get(group=self.group)
        self.assertEqual(workflow.status, GroupClosureWorkflow.STATUS_CONTINUE)
        self.group.refresh_from_db()
        self.assertFalse(self.group.is_archived)

        self.client.force_login(self.director)
        yes_resp = self.client.post(
            reverse("education:group_closure_action", args=[self.group.id]),
            {"action": "yes", "date": timezone.localdate().isoformat()},
        )
        self.assertEqual(yes_resp.status_code, 302)

        workflow.refresh_from_db()
        self.assertEqual(workflow.status, GroupClosureWorkflow.STATUS_CLOSED)
        self.group.refresh_from_db()
        self.assertFalse(self.group.is_archived)
        self.assertTrue(Enrollment.objects.filter(group=self.group, student=self.student, is_active=True).exists())
