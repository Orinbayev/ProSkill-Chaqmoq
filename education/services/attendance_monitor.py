"""Kunlik davomat nazorati — o'qituvchi davomat qilmagan guruhlarni aniqlaydi.

Manager va Director dashboardlari uchun: berilgan kunda darsi bo'lgan har bir
guruh uchun o'qituvchi davomat qildimi yoki unutdimi, kim keldi kim kelmadi
(sababli/sababsiz) — hammasini bitta tuzilgan javobda beradi.

Dars kunlari qanday aniqlanadi:
  1) GroupSchedule bo'lsa → aniq weekday + start_time (eng ishonchli).
  2) GroupSchedule bo'lmasa → enrollment naqshi (toq/juft/kunlik) dan olinadi.
  3) Naqsh "group" (Avtomatik) + jadval yo'q → dars kuni aniqlanmaydi →
     "jadval belgilanmagan" ro'yxatiga tushadi (manager jadval sozlashi kerak).

Weekday konvensiyasi: isoweekday (1=Dushanba .. 7=Yakshanba).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date as _date, time as _time

from django.db.models import Count, Q
from django.utils import timezone

# Dars boshlangandan keyin necha daqiqa o'tsa "davomat qilinmadi" deb belgilanadi.
GRACE_MINUTES = 60
# Jadvalsiz (vaqti noma'lum, naqsh bo'yicha) guruhlar uchun: shu vaqtdan keyin
# davomat yo'q bo'lsa "unutilgan" deb belgilanadi.
DEFAULT_CUTOFF = _time(21, 0)

# Naqsh → hafta kunlari (isoweekday).
PATTERN_WEEKDAYS = {
    "odd": {1, 3, 5},               # Toq: Du/Chor/Juma
    "even": {2, 4, 6},              # Juft: Se/Pay/Shan
    "daily": {1, 2, 3, 4, 5, 6},    # Har kuni (Du-Shan)
}

STATUS_TAKEN = "taken"
STATUS_MISSING = "missing"
STATUS_PENDING = "pending"


def _minutes(t: _time) -> int:
    return t.hour * 60 + t.minute


def _person_name(u) -> str:
    if not u:
        return "—"
    name = " ".join(filter(None, [getattr(u, "ism", ""), getattr(u, "familya", "")])).strip()
    return name or getattr(u, "email", "—")


def get_attendance_monitor(center, target_date: _date | None = None, *, now=None) -> dict:
    """Berilgan kun uchun kunlik davomat nazorati ma'lumotlari."""
    from education.models import Attendance, Enrollment, Group, GroupSchedule

    if target_date is None:
        target_date = timezone.localdate()
    if now is None:
        now = timezone.localtime()
    today = timezone.localdate()
    iso = target_date.isoweekday()
    now_minutes = _minutes(now.time())

    empty_summary = {k: 0 for k in (
        "scheduled", "taken", "missing", "pending", "unscheduled",
        "present", "late", "absent_excused", "absent_unexcused")}

    # Faol o'quvchisi bor faol guruhlar.
    active_group_ids = set(
        Enrollment.objects.filter(
            center=center, is_active=True,
            group__is_archived=False, group__is_deleted=False,
        ).values_list("group_id", flat=True)
    )
    if not active_group_ids:
        return {"date": target_date.isoformat(), "summary": empty_summary, "rows": [], "unscheduled": []}

    groups = {
        g.id: g for g in Group.objects.filter(id__in=active_group_ids)
        .select_related("oqituvchi")
    }

    # 1) GroupSchedule: har guruh uchun {weekday: eng erta start_time}.
    sched_map: dict[int, dict[int, _time]] = defaultdict(dict)
    for s in GroupSchedule.objects.filter(group_id__in=active_group_ids).order_by("group_id", "start_time"):
        wd_map = sched_map[s.group_id]
        if s.weekday not in wd_map:
            wd_map[s.weekday] = s.start_time

    # 2) Jadvalsiz guruhlar uchun dominant naqsh (faol enrollmentlardan).
    pattern_counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in (
        Enrollment.objects.filter(group_id__in=active_group_ids, is_active=True)
        .values("group_id", "lesson_pattern").annotate(c=Count("id"))
    ):
        pattern_counts[row["group_id"]][row["lesson_pattern"] or "group"] += row["c"]

    def dominant_pattern(gid):
        counts = pattern_counts.get(gid, {})
        # "group" (Avtomatik) ni oxirgi o'ringa — aniq naqsh (odd/even/daily) ustun.
        best, best_c = None, -1
        for pat, c in counts.items():
            weight = c + (0 if pat == "group" else 1000)  # aniq naqshlarni afzal ko'ramiz
            if weight > best_c:
                best, best_c = pat, weight
        return best

    # Bugungi davomat status-hisobi (bitta so'rov).
    att_counts = {
        r["group_id"]: r
        for r in Attendance.objects.filter(group_id__in=active_group_ids, date=target_date)
        .values("group_id").annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status="present")),
            late=Count("id", filter=Q(status="late")),
            absent_excused=Count("id", filter=Q(status="absent_excused")),
            absent_unexcused=Count("id", filter=Q(status="absent_unexcused")),
        )
    }
    status_labels = dict(Attendance.STATUS_CHOICES)
    absentees_by_group: dict[int, list] = defaultdict(list)
    for a in (
        Attendance.objects.filter(
            group_id__in=active_group_ids, date=target_date,
            status__in=("absent_excused", "absent_unexcused", "late"),
        ).select_related("student").order_by("group_id", "status")
    ):
        absentees_by_group[a.group_id].append({
            "name": _person_name(a.student),
            "status": a.status,
            "status_label": status_labels.get(a.status, a.status),
        })

    rows = []
    unscheduled = []
    summary = dict(empty_summary)

    for gid, g in groups.items():
        gs = sched_map.get(gid)
        start_time = None
        if gs:
            if iso not in gs:
                continue  # bugun jadval bo'yicha dars yo'q
            start_time = gs[iso]
        else:
            pat = dominant_pattern(gid)
            wds = PATTERN_WEEKDAYS.get(pat)
            if not wds:
                # "group"/Avtomatik + jadval yo'q → jadval belgilanmagan
                unscheduled.append({
                    "group_id": gid, "group_name": g.nom,
                    "teacher_name": _person_name(g.oqituvchi),
                })
                summary["unscheduled"] += 1
                continue
            if iso not in wds:
                continue  # bugun naqsh bo'yicha dars yo'q
            start_time = None  # vaqt noma'lum (jadval sozlanmagan)

        counts = att_counts.get(gid)
        summary["scheduled"] += 1

        if counts and counts["total"] > 0:
            status = STATUS_TAKEN
            summary["taken"] += 1
            for key in ("present", "late", "absent_excused", "absent_unexcused"):
                summary[key] += counts[key]
        else:
            counts = {"total": 0, "present": 0, "late": 0, "absent_excused": 0, "absent_unexcused": 0}
            if start_time is not None:
                due = _minutes(start_time) + GRACE_MINUTES
                overdue = target_date < today or (target_date == today and now_minutes >= due)
            else:
                # vaqt noma'lum → o'tgan kun bo'lsa yoki bugun kunning oxiriga yaqin bo'lsa missing
                overdue = target_date < today or (target_date == today and now_minutes >= _minutes(DEFAULT_CUTOFF))
            status = STATUS_MISSING if overdue else STATUS_PENDING
            summary[status] += 1

        rows.append({
            "group_id": gid,
            "group_name": g.nom,
            "teacher_name": _person_name(g.oqituvchi),
            "start_time": start_time.strftime("%H:%M") if start_time else "",
            "has_time": start_time is not None,
            "status": status,
            "present": counts["present"],
            "late": counts["late"],
            "absent_excused": counts["absent_excused"],
            "absent_unexcused": counts["absent_unexcused"],
            "total_marked": counts["total"],
            "absentees": absentees_by_group.get(gid, []),
        })

    order = {STATUS_MISSING: 0, STATUS_PENDING: 1, STATUS_TAKEN: 2}
    rows.sort(key=lambda r: (order.get(r["status"], 9), r["start_time"] or "99:99"))
    unscheduled.sort(key=lambda r: r["group_name"])

    return {
        "date": target_date.isoformat(),
        "summary": summary,
        "rows": rows,
        "unscheduled": unscheduled,
    }
