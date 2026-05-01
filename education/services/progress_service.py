"""
Progress timeline service.

Builds the data the mobile chart needs:
- per-day score (sum of StudentActivity.score on that day)
- per-day list of human-readable reasons (used for the tap bottom sheet)

Activities come from two sources:
  1. Explicit StudentActivity rows (created by teachers, by signals, etc.)
  2. Auto-derivation from existing Attendance + ExamResult so the chart isn't
     empty before teachers start using the new tracker.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from django.utils import timezone

from django.db.models import Q

from education.models import (
    Attendance,
    ExamResult,
    StudentActivity,
)


# Score weights — tweak in one place.
SCORE_ATTENDANCE_PRESENT = 1
SCORE_ATTENDANCE_ABSENT = -1
SCORE_HOMEWORK_DONE = 2
SCORE_PARTICIPATION_ACTIVE = 3
SCORE_TEST_PASS = 3
SCORE_TEST_FAIL = -1


PERIOD_BOUNDS_DAYS = {
    "week": 7,
    "month": 30,
    "quarter": 90,
    "all": 365,
}


def resolve_period(period_key: str | None) -> tuple[str, date, date]:
    """Return (normalized_key, start_date, end_date)."""
    today = timezone.localdate()
    key = (period_key or "month").strip().lower()
    if key not in PERIOD_BOUNDS_DAYS:
        key = "month"
    start = today - timedelta(days=PERIOD_BOUNDS_DAYS[key] - 1)
    return key, start, today


def derive_activity_for_attendance(att: Attendance) -> StudentActivity | None:
    """Backfill: ensure each Attendance row has a matching StudentActivity.

    Fallback skoring (mobil progress diagrammasi uchun):
      present -> +1
      absent (sababli yoki sababsiz) -> -1
    """
    if not att.student_id or not att.group_id:
        return None
    is_present = att.status == "present" or att.present or att.forced
    is_absent = att.status in ("absent_unexcused", "absent_excused")
    if not is_present and not is_absent:
        return None

    if is_present:
        score = SCORE_ATTENDANCE_PRESENT
        note = "Darsga qatnashdi"
    else:
        score = SCORE_ATTENDANCE_ABSENT
        note = (
            "Sababli darsga kelmadi"
            if att.status == "absent_excused"
            else "Darsga kelmadi"
        )

    obj, _ = StudentActivity.objects.update_or_create(
        source_attendance=att,
        defaults={
            "center_id": att.group.center_id,
            "student_id": att.student_id,
            "group_id": att.group_id,
            "type": StudentActivity.TYPE_ATTENDANCE
            if is_present
            else StudentActivity.TYPE_PENALTY,
            "score": score,
            "date": att.date,
            "note": note,
        },
    )
    return obj


def derive_activity_for_exam(exam: ExamResult) -> StudentActivity | None:
    if not exam.student_id or exam.percent is None:
        return None
    pct = float(exam.percent)
    score = SCORE_TEST_PASS if pct >= 60 else SCORE_TEST_FAIL
    note = f"Test natijasi: {int(round(pct))}%"
    obj, _ = StudentActivity.objects.update_or_create(
        source_exam=exam,
        defaults={
            "center_id": exam.center_id,
            "student_id": exam.student_id,
            "group_id": exam.group_id,
            "type": StudentActivity.TYPE_TEST,
            "score": score,
            "date": exam.exam_date,
            "note": note,
        },
    )
    return obj


def backfill_activities_for_student(
    student_id: int, *, since: date | None = None
) -> int:
    """
    Walks recent Attendance + ExamResult rows that don't yet have a
    derived StudentActivity and creates them.
    Returns count created/updated.
    """
    if since is None:
        since = timezone.localdate() - timedelta(days=120)
    count = 0
    att_qs = (
        Attendance.objects.filter(student_id=student_id, date__gte=since)
        .select_related("group")
    )
    for att in att_qs.iterator(chunk_size=200):
        if derive_activity_for_attendance(att) is not None:
            count += 1
    exam_qs = ExamResult.objects.filter(
        student_id=student_id,
        exam_date__gte=since,
        percent__isnull=False,
    )
    for exam in exam_qs.iterator(chunk_size=200):
        if derive_activity_for_exam(exam) is not None:
            count += 1
    return count


def _ledger_kind(rule_tur: str, ball: int) -> str:
    """Normalize chaqmoq.Rule type to a simple timeline kind for the UI."""
    rt = (rule_tur or "").lower()
    if "attendance" in rt:
        return "attendance" if ball >= 0 else "attendance_missed"
    if "payment" in rt:
        return "payment"
    if rt == "minus":
        return "penalty"
    return "other"


def build_timeline(
    student_id: int,
    *,
    center_id: int | None = None,
    period_key: str | None = "month",
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """
    Reads chaqmoq awards directly from ``chaqmoq.Ledger`` so the parent panel
    shows the same scores the teacher actually granted (e.g. +3 for darsga
    qatnashdi). Falls back to derived ``StudentActivity`` rows when the ledger
    is empty for the period — keeps charts populated for legacy data.

    Returns:
      {
        "period": "month",
        "start_date": "...",
        "end_date":   "...",
        "total_score":    +27,         # net (sum)
        "total_chaqmoq":  +30,         # earned (positive only)
        "timeline": [
          {"date": "...", "score": 5,
           "reasons": ["Darsga keldi", "Vazifa bajardi"],
           "entries": [
             {"text": "Darsga keldi",  "score": 3, "type": "attendance"},
             {"text": "Vazifa bajardi","score": 2, "type": "other"},
           ]},
          ...
        ]
      }
    """
    # Ledger is the live source of truth. Activity backfill stays as a safety
    # net for older centers that have no ledger usage yet.
    from chaqmoq.models import Ledger

    backfill_activities_for_student(student_id)

    if start_date is not None and end_date is not None:
        # UI dan kelgan aniq oraliq (e.g. "3 oy" → currentMonth-2 .. currentMonth+1).
        key = (period_key or "month").strip().lower() or "month"
        start = start_date
        # `end_date` UI bounds odatda exclusive (oyning 1-kuni). Timeline bizdan
        # `<= end` ishlaydi, shuning uchun bir kun oldinga olamiz.
        end = end_date - timedelta(days=1)
        if end < start:
            end = start
    else:
        key, start, end = resolve_period(period_key)

    daily_score: dict[date, int] = defaultdict(int)
    daily_entries: dict[date, list[dict]] = defaultdict(list)

    ledger_qs = Ledger.objects.filter(
        student_id=student_id,
        sana__date__gte=start,
        sana__date__lte=end,
    ).select_related("rule", "group", "group__oqituvchi", "beruvchi")
    if center_id is not None:
        ledger_qs = ledger_qs.filter(
            Q(group__center_id=center_id)
            | Q(rule__center_id=center_id)
            | Q(rule__center__isnull=True)
        )

    for entry in ledger_qs.order_by("sana", "id"):
        ball = int(entry.ball or 0)
        if ball == 0:
            continue
        d = entry.sana.date()
        text = entry.rule_nom or (entry.rule.nom if entry.rule_id else "Chaqmoq")
        rule_tur = entry.rule_tur or (entry.rule.tur if entry.rule_id else "")
        group_obj = entry.group
        teacher_obj = group_obj.oqituvchi if group_obj else None
        daily_score[d] += ball
        daily_entries[d].append(
            {
                "id": entry.id,
                "text": text,
                "score": ball,
                "type": _ledger_kind(rule_tur, ball),
                "source": "ledger",
                "created_at": entry.sana.isoformat() if entry.sana else "",
                "group": group_obj.nom if group_obj else "",
                "teacher": teacher_obj.get_full_name() if teacher_obj else "",
                "awarded_by": (
                    entry.beruvchi.get_full_name() if entry.beruvchi_id else ""
                ),
                "reason": "",
            }
        )

    # If teacher hasn't issued any chaqmoq yet for this period, fall back to
    # auto-derived activities so the panel isn't blank.
    if not daily_entries:
        act_qs = StudentActivity.objects.filter(
            student_id=student_id,
            date__gte=start,
            date__lte=end,
            is_deleted=False,
        )
        if center_id is not None:
            act_qs = act_qs.filter(center_id=center_id)
        act_qs = act_qs.select_related("group", "group__oqituvchi")
        for activity in act_qs.order_by("date", "id"):
            score = int(activity.score or 0)
            if score == 0:
                continue
            d = activity.date
            reason = activity.display_reason or ""
            if not reason:
                continue
            daily_score[d] += score
            kind = (
                "attendance"
                if activity.type == StudentActivity.TYPE_ATTENDANCE and score >= 0
                else "attendance_missed"
                if activity.type in (
                    StudentActivity.TYPE_ATTENDANCE,
                    StudentActivity.TYPE_PENALTY,
                )
                else activity.type
            )
            group_obj = activity.group
            teacher_obj = group_obj.oqituvchi if group_obj else None
            daily_entries[d].append(
                {
                    "id": activity.id,
                    "text": reason,
                    "score": score,
                    "type": kind,
                    "source": "activity",
                    "created_at": activity.created_at.isoformat()
                    if activity.created_at
                    else "",
                    "group": group_obj.nom if group_obj else "",
                    "teacher": teacher_obj.get_full_name() if teacher_obj else "",
                    "awarded_by": "",
                    "reason": activity.note or "",
                }
            )

    # Walk every day in the window so the chart has continuous x-axis points.
    timeline: list[dict] = []
    cur = start
    while cur <= end:
        entries = daily_entries.get(cur, [])
        timeline.append(
            {
                "date": cur.isoformat(),
                "score": int(daily_score.get(cur, 0)),
                "reasons": [e["text"] for e in entries if e["text"]],
                "entries": entries,
            }
        )
        cur += timedelta(days=1)

    total_score = sum(point["score"] for point in timeline)
    total_chaqmoq = sum(
        max(0, e["score"])
        for entries in daily_entries.values()
        for e in entries
    )

    return {
        "period": key,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_score": total_score,
        "total_chaqmoq": total_chaqmoq,
        "timeline": timeline,
    }
