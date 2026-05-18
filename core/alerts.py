from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from education.models import Attendance, Group, StudentGroupHistory

from core.dashboard_metrics import (
    active_groups_for_center,
    attendance_for_center,
    attendance_present_filter,
    get_center_capacity_alert_rows,
    get_center_debtors_count,
    get_center_zero_payment_count,
    month_start,
)


def get_director_alerts(center):
    """
    Direktorga ko'rsatilishi kerak bo'lgan ogohlantirishlar.
    Har bir alert: {'level': 'danger/warning/info', 'icon': '...', 'text': '...', 'url': '...'}
    """
    alerts = []
    today = timezone.localdate()
    current_month = month_start(today)
    previous_month = (current_month - timedelta(days=1)).replace(day=1)

    current_debtors = get_center_debtors_count(center, current_month)
    previous_debtors = get_center_debtors_count(center, previous_month)
    if previous_debtors > 0:
        growth_pct = round((current_debtors - previous_debtors) * 100 / previous_debtors, 1)
        if growth_pct > 20:
            alerts.append(
                {
                    "level": "danger",
                    "icon": "💸",
                    "text": f"Qarzdorlar soni o'tgan oyga nisbatan {growth_pct}% ga oshdi ({previous_debtors} → {current_debtors}).",
                    "url": reverse("core:billing_dashboard"),
                }
            )

    low_attendance_rows = (
        attendance_for_center(center)
        .filter(
            date__gte=today - timedelta(days=21),
            group__is_archived=False,
            group__is_deleted=False,
        )
        .values("group_id", "group__nom", "date")
        .annotate(
            total=Count("id"),
            present=Count("id", filter=attendance_present_filter()),
        )
        .order_by("group_id", "-date")
    )
    group_history = defaultdict(list)
    for row in low_attendance_rows:
        group_history[row["group_id"]].append(row)
    for rows in group_history.values():
        recent_rows = rows[:3]
        if len(recent_rows) < 3:
            continue
        if all((row["present"] * 100 / row["total"]) < 50 for row in recent_rows if row["total"]):
            group_name = recent_rows[0]["group__nom"] or "Guruh"
            alerts.append(
                {
                    "level": "warning",
                    "icon": "📉",
                    "text": f"{group_name} guruhida ketma-ket 3 darsda davomat 50% dan past bo'ldi.",
                    "url": reverse("core:groups_dashboard"),
                }
            )
            break

    no_payment_count = get_center_zero_payment_count(center, current_month)
    if no_payment_count > 10:
        alerts.append(
            {
                "level": "danger",
                "icon": "❗",
                "text": f"Bu oy hali hech to'lov qilmagan o'quvchilar soni {no_payment_count} taga yetdi.",
                "url": reverse("core:billing_dashboard"),
            }
        )

    recent_dates = [today - timedelta(days=offset) for offset in range(3)]
    teachers = User.objects.filter(center=center, role="teacher")
    teacher_groups = active_groups_for_center(center).values("oqituvchi_id").annotate(total=Count("id"))
    active_teacher_ids = {row["oqituvchi_id"] for row in teacher_groups if row["oqituvchi_id"]}
    silent_teachers = teachers.filter(id__in=active_teacher_ids).exclude(
        taken_attendances__group__center=center,
        taken_attendances__date__in=recent_dates,
    )
    teacher = silent_teachers.order_by("ism", "familya").first()
    if teacher:
        alerts.append(
            {
                "level": "warning",
                "icon": "📝",
                "text": f"{teacher.get_full_name()} oxirgi 3 kunda davomat kiritmagan bo'lishi mumkin.",
                "url": reverse("core:teacher_performance_dashboard"),
            }
        )

    capacity_rows = get_center_capacity_alert_rows(center)
    if capacity_rows:
        top_row = capacity_rows[0]
        alerts.append(
            {
                "level": "info",
                "icon": "👥",
                "text": f"{top_row['group'].nom} guruhi {top_row['fill_pct']:.0f}% to'lgan ({top_row['active_students']}/{top_row['capacity']}).",
                "url": reverse("core:groups_dashboard"),
            }
        )

    dropout_count = StudentGroupHistory.objects.filter(
        center=center,
        end_date__range=(current_month, today),
    ).count()
    if dropout_count >= 5:
        alerts.append(
            {
                "level": "warning",
                "icon": "🚪",
                "text": f"Joriy oyda {dropout_count} ta o'quvchi guruhlarni tark etdi.",
                "url": reverse("core:student_performance_dashboard"),
            }
        )

    level_order = {"danger": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda alert: level_order.get(alert["level"], 9))
    return alerts[:5]
