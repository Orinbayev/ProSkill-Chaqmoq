from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from django.core.exceptions import ValidationError
from django.utils import timezone

from education.services.tuition import (
    lesson_pattern_hint,
    lesson_pattern_label,
    lesson_pattern_weekdays,
    normalize_lesson_pattern,
    resolve_lesson_schedule,
)


MAX_REMAINING_LESSONS = 999


def validate_remaining_lessons(value) -> int:
    try:
        remaining_lessons = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Qolgan dars soni butun son bo'lishi kerak.") from exc

    if remaining_lessons < 0:
        raise ValidationError("Qolgan dars manfiy bo'lishi mumkin emas.")
    if remaining_lessons > MAX_REMAINING_LESSONS:
        raise ValidationError(
            f"Qolgan dars {MAX_REMAINING_LESSONS} tadan oshmasligi kerak."
        )
    return remaining_lessons


def calculate_lessons(
    start_date: Optional[date],
    remaining_lessons,
    pattern: Optional[str],
    *,
    from_date: Optional[date] = None,
    group=None,
) -> dict:
    if not start_date:
        raise ValidationError("Boshlanish sanasini kiriting.")

    normalized_pattern = normalize_lesson_pattern(pattern)
    schedule_meta = resolve_lesson_schedule(start_date, normalized_pattern)
    resolved_pattern = schedule_meta["lesson_pattern"]
    effective_start_date = schedule_meta["start_date"]
    remaining_lessons_value = validate_remaining_lessons(remaining_lessons)

    reference_date = from_date or timezone.localdate()
    calculation_start_date = max(effective_start_date, reference_date)

    weekdays = tuple(
        int(weekday)
        for weekday in lesson_pattern_weekdays(resolved_pattern, group=group)
    )
    if not weekdays:
        raise ValidationError("Tanlangan pattern bo'yicha dars kunlari topilmadi.")

    lesson_dates = []
    cursor = calculation_start_date
    while len(lesson_dates) < remaining_lessons_value:
        if cursor.isoweekday() in weekdays:
            lesson_dates.append(cursor)
        cursor += timedelta(days=1)

    calculation_note_parts = []
    if schedule_meta["adjustment_note"]:
        calculation_note_parts.append(schedule_meta["adjustment_note"])
    if calculation_start_date > effective_start_date:
        calculation_note_parts.append(
            f"Hisob {calculation_start_date.strftime('%d.%m.%Y')} holatidan davom etdi"
        )

    last_lesson_date = lesson_dates[-1] if lesson_dates else None
    return {
        "requested_start_date": schedule_meta["requested_start_date"],
        "start_date": effective_start_date,
        "calculation_start_date": calculation_start_date,
        "remaining_lessons": remaining_lessons_value,
        "lesson_pattern": resolved_pattern,
        "lesson_pattern_label": lesson_pattern_label(resolved_pattern),
        "lesson_pattern_hint": lesson_pattern_hint(resolved_pattern),
        "lesson_dates": lesson_dates,
        "lesson_date_labels": [lesson_date.strftime("%d.%m.%Y") for lesson_date in lesson_dates],
        "last_lesson_date": last_lesson_date,
        "last_lesson_date_label": last_lesson_date.strftime("%d.%m.%Y") if last_lesson_date else "—",
        "calculation_note": " • ".join(calculation_note_parts),
        "used_reference_date": calculation_start_date > effective_start_date,
    }
