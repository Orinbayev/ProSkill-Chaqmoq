from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from django.core.files.base import ContentFile
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from education.models import (
    CertificateRecord,
    CertificateTemplate,
    CertificateVerificationLog,
    StudentAcademicSummary,
)
from education.services.audit_service import log_education_event
from education.services.ranking_service import build_group_completion_recommendations

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _abs_uri(request, path: str) -> str:
    if request is None:
        return path
    return request.build_absolute_uri(path)


def get_active_template(*, center, certificate_type: str):
    return (
        CertificateTemplate.objects.filter(center=center, template_type=certificate_type, is_active=True)
        .order_by("-updated_at", "-id")
        .first()
    )


def get_or_build_summary(*, group, student, actor=None):
    summary = StudentAcademicSummary.objects.filter(group=group, student=student).first()
    if summary:
        return summary

    payload = build_group_completion_recommendations(group=group, actor=actor, persist=True)
    for row in payload["rows"]:
        if row["student"].id == student.id and row.get("summary") is not None:
            return row["summary"]
    return StudentAcademicSummary.objects.filter(group=group, student=student).first()


def _certificate_number_for_record(record: CertificateRecord) -> str:
    year = record.issue_date.year
    return f"CHQ-{record.center_id}-{year}-{record.id:06d}"


def _verification_path(record: CertificateRecord) -> str:
    return reverse("education:certificate_verify", kwargs={"certificate_number": record.certificate_number})


def _draw_qr(c: canvas.Canvas, *, payload: str, x: float, y: float, size: float):
    widget = qr.QrCodeWidget(payload)
    b = widget.getBounds()
    width = b[2] - b[0]
    height = b[3] - b[1]
    drawing = Drawing(size, size, transform=[size / width, 0, 0, size / height, 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, c, x, y)


def _draw_template_background(c: canvas.Canvas, record: CertificateRecord):
    template = record.template
    if not template or not template.template_file:
        return

    ext = Path(template.template_file.name or "").suffix.lower()
    if ext not in IMAGE_EXTENSIONS:
        return

    try:
        template.template_file.open("rb")
        img_reader = ImageReader(template.template_file)
        page_w, page_h = A4
        c.drawImage(img_reader, 0, 0, width=page_w, height=page_h, preserveAspectRatio=False, mask="auto")
    except Exception:
        # Template muammosi bo'lsa ham certificate generation to'xtab qolmasin.
        pass


def _generate_pdf_bytes(*, record: CertificateRecord, verify_url: str) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4

    _draw_template_background(c, record)

    c.setStrokeColor(colors.HexColor("#D9DDE5"))
    c.setLineWidth(1)
    c.rect(12 * mm, 12 * mm, page_w - 24 * mm, page_h - 24 * mm)

    title = "CERTIFICATE" if record.certificate_type == CertificateRecord.TYPE_CERTIFICATE else "DIPLOMA"
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(colors.HexColor("#1F2937"))
    c.drawCentredString(page_w / 2, page_h - 42 * mm, title)

    c.setFont("Helvetica", 12)
    c.setFillColor(colors.HexColor("#4B5563"))
    c.drawCentredString(page_w / 2, page_h - 52 * mm, "This is to certify that")

    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawCentredString(page_w / 2, page_h - 66 * mm, record.student.get_full_name())

    c.setFont("Helvetica", 12)
    c.setFillColor(colors.HexColor("#374151"))
    c.drawCentredString(page_w / 2, page_h - 78 * mm, f"has successfully completed the course/group: {record.group.nom}")

    teacher_name = record.group.oqituvchi.get_full_name() if record.group.oqituvchi_id else "—"
    c.drawCentredString(page_w / 2, page_h - 88 * mm, f"Teacher: {teacher_name}")
    c.drawCentredString(page_w / 2, page_h - 96 * mm, f"Center: {record.center.name}")

    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawString(20 * mm, 26 * mm, f"Certificate No: {record.certificate_number}")
    c.drawString(20 * mm, 20 * mm, f"Issue Date: {record.issue_date.isoformat()}")
    c.drawString(20 * mm, 14 * mm, f"Status: {record.get_status_display()}")

    qr_size = 28 * mm
    _draw_qr(c, payload=verify_url, x=page_w - 48 * mm, y=14 * mm, size=qr_size)
    c.setFont("Helvetica", 8)
    c.drawRightString(page_w - 18 * mm, 12 * mm, "Scan to verify")

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#9CA3AF"))
    c.drawString(20 * mm, 8 * mm, verify_url)

    c.showPage()
    c.save()
    return buffer.getvalue()


@transaction.atomic
def issue_certificate_for_student(
    *,
    group,
    student,
    actor,
    certificate_type: str = CertificateRecord.TYPE_CERTIFICATE,
    note: str = "",
    request=None,
):
    existing = (
        CertificateRecord.objects.filter(
            group=group,
            student=student,
            certificate_type=certificate_type,
            status=CertificateRecord.STATUS_ISSUED,
        )
        .order_by("-id")
        .first()
    )
    if existing:
        if not existing.pdf_file:
            regenerate_certificate_pdf(record=existing, request=request)
        return existing

    summary = get_or_build_summary(group=group, student=student, actor=actor)

    template = get_active_template(center=group.center, certificate_type=certificate_type)

    recommendation_status = (
        summary.completion_recommendation if summary else StudentAcademicSummary.RECOMMENDATION_NEEDS_REVIEW
    )
    recommendation_reason = summary.recommendation_reason if summary else "Yakuniy summary topilmadi"

    record = CertificateRecord.objects.create(
        center=group.center,
        group=group,
        student=student,
        template=template,
        summary=summary,
        certificate_type=certificate_type,
        certificate_number=f"TMP-{uuid4().hex[:10]}",
        issue_date=timezone.localdate(),
        status=CertificateRecord.STATUS_ISSUED,
        recommendation_status=recommendation_status,
        recommendation_reason=recommendation_reason,
        approved_by=actor,
        approved_at=timezone.now(),
        issued_by=actor,
        issued_at=timezone.now(),
        note=note or "",
    )

    record.certificate_number = _certificate_number_for_record(record)
    verify_url = _abs_uri(request, _verification_path(record))

    pdf_bytes = _generate_pdf_bytes(record=record, verify_url=verify_url)
    filename = f"{record.certificate_number}.pdf"
    record.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)

    record.metadata = {
        "verify_url": verify_url,
        "summary_id": summary.id if summary else None,
    }
    record.save(
        update_fields=[
            "certificate_number",
            "pdf_file",
            "metadata",
            "updated_at",
        ]
    )

    log_education_event(
        center=group.center,
        actor=actor,
        action_type="certificate_approved",
        entity=record,
        payload={
            "group_id": group.id,
            "student_id": student.id,
            "recommendation_status": recommendation_status,
        },
    )
    log_education_event(
        center=group.center,
        actor=actor,
        action_type="certificate_generated",
        entity=record,
        payload={
            "certificate_number": record.certificate_number,
            "certificate_type": record.certificate_type,
        },
    )

    return record


def regenerate_certificate_pdf(*, record: CertificateRecord, request=None):
    verify_url = _abs_uri(request, _verification_path(record))
    pdf_bytes = _generate_pdf_bytes(record=record, verify_url=verify_url)
    filename = f"{record.certificate_number}.pdf"
    record.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
    return record


def record_verification_hit(*, record: CertificateRecord, request=None):
    ip = ""
    agent = ""
    actor = None
    if request is not None:
        actor = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = (xff.split(",")[0] if xff else request.META.get("REMOTE_ADDR", ""))[:64]
        agent = (request.META.get("HTTP_USER_AGENT", "") or "")[:1000]

    log = CertificateVerificationLog.objects.create(
        certificate=record,
        verified_by=actor,
        ip_address=ip,
        user_agent=agent,
        metadata={"status": record.status},
    )

    log_education_event(
        center=record.center,
        actor=actor,
        action_type="certificate_verified",
        entity=record,
        payload={
            "certificate_number": record.certificate_number,
            "verification_log_id": log.id,
        },
    )
    return log


def user_can_view_certificate(user, record: CertificateRecord) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or getattr(user, "role", "") in ("director", "manager"):
        return True
    if getattr(user, "role", "") == "teacher" and record.group.oqituvchi_id == user.id:
        return True
    if getattr(user, "role", "") == "student" and record.student_id == user.id:
        return True
    if getattr(user, "role", "") == "parent" and record.student in user.children.all():
        return True
    return False
