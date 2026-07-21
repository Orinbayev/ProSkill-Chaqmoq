from __future__ import annotations

import logging
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
    ExamResult,
    StudentAcademicSummary,
)
from education.services.audit_service import log_education_event
from education.services.ranking_service import build_group_completion_recommendations

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
PDF_LAYOUT_VERSION = 11
CERT_PAGE_WIDTH = 297 * mm
CERT_PAGE_HEIGHT = CERT_PAGE_WIDTH * 9 / 16
CERT_PAGE_SIZE = (CERT_PAGE_WIDTH, CERT_PAGE_HEIGHT)
# Gold brand mark (cream/gold certificate palette bilan mos)
CERT_LOGO_PATH = Path(settings.BASE_DIR) / "static" / "img" / "chaqmoq_logo_transparent.png"
CERT_LOGO_FALLBACK = Path(settings.BASE_DIR) / "static" / "img" / "chaqmoq_blue_logo_v2.png"
logger = logging.getLogger(__name__)

# Premium palette — navy + gold academy style
C_NAVY = "#0B1F3A"
C_NAVY_MID = "#163A66"
C_GOLD = "#C9A227"
C_GOLD_LIGHT = "#E8D48B"
C_GOLD_DEEP = "#9A7B1A"
C_CREAM = "#FFFCF5"
C_CREAM_SOFT = "#F7F1E3"
C_INK = "#1A2332"
C_MUTED = "#5C6570"
C_LINE = "#D9C78A"
C_WHITE = "#FFFFFF"


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
    fill_color=None,
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

    if fill_color is not None:
        c.setFillColor(fill_color)
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


def _draw_corner_ornament(c: canvas.Canvas, *, x: float, y: float, size: float, rotate_deg: float = 0):
    """Classic L-shaped gold corner flourish."""
    c.saveState()
    c.translate(x, y)
    c.rotate(rotate_deg)
    gold = colors.HexColor(C_GOLD)
    gold_deep = colors.HexColor(C_GOLD_DEEP)
    c.setStrokeColor(gold)
    c.setFillColor(gold)
    c.setLineWidth(1.6)
    c.setLineCap(1)
    # Outer L
    path = c.beginPath()
    path.moveTo(0, size)
    path.lineTo(0, 0)
    path.lineTo(size, 0)
    c.drawPath(path, stroke=1, fill=0)
    # Inner L
    inset = 2.2 * mm
    c.setLineWidth(0.9)
    c.setStrokeColor(gold_deep)
    path2 = c.beginPath()
    path2.moveTo(inset, size - 1.5 * mm)
    path2.lineTo(inset, inset)
    path2.lineTo(size - 1.5 * mm, inset)
    c.drawPath(path2, stroke=1, fill=0)
    # Diamond accent at corner
    d = 1.3 * mm
    c.setFillColor(gold)
    diamond = c.beginPath()
    diamond.moveTo(inset, inset + d)
    diamond.lineTo(inset + d, inset)
    diamond.lineTo(inset, inset - d)
    diamond.lineTo(inset - d, inset)
    diamond.close()
    c.drawPath(diamond, stroke=0, fill=1)
    c.restoreState()


def _draw_gold_divider(c: canvas.Canvas, *, cx: float, y: float, half_width: float):
    """Horizontal gold rule with center diamond."""
    c.saveState()
    gold = colors.HexColor(C_GOLD)
    c.setStrokeColor(gold)
    c.setFillColor(gold)
    c.setLineWidth(1.0)
    c.line(cx - half_width, y, cx - 3.2 * mm, y)
    c.line(cx + 3.2 * mm, y, cx + half_width, y)
    # diamond
    d = 1.8 * mm
    path = c.beginPath()
    path.moveTo(cx, y + d)
    path.lineTo(cx + d, y)
    path.lineTo(cx, y - d)
    path.lineTo(cx - d, y)
    path.close()
    c.drawPath(path, stroke=0, fill=1)
    # tiny outer ring
    c.setLineWidth(0.7)
    c.circle(cx, y, 2.6 * mm, stroke=1, fill=0)
    c.restoreState()


def _draw_premium_seal(c: canvas.Canvas, *, center_name: str, x: float, y: float, radius: float):
    """Gold official seal — clean center monogram + top ring label only."""
    c.saveState()
    gold = colors.HexColor(C_GOLD)
    navy = colors.HexColor(C_NAVY)
    cream = colors.HexColor(C_CREAM)

    # Soft glow
    c.setFillColor(colors.Color(0.79, 0.64, 0.15, alpha=0.12))
    c.circle(x, y, radius + 1.8 * mm, stroke=0, fill=1)

    # Outer gold disc + cream face
    c.setFillColor(gold)
    c.circle(x, y, radius, stroke=0, fill=1)
    c.setFillColor(cream)
    c.circle(x, y, radius - 1.5 * mm, stroke=0, fill=1)

    # Rings
    c.setStrokeColor(gold)
    c.setLineWidth(1.15)
    c.circle(x, y, radius - 1.5 * mm, stroke=1, fill=0)
    c.setLineWidth(0.75)
    c.circle(x, y, radius - 3.2 * mm, stroke=1, fill=0)
    c.circle(x, y, radius - 8.2 * mm, stroke=1, fill=0)

    # Decorative beads on outer gold band
    c.setFillColor(gold)
    for deg in range(0, 360, 30):
        ang = math.radians(deg)
        sx = x + (radius - 0.75 * mm) * math.cos(ang)
        sy = y + (radius - 0.75 * mm) * math.sin(ang)
        c.circle(sx, sy, 0.45 * mm, stroke=0, fill=1)

    # Top arc label (angles decrease: left → right across the top)
    _draw_circular_text(
        c,
        text="RASMIY MUHR",
        x=x,
        y=y,
        radius=radius - 4.4 * mm,
        start_angle=155,
        end_angle=25,
        font_name="Helvetica-Bold",
        font_size=5.8,
        fill_color=colors.HexColor(C_GOLD_DEEP),
    )

    # Center: short center name + CERT
    c.setFillColor(navy)
    short = _short_text(center_name, 22)
    max_inner = (radius - 9.0 * mm) * 2
    lines = simpleSplit(short, "Helvetica-Bold", 7.0, max_inner)[:2] or [short]
    step = 3.4 * mm
    block_h = (len(lines) - 1) * step
    start_y = y + block_h / 2 + 1.2 * mm
    for idx, line in enumerate(lines):
        c.setFont("Helvetica-Bold", 7.0)
        c.drawCentredString(x, start_y - idx * step, line)
    c.setFont("Helvetica", 5.4)
    c.setFillColor(colors.HexColor(C_GOLD_DEEP))
    c.drawCentredString(x, y - block_h / 2 - 3.6 * mm, "SERTIFIKAT")
    c.restoreState()


def _load_cert_logo_reader():
    """
    Logo PNG (ko'pincha qora fon) → shaffof fon + ImageReader.
    Certificate cream fonida chiroyli ko'rinishi uchun.
    """
    path = CERT_LOGO_PATH if CERT_LOGO_PATH.exists() else CERT_LOGO_FALLBACK
    if not path.exists():
        return None
    try:
        from PIL import Image

        img = Image.open(path).convert("RGBA")
        pixels = img.load()
        w, h = img.size
        for py in range(h):
            for px in range(w):
                r, g, b, a = pixels[px, py]
                # Qora / deyarli qora fonni olib tashlash
                if r < 28 and g < 28 and b < 28:
                    pixels[px, py] = (0, 0, 0, 0)
                # Juda qorong'i pixel — yumshoq alpha
                elif r < 45 and g < 45 and b < 45 and a > 0:
                    pixels[px, py] = (r, g, b, max(0, a // 3))

        # Contented bounding box
        bbox = img.getbbox()
        if bbox:
            # Biroz padding
            pad = 8
            l, t, r, b = bbox
            l = max(0, l - pad)
            t = max(0, t - pad)
            r = min(w, r + pad)
            b = min(h, b + pad)
            img = img.crop((l, t, r, b))

        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return ImageReader(buf)
    except Exception:
        try:
            return ImageReader(str(path))
        except Exception:
            return None


def _draw_logo_badge(c: canvas.Canvas, *, cx: float, y: float, size: float = 18 * mm):
    """Premium gold-ring badge with ChaqmoqApp mark."""
    logo_reader = _load_cert_logo_reader()
    cy = y + size / 2
    outer_r = size / 2 + 3.2 * mm

    c.saveState()
    # Soft gold glow rings
    c.setFillColor(colors.Color(0.79, 0.64, 0.15, alpha=0.10))
    c.circle(cx, cy, outer_r + 2.5 * mm, stroke=0, fill=1)
    c.setFillColor(colors.Color(0.79, 0.64, 0.15, alpha=0.16))
    c.circle(cx, cy, outer_r + 0.8 * mm, stroke=0, fill=1)

    # White/cream disc
    c.setFillColor(colors.HexColor(C_CREAM))
    c.circle(cx, cy, outer_r, stroke=0, fill=1)

    # Gold double ring
    c.setStrokeColor(colors.HexColor(C_GOLD))
    c.setLineWidth(1.6)
    c.circle(cx, cy, outer_r, stroke=1, fill=0)
    c.setLineWidth(0.7)
    c.setStrokeColor(colors.HexColor(C_GOLD_DEEP))
    c.circle(cx, cy, outer_r - 1.6 * mm, stroke=1, fill=0)

    # Decorative beads
    c.setFillColor(colors.HexColor(C_GOLD))
    for deg in (20, 70, 110, 160, 200, 250, 290, 340):
        ang = math.radians(deg)
        bx = cx + (outer_r - 0.15 * mm) * math.cos(ang)
        by = cy + (outer_r - 0.15 * mm) * math.sin(ang)
        c.circle(bx, by, 0.55 * mm, stroke=0, fill=1)

    if logo_reader is not None:
        # Logo slightly inset inside the ring
        logo_box = size * 0.92
        c.drawImage(
            logo_reader,
            cx - logo_box / 2,
            cy - logo_box / 2,
            width=logo_box,
            height=logo_box,
            preserveAspectRatio=True,
            mask="auto",
        )
    else:
        # Fallback monogram
        c.setFillColor(colors.HexColor(C_NAVY))
        c.setFont("Times-Bold", 11)
        c.drawCentredString(cx, cy - 1.5 * mm, "C")
    c.restoreState()


def _draw_certificate_frame(c: canvas.Canvas, *, page_w: float, page_h: float):
    """Cream background, navy outer + gold double border, corner ornaments."""
    # Base cream
    c.setFillColor(colors.HexColor(C_CREAM))
    c.rect(0, 0, page_w, page_h, stroke=0, fill=1)

    # Soft vertical wash
    _draw_vertical_gradient(
        c,
        x=0,
        y=0,
        width=page_w,
        height=page_h,
        top_hex=C_CREAM,
        bottom_hex=C_CREAM_SOFT,
        steps=80,
    )

    # Outer navy frame
    m1 = 4.5 * mm
    c.setStrokeColor(colors.HexColor(C_NAVY))
    c.setLineWidth(2.4)
    c.rect(m1, m1, page_w - 2 * m1, page_h - 2 * m1, stroke=1, fill=0)

    # Gold middle frame
    m2 = 6.2 * mm
    c.setStrokeColor(colors.HexColor(C_GOLD))
    c.setLineWidth(1.5)
    c.rect(m2, m2, page_w - 2 * m2, page_h - 2 * m2, stroke=1, fill=0)

    # Inner thin navy
    m3 = 7.6 * mm
    c.setStrokeColor(colors.HexColor(C_NAVY_MID))
    c.setLineWidth(0.6)
    c.rect(m3, m3, page_w - 2 * m3, page_h - 2 * m3, stroke=1, fill=0)

    # Corner ornaments
    corner = 14 * mm
    inset = 9.2 * mm
    _draw_corner_ornament(c, x=inset, y=inset, size=corner, rotate_deg=0)  # BL
    _draw_corner_ornament(c, x=page_w - inset, y=inset, size=corner, rotate_deg=90)  # BR
    _draw_corner_ornament(c, x=page_w - inset, y=page_h - inset, size=corner, rotate_deg=180)  # TR
    _draw_corner_ornament(c, x=inset, y=page_h - inset, size=corner, rotate_deg=270)  # TL

    # Faint watermark circle
    c.saveState()
    c.setStrokeColor(colors.Color(0.79, 0.64, 0.15, alpha=0.07))
    c.setLineWidth(8)
    c.circle(page_w / 2, page_h / 2, 48 * mm, stroke=1, fill=0)
    c.setLineWidth(1.2)
    c.circle(page_w / 2, page_h / 2, 42 * mm, stroke=1, fill=0)
    c.restoreState()


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
    """
    Premium academy-style landscape certificate:
    cream canvas, navy + gold double frame, centered typography,
    gold seal, QR verification, certificate number.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=CERT_PAGE_SIZE)
    page_w, page_h = CERT_PAGE_SIZE
    cx = page_w / 2

    has_image_template = _has_image_template(record)
    if has_image_template:
        # Custom background image, then light cream veil so text stays readable
        _draw_template_background(c, record)
        c.saveState()
        try:
            c.setFillAlpha(0.88)
        except Exception:
            pass
        c.setFillColor(colors.HexColor(C_CREAM))
        c.rect(0, 0, page_w, page_h, stroke=0, fill=1)
        c.restoreState()
        # Still draw elegant borders on top of custom template
        m1, m2, m3 = 4.5 * mm, 6.2 * mm, 7.6 * mm
        c.setStrokeColor(colors.HexColor(C_NAVY))
        c.setLineWidth(2.4)
        c.rect(m1, m1, page_w - 2 * m1, page_h - 2 * m1, stroke=1, fill=0)
        c.setStrokeColor(colors.HexColor(C_GOLD))
        c.setLineWidth(1.5)
        c.rect(m2, m2, page_w - 2 * m2, page_h - 2 * m2, stroke=1, fill=0)
        c.setStrokeColor(colors.HexColor(C_NAVY_MID))
        c.setLineWidth(0.6)
        c.rect(m3, m3, page_w - 2 * m3, page_h - 2 * m3, stroke=1, fill=0)
        corner = 14 * mm
        inset = 9.2 * mm
        _draw_corner_ornament(c, x=inset, y=inset, size=corner, rotate_deg=0)
        _draw_corner_ornament(c, x=page_w - inset, y=inset, size=corner, rotate_deg=90)
        _draw_corner_ornament(c, x=page_w - inset, y=page_h - inset, size=corner, rotate_deg=180)
        _draw_corner_ornament(c, x=inset, y=page_h - inset, size=corner, rotate_deg=270)
    else:
        _draw_certificate_frame(c, page_w=page_w, page_h=page_h)

    completion_date = _resolve_completion_date(record)
    completion_date_text = completion_date.strftime("%d.%m.%Y") if completion_date else "—"
    issue_date_text = record.issue_date.strftime("%d.%m.%Y") if record.issue_date else "—"
    student_name = " ".join((record.student.get_full_name() or "O'quvchi").split())
    course_name = " ".join((record.group.nom or "Kurs").split())
    center_name = _short_text(record.center.name, max_len=60)
    cert_no = record.certificate_number or ""
    is_diploma = record.certificate_type == CertificateRecord.TYPE_DIPLOMA
    title = "DIPLOM" if is_diploma else "SERTIFIKAT"
    subtitle = "Certificate of Achievement" if not is_diploma else "Diploma of Completion"

    content_max_w = page_w - 52 * mm
    footer_top = 52 * mm  # everything below is seal zone

    # ── Header: logo → center name (gap) → kicker → divider → title ──
    # Sequential Y so long names never collide with the logo badge.
    # _draw_logo_badge: outer_r = size/2 + 3.2mm, glow +2.5mm → ring past box bottom ~5.7mm
    logo_size = 14 * mm
    logo_top = page_h - 11 * mm
    logo_bottom_y = logo_top - logo_size
    _draw_logo_badge(c, cx=cx, y=logo_bottom_y, size=logo_size)

    # Clear gap under badge (ring + glow + font ascent). Must stay clear of icon.
    y_cursor = logo_bottom_y - 12.5 * mm

    # Center name: up to 2 lines, auto-shrink so it never runs into the icon
    center_display = (center_name or "").upper()
    center_font, center_lines = _fit_text_lines(
        text=center_display,
        font_name="Times-Bold",
        max_width=content_max_w * 0.90,
        max_lines=2,
        max_font_size=11,
        min_font_size=8,
    )
    c.setFillColor(colors.HexColor(C_NAVY))
    c.setFont("Times-Bold", center_font)
    center_step = center_font * 1.22
    for line in center_lines:
        c.drawCentredString(cx, y_cursor, line)
        y_cursor -= center_step

    y_cursor -= 2.8 * mm
    c.setFillColor(colors.HexColor(C_GOLD_DEEP))
    c.setFont("Helvetica", 7.2)
    c.drawCentredString(cx, y_cursor, "O'QUV MARKAZI  •  RASMIY HUJJAT")

    y_cursor -= 4.2 * mm
    _draw_gold_divider(c, cx=cx, y=y_cursor, half_width=50 * mm)

    y_cursor -= 9.5 * mm
    c.setFillColor(colors.HexColor(C_NAVY))
    c.setFont("Times-Bold", 30)
    c.drawCentredString(cx, y_cursor, title)

    y_cursor -= 6.2 * mm
    c.setFillColor(colors.HexColor(C_GOLD))
    c.setFont("Helvetica-Oblique", 9.5)
    c.drawCentredString(cx, y_cursor, subtitle)

    y_cursor -= 7.5 * mm
    c.setFillColor(colors.HexColor(C_MUTED))
    c.setFont("Times-Italic", 10)
    c.drawCentredString(
        cx,
        y_cursor,
        "Ushbu hujjat quyidagi o'quvchiga muvaffaqiyatli o'qishni yakunlagani uchun beriladi:",
    )

    # ── Student name (middle band, below intro) ──
    name_font, name_lines = _fit_text_lines(
        text=student_name,
        font_name="Times-Bold",
        max_width=content_max_w,
        max_lines=2,
        max_font_size=30,
        min_font_size=15,
    )
    name_step = name_font * 1.12
    name_block_h = max(len(name_lines) - 1, 0) * name_step
    mid_band_top = y_cursor - 6 * mm
    mid_band_bottom = footer_top + 8 * mm
    mid_center = (mid_band_top + mid_band_bottom) / 2 + 4 * mm

    c.setFillColor(colors.HexColor(C_NAVY))
    c.setFont("Times-Bold", name_font)
    y_name = mid_center + name_block_h / 2 + 6 * mm
    for line in name_lines:
        c.drawCentredString(cx, y_name, line)
        y_name -= name_step

    name_width = max((stringWidth(line, "Times-Bold", name_font) for line in name_lines), default=80 * mm)
    underline_half = min(max(name_width / 2 + 6 * mm, 38 * mm), 95 * mm)
    _draw_gold_divider(c, cx=cx, y=y_name - 1.2 * mm, half_width=underline_half)

    # ── Course line ──
    course_text = f'"{course_name}" kursini muvaffaqiyatli tamomladi.'
    course_font, course_lines = _fit_text_lines(
        text=course_text,
        font_name="Times-Roman",
        max_width=content_max_w,
        max_lines=2,
        max_font_size=14,
        min_font_size=11,
    )
    c.setFillColor(colors.HexColor(C_INK))
    c.setFont("Times-Roman", course_font)
    y_course = y_name - 8 * mm
    course_step = course_font * 1.32
    for line in course_lines:
        c.drawCentredString(cx, y_course, line)
        y_course -= course_step

    # Meta — always above footer band
    chip_y = min(y_course - 5 * mm, footer_top + 2 * mm)
    chip_y = max(chip_y, footer_top + 1 * mm)
    c.setFillColor(colors.HexColor(C_MUTED))
    c.setFont("Helvetica", 8.8)
    meta_line = f"Kurs tugagan sana: {completion_date_text}   ·   Berilgan sana: {issue_date_text}"
    c.drawCentredString(cx, chip_y, meta_line)

    # ── Bottom zone: date | seal | QR (fixed, no overlap) ──
    col_left = page_w * 0.20
    col_mid = cx
    col_right = page_w * 0.80
    seal_cy = 28 * mm
    seal_r = 16 * mm

    # Left: date / signature
    c.setStrokeColor(colors.HexColor(C_LINE))
    c.setLineWidth(0.85)
    c.line(col_left - 24 * mm, seal_cy + 6 * mm, col_left + 24 * mm, seal_cy + 6 * mm)
    c.setFillColor(colors.HexColor(C_NAVY))
    c.setFont("Helvetica-Bold", 9.5)
    c.drawCentredString(col_left, seal_cy - 1 * mm, issue_date_text)
    c.setFillColor(colors.HexColor(C_MUTED))
    c.setFont("Helvetica", 7.4)
    c.drawCentredString(col_left, seal_cy - 5.5 * mm, "Berilgan sana")
    c.setFont("Helvetica", 6.8)
    c.drawCentredString(col_left, seal_cy - 10 * mm, _short_text(center_name, 30))

    # Center seal
    _draw_premium_seal(c, center_name=center_name, x=col_mid, y=seal_cy, radius=seal_r)

    # Right: QR
    qr_card = 26 * mm
    qr_x = col_right - qr_card / 2
    qr_y = seal_cy - qr_card / 2 + 1 * mm
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor(C_GOLD))
    c.setLineWidth(1.05)
    c.roundRect(qr_x - 2.2 * mm, qr_y - 3 * mm, qr_card + 4.4 * mm, qr_card + 9 * mm, 2.0 * mm, stroke=1, fill=1)
    _draw_qr(c, payload=verify_url or cert_no, x=qr_x, y=qr_y, size=qr_card)
    c.setFillColor(colors.HexColor(C_NAVY))
    c.setFont("Helvetica-Bold", 6.4)
    c.drawCentredString(col_right, qr_y - 1.8 * mm, "TEKSHIRISH")

    # ── Footer: tekshirish kodi (unique ID) — "№" o'rniga ASCII (font black-box bo'lmasin)
    c.setFillColor(colors.HexColor(C_MUTED))
    c.setFont("Helvetica", 6.5)
    c.drawString(14 * mm, 9.2 * mm, "Tekshirish kodi:")
    c.setFillColor(colors.HexColor(C_NAVY))
    c.setFont("Helvetica-Bold", 7.0)
    c.drawString(14 * mm, 5.8 * mm, cert_no)
    c.setFillColor(colors.HexColor(C_MUTED))
    c.setFont("Helvetica", 6.5)
    c.drawRightString(page_w - 14 * mm, 7.5 * mm, "chaqmoqapp.uz  •  Powered by ChaqmoqApp")

    c.setFillColor(colors.HexColor(C_GOLD))
    c.rect(0, 0, page_w, 1.15 * mm, stroke=0, fill=1)
    c.setFillColor(colors.HexColor(C_NAVY))
    c.rect(0, page_h - 1.15 * mm, page_w, 1.15 * mm, stroke=0, fill=1)

    c.showPage()
    c.save()
    return buffer.getvalue()


def _finalize_certificate_record(*, record: CertificateRecord, actor, note: str = "", request=None):
    summary = record.summary or get_or_build_summary(group=record.group, student=record.student, actor=actor)
    template = record.template or get_active_template(center=record.center, certificate_type=record.certificate_type)

    recommendation_status = (
        summary.completion_recommendation if summary else StudentAcademicSummary.RECOMMENDATION_NEEDS_REVIEW
    )
    recommendation_reason = summary.recommendation_reason if summary else "Yakuniy summary topilmadi"

    record.summary = summary
    record.template = template
    record.issue_date = timezone.localdate()
    record.status = CertificateRecord.STATUS_ISSUED
    record.recommendation_status = recommendation_status
    record.recommendation_reason = recommendation_reason
    record.approved_by = actor
    record.approved_at = timezone.now()
    record.issued_by = actor
    record.issued_at = timezone.now()
    if note:
        record.note = note
    record.save(
        update_fields=[
            "summary",
            "template",
            "issue_date",
            "status",
            "recommendation_status",
            "recommendation_reason",
            "approved_by",
            "approved_at",
            "issued_by",
            "issued_at",
            "note",
            "updated_at",
        ]
    )

    if not record.certificate_number.startswith("CHQ-"):
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
        center=record.group.center,
        actor=actor,
        action_type="certificate_approved",
        entity=record,
        payload={
            "group_id": record.group.id,
            "student_id": record.student.id,
            "recommendation_status": recommendation_status,
        },
    )
    log_education_event(
        center=record.group.center,
        actor=actor,
        action_type="certificate_generated",
        entity=record,
        payload={
            "certificate_number": record.certificate_number,
            "certificate_type": record.certificate_type,
        },
    )
    return record


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

    draft = (
        CertificateRecord.objects.filter(
            group=group,
            student=student,
            certificate_type=certificate_type,
            status=CertificateRecord.STATUS_DRAFT,
        )
        .order_by("-id")
        .first()
    )
    if draft:
        return _finalize_certificate_record(record=draft, actor=actor, note=note, request=request)

    record = CertificateRecord.objects.create(
        center=group.center,
        group=group,
        student=student,
        certificate_type=certificate_type,
        certificate_number=f"TMP-{uuid4().hex[:10]}",
        issue_date=timezone.localdate(),
        status=CertificateRecord.STATUS_DRAFT,
        note=note or "",
    )
    return _finalize_certificate_record(record=record, actor=actor, note=note, request=request)


def auto_check_certificate_eligibility(session):
    """
    Sessiya yakunlangach o'tgan o'quvchilar uchun qoralama sertifikat tayyorlaydi.
    """
    try:
        from accounts.models import User
        from core.models import Notification

        center = session.center
        active_template = get_active_template(
            center=center,
            certificate_type=CertificateRecord.TYPE_CERTIFICATE,
        ) or CertificateTemplate.objects.filter(center=center, is_active=True).order_by("-updated_at", "-id").first()
        if not active_template:
            return 0

        passed_results = (
            ExamResult.objects.filter(
                session=session,
                passed=True,
                absent_in_exam=False,
            )
            .select_related("student")
            .order_by("student_id")
        )

        created_count = 0
        for result in passed_results:
            already_exists = CertificateRecord.objects.filter(
                center=center,
                student=result.student,
                group=session.group,
                status__in=[CertificateRecord.STATUS_DRAFT, CertificateRecord.STATUS_ISSUED],
            ).exists()
            if already_exists:
                continue

            summary = get_or_build_summary(group=session.group, student=result.student, actor=session.teacher)
            recommendation_status = (
                summary.completion_recommendation if summary else StudentAcademicSummary.RECOMMENDATION_NEEDS_REVIEW
            )
            recommendation_reason = summary.recommendation_reason if summary else "Yakuniy summary topilmadi"

            CertificateRecord.objects.create(
                center=center,
                student=result.student,
                group=session.group,
                template=active_template,
                summary=summary,
                certificate_type=active_template.template_type,
                certificate_number=f"CERT-{center.pk}-{uuid4().hex[:8].upper()}",
                issue_date=timezone.localdate(),
                status=CertificateRecord.STATUS_DRAFT,
                recommendation_status=recommendation_status,
                recommendation_reason=recommendation_reason,
                issued_by=session.teacher,
                note="Imtihon yakunlangach avtomatik qoralama yaratildi.",
            )
            created_count += 1

        if created_count > 0:
            candidates_url = reverse(
                "education:group_certificate_candidates",
                kwargs={"group_id": session.group.pk},
            )
            managers = User.objects.filter(
                center=center,
                role__in=["manager", "director"],
                is_archived=False,
            )
            for manager in managers:
                Notification.objects.create(
                    center=center,
                    recipient=manager,
                    title="Sertifikatlar tayyor",
                    message=(
                        f"{session.group.nom}: {created_count} ta o'quvchi uchun qoralama sertifikat tayyorlandi. "
                        f"Tasdiqlash sahifasi: {candidates_url}"
                    ),
                    type="system",
                )

        return created_count
    except Exception:
        logger.exception(
            "auto_check_certificate_eligibility failed: session_id=%s",
            getattr(session, "id", None),
        )
        return 0


def regenerate_certificate_pdf(*, record: CertificateRecord, request=None):
    path = _verification_path(record)
    metadata = record.metadata if isinstance(record.metadata, dict) else {}
    metadata = dict(metadata)

    # Request bo'lmasa — avvalgi absolute verify_url ni saqlaymiz (QR ishlashi uchun)
    if request is not None:
        verify_url = _abs_uri(request, path)
    else:
        prev = str(metadata.get("verify_url") or "").strip()
        if prev.startswith("http://") or prev.startswith("https://"):
            verify_url = prev
        else:
            from django.conf import settings as dj_settings

            base = (
                getattr(dj_settings, "PUBLIC_BASE_URL", None)
                or getattr(dj_settings, "SITE_URL", None)
                or ""
            ).rstrip("/")
            verify_url = f"{base}{path}" if base else path

    pdf_bytes = _generate_pdf_bytes(record=record, verify_url=verify_url)
    filename = f"{record.certificate_number}.pdf"
    completion_date = _resolve_completion_date(record)

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
