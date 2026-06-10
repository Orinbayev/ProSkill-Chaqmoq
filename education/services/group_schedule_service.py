from datetime import date, timedelta

ODD_WEEKDAYS = (1, 3, 5)
EVEN_WEEKDAYS = (2, 4, 6)

DEFAULT_ESTIMATION_NOTE = (
    "Bu sana taxminiy hisob bo‘lib, bayramlar, tadbirlar yoki dars ko‘chirilishlari sabab o‘zgarishi mumkin"
)


def add_months(start: date, months: int) -> date:
    """
    dateutil'siz oy qo'shish.
    """
    month_index = (start.month - 1) + max(0, int(months))
    year = start.year + month_index // 12
    month = month_index % 12 + 1

    # Month-end safe
    days_in_month = [
        31,
        29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]
    day = min(start.day, days_in_month[month - 1])
    return date(year, month, day)


def calculate_estimated_end_date(
    *,
    course_start_date: date | None,
    duration_months: int | None,
    lessons_per_week: int | None = 3,
) -> date | None:
    """
    Taxminiy tugash sanasini hisoblaydi.
    Bu qat'iy deadline emas.
    """
    if not course_start_date:
        return None

    months = int(duration_months or 0)
    if months <= 0:
        return None

    estimated = add_months(course_start_date, months)

    # Haftalik darslar soni 3 dan kam bo'lsa, ozroq buffer qo'shamiz.
    lpw = int(lessons_per_week or 3)
    if lpw < 3:
        estimated += timedelta(days=(3 - lpw) * max(1, months))
    elif lpw > 3:
        estimated -= timedelta(days=min(months, (lpw - 3) * months // 2))

    return estimated


def apply_group_duration_defaults(group, *, force_recalculate: bool = False):
    """
    Group model instance uchun duration fieldlarida safe default/recalculation.
    """
    if not getattr(group, "lessons_per_week", None):
        group.lessons_per_week = 3

    if not getattr(group, "schedule_estimation_note", ""):
        group.schedule_estimation_note = DEFAULT_ESTIMATION_NOTE

    manual = bool(getattr(group, "estimated_end_date_manual", False))
    if force_recalculate or not manual:
        group.estimated_end_date = calculate_estimated_end_date(
            course_start_date=getattr(group, "course_start_date", None),
            duration_months=getattr(group, "duration_months", 0),
            lessons_per_week=getattr(group, "lessons_per_week", 3),
        )

    return group


def infer_simple_schedule(group) -> dict:
    from education.models import GroupSchedule

    empty = {"mode": "", "weekdays": [], "start_time": None, "end_time": None, "room": ""}
    if not getattr(group, "pk", None) or not getattr(group, "center_id", None):
        return empty

    schedules = list(
        GroupSchedule.objects.filter(group=group, center=group.center)
        .order_by("weekday", "start_time")
    )
    if not schedules:
        return empty

    first = schedules[0]
    weekdays = tuple(item.weekday for item in schedules)
    same_time = all(
        item.start_time == first.start_time
        and item.end_time == first.end_time
        and (item.room or "").strip() == (first.room or "").strip()
        for item in schedules
    )

    mode = "custom"
    if same_time and weekdays == ODD_WEEKDAYS:
        mode = "odd"
    elif same_time and weekdays == EVEN_WEEKDAYS:
        mode = "even"

    return {
        "mode": mode,
        "weekdays": list(weekdays),
        "start_time": first.start_time,
        "end_time": first.end_time,
        "room": first.room or "",
    }


def sync_simple_group_schedule(
    *,
    group,
    schedule_mode: str,
    custom_days=None,
    start_time=None,
    end_time=None,
    room: str = "",
):
    from education.models import GroupSchedule

    mode = (schedule_mode or "").strip().lower()

    if mode == "odd":
        weekdays = ODD_WEEKDAYS
    elif mode == "even":
        weekdays = EVEN_WEEKDAYS
    elif mode == "custom" and custom_days:
        try:
            weekdays = tuple(sorted(int(d) for d in custom_days if str(d).strip().isdigit() and 1 <= int(d) <= 7))
        except (ValueError, TypeError):
            weekdays = ()
    else:
        return []

    if not weekdays:
        return []

    if not getattr(group, "pk", None) or not getattr(group, "center_id", None) or not start_time:
        return []

    clean_room = (room or "").strip()

    GroupSchedule.objects.filter(group=group, center=group.center).delete()
    created = GroupSchedule.objects.bulk_create(
        [
            GroupSchedule(
                center=group.center,
                group=group,
                weekday=weekday,
                start_time=start_time,
                end_time=end_time,
                room=clean_room,
            )
            for weekday in weekdays
        ]
    )
    return created
