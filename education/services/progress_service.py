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


def build_timeline(
    student_id: int,
    *,
    center_id: int | None = None,
    period_key: str | None = "month",
) -> dict:
    """
    Returns:
      {
        "period": "month",
        "start_date": "2026-04-01",
        "end_date":   "2026-04-30",
        "total_score": 17,
        "timeline": [
            {"date": "2026-04-01", "score": 3, "reasons": ["Darsga keldi", "Vazifa bajardi"]},
            ...
        ]
      }
    """
    backfill_activities_for_student(student_id)

    key, start, end = resolve_period(period_key)
    qs = (
        StudentActivity.objects
        .filter(
            student_id=student_id,
            date__gte=start,
            date__lte=end,
            is_deleted=False,
        )
    )
    if center_id is not None:
        qs = qs.filter(center_id=center_id)

    daily_score: dict[date, int] = defaultdict(int)
    daily_reasons: dict[date, list[str]] = defaultdict(list)

    for activity in qs.order_by("date", "id"):
        daily_score[activity.date] += int(activity.score or 0)
        reason = activity.display_reason
        if reason and reason not in daily_reasons[activity.date]:
            daily_reasons[activity.date].append(reason)

    # Walk every day in the window so the chart has continuous x-axis points.
    timeline: list[dict] = []
    cur = start
    while cur <= end:
        timeline.append(
            {
                "date": cur.isoformat(),
                "score": int(daily_score.get(cur, 0)),
                "reasons": list(daily_reasons.get(cur, [])),
            }
        )
        cur += timedelta(days=1)

    total_score = sum(point["score"] for point in timeline)

    return {
        "period": key,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_score": total_score,
        "timeline": timeline,
    }
