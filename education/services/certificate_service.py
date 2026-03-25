from __future__ import annotations

import math
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils import timezone

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
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
PDF_LAYOUT_VERSION = 8
CERT_PAGE_WIDTH = 297 * mm
CERT_PAGE_HEIGHT = CERT_PAGE_WIDTH * 9 / 16
CERT_PAGE_SIZE = (CERT_PAGE_WIDTH, CERT_PAGE_HEIGHT)
CERT_LOGO_PATH = Path(settings.BASE_DIR) / "static" / "img" / "chaqmoq_blue_logo_v2.png"


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


def _has_image_template(record: CertificateRecord) -> bool:
    template = record.template
    if not template or not template.template_file:
        return False
    ext = Path(template.template_file.name or "").suffix.lower()
    return ext in IMAGE_EXTENSIONS


def _draw_template_background(c: canvas.Canvas, record: CertificateRecord):
    if not _has_image_template(record):
        return

    try:
        template = record.template
        template.template_file.open("rb")
        img_reader = ImageReader(template.template_file)
        page_w, page_h = CERT_PAGE_SIZE
        c.drawImage(img_reader, 0, 0, width=page_w, height=page_h, preserveAspectRatio=False, mask="auto")
    except Exception:
        # Template muammosi bo'lsa ham certificate generation to'xtab qolmasin.
        pass


def _short_text(value: str, max_len: int = 96) -> str:
    cleaned = " ".join(str(value or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[: max_len - 3].rstrip()}..."


def _draw_centered_paragraph(
    c: canvas.Canvas,
    *,
    text: str,
    x_center: float,
    y_top: float,
    font_name: str,
    font_size: int,
    color,
    max_width: float,
    line_step: float,
) -> float:
    c.setFont(font_name, font_size)
    c.setFillColor(color)
    lines = simpleSplit(text or "", font_name, font_size, max_width) or [""]

    y_cursor = y_top
    for line in lines:
        c.drawCentredString(x_center, y_cursor, line)
        y_cursor -= line_step
    return y_cursor


def _mix_color(top_hex: str, bottom_hex: str, ratio: float):
    ratio = max(0.0, min(1.0, float(ratio)))
    top = colors.HexColor(top_hex)
    bottom = colors.HexColor(bottom_hex)
    return colors.Color(
        top.red + (bottom.red - top.red) * ratio,
        top.green + (bottom.green - top.green) * ratio,
        top.blue + (bottom.blue - top.blue) * ratio,
    )


def _draw_vertical_gradient(
    c: canvas.Canvas,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    top_hex: str,
    bottom_hex: str,
    steps: int = 120,
):
    step_h = height / max(steps, 1)
    for i in range(steps):
        ratio = i / max(steps - 1, 1)
        c.setFillColor(_mix_color(top_hex, bottom_hex, ratio))
        y_strip = y + height - (i + 1) * step_h
        c.rect(x, y_strip, width, step_h + 0.4, stroke=0, fill=1)


def _draw_hex_pattern(c: canvas.Canvas, *, x: float, y: float, width: float, height: float, radius: float = 4.6 * mm):
    c.saveState()
    c.setStrokeColor(colors.HexColor("#EAF2FF"))
    c.setLineWidth(0.6)

    step_x = radius * 1.72
    step_y = radius * 1.48
    rows = int(height / step_y) + 3
    cols = int(width / step_x) + 3

    for row in range(rows):
        cy = y + row * step_y
        if cy - radius > y + height:
            continue
        x_offset = (step_x / 2) if row % 2 else 0
        for col in range(cols):
            cx = x + x_offset + col * step_x
            if cx + radius < x or cx - radius > x + width:
                continue

            pts = []
            for k in range(6):
                angle = math.radians(60 * k + 30)
                px = cx + radius * math.cos(angle)
                py = cy + radius * math.sin(angle)
                pts.append((px, py))

            path = c.beginPath()
            path.moveTo(pts[0][0], pts[0][1])
            for px, py in pts[1:]:
                path.lineTo(px, py)
            path.close()
            c.drawPath(path, stroke=1, fill=0)
    c.restoreState()


def _fit_text_lines(
    *,
    text: str,
    font_name: str,
    max_width: float,
    max_lines: int,
    max_font_size: int,
    min_font_size: int,
):
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return min_font_size, [""]

    for font_size in range(max_font_size, min_font_size - 1, -1):
        lines = simpleSplit(cleaned, font_name, font_size, max_width)
        if len(lines) <= max_lines:
            return font_size, lines

    font_size = min_font_size
    lines = simpleSplit(cleaned, font_name, font_size, max_width)
    lines = lines[:max_lines]
    if lines:
        last = lines[-1]
        while last and stringWidth(f"{last}...", font_name, font_size) > max_width:
            last = last[:-1]
        lines[-1] = f"{last.rstrip()}..." if last else "..."
    return font_size, lines


def _draw_circular_text(
    c: canvas.Canvas,
    *,
    text: str,
    x: float,
    y: float,
    radius: float,
    start_angle: float,
    end_angle: float,
    font_name: str,
    font_size: float,
):
    letters = [ch for ch in (text or "").strip() if ch]
    if not letters:
        return

    if len(letters) == 1:
        angles = [(start_angle + end_angle) / 2]
    else:
        span = end_angle - start_angle
        step = span / (len(letters) - 1)
        angles = [start_angle + i * step for i in range(len(letters))]

    for letter, angle in zip(letters, angles):
        rad = math.radians(angle)
        px = x + radius * math.cos(rad)
        py = y + radius * math.sin(rad)
        c.saveState()
        c.translate(px, py)
        c.rotate(angle - 90)
        c.setFont(font_name, font_size)
        c.drawCentredString(0, 0, letter)
        c.restoreState()


def _draw_center_seal(c: canvas.Canvas, *, center_name: str, x: float, y: float, radius: float):
    c.saveState()
    blue = colors.HexColor("#2C7BF3")
    pale = colors.Color(0.16, 0.48, 0.95, alpha=0.06)

    c.setFillColor(pale)
    c.circle(x, y, radius - 2 * mm, stroke=0, fill=1)

    c.setStrokeColor(blue)
    c.setLineWidth(1.2)
    c.circle(x, y, radius, stroke=1, fill=0)
    c.circle(x, y, radius - 2.2 * mm, stroke=1, fill=0)
    c.circle(x, y, radius - 8.0 * mm, stroke=1, fill=0)

    c.setFillColor(blue)
    c.setStrokeColor(blue)
    c.setLineWidth(0.8)
    for deg in (265, 275):
        ang = math.radians(deg)
        sx = x + (radius - 4.0 * mm) * math.cos(ang)
        sy = y + (radius - 4.0 * mm) * math.sin(ang)
        c.circle(sx, sy, 0.85 * mm, stroke=1, fill=1)

    ring_text = _short_text(center_name.upper().replace("'", " "), 44)
    _draw_circular_text(
        c,
        text=ring_text,
        x=x,
        y=y,
        radius=radius - 3.7 * mm,
        start_angle=160,
        end_angle=20,
        font_name="Helvetica",
        font_size=6.6,
    )
    _draw_circular_text(
        c,
        text="RASMIY MUHR",
        x=x,
        y=y,
        radius=radius - 3.7 * mm,
        start_angle=340,
        end_angle=200,
        font_name="Helvetica-Bold",
        font_size=6.8,
    )

    c.setFillColor(blue)
    center_lines = simpleSplit(_short_text(center_name, 42), "Helvetica-Bold", 8.2, (radius - 8.8 * mm) * 2)
    center_lines = center_lines[:2] if center_lines else [center_name]
    line_specs = [("Helvetica-Bold", 8.2, line) for line in center_lines]
    line_specs.append(("Helvetica", 6.2, "SERTIFIKAT"))

    block_step = 4.15 * mm
    start_y = y + ((len(line_specs) - 1) * block_step) / 2
    for idx, (font_name, font_size, line) in enumerate(line_specs):
        c.setFont(font_name, font_size)
        c.drawCentredString(x, start_y - idx * block_step, line)
    c.restoreState()


def _draw_decorative_panel(c: canvas.Canvas, *, x: float, y: float, width: float, height: float):
    _draw_vertical_gradient(
        c,
        x=x,
        y=y,
        width=width,
        height=height,
        top_hex="#25A8FF",
        bottom_hex="#1D4DF1",
    )

    c.saveState()
    c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.18))
    c.setLineWidth(1.1)
    for i in range(5):
        r = 12 * mm + i * 4.4 * mm
        c.circle(x + width * 0.64, y + height * 0.34, r, stroke=1, fill=0)

    c.setFillColor(colors.Color(1, 1, 1, alpha=0.16))
    c.circle(x + width * 0.60, y + height * 0.34, 12.5 * mm, stroke=0, fill=1)

    c.setFillColor(colors.Color(1, 1, 1, alpha=0.18))
    c.roundRect(x + width * 0.10, y + height * 0.68, 10 * mm, 7 * mm, 3 * mm, stroke=0, fill=1)
    c.roundRect(x + width * 0.72, y + height * 0.54, 12 * mm, 8 * mm, 3.2 * mm, stroke=0, fill=1)

    c.setFillColor(colors.Color(1, 1, 1, alpha=0.20))
    c.rect(x + width * 0.12, y + 16 * mm, 22 * mm, 1.2 * mm, stroke=0, fill=1)
    c.rect(x + width * 0.12, y + 12 * mm, 17 * mm, 1.2 * mm, stroke=0, fill=1)
    c.rect(x + width * 0.12, y + 8 * mm, 20 * mm, 1.2 * mm, stroke=0, fill=1)
    c.restoreState()


def _draw_brand(c: canvas.Canvas, *, x: float, y: float, center_name: str):
    c.saveState()
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y + 1.0 * mm, _short_text(center_name, 44))
    c.setFillColor(colors.HexColor("#4B5563"))
    c.setFont("Helvetica", 8.8)
    c.drawString(x, y - 3.7 * mm, "O'QUV MARKAZI SERTIFIKATI")
    c.restoreState()


def _draw_panel_center_logo(c: canvas.Canvas, *, panel_x: float, panel_y: float, panel_w: float, panel_h: float):
    if not CERT_LOGO_PATH.exists():
        return
    try:
        logo_reader = ImageReader(str(CERT_LOGO_PATH))
    except Exception:
        return

    logo_size = 30 * mm
    logo_x = panel_x + (panel_w - logo_size) / 2
    logo_y = panel_y + panel_h * 0.52

    c.saveState()
    c.setFillColor(colors.Color(1, 1, 1, alpha=0.12))
    c.circle(panel_x + panel_w / 2, logo_y + logo_size / 2, 18 * mm, stroke=0, fill=1)
    c.restoreState()

    c.drawImage(
        logo_reader,
        logo_x,
        logo_y,
        width=logo_size,
        height=logo_size,
        preserveAspectRatio=True,
        mask="auto",
    )


def _resolve_completion_date(record: CertificateRecord):
    metadata = record.metadata if isinstance(record.metadata, dict) else {}
    raw_completion = metadata.get("completion_date")
    if isinstance(raw_completion, str):
        parsed = parse_date(raw_completion)
        if parsed:
            return parsed

    summary_metadata = getattr(getattr(record, "summary", None), "metadata", None)
    if isinstance(summary_metadata, dict):
        raw_snapshot = summary_metadata.get("snapshot_date")
        if isinstance(raw_snapshot, str):
            parsed = parse_date(raw_snapshot)
            if parsed:
                return parsed

    group_closed_at = getattr(record.group, "closed_at", None)
    if group_closed_at:
        return group_closed_at.date()

    group_estimated_end = getattr(record.group, "estimated_end_date", None)
    if group_estimated_end:
        return group_estimated_end

    return record.issue_date


def _generate_pdf_bytes(*, record: CertificateRecord, verify_url: str) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=CERT_PAGE_SIZE)
    page_w, page_h = CERT_PAGE_SIZE
    has_image_template = _has_image_template(record)

    if has_image_template:
        _draw_template_background(c, record)
        c.saveState()
        try:
            c.setFillAlpha(0.92)
        except Exception:
            pass
        c.setFillColor(colors.white)
        c.rect(0, 0, page_w, page_h, stroke=0, fill=1)
        c.restoreState()
    else:
        c.setFillColor(colors.white)
        c.rect(0, 0, page_w, page_h, stroke=0, fill=1)

    completion_date = _resolve_completion_date(record)
    completion_date_text = completion_date.strftime("%d.%m.%Y") if completion_date else "—"
    issue_date_text = record.issue_date.strftime("%d.%m.%Y")
    student_name = " ".join((record.student.get_full_name() or "").split())
    course_name = " ".join((record.group.nom or "").split())
    center_name = _short_text(record.center.name, max_len=70)

    margin = 6 * mm
    frame_x = margin
    frame_y = margin
    frame_w = page_w - (2 * margin)
    frame_h = page_h - (2 * margin)

    c.setStrokeColor(colors.HexColor("#D4E0F5"))
    c.setLineWidth(1)
    c.roundRect(frame_x, frame_y, frame_w, frame_h, 3.6 * mm, stroke=1, fill=0)

    panel_w = frame_w * 0.26
    panel_x = frame_x + frame_w - panel_w
    panel_y = frame_y
    panel_h = frame_h

    _draw_decorative_panel(c, x=panel_x, y=panel_y, width=panel_w, height=panel_h)

    left_x = frame_x
    left_y = frame_y
    left_w = panel_x - frame_x
    left_h = frame_h
    _draw_hex_pattern(
        c,
        x=left_x + 2.5 * mm,
        y=left_y + 2.5 * mm,
        width=left_w - 5 * mm,
        height=left_h - 5 * mm,
    )

    content_x = left_x + 10 * mm
    content_w = left_w - 20 * mm
    top_y = frame_y + frame_h - 11 * mm

    _draw_brand(c, x=content_x, y=top_y - 1.5 * mm, center_name=center_name)

    title = "SERTIFIKAT" if record.certificate_type == CertificateRecord.TYPE_CERTIFICATE else "DIPLOM"
    c.setFillColor(colors.HexColor("#2A9DF4"))
    c.setFont("Helvetica-Bold", 36)
    c.drawString(content_x, top_y - 24 * mm, title)

    c.setFillColor(colors.HexColor("#4B5563"))
    c.setFont("Helvetica", 11)
    c.drawString(content_x, top_y - 32.5 * mm, "Ushbu sertifikat quyidagi o'quvchiga berildi:")

    name_font, name_lines = _fit_text_lines(
        text=student_name,
        font_name="Helvetica-Bold",
        max_width=content_w,
        max_lines=3,
        max_font_size=28,
        min_font_size=16,
    )
    c.setFillColor(colors.HexColor("#1D7FE9"))
    c.setFont("Helvetica-Bold", name_font)
    y_name = top_y - 45 * mm
    name_step = name_font * 1.20
    for line in name_lines:
        c.drawString(content_x, y_name, line)
        y_name -= name_step

    course_font, course_lines = _fit_text_lines(
        text=f"{course_name} kursini muvaffaqiyatli tamomladi.",
        font_name="Helvetica",
        max_width=content_w,
        max_lines=3,
        max_font_size=15,
        min_font_size=11,
    )
    c.setFillColor(colors.HexColor("#374151"))
    c.setFont("Helvetica", course_font)
    y_course = y_name - 3 * mm
    course_step = course_font * 1.35
    for line in course_lines:
        c.drawString(content_x, y_course, line)
        y_course -= course_step

    c.setFont("Helvetica", 10.2)
    c.setFillColor(colors.HexColor("#4B5563"))
    c.drawString(content_x, y_course - 2.3 * mm, f"Kursni tugatgan sana: {completion_date_text}")
    c.drawString(content_x, y_course - 7.2 * mm, f"O'quv markazi: {center_name}")

    meta_y = frame_y + 10.5 * mm
    c.setFillColor(colors.HexColor("#5B6473"))
    c.setFont("Helvetica-Bold", 10.7)
    c.drawString(content_x, meta_y + 3.5 * mm, f"Berilgan sana: {issue_date_text}")

    _draw_center_seal(c, center_name=center_name, x=content_x + 101 * mm, y=meta_y + 10.0 * mm, radius=21.5 * mm)

    c.setFillColor(colors.white)
    panel_title_font, panel_title_lines = _fit_text_lines(
        text=center_name,
        font_name="Helvetica-Bold",
        max_width=panel_w - 14 * mm,
        max_lines=4,
        max_font_size=28,
        min_font_size=16,
    )
    c.setFont("Helvetica-Bold", panel_title_font)
    panel_title_y = panel_y + panel_h - 18 * mm
    panel_step = panel_title_font * 1.22
    panel_center_x = panel_x + panel_w / 2
    for line in panel_title_lines:
        c.drawCentredString(panel_center_x, panel_title_y, line)
        panel_title_y -= panel_step

    qr_card = 31 * mm
    qr_x = panel_x + panel_w - qr_card - 8 * mm
    qr_y = panel_y + 10 * mm
    c.setFillColor(colors.white)
    c.roundRect(qr_x, qr_y, qr_card, qr_card, 2.4 * mm, stroke=0, fill=1)

    qr_size = qr_card - 4 * mm
    _draw_qr(c, payload=verify_url, x=qr_x + 2 * mm, y=qr_y + 2 * mm, size=qr_size)

    c.saveState()
    c.setFillColor(colors.HexColor("#8EA7D4"))
    c.setFont("Helvetica", 6.3)
    c.drawRightString(page_w - 8.5 * mm, frame_y + 2.9 * mm, "chaqmoqapp.uz sayti tomonidan tayyorlandi")
    c.restoreState()

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
    completion_date = _resolve_completion_date(record)

    pdf_bytes = _generate_pdf_bytes(record=record, verify_url=verify_url)
    filename = f"{record.certificate_number}.pdf"
    record.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)

    record.metadata = {
        "verify_url": verify_url,
        "summary_id": summary.id if summary else None,
        "completion_date": completion_date.isoformat() if completion_date else None,
        "pdf_layout_version": PDF_LAYOUT_VERSION,
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
    completion_date = _resolve_completion_date(record)

    metadata = record.metadata if isinstance(record.metadata, dict) else {}
    metadata = dict(metadata)
    metadata["verify_url"] = verify_url
    metadata["pdf_layout_version"] = PDF_LAYOUT_VERSION
    metadata["completion_date"] = completion_date.isoformat() if completion_date else None

    record.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
    record.metadata = metadata
    record.save(update_fields=["pdf_file", "metadata", "updated_at"])
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
