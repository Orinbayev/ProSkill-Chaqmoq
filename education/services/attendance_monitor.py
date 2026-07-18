"""Kunlik davomat nazorati — o'qituvchi davomat qilmagan guruhlarni aniqlaydi.

Manager va Director dashboardlari uchun: berilgan kunda jadval bo'yicha darsi
bo'lgan har bir guruh uchun o'qituvchi davomat qildimi yoki unutdimi, kim keldi
kim kelmadi (sababli/sababsiz) — hammasini bitta tuzilgan javobda beradi.

Weekday konvensiyasi: GroupSchedule.weekday = isoweekday (1=Dushanba .. 7=Yakshanba).
"""
from __future__ import annotations

from datetime import date as _date, time as _time

from django.db.models import Count, Q
from django.utils import timezone

# Dars boshlangandan keyin necha daqiqa o'tsa "davomat qilinmadi" deb belgilanadi.
GRACE_MINUTES = 60

STATUS_TAKEN = "taken"        # davomat qilingan
STATUS_MISSING = "missing"    # jadvalда dars bor, vaqt o'tdi, davomat YO'Q → unutgan
STATUS_PENDING = "pending"    # jadvalda dars bor, lekin hali vaqti kelmagan


def _minutes(t: _time) -> int:
    return t.hour * 60 + t.minute


def get_attendance_monitor(center, target_date: _date | None = None, *, now=None) -> dict:
    """Berilgan kun uchun kunlik davomat nazorati ma'lumotlari.

    Qaytaradi:
        {
          "date": iso,
          "summary": {scheduled, taken, missing, pending,
                      present, late, absent_excused, absent_unexcused},
          "rows": [ {group_id, group_name, teacher_name, start_time, end_time, room,
                     status, present, late, absent_excused, absent_unexcused,
                     total_marked, absentees:[{name, status, status_label}]} ]
        }
    """
    from education.models import Attendance, Group, GroupSchedule

    if target_date is None:
        target_date = timezone.localdate()
    if now is None:
        now = timezone.localtime()
    today = timezone.localdate()
    iso = target_date.isoweekday()

    groups = Group.objects.filter(center=center, is_archived=False, is_deleted=False)

    # Bugun jadval bo'yicha darsi bor guruhlar (guruhga eng erta dars vaqti).
    scheds = (
        GroupSchedule.objects.filter(group__in=groups, weekday=iso)
        .select_related("group", "group__oqituvchi")
        .order_by("group_id", "start_time")
    )
    # Har guruh uchun eng erta dars vaqtini olamiz (bir kunда bir necha slot bo'lishi mumkin).
    first_sched: dict[int, GroupSchedule] = {}
    for s in scheds:
        if s.group_id not in first_sched:
            first_sched[s.group_id] = s

    if not first_sched:
        return {
            "date": target_date.isoformat(),
            "summary": {k: 0 for k in (
                "scheduled", "taken", "missing", "pending",
                "present", "late", "absent_excused", "absent_unexcused")},
            "rows": [],
        }

    group_ids = list(first_sched.keys())

    # Har guruh uchun shu kundagi davomat status-hisobi (bitta so'rovda).
    att_counts = {
        row["group_id"]: row
        for row in Attendance.objects.filter(group_id__in=group_ids, date=target_date)
        .values("group_id")
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status="present")),
            late=Count("id", filter=Q(status="late")),
            absent_excused=Count("id", filter=Q(status="absent_excused")),
            absent_unexcused=Count("id", filter=Q(status="absent_unexcused")),
        )
    }

    # Kelmaganlar (sababli/sababsiz) ro'yxati — interfeysда sabab bilan ko'rsatish uchun.
    absentees_by_group: dict[int, list] = {gid: [] for gid in group_ids}
    status_labels = dict(Attendance.STATUS_CHOICES)
    absent_qs = (
        Attendance.objects.filter(
            group_id__in=group_ids, date=target_date,
            status__in=("absent_excused", "absent_unexcused", "late"),
        )
        .select_related("student")
        .order_by("group_id", "status")
    )
    for a in absent_qs:
        stu = a.student
        name = " ".join(filter(None, [getattr(stu, "ism", ""), getattr(stu, "familya", "")])).strip() \
            or getattr(stu, "email", "—")
        absentees_by_group[a.group_id].append({
            "name": name,
            "status": a.status,
            "status_label": status_labels.get(a.status, a.status),
        })

    now_minutes = _minutes(now.time())
    rows = []
    summary = {k: 0 for k in (
        "scheduled", "taken", "missing", "pending",
        "present", "late", "absent_excused", "absent_unexcused")}

    for gid in group_ids:
        s = first_sched[gid]
        g = s.group
        teacher = g.oqituvchi
        teacher_name = "—"
        if teacher:
            teacher_name = " ".join(filter(None, [getattr(teacher, "ism", ""), getattr(teacher, "familya", "")])).strip() \
                or getattr(teacher, "email", "—")
        counts = att_counts.get(gid)
        summary["scheduled"] += 1

        if counts and counts["total"] > 0:
            status = STATUS_TAKEN
            summary["taken"] += 1
            for key in ("present", "late", "absent_excused", "absent_unexcused"):
                summary[key] += counts[key]
        else:
            # Davomat yo'q — vaqti o'tganmi?
            due_minutes = _minutes(s.start_time) + GRACE_MINUTES
            overdue = target_date < today or (target_date == today and now_minutes >= due_minutes)
            status = STATUS_MISSING if overdue else STATUS_PENDING
            summary[status] += 1
            counts = {"total": 0, "present": 0, "late": 0, "absent_excused": 0, "absent_unexcused": 0}

        rows.append({
            "group_id": gid,
            "group_name": g.nom,
            "teacher_name": teacher_name,
            "start_time": s.start_time.strftime("%H:%M") if s.start_time else "",
            "end_time": s.end_time.strftime("%H:%M") if s.end_time else "",
            "room": s.room or "",
            "status": status,
            "present": counts["present"],
            "late": counts["late"],
            "absent_excused": counts["absent_excused"],
            "absent_unexcused": counts["absent_unexcused"],
            "total_marked": counts["total"],
            "absentees": absentees_by_group.get(gid, []),
        })

    # Tartib: avval "unutilgan" (missing), keyin pending, keyin taken.
    order = {STATUS_MISSING: 0, STATUS_PENDING: 1, STATUS_TAKEN: 2}
    rows.sort(key=lambda r: (order.get(r["status"], 9), r["start_time"]))

    return {"date": target_date.isoformat(), "summary": summary, "rows": rows}
