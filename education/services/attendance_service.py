"""
education/services/attendance_service.py

Davomat (attendance) bilan bog'liq barcha biznes logika shu yerda.
Viewlar faqat HTTP request/response bilan shug'ullanadi,
biznes mantiq esa shu servisga delegatsiya qilinadi.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Literal

from django.db import transaction

logger = logging.getLogger(__name__)

AttendanceStatus = Literal["present", "absent", "absent_excused", "absent_unexcused", "none"]


def toggle_attendance(
    *,
    group,
    student,
    date_value: date,
    target_status: AttendanceStatus | None = None,
    current_status: AttendanceStatus = "none",
) -> AttendanceStatus:
    """
    Davomat yozuvini to'g'ridan-to'g'ri o'rnatish yoki siklik almashtirish.

    Parametrlar:
        group         - Guruh obyekti
        student       - Talaba (User) obyekti
        date_value    - Davomat sanasi
        target_status - Agar berilsa, to'g'ridan-to'g'ri o'rnatiladi (popover rejimi).
                        None bo'lsa, siklik almashtirish (none → present → absent → none)
        current_status- Hozirgi holat (siklik rejimda ishlatiladi)

    Qaytaradi:
        Yangi holat satri ('present', 'absent', 'absent_excused', 'none' va boshqalar)
    """
    from education.models import Attendance

    att = Attendance.objects.filter(
        group=group, student=student, date=date_value
    ).first()

    def _prepare_att() -> "Attendance":
        nonlocal att
        if not att:
            att = Attendance(group=group, student=student, date=date_value)
            if hasattr(att, "center"):
                att.center = group.center
        if not getattr(att, "teacher_id", None) and getattr(group, "oqituvchi_id", None):
            att.teacher = group.oqituvchi
        return att

    # --- To'g'ridan-to'g'ri o'rnatish rejimi (popover) ---
    if target_status is not None:
        if target_status == "none":
            if att:
                att.delete()
            return "none"

        att = _prepare_att()
        if target_status == "present":
            att.present = True
            att.forced = False
            if hasattr(att, "status"):
                att.status = "present"
            att.save()
            return "present"

        elif target_status == "absent":
            att.present = False
            att.forced = False
            if hasattr(att, "status"):
                att.status = "absent_unexcused"
            att.save()
            return "absent"

        elif target_status == "excused":
            att.present = False
            att.forced = False
            if hasattr(att, "status"):
                att.status = "absent_excused"
            att.save()
            return "absent_excused"

        # Noto'g'ri qiymat — o'zgartirmasdan qaytaramiz
        return current_status or "none"

    # --- Siklik almashtirish rejimi (orqaga mos kelish) ---
    if current_status == "none":
        att = _prepare_att()
        att.present = True
        att.forced = False
        att.save()
        return "present"

    elif current_status == "present":
        att = _prepare_att()
        att.present = False
        att.forced = False
        att.save()
        return "absent"

    elif current_status in ("absent", "forced"):
        if att:
            att.delete()
        return "none"

    return current_status or "none"


def mark_all_present(*, group, date_value: date) -> int:
    """
    Guruhning barcha faol talabalarini mavjud deb belgilaydi.

    Qaytaradi: yangilangan yozuvlar soni
    """
    from education.models import Attendance, Enrollment

    enrollments = Enrollment.objects.filter(
        group=group, is_active=True
    ).select_related("student")

    count = 0
    with transaction.atomic():
        for enr in enrollments:
            att, created = Attendance.objects.get_or_create(
                group=group,
                student=enr.student,
                date=date_value,
                defaults={
                    "present": True,
                    "forced": False,
                    "center": getattr(group, "center", None),
                    "teacher": getattr(group, "oqituvchi", None),
                },
            )
            if not created and not att.present:
                att.present = True
                att.forced = False
                att.save(update_fields=["present", "forced"])
            count += 1

    return count


def mark_all_absent(*, group, date_value: date) -> int:
    """
    Guruhning barcha faol talabalarini yo'q deb belgilaydi.

    Qaytaradi: o'chirilgan yozuvlar soni
    """
    deleted, _ = (
        __import__("education.models", fromlist=["Attendance"])
        .Attendance.objects.filter(group=group, date=date_value)
        .delete()
    )
    return deleted


def get_attendance_summary(*, group, month: date) -> dict:
    """
    Guruh uchun bir oylik davomat xulosasini qaytaradi.

    Qaytaradi:
        {
            "total_days": int,
            "present_count": int,
            "absent_count": int,
            "attendance_rate": float,  # 0.0–1.0
        }
    """
    from education.models import Attendance
    import calendar

    _, days_in_month = calendar.monthrange(month.year, month.month)
    atts = Attendance.objects.filter(
        group=group,
        date__year=month.year,
        date__month=month.month,
    )
    total = atts.count()
    present = atts.filter(present=True).count()
    absent = total - present
    rate = present / total if total > 0 else 0.0

    return {
        "total_days": days_in_month,
        "total_records": total,
        "present_count": present,
        "absent_count": absent,
        "attendance_rate": round(rate, 3),
    }
