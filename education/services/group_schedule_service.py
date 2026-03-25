from datetime import date, timedelta


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
