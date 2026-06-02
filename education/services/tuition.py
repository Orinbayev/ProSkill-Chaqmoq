# education/services/tuition.py
from __future__ import annotations

import calendar
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Iterable, Optional, Sequence, Union

from django.db import transaction
from django.db.models import Q, Sum, F
from django.db.models.functions import Coalesce
from django.utils import timezone

from education.models import TuitionMonth, PaymentAllocation, Payment, Enrollment, StudentGroupHistory


# =========================
#  SMALL HELPERS
# =========================

def _model_has_field(Model, field_name: str) -> bool:
    try:
        Model._meta.get_field(field_name)
        return True
    except Exception:
        return False


def tuition_month_fee_field() -> str:
    """
    TuitionMonth modelida fee field nomi turlicha bo'lishi mumkin:
    - fee_amount
    - fee
    """
    return "fee_amount" if _model_has_field(TuitionMonth, "fee_amount") else "fee"


def tuition_month_fee(tm: TuitionMonth) -> int:
    field = tuition_month_fee_field()
    return int(getattr(tm, field, 0) or 0)


def set_tuition_month_fee(tm: TuitionMonth, amount: int) -> None:
    field = tuition_month_fee_field()
    setattr(tm, field, int(amount or 0))
    tm.save(update_fields=[field])


def month_first_day(d: date) -> date:
    return date(d.year, d.month, 1)


def add_month(d: date, n: int = 1) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)


def round_div(numerator: int, denominator: int) -> int:
    numerator = int(numerator or 0)
    denominator = int(denominator or 0)
    if denominator <= 0:
        return 0
    return (numerator + denominator // 2) // denominator


def proportional_amount(amount: int, units: int, total_units: int) -> int:
    return round_div(int(amount or 0) * int(units or 0), int(total_units or 0))


def round_money_to_thousand(amount: int | float | None) -> int:
    amount = int(round(amount or 0))
    if amount == 0:
        return 0
    sign = 1 if amount >= 0 else -1
    absolute_amount = abs(amount)
    rounded = ((absolute_amount + 500) // 1000) * 1000
    return rounded * sign


def format_money(amount: int | float | None, *, compact: bool = False) -> str:
    rounded = round_money_to_thousand(amount)
    absolute_amount = abs(rounded)
    if compact and absolute_amount >= 1000:
        return f"{rounded // 1000:,}".replace(",", " ") + " ming so'm"
    return f"{rounded:,}".replace(",", " ") + " so'm"


def month_range_starts(start_date: date, end_date: date) -> list[date]:
    """
    [start_date, end_date] oralig'idagi oy boshlarini qaytaradi.
    """
    start_month = month_first_day(start_date)
    end_month = month_first_day(end_date)
    if start_month > end_month:
        start_month, end_month = end_month, start_month

    months = []
    cur = start_month
    while cur <= end_month:
        months.append(cur)
        cur = add_month(cur, 1)
    return months


def parse_month_str(s: str) -> Optional[date]:
    """
    'YYYY-MM' yoki 'YYYY-MM-DD' -> date(YYYY,MM,1)
    invalid -> None
    """
    if not s:
        return None
    s = s.strip()
    if len(s) >= 10:
        s = s[:7]
    if len(s) != 7 or s[4] != "-":
        return None
    try:
        y = int(s[:4])
        m = int(s[5:7])
        if 1 <= m <= 12:
            return date(y, m, 1)
        return None
    except Exception:
        return None



def full_course_amount(enrollment: Enrollment) -> int:
    if not enrollment:
        return 0
    return int(getattr(enrollment, "full_course_amount", 0) or 0)


def enrollment_start_date(enrollment: Enrollment) -> date:
    if not enrollment:
        return timezone.localdate()

    # In-process memoization: this function is called repeatedly during a
    # single dashboard render (e.g. once per (enrollment, month) in the
    # debt snapshot loop). The result is deterministic for a given
    # Enrollment instance, so cache it on the object to avoid hammering
    # StudentGroupHistory with thousands of identical queries.
    cached = getattr(enrollment, "__resolved_start_date__", None)
    if cached is not None:
        return cached

    explicit_start_date = getattr(enrollment, "_tuition_start_date", None)
    if explicit_start_date:
        result = normalize_lesson_start_date(explicit_start_date) or timezone.localdate()
        try:
            enrollment.__resolved_start_date__ = result
        except Exception:
            pass
        return result

    joined_at = getattr(enrollment, "joined_at", None)
    student = getattr(enrollment, "student", None)
    group = getattr(enrollment, "group", None)
    history_start = getattr(enrollment, "__preloaded_history_start_date__", _UNSET)
    if history_start is _UNSET and student and group:
        history = StudentGroupHistory.objects.filter(
            student=student,
            group=group,
        ).order_by("-start_date").first()
        history_start = history.start_date if history and history.start_date else None
    if history_start:
        created_at = getattr(enrollment, "created_at", None)
        created_date = timezone.localtime(created_at).date() if created_at else None
        if joined_at and joined_at != created_date:
            result = normalize_lesson_start_date(joined_at) or timezone.localdate()
        else:
            result = normalize_lesson_start_date(history_start) or timezone.localdate()
        try:
            enrollment.__resolved_start_date__ = result
        except Exception:
            pass
        return result

    if joined_at:
        result = normalize_lesson_start_date(joined_at) or timezone.localdate()
        try:
            enrollment.__resolved_start_date__ = result
        except Exception:
            pass
        return result

    start_dt = getattr(enrollment, "created_at", None) or timezone.now()
    result = normalize_lesson_start_date(start_dt.date()) or timezone.localdate()
    try:
        enrollment.__resolved_start_date__ = result
    except Exception:
        pass
    return result


# Sentinel for "not yet preloaded" vs explicit None
_UNSET = object()


def preload_enrollment_history_starts(enrollments) -> None:
    """
    Pre-populate the __preloaded_history_start_date__ attribute on each
    enrollment using a single grouped query, so the next call to
    enrollment_start_date() doesn't hit the DB per-enrollment.

    Safe to call with any iterable of enrollments. Idempotent.
    """
    enrollments = [e for e in enrollments if getattr(e, "id", None)]
    if not enrollments:
        return

    pairs = [(e.student_id, e.group_id) for e in enrollments
             if getattr(e, "student_id", None) and getattr(e, "group_id", None)]
    if not pairs:
        for e in enrollments:
            if not hasattr(e, "__preloaded_history_start_date__"):
                try:
                    e.__preloaded_history_start_date__ = None
                except Exception:
                    pass
        return

    student_ids = {p[0] for p in pairs}
    group_ids = {p[1] for p in pairs}

    history_map: dict[tuple[int, int], date] = {}
    rows = (
        StudentGroupHistory.objects
        .filter(student_id__in=student_ids, group_id__in=group_ids)
        .order_by("student_id", "group_id", "-start_date")
        .values("student_id", "group_id", "start_date")
    )
    for row in rows:
        key = (row["student_id"], row["group_id"])
        # First (newest) row wins because of order_by("-start_date")
        if key not in history_map and row["start_date"]:
            history_map[key] = row["start_date"]

    for e in enrollments:
        key = (getattr(e, "student_id", None), getattr(e, "group_id", None))
        try:
            e.__preloaded_history_start_date__ = history_map.get(key)
        except Exception:
            pass


def effective_student_payable_amount(enrollment: Enrollment) -> int:
    if not enrollment:
        return 0
    return int(getattr(enrollment, "effective_student_payable_amount", 0) or 0)


def get_fee_amount(enrollment: Enrollment) -> int:
    """
    fee manbasi:
    - enrollment.student_payable_amount (agar berilgan bo'lsa)
    - aks holda to'liq kurs narxi
    """
    return effective_student_payable_amount(enrollment)


def _billable_attendance_q() -> Q:
    return (
        Q(status="present")
        | Q(status="absent_unexcused")
        | Q(present=True)
        | Q(forced=True)
    )


# =========================
#  PRORATED FEE CALCULATIONS
# =========================
#
# Muammo:
#   O'quvchi oy o'rtasida (masalan 18-sanada) qo'shilsa ham, TuitionMonth.fee_amount
#   to'liq oylik narxga qo'yilardi. Natijada "qarzdorlar" bo'limida yolg'on qarz paydo
#   bo'lardi (masalan 550k − 4 dars × 45.8k = 367k sun'iy qarz).
#
# Yechim:
#   1) prorated_monthly_fee()  — enrollment yaratilganda birinchi oy uchun
#      expected_lessons (GroupSchedule dan) × per_lesson narxni hisoblaydi.
#   2) reconcile_tuition_month() — oy oxirida haqiqiy davomatga qarab
#      (present + absent_unexcused) fee_amount ni qayta yozadi.
#   3) Har ikkalasi ham effective_student_payable_amount (chegirmali narx) dan
#      hisoblaydi, shuning uchun chegirma va tekin holatlar ham qamrab olinadi.
#   4) O'qituvchi maoshi bu yerda HECH qanday o'zgartirilmaydi — u alohida
#      HistoricalFinanceService orqali ASL kurs_narhi dan hisoblanadi.


def month_last_day(d: date) -> date:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last_day)


def scheduled_lessons_between(group, start: date, end: date) -> int:
    """
    GroupSchedule ga qarab [start, end] oralig'ida nechta rejalashtirilgan dars
    borligini sanaydi. Jadval bo'sh bo'lsa 0 qaytaradi (fallback yuqorida).

    PERF: agar caller `preload_group_schedules([group_id, ...])` chaqirgan
    bo'lsa, request-scope cache'dan o'qiydi (1 query vs N query).
    """
    from education.models import GroupSchedule

    if start > end:
        return 0

    gid = getattr(group, "id", None)
    weekday_counts = _get_cached_group_weekdays(gid)
    if weekday_counts is None:
        # Fallback: cache yo'q — har query
        weekday_counts = Counter(
            GroupSchedule.objects.filter(group=group).values_list("weekday", flat=True)
        )

    if not weekday_counts:
        return 0

    count = 0
    cur = start
    # GroupSchedule.weekday: 1=Mon .. 7=Sun (Python isoweekday bilan mos)
    while cur <= end:
        count += int(weekday_counts.get(cur.isoweekday(), 0) or 0)
        cur += timedelta(days=1)
    return count


# ──────────────────────────────────────────────────────────────────────
# Request-scope cache for group schedules — performance optimisation.
# Caller calls `preload_group_schedules([group_ids])` once before the loop;
# `scheduled_lessons_between` reads from this cache.
# ──────────────────────────────────────────────────────────────────────
import threading as _threading

_request_cache = _threading.local()


def _get_cache_dict():
    if not hasattr(_request_cache, "schedule_weekdays"):
        _request_cache.schedule_weekdays = None
    return _request_cache.schedule_weekdays


def _get_cached_group_weekdays(group_id):
    cache = _get_cache_dict()
    if cache is None or group_id is None:
        return None
    return cache.get(group_id, Counter())  # bo'sh Counter — schedule yo'q


def preload_group_schedules(group_ids) -> None:
    """Berilgan guruhlar uchun GroupSchedule weekday_counts'larini bir
    martalik query bilan yuklaydi va request-scope cache'ga saqlaydi.

    Keyin `scheduled_lessons_between` har chaqirilganda DB'ga bormaydi.
    """
    from education.models import GroupSchedule

    ids = [int(gid) for gid in group_ids if gid]
    if not ids:
        _request_cache.schedule_weekdays = {}
        return

    cache: dict[int, Counter] = {gid: Counter() for gid in set(ids)}
    rows = GroupSchedule.objects.filter(group_id__in=ids).values_list("group_id", "weekday")
    for gid, weekday in rows:
        cache.setdefault(gid, Counter())[weekday] += 1
    _request_cache.schedule_weekdays = cache


def clear_group_schedule_cache() -> None:
    """Request oxirida tozalash (xohlasangiz)."""
    _request_cache.schedule_weekdays = None


LESSON_PATTERN_GROUP = "group"
LESSON_PATTERN_EVEN = "even"
LESSON_PATTERN_ODD = "odd"
LESSON_PATTERN_DAILY = "daily"
LESSON_PATTERN_LABELS = {
    LESSON_PATTERN_GROUP: "Avtomatik",
    LESSON_PATTERN_EVEN: "Juft kunlari",
    LESSON_PATTERN_ODD: "Toq kunlari",
    LESSON_PATTERN_DAILY: "Har kuni",
}
LESSON_PATTERN_HINTS = {
    LESSON_PATTERN_GROUP: "Boshlanish sanasiga qarab aniqlanadi",
    LESSON_PATTERN_EVEN: "Seshanba • Payshanba • Shanba",
    LESSON_PATTERN_ODD: "Dushanba • Chorshanba • Juma",
    LESSON_PATTERN_DAILY: "Dushanba-Shanba",
}
LESSON_PATTERN_WEEKDAYS = {
    LESSON_PATTERN_EVEN: (2, 4, 6),
    LESSON_PATTERN_ODD: (1, 3, 5),
    LESSON_PATTERN_DAILY: (1, 2, 3, 4, 5, 6),
}
WEEKDAY_LABELS = {
    1: "Dushanba",
    2: "Seshanba",
    3: "Chorshanba",
    4: "Payshanba",
    5: "Juma",
    6: "Shanba",
    7: "Yakshanba",
}
WEEKDAY_SHORT_LABELS = {
    1: "Dush",
    2: "Sesh",
    3: "Chor",
    4: "Pay",
    5: "Jum",
    6: "Shan",
    7: "Yak",
}
AUTO_LESSON_PATTERN_BY_WEEKDAY = {
    1: LESSON_PATTERN_ODD,
    2: LESSON_PATTERN_EVEN,
    3: LESSON_PATTERN_ODD,
    4: LESSON_PATTERN_EVEN,
    5: LESSON_PATTERN_ODD,
    6: LESSON_PATTERN_EVEN,
}


def normalize_lesson_pattern(pattern: Optional[str]) -> str:
    pattern = (pattern or "").strip().lower()
    if pattern in {LESSON_PATTERN_EVEN, LESSON_PATTERN_ODD, LESSON_PATTERN_DAILY}:
        return pattern
    return LESSON_PATTERN_GROUP


def normalize_lesson_start_date(start_date: Optional[date]) -> Optional[date]:
    if not start_date:
        return start_date
    if start_date.isoweekday() == 7:
        return start_date + timedelta(days=1)
    return start_date


def auto_lesson_pattern_for_date(start_date: Optional[date]) -> str:
    effective_start_date = normalize_lesson_start_date(start_date) or timezone.localdate()
    return AUTO_LESSON_PATTERN_BY_WEEKDAY.get(
        effective_start_date.isoweekday(),
        LESSON_PATTERN_ODD,
    )


def resolve_lesson_schedule(start_date: Optional[date], pattern: Optional[str] = None) -> dict:
    requested_start_date = start_date or timezone.localdate()
    effective_start_date = normalize_lesson_start_date(requested_start_date) or timezone.localdate()
    requested_pattern = normalize_lesson_pattern(pattern)
    resolved_pattern = (
        requested_pattern
        if requested_pattern in {LESSON_PATTERN_EVEN, LESSON_PATTERN_ODD, LESSON_PATTERN_DAILY}
        else auto_lesson_pattern_for_date(effective_start_date)
    )

    adjustment_note = ""
    if requested_start_date and effective_start_date != requested_start_date:
        adjustment_note = (
            "Yakshanba tanlangani uchun hisob-kitob "
            f"{effective_start_date.strftime('%d.%m.%Y')} dan boshlandi"
        )

    return {
        "requested_start_date": requested_start_date,
        "start_date": effective_start_date,
        "requested_pattern": requested_pattern,
        "lesson_pattern": resolved_pattern,
        "adjustment_note": adjustment_note,
    }


def lesson_pattern_label(pattern: Optional[str]) -> str:
    return LESSON_PATTERN_LABELS.get(
        normalize_lesson_pattern(pattern),
        LESSON_PATTERN_LABELS[LESSON_PATTERN_GROUP],
    )


def lesson_pattern_hint(pattern: Optional[str]) -> str:
    normalized = normalize_lesson_pattern(pattern)
    return LESSON_PATTERN_HINTS.get(normalized, LESSON_PATTERN_HINTS[LESSON_PATTERN_GROUP])


def weekday_label(weekday: int, *, short: bool = False) -> str:
    labels = WEEKDAY_SHORT_LABELS if short else WEEKDAY_LABELS
    return labels.get(int(weekday or 0), "")


def lesson_pattern_weekdays(
    pattern: Optional[str],
    *,
    group=None,
) -> tuple[int, ...]:
    normalized = normalize_lesson_pattern(pattern)
    if normalized == LESSON_PATTERN_GROUP:
        gid = getattr(group, "id", None)
        if not gid:
            return ()
        # Preloaded cache'dan o'qiymiz (preload_group_schedules chaqirilgan bo'lsa)
        cached = _get_cached_group_weekdays(gid)
        if cached is not None:
            return tuple(sorted(int(w) for w in cached))
        # Fallback: cache yo'q — DB query
        from education.models import GroupSchedule
        weekdays = (
            GroupSchedule.objects.filter(group=group)
            .order_by("weekday")
            .values_list("weekday", flat=True)
            .distinct()
        )
        return tuple(int(weekday) for weekday in weekdays)
    return LESSON_PATTERN_WEEKDAYS.get(normalized, ())


def lesson_pattern_preview_meta(enrollment: Enrollment) -> dict:
    schedule_meta = resolve_lesson_schedule(
        getattr(enrollment, "_tuition_requested_start_date", None) or enrollment_start_date(enrollment),
        getattr(enrollment, "lesson_pattern", None),
    )
    pattern = enrollment_lesson_pattern(enrollment)
    weekdays = lesson_pattern_weekdays(pattern, group=getattr(enrollment, "group", None))
    weekday_labels = [weekday_label(weekday) for weekday in weekdays if weekday_label(weekday)]
    weekday_short_labels = [
        weekday_label(weekday, short=True)
        for weekday in weekdays
        if weekday_label(weekday, short=True)
    ]

    counted_days_summary_parts = []
    if schedule_meta["adjustment_note"]:
        counted_days_summary_parts.append(schedule_meta["adjustment_note"])
    if weekday_short_labels:
        counted_days_summary_parts.append(f"Hisoblangan kunlar: {', '.join(weekday_short_labels)}")

    return {
        "lesson_pattern_hint": lesson_pattern_hint(pattern),
        "counted_weekdays": list(weekdays),
        "counted_weekday_labels": weekday_labels,
        "counted_weekday_short_labels": weekday_short_labels,
        "counted_days_text": " • ".join(weekday_labels),
        "counted_days_summary": " • ".join(counted_days_summary_parts),
        "start_date_note": schedule_meta["adjustment_note"],
    }


def enrollment_lesson_pattern(enrollment: Enrollment) -> str:
    schedule_meta = resolve_lesson_schedule(
        enrollment_start_date(enrollment),
        getattr(enrollment, "lesson_pattern", None),
    )
    return schedule_meta["lesson_pattern"]


def pattern_lessons_between(start: date, end: date, pattern: Optional[str]) -> int:
    """
    Juft/toq/har kuni patterni bo'yicha [start, end] oralig'idagi darslarni sanaydi.
    Juft/toq ish haftasi kunlarining paritysiga qaraydi:
      - toq: Dushanba, Chorshanba, Juma
      - juft: Seshanba, Payshanba, Shanba
      - har kuni: Dushanba-Shanba
    Yakshanba bu patternlarda hech qachon hisobga kirmaydi.
    """
    if start > end:
        return 0

    pattern = normalize_lesson_pattern(pattern)
    if pattern == LESSON_PATTERN_GROUP:
        return 0

    allowed_weekdays = set(lesson_pattern_weekdays(pattern))
    count = 0
    cur = start
    while cur <= end:
        if cur.isoweekday() in allowed_weekdays:
            count += 1
        cur += timedelta(days=1)
    return count


def lesson_dates_between(
    start: date,
    end: date,
    pattern: Optional[str],
    *,
    group=None,
) -> list[date]:
    if start > end:
        return []

    allowed_weekdays = set(lesson_pattern_weekdays(pattern, group=group))
    if not allowed_weekdays:
        return []

    dates: list[date] = []
    cur = start
    while cur <= end:
        if cur.isoweekday() in allowed_weekdays:
            dates.append(cur)
        cur += timedelta(days=1)
    return dates


def expected_lesson_dates_in_period(enrollment: Enrollment, start: date, end: date) -> list[date]:
    if start > end:
        return []

    pattern = enrollment_lesson_pattern(enrollment)
    if pattern != LESSON_PATTERN_GROUP:
        return lesson_dates_between(start, end, pattern)

    group = getattr(enrollment, "group", None)
    return lesson_dates_between(start, end, LESSON_PATTERN_GROUP, group=group)


def expected_lessons_in_period(enrollment: Enrollment, start: date, end: date) -> int:
    """
    Oralig'idagi "kutilayotgan" darslar sonini qaytaradi.
    Avval GroupSchedule dan sanaydi, bo'sh bo'lsa — oy_dars_soni ni kunlar
    nisbatiga asosan prorate qiladi (fallback).
    """
    if start > end:
        return 0

    pattern = enrollment_lesson_pattern(enrollment)
    if pattern != LESSON_PATTERN_GROUP:
        return pattern_lessons_between(start, end, pattern)

    group = enrollment.group
    scheduled = scheduled_lessons_between(group, start, end)
    if scheduled > 0:
        return scheduled

    oy_dars_soni = _monthly_lessons_count(enrollment)
    month_total_days = calendar.monthrange(start.year, start.month)[1]
    period_days = (end - start).days + 1
    return min(oy_dars_soni, proportional_amount(oy_dars_soni, period_days, month_total_days))


def billable_attendance_count(enrollment: Enrollment, month: date) -> int:
    """
    Shu oyda hisob-kitobga kiradigan davomatlar soni:
      - status='present' yoki status='absent_unexcused' (sababsiz)
      - eski maydonlar uchun: present=True yoki forced=True
    Sababli (absent_excused) — hisoblanmaydi.
    """
    from education.models import Attendance

    month_start = month_first_day(month)
    month_end = month_last_day(month_start)

    return (
        Attendance.objects.filter(
            group=enrollment.group,
            student=enrollment.student,
            date__gte=month_start,
            date__lte=month_end,
        )
        .filter(_billable_attendance_q())
        .count()
    )


def _monthly_lessons_count(enrollment: Enrollment) -> int:
    monthly_lessons = int(getattr(enrollment, "monthly_lessons", 0) or 0)
    if monthly_lessons <= 0:
        group = getattr(enrollment, "group", None)
        monthly_lessons = int(getattr(group, "oy_dars_soni", 0) or 0) or 12
    return monthly_lessons if monthly_lessons > 0 else 12


def _prorated_monthly_fee_from_amount(
    enrollment: Enrollment,
    month: date,
    effective_price: int,
) -> int:
    month_start = month_first_day(month)
    month_end = month_last_day(month_start)

    effective_price = int(effective_price or 0)
    if effective_price <= 0:
        return 0

    monthly_lessons = _monthly_lessons_count(enrollment)
    lesson_count = tuition_month_lesson_count(enrollment, month_start)
    if lesson_count <= 0:
        return 0

    billing = calculate_student_month_billing(
        effective_price,
        monthly_lessons,
        lesson_count,
        getattr(enrollment, "oqituvchi_foiz", 0) or 0,
    )
    return int(billing["student_debt"])


def calculate_student_month_billing(
    course_price: int,
    standard_lessons_count: int,
    calculated_lessons_count: int,
    teacher_percent: int,
) -> dict:
    """
    O'quvchi oylik qarzini yagona formula bilan hisoblaydi.

    Bir dars narxi standart oylik dars sonidan olinadi.
    O'quvchi qarzi kurs narxidan oshmaydi.
    O'qituvchi summasi real hisoblangan darslar bo'yicha ketadi.
    """
    course_price = max(0, int(course_price or 0))
    standard_lessons_count = max(0, int(standard_lessons_count or 0))
    calculated_lessons_count = max(0, int(calculated_lessons_count or 0))
    teacher_percent = max(0, min(100, int(teacher_percent or 0)))

    lesson_price = round_div(course_price, standard_lessons_count)
    student_debt = min(
        proportional_amount(course_price, calculated_lessons_count, standard_lessons_count),
        course_price
    )
    teacher_month_amount = course_price * teacher_percent // 100
    teacher_per_lesson = (
        teacher_month_amount // standard_lessons_count
        if teacher_month_amount > 0 and standard_lessons_count > 0
        else 0
    )
    teacher_amount = teacher_per_lesson * calculated_lessons_count
    center_amount = student_debt - teacher_amount

    return {
        "calculated_lessons": int(calculated_lessons_count),
        "lesson_price": int(lesson_price),
        "student_debt": int(student_debt),
        "teacher_amount": int(teacher_amount),
        "center_amount": int(center_amount),
    }


def calculate_student_month_payment(
    course_price: int,
    standard_lessons_count: int,
    calculated_lessons_count: int,
    teacher_percent: int,
) -> dict:
    return calculate_student_month_billing(
        course_price,
        standard_lessons_count,
        calculated_lessons_count,
        teacher_percent,
    )


def tuition_amount_breakdown(
    enrollment: Enrollment,
    lesson_count: int,
    *,
    course_price: int | None = None,
    monthly_lessons: int | None = None,
    teacher_percent: int | None = None,
) -> dict:
    """
    Backward-compatible wrapper around calculate_student_month_billing().
    """
    course_price = int(course_price if course_price is not None else full_course_amount(enrollment) or 0)
    monthly_lessons = int(monthly_lessons if monthly_lessons is not None else _monthly_lessons_count(enrollment) or 0)
    teacher_percent = int(
        teacher_percent
        if teacher_percent is not None
        else getattr(enrollment, "oqituvchi_foiz", 0)
        or 0
    )
    payment = calculate_student_month_billing(
        course_price,
        monthly_lessons,
        lesson_count,
        teacher_percent,
    )
    return {
        "course_price": int(course_price),
        "monthly_lessons": int(monthly_lessons),
        "lesson_count": payment["calculated_lessons"],
        "per_lesson_amount": payment["lesson_price"],
        "fee_amount": payment["student_debt"],
        "teacher_share": payment["teacher_amount"],
        "center_share": payment["center_amount"],
    }


def prorated_monthly_fee(enrollment: Enrollment, month: date) -> int:
    """
    Oylik to'lov summasini kutilayotgan darslarga qarab hisoblaydi.

    - To'liq oy (start_date <= oy boshi): effective_student_payable_amount
    - Qisman oy (start_date oy ichida): expected_lessons × per_lesson
    - Cap: hech qachon effective_student_payable_amount dan oshmaydi
    - Oy enrollment boshlanishidan oldin: 0 (qarz yaratilmaydi)
    """
    return _prorated_monthly_fee_from_amount(
        enrollment,
        month,
        effective_student_payable_amount(enrollment),
    )


def attendance_based_fee(enrollment: Enrollment, month: date) -> int:
    """
    Haqiqiy davomatga qarab to'lov summasini hisoblaydi (reconcile uchun).
    fee = min(billable_lessons × per_lesson, effective_student_payable_amount)
    """
    effective_price = effective_student_payable_amount(enrollment)
    if effective_price <= 0:
        return 0

    billable = billable_attendance_count(enrollment, month)
    billing = calculate_student_month_billing(
        effective_price,
        _monthly_lessons_count(enrollment),
        billable,
        getattr(enrollment, "oqituvchi_foiz", 0) or 0,
    )
    return int(billing["student_debt"])


def teacher_monthly_financials(
    enrollment: Enrollment,
    billable_lessons: int,
    *,
    teacher_percent: Optional[int] = None,
) -> dict:
    """
    O'qituvchi to'lovini standart oylik dars narxidan hisoblaydi.

    Formula:
      per_lesson = (kurs_narxi × foiz%) / standart_dars_soni
      teacher_salary = per_lesson × REAL dars soni

    Standart oyda 12 dars bo'lsa ham, 13 yoki 14 dars bo'lganda
    o'qituvchi har ortiqcha dars uchun qo'shimcha per_lesson oladi.
    O'quvchi to'lovi (turnover) kurs narxidan oshmaydi.
    """
    monthly_lessons = _monthly_lessons_count(enrollment)

    billable_lessons = max(0, int(billable_lessons or 0))
    full_amount = full_course_amount(enrollment)
    effective_percent = int(teacher_percent or 0)
    if effective_percent <= 0:
        effective_percent = int(getattr(enrollment, "oqituvchi_foiz", 0) or 0)

    if full_amount <= 0:
        return {
            "billable_lessons": billable_lessons,
            "teacher_salary": 0,
            "center_profit": 0,
            "turnover": 0,
            "teacher_salary_cap": 0,
            "turnover_cap": 0,
        }

    # Standart oylik o'qituvchi ulushi (masalan: 250_000 × 50% = 125_000)
    teacher_salary_cap = round_div(full_amount * effective_percent, 100)
    turnover_cap = int(full_amount)

    # Per-lesson teacher amount, rounded evenly:
    #   round_div(125_000 × 12, 12) = 125_000  (12 dars)
    #   round_div(125_000 × 13, 12) = 135_417  (13 dars)
    #   round_div(125_000 × 14, 12) = 145_834  (14 dars)
    raw_teacher_salary = (
        round_div(teacher_salary_cap * billable_lessons, monthly_lessons)
        if monthly_lessons > 0 else 0
    )
    teacher_salary = min(raw_teacher_salary, teacher_salary_cap)

    # O'quvchi to'lovi kurs narxidan oshmaydi
    turnover = min(
        proportional_amount(full_amount, billable_lessons, monthly_lessons),
        turnover_cap,
    )
    center_profit = turnover - teacher_salary

    return {
        "billable_lessons": billable_lessons,
        "teacher_salary": int(teacher_salary),
        "center_profit": int(center_profit),
        "turnover": int(turnover),
        "teacher_salary_cap": int(teacher_salary_cap),
        "turnover_cap": int(turnover_cap),
    }


def tuition_month_lesson_count(enrollment: Enrollment, month: date) -> int:
    month_start = month_first_day(month)
    month_end = month_last_day(month_start)
    start_date = enrollment_start_date(enrollment)
    if start_date > month_end:
        return 0
    period_start = max(start_date, month_start)
    return expected_lessons_in_period(enrollment, period_start, month_end)


def tuition_month_preview(enrollment: Enrollment, month: date) -> dict:
    month_start = month_first_day(month)
    start_date = enrollment_start_date(enrollment)
    lesson_pattern = enrollment_lesson_pattern(enrollment)
    preview_meta = lesson_pattern_preview_meta(enrollment)
    monthly_lessons = _monthly_lessons_count(enrollment)
    full_amount = full_course_amount(enrollment)
    effective_amount = effective_student_payable_amount(enrollment)
    month_end = month_last_day(month_start)
    period_start = max(start_date, month_start)
    lesson_dates = expected_lesson_dates_in_period(enrollment, period_start, month_end)
    lesson_count = len(lesson_dates)
    teacher_percent = int(getattr(enrollment, "oqituvchi_foiz", 0) or 0)
    fee_billing = calculate_student_month_billing(
        effective_amount,
        monthly_lessons,
        lesson_count,
        teacher_percent,
    )
    full_billing = calculate_student_month_billing(
        full_amount,
        monthly_lessons,
        lesson_count,
        teacher_percent,
    )
    fee_amount = fee_billing["student_debt"]
    full_turnover = full_billing["student_debt"]
    teacher_share = full_billing["teacher_amount"]
    center_share = full_turnover - teacher_share

    _UZBEK_MONTHS = {
        1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel", 5: "may", 6: "iyun",
        7: "iyul", 8: "avgust", 9: "sentabr", 10: "oktabr", 11: "noyabr", 12: "dekabr"
    }
    month_label_uz = _UZBEK_MONTHS[month_start.month]

    return {
        "month": month_start,
        "start_date": start_date,
        "lesson_pattern": lesson_pattern,
        "lesson_pattern_label": lesson_pattern_label(lesson_pattern),
        "monthly_lessons": monthly_lessons,
        "lesson_count": lesson_count,
        "per_lesson_amount": round_div(full_amount, monthly_lessons) if monthly_lessons else 0,
        "per_lesson_amount_display": format_money(round_div(full_amount, monthly_lessons) if monthly_lessons else 0),
        "lesson_pattern_hint": preview_meta["lesson_pattern_hint"],
        "counted_weekdays": preview_meta["counted_weekdays"],
        "counted_weekday_labels": preview_meta["counted_weekday_labels"],
        "counted_weekday_short_labels": preview_meta["counted_weekday_short_labels"],
        "counted_days_text": preview_meta["counted_days_text"],
        "counted_days_summary": preview_meta["counted_days_summary"],
        "lesson_count_summary": f"Bu oy bo'yicha {lesson_count} ta mos dars kuni topildi",
        "lesson_dates": lesson_dates,
        "lesson_date_labels": [lesson_date.strftime("%d.%m.%Y") for lesson_date in lesson_dates],
        "fee_amount": int(fee_amount or 0),
        "fee_amount_rounded": round_money_to_thousand(fee_amount),
        "fee_amount_display": format_money(fee_amount),
        "full_turnover": int(full_turnover or 0),
        "teacher_share": int(teacher_share or 0),
        "teacher_share_rounded": round_money_to_thousand(teacher_share),
        "teacher_share_display": format_money(teacher_share),
        "center_share": int(center_share or 0),
        "center_share_rounded": round_money_to_thousand(center_share),
        "center_share_display": format_money(center_share),
        "month_label_uz": month_label_uz,
        "debt_label_uz": f"{month_label_uz.upper()} OYI QARZI",
    }


def enrollment_month_financial_snapshot(enrollment: Enrollment, month: date) -> dict:
    preview = tuition_month_preview(enrollment, month)
    start_date = enrollment_start_date(enrollment)
    month_start = month_first_day(month)
    month_end = month_last_day(month_start)
    period_start = max(start_date, month_start)
    lesson_dates = expected_lesson_dates_in_period(enrollment, period_start, month_end)
    lesson_count = len(lesson_dates)
    debt_amount = max(0, int(preview["fee_amount"] or 0) - int(get_month_paid(enrollment, month_start) or 0))

    return {
        "enrollment": enrollment,
        "group": getattr(enrollment, "group", None),
        "start_date": start_date,
        "lesson_pattern": preview["lesson_pattern"],
        "lesson_pattern_label": preview["lesson_pattern_label"],
        "lesson_pattern_hint": preview.get("lesson_pattern_hint", ""),
        "lesson_count": lesson_count,
        "lesson_dates": lesson_dates,
        "lesson_date_labels": [lesson_date.strftime("%d.%m.%Y") for lesson_date in lesson_dates],
        "course_price": full_course_amount(enrollment),
        "course_price_display": format_money(full_course_amount(enrollment)),
        "fee_amount": int(preview["fee_amount"] or 0),
        "fee_amount_display": format_money(preview["fee_amount"]),
        "teacher_share": int(preview["teacher_share"] or 0),
        "teacher_share_display": format_money(preview["teacher_share"]),
        "center_share": int(preview["center_share"] or 0),
        "center_share_display": format_money(preview["center_share"]),
        "debt_amount": debt_amount,
        "debt_amount_display": format_money(debt_amount),
        "preview": preview,
    }


# =========================
#  TUITION MONTH HELPERS
# =========================


def is_month_closed_for_center(center, month: date) -> bool:
    from education.models import FinancialMonth

    if not center:
        return False

    month = month_first_day(month)
    return FinancialMonth.objects.filter(
        center=center,
        year=month.year,
        month=month.month,
        is_closed=True,
    ).exists()


def get_effective_month_fee(enrollment: Enrollment, month: date) -> int:
    month = month_first_day(month)
    tm = TuitionMonth.objects.filter(enrollment=enrollment, month=month).first()
    if tm:
        return tuition_month_fee(tm)
    return int(prorated_monthly_fee(enrollment, month) or 0)


def calculate_enrollment_debt_snapshots(
    enrollments: Iterable[Enrollment],
    months: Sequence[date],
    *,
    virtual_missing_months: Optional[Iterable[date]] = None,
    cumulative_up_to: Optional[date] = None,
) -> dict[int, dict]:
    """
    Read-only qarzdorlik snapshoti.

    Qarz bitta qoida bilan hisoblanadi:
      har bir enrollment + oy uchun max(0, fee - paid),
      keyin shu qiymatlar yig'iladi.

    Mavjud TuitionMonth bo'lsa, saqlangan fee ishlatiladi. Rekord bo'lmasa,
    faqat xotirada prorated fee hisoblanadi; DBga yozilmaydi.
    virtual_missing_months berilsa, virtual fee faqat shu oylar uchun ishlaydi.
    """
    enrollment_list = [enrollment for enrollment in enrollments if getattr(enrollment, "id", None)]
    month_list = [month_first_day(month) for month in months]
    month_list = list(dict.fromkeys(month_list))
    virtual_month_set = (
        None
        if virtual_missing_months is None
        else {month_first_day(month) for month in virtual_missing_months}
    )

    snapshots = {
        enrollment.id: {
            "total_fee": 0,
            "total_paid": 0,
            "debt": 0,
            "lesson_count": 0,
            "months": {},
        }
        for enrollment in enrollment_list
    }
    if not enrollment_list or not month_list:
        return snapshots

    enrollment_ids = [enrollment.id for enrollment in enrollment_list]
    fee_field = tuition_month_fee_field()

    fee_map: dict[tuple[int, date], int] = {}
    # is_deleted=True bo'lgan (o'chirilgan) TuitionMonth'lar uchun fee=0
    # virtual hisoblashni bloklaymiz: deleted_key_set'da bo'lgan oy uchun
    # prorated_monthly_fee chaqirilmaydi.
    deleted_key_set: set[tuple[int, date]] = set()
    tuition_month_ids: list[int] = []
    for row in (
        TuitionMonth.all_objects
        .filter(enrollment_id__in=enrollment_ids, month__in=month_list)
        .values("id", "enrollment_id", "month", fee_field, "is_deleted")
    ):
        key = (row["enrollment_id"], row["month"])
        if row["is_deleted"]:
            # O'chirilgan — virtual fee hisoblashni bloklash, paid ham 0
            deleted_key_set.add(key)
        else:
            fee_map[key] = int(row[fee_field] or 0)
            tuition_month_ids.append(row["id"])

    paid_map: dict[tuple[int, date], int] = {}
    if tuition_month_ids:
        for row in (
            PaymentAllocation.objects
            .filter(
                tuition_month_id__in=tuition_month_ids,
                tuition_month__is_deleted=False,
                payment__is_deleted=False,
            )
            .values("tuition_month__enrollment_id", "tuition_month__month")
            .annotate(paid=Coalesce(Sum("amount"), 0))
        ):
            key = (row["tuition_month__enrollment_id"], row["tuition_month__month"])
            paid_map[key] = int(row["paid"] or 0)

    today_month_first = date.today().replace(day=1)

    for enrollment in enrollment_list:
        enrollment_snapshot = snapshots[enrollment.id]
        for month in month_list:
            key = (enrollment.id, month)
            fee = fee_map.get(key)
            if fee is None:
                if key in deleted_key_set:
                    # O'chirilgan TuitionMonth — fee=0, virtual hisoblash yo'q
                    fee = 0
                elif virtual_month_set is None or month in virtual_month_set:
                    fee = int(prorated_monthly_fee(enrollment, month) or 0)
                else:
                    fee = 0
            else:
                # Kelajak oy DB da fee=0 saqlanib qolgan bo'lsa (masalan noto'g'ri tahrirlash),
                # real kurs narxini ishlatamiz — o'quvchi to'lamagan bo'lishi mumkin.
                if fee == 0 and month > today_month_first:
                    paid_check = int(paid_map.get(key, 0) or 0)
                    if paid_check == 0:
                        fee = int(prorated_monthly_fee(enrollment, month) or 0)
            paid = int(paid_map.get(key, 0) or 0)
            debt = max(0, fee - paid)
            lesson_count = tuition_month_lesson_count(enrollment, month)

            enrollment_snapshot["total_fee"] += fee
            enrollment_snapshot["total_paid"] += paid
            enrollment_snapshot["debt"] += debt
            enrollment_snapshot["lesson_count"] += lesson_count
            enrollment_snapshot["months"][month] = {
                "fee": fee,
                "paid": paid,
                "debt": debt,
                "lesson_count": lesson_count,
            }

    # ── KUMULATIV QARZ (cumulative_up_to berilganda) ──────────────────────
    # Har enrollment uchun enrollment.started_at dan cumulative_up_to gacha
    # barcha oylar bo'yicha yig'indi qarzni hisoblaymiz.
    # is_deleted=True (manual_cleared) bo'lgan oylar — fee=0 hisoblanadi.
    if cumulative_up_to is not None:
        cumulative_up_to_month = month_first_day(cumulative_up_to)

        # Barcha relevant TuitionMonth'larni bir so'rovda olamiz
        cum_fee_field = tuition_month_fee_field()
        # Enrollment'lar uchun start oyidan cumulative_up_to gacha bo'lgan
        # barcha TuitionMonth'larni (o'chirilganlari ham) yuklaymiz
        all_cum_tms: dict[tuple[int, date], tuple[int, bool]] = {}  # (enr_id, month) -> (fee, is_deleted)
        for row in (
            TuitionMonth.all_objects
            .filter(enrollment_id__in=enrollment_ids, month__lte=cumulative_up_to_month)
            .values("enrollment_id", "month", cum_fee_field, "is_deleted")
        ):
            key = (row["enrollment_id"], row["month"])
            all_cum_tms[key] = (int(row[cum_fee_field] or 0), bool(row["is_deleted"]))

        # Kumulativ oylar uchun paid_map ham kerak — barcha oylar bo'yicha
        all_cum_paid: dict[tuple[int, date], int] = {}
        cum_alive_ids = [
            # Faqat is_deleted=False bo'lgan TuitionMonth id'lari kerak
        ]
        for row in (
            TuitionMonth.all_objects
            .filter(enrollment_id__in=enrollment_ids, month__lte=cumulative_up_to_month, is_deleted=False)
            .values("id", "enrollment_id", "month")
        ):
            cum_alive_ids.append((row["id"], row["enrollment_id"], row["month"]))

        if cum_alive_ids:
            tm_id_list = [x[0] for x in cum_alive_ids]
            for row in (
                PaymentAllocation.objects
                .filter(
                    tuition_month_id__in=tm_id_list,
                    tuition_month__is_deleted=False,
                    payment__is_deleted=False,
                )
                .values("tuition_month__enrollment_id", "tuition_month__month")
                .annotate(paid=Coalesce(Sum("amount"), 0))
            ):
                k = (row["tuition_month__enrollment_id"], row["tuition_month__month"])
                all_cum_paid[k] = int(row["paid"] or 0)

        # credit_balance larni bir so'rovda yuklaymiz
        credit_balance_map: dict[int, int] = {}
        for row in Enrollment.objects.filter(pk__in=enrollment_ids).values("id", "credit_balance"):
            credit_balance_map[row["id"]] = int(row["credit_balance"] or 0)

        for enrollment in enrollment_list:
            enr_start = month_first_day(enrollment_start_date(enrollment))
            if enr_start > cumulative_up_to_month:
                snapshots[enrollment.id]["cumulative_debt"] = 0
                snapshots[enrollment.id]["previous_unpaid"] = 0
                snapshots[enrollment.id]["credit_balance"] = credit_balance_map.get(enrollment.id, 0)
                snapshots[enrollment.id]["net_cumulative_debt"] = 0
                continue

            cumulative_debt = 0
            cur_m = enr_start
            while cur_m <= cumulative_up_to_month:
                tm_key = (enrollment.id, cur_m)
                if tm_key in all_cum_tms:
                    tm_fee, tm_deleted = all_cum_tms[tm_key]
                    if tm_deleted:
                        # manual_cleared — bu oy 0 qarz
                        cur_m = add_month(cur_m, 1)
                        continue
                    tm_paid = all_cum_paid.get(tm_key, 0)
                    month_debt = max(0, tm_fee - tm_paid)
                else:
                    # Virtual oy: prorated hisoblash
                    month_debt = int(prorated_monthly_fee(enrollment, cur_m) or 0)
                cumulative_debt += month_debt
                cur_m = add_month(cur_m, 1)

            current_month_debt = int(snapshots[enrollment.id].get("debt", 0) or 0)
            credit = credit_balance_map.get(enrollment.id, 0)
            net_cumulative_debt = max(0, cumulative_debt - credit)
            snapshots[enrollment.id]["cumulative_debt"] = cumulative_debt
            snapshots[enrollment.id]["previous_unpaid"] = max(0, cumulative_debt - current_month_debt)
            snapshots[enrollment.id]["credit_balance"] = credit
            snapshots[enrollment.id]["net_cumulative_debt"] = net_cumulative_debt

    return snapshots

def ensure_tuition_month(enrollment: Enrollment, month: date) -> TuitionMonth:
    """
    Agar shu oy uchun TuitionMonth bo‘lmasa yaratadi.
    Fee = prorated_monthly_fee (qisman oyni hisobga oladi, cheat-proof).
    Fee 0 bo‘lib qolsa va prorated > 0 bo‘lsa -> qayta yozadi.
    """
    month = month_first_day(month)
    fee = int(prorated_monthly_fee(enrollment, month) or 0)
    fee_field = tuition_month_fee_field()

    tm, created = TuitionMonth.all_objects.get_or_create(
        enrollment=enrollment,
        month=month,
        defaults={
            "center": getattr(enrollment, "center", None),
            fee_field: fee,
        },
    )
    if not created and tm.is_deleted:
        # "manual_cleared" deb belgilangan — foydalanuvchi ataylab o'chirgan.
        # Bu holda ensure_tuition_month qayta tiklamasligi kerak.
        if getattr(tm, "deleted_reason", None) == "manual_cleared":
            return tm
        tm.restore()

    update_fields = []
    if not getattr(tm, "center_id", None) and getattr(enrollment, "center_id", None):
        tm.center = enrollment.center
        update_fields.append("center")

    cur_fee = int(getattr(tm, fee_field, 0) or 0)
    if (
        not is_month_closed_for_center(getattr(enrollment, "center", None), month)
        and cur_fee != fee
    ):
        setattr(tm, fee_field, fee)
        update_fields.append(fee_field)

    if update_fields:
        tm.save(update_fields=update_fields)

    # ── CREDIT BALANCE AUTO-APPLY ─────────────────────────────────────────────
    # Yangi TuitionMonth yaratilganda (yoki fee yangilanganda), agar enrollment'da
    # credit_balance mavjud bo'lsa, uni shu oyga avtomatik allocation sifatida yozamiz.
    # Bu overpayment (ortiqcha to'lov) ni keyingi oyga ko'chirishni ta'minlaydi.
    if created and fee > 0:
        # Enrollment'ni DB'dan yangilaymiz (credit_balance aktual bo'lsin)
        try:
            enr_fresh = Enrollment.objects.filter(pk=enrollment.pk).only("credit_balance").first()
            credit = int(getattr(enr_fresh, "credit_balance", 0) or 0) if enr_fresh else 0
        except Exception:
            credit = 0

        if credit > 0:
            use = min(fee, credit)
            # Oxirgi to'lovni topamiz (PaymentAllocation uchun payment FK kerak)
            last_payment = Payment.objects.filter(
                enrollment=enrollment,
                is_deleted=False,
            ).order_by("-id").first()
            if last_payment and use > 0:
                PaymentAllocation.objects.create(
                    center=getattr(enrollment, "center", None) or getattr(tm, "center", None),
                    payment=last_payment,
                    tuition_month=tm,
                    amount=use,
                )
                Enrollment.objects.filter(pk=enrollment.pk).update(
                    credit_balance=F("credit_balance") - use
                )

    return tm


@transaction.atomic
def reconcile_tuition_month(enrollment: Enrollment, month: date) -> TuitionMonth:
    """
    Oy oxirida (yoki qo'lda) chaqiriladi.
    TuitionMonth.fee_amount ni haqiqiy davomatga qarab qayta hisoblaydi:
      fee = min(billable_lessons × per_lesson, effective_student_payable_amount)

    - Davomat yo'q bo'lsa (fee=0) va TuitionMonth allaqachon to'langan bo'lsa,
      fee ni pastga tushirmaymiz (ma'lumotlarni yo'qotmaslik uchun).
    - Aks holda yangi fee ni yozadi.
    """
    month_start = month_first_day(month)
    new_fee = int(attendance_based_fee(enrollment, month_start) or 0)
    fee_field = tuition_month_fee_field()

    tm, created = TuitionMonth.all_objects.get_or_create(
        enrollment=enrollment,
        month=month_start,
        defaults={
            "center": getattr(enrollment, "center", None),
            fee_field: new_fee,
        },
    )
    if not created and tm.is_deleted:
        tm.restore()

    paid = get_month_paid(tm)
    current_fee = int(getattr(tm, fee_field, 0) or 0)
    update_fields = []

    if not getattr(tm, "center_id", None) and getattr(enrollment, "center_id", None):
        tm.center = enrollment.center
        update_fields.append("center")

    # Xavfsizlik: agar hech qanday davomat yo'q va oyga to'lov qilingan bo'lsa,
    # fee ni 0 ga tushirmaymiz. Admin qo'lda tekshirishi kerak.
    if new_fee == 0 and paid > 0 and current_fee > 0:
        if update_fields:
            tm.save(update_fields=update_fields)
        return tm

    if current_fee != new_fee:
        setattr(tm, fee_field, new_fee)
        update_fields.append(fee_field)

    if update_fields:
        tm.save(update_fields=update_fields)

    return tm


def ensure_all_tuition_months_since_start(enrollment: Enrollment, up_to_month: date) -> None:
    """
    Enrollment yaratilgan kundan boshlab berilgan oygacha (up_to_month)
    barcha TuitionMonth rekordlarini yaratilishini ta'minlaydi.
    """
    cur = month_first_day(enrollment_start_date(enrollment))
    final = month_first_day(up_to_month)

    # Xavfsizlik uchun max 3 yil (36 oy)
    limit = 36
    while cur <= final and limit > 0:
        ensure_tuition_month(enrollment, cur)
        cur = add_month(cur, 1)
        limit -= 1


def get_month_paid(enrollment_or_tm: Union[Enrollment, TuitionMonth], month: Optional[date] = None) -> int:
    """
    Moslik uchun 2 xil ishlaydi:
    - get_month_paid(enrollment, month)
    - get_month_paid(tm)
    """
    if isinstance(enrollment_or_tm, TuitionMonth):
        tm = enrollment_or_tm
    else:
        if month is None:
            month = timezone.localdate()
        month = month_first_day(month)
        tm = TuitionMonth.objects.filter(enrollment=enrollment_or_tm, month=month).first()
        if not tm:
            return 0

    s = PaymentAllocation.objects.filter(tuition_month=tm).aggregate(s=Sum("amount"))["s"] or 0
    return int(s)


def find_earliest_unpaid_month(enrollment: Enrollment, start_month: Optional[date] = None) -> TuitionMonth:
    """
    Eng oldingi to‘lanmagan (paid < fee) oyni topadi.
    start_month berilsa -> o‘sha oydan boshlab qidiradi.
    """
    fee_field = tuition_month_fee_field()

    if start_month is None:
        start_month = month_first_day(enrollment_start_date(enrollment))
    else:
        start_month = month_first_day(start_month)

    ensure_tuition_month(enrollment, start_month)

    months = TuitionMonth.objects.filter(enrollment=enrollment, month__gte=start_month).order_by("month")

    for tm in months:
        fee = int(getattr(tm, fee_field, 0) or 0)
        if fee <= 0:
            continue
        paid = get_month_paid(tm)
        if paid < fee:
            return tm

    last = months.last()
    next_m = add_month(last.month, 1) if last else start_month
    return ensure_tuition_month(enrollment, next_m)


def sync_tuition_fee(enrollment: Enrollment, start_month: date, new_fee: int) -> None:
    """
    enrollment kurs narhi o'zgarsa, shu oydan boshlab TuitionMonth fee larni yangilaydi.
    fee field nomi fee_amount yoki fee bo'lishi mumkin.
    """
    start_month = month_first_day(start_month)
    fee_field = tuition_month_fee_field()
    effective_amount = int(
        new_fee if new_fee is not None else effective_student_payable_amount(enrollment) or 0
    )

    existing_months = list(
        TuitionMonth.all_objects.filter(enrollment=enrollment, month__gte=start_month).order_by("month")
    )

    for tm in existing_months:
        if tm.is_deleted:
            tm.restore()
        target_fee = int(
            _prorated_monthly_fee_from_amount(enrollment, tm.month, effective_amount) or 0
        )
        update_fields = []
        if int(getattr(tm, fee_field, 0) or 0) != target_fee:
            setattr(tm, fee_field, target_fee)
            update_fields.append(fee_field)
        if not getattr(tm, "center_id", None) and getattr(enrollment, "center_id", None):
            tm.center = enrollment.center
            update_fields.append("center")
        if update_fields:
            tm.save(update_fields=update_fields)

    TuitionMonth.all_objects.update_or_create(
        enrollment=enrollment,
        month=start_month,
        defaults={
            "center": getattr(enrollment, "center", None),
            fee_field: int(
                _prorated_monthly_fee_from_amount(enrollment, start_month, effective_amount) or 0
            ),
        },
    )


# =========================
#  CORE ALLOCATION ENGINE
# =========================

def _get_payment_card_amount(p: Payment) -> int:
    if _model_has_field(Payment, "card_amount_som"):
        return int(getattr(p, "card_amount_som", 0) or 0)
    return int(getattr(p, "card_amount", 0) or 0)


def infer_payment_type(cash_amount: int, card_amount_som: int) -> str:
    cash_amount = int(cash_amount or 0)
    card_amount_som = int(card_amount_som or 0)
    if cash_amount > 0 and card_amount_som > 0:
        return "mixed"
    if card_amount_som > 0:
        return "card"
    return "cash"


def _set_payment_amounts(p: Payment, cash_amount: int, card_amount_som: int, total: int) -> None:
    update_fields = []

    if _model_has_field(Payment, "cash_amount"):
        p.cash_amount = int(cash_amount or 0)
        update_fields.append("cash_amount")

    if _model_has_field(Payment, "card_amount_som"):
        p.card_amount_som = int(card_amount_som or 0)
        update_fields.append("card_amount_som")
    elif _model_has_field(Payment, "card_amount"):
        p.card_amount = int(card_amount_som or 0)
        update_fields.append("card_amount")

    if _model_has_field(Payment, "summa"):
        p.summa = int(total or 0)
        update_fields.append("summa")

    if _model_has_field(Payment, "payment_type"):
        p.payment_type = infer_payment_type(cash_amount, card_amount_som)
        update_fields.append("payment_type")

    if update_fields:
        p.save(update_fields=update_fields)


_FUTURE_OVERFLOW_MONTH_LIMIT = 12


def _allocate_amount_forward(*, enrollment: Enrollment, payment: Payment, amount: int, start_month: date) -> None:
    """
    To'lovni `start_month` dan boshlab TuitionMonth'lar bo'ylab oldinga
    taqsimlaydi.

    Qoidalar:
      • Har oyga `min(qolgan_summa, owed=fee-paid)` yoziladi — oydagi qarzdan
        ko'p yozilmaydi.
      • Avval mavjud TuitionMonth (`is_deleted=False`)'lar bo'ylab boradi.
      • Mavjud oylar yopilgandan keyin pul qolsa — kelgusi oylar uchun
        TuitionMonth avtomatik yaratiladi (max `_FUTURE_OVERFLOW_MONTH_LIMIT`
        oy oldinga) va to'lov ularga ham oqim qiladi.
      • Limit dan keyin hali pul qolsa — qolgan qism oxirgi taqsimlangan
        oyga "credit" sifatida yoziladi.

    Stsenariylar:
      - Aprel 40k qarz + may 250k qarz, foydalanuvchi 290k to'laydi:
        aprel 40k yopiladi, may 250k yopiladi, qarzdorlar safidan chiqadi.
      - May 250k qarz, foydalanuvchi 500k to'laydi: may yopiladi, iyun uchun
        TuitionMonth yaratilib, 250k unga yoziladi (iyun ham yopiladi).
    """
    amount = int(amount or 0)
    if amount <= 0:
        return

    cur = month_first_day(start_month)
    fee_field = tuition_month_fee_field()
    payment_center = getattr(payment, "center", None) or getattr(enrollment, "center", None)
    remaining = amount

    # start_month TuitionMonth'i mavjudligi kafolatlanadi.
    ensure_tuition_month(enrollment, cur)

    months_qs = (
        TuitionMonth.objects
        .filter(enrollment=enrollment, month__gte=cur, is_deleted=False)
        .order_by("month")
    )
    months_list = list(months_qs)
    last_allocated_tm = None

    def _allocate_to_tm(tm):
        nonlocal remaining, last_allocated_tm
        # Yopiq (closed) oyga to'lov yozmaymiz — buxgalter oyni mahkamlasa,
        # o'sha oyga keyin allocation kirib hisobotni o'zgartirmasligi kerak.
        if is_month_closed_for_center(getattr(enrollment, "center", None), tm.month):
            return
        fee = int(getattr(tm, fee_field, 0) or 0)
        if fee <= 0:
            return
        paid_now = int(
            tm.allocations.filter(is_deleted=False)
            .aggregate(s=Sum("amount"))["s"] or 0
        )
        owed = max(0, fee - paid_now)
        if owed <= 0:
            return
        portion = min(remaining, owed)
        PaymentAllocation.objects.create(
            center=payment_center,
            payment=payment,
            tuition_month=tm,
            amount=portion,
        )
        remaining -= portion
        last_allocated_tm = tm

    for tm in months_list:
        if remaining <= 0:
            break
        _allocate_to_tm(tm)

    # Mavjud oylar yopilgandan keyin pul qolsa — kelgusi oylar uchun
    # TuitionMonth yaratib, allocation davom ettiriladi (max 12 oy).
    if remaining > 0:
        next_month = (
            add_month(months_list[-1].month, 1) if months_list else cur
        )
        for _ in range(_FUTURE_OVERFLOW_MONTH_LIMIT):
            if remaining <= 0:
                break
            tm = ensure_tuition_month(enrollment, next_month)
            _allocate_to_tm(tm)
            next_month = add_month(next_month, 1)

    # 12 oydan tashqari hali pul qolsa — Enrollment.credit_balance ga yoziladi.
    # Keyingi oy ensure_tuition_month chaqirilganda credit_balance avtomatik ayiriladi.
    if remaining > 0:
        Enrollment.objects.filter(pk=enrollment.pk).update(
            credit_balance=F("credit_balance") + remaining
        )



# =========================
#  CREATE PAYMENT + ALLOCATE
# =========================

@transaction.atomic
def create_payment_and_allocate(
    *,
    enrollment: Enrollment,
    created_by=None,
    cash_amount: int,
    card_amount_som: int,
    start_month: Optional[date] = None,
    paid_at=None,
    note: str = "",
    payment_type: Optional[str] = None,
) -> Payment:
    """
    Payment yaratadi va pullarni oylar bo‘yicha taqsimlaydi:
    - start_month berilsa: o‘sha oydan boshlab ketma-ket taqsimlaydi
    - start_month bo‘lmasa: joriy oy (oy boshidan) boshlab
    """
    cash_amount = int(cash_amount or 0)
    card_amount_som = int(card_amount_som or 0)
    total = cash_amount + card_amount_som
    if total <= 0:
        raise ValueError("To‘lov summasi 0 bo‘lishi mumkin emas")

    # Multi-tenant himoyasi: created_by foydalanuvchining markazi enrollment
    # markazi bilan mos kelishi kerak (yoki superuser).
    enr_center_id = getattr(enrollment, "center_id", None)
    if created_by is not None and enr_center_id is not None:
        actor_center_id = getattr(created_by, "center_id", None)
        if (
            not getattr(created_by, "is_superuser", False)
            and actor_center_id is not None
            and actor_center_id != enr_center_id
        ):
            raise ValueError(
                "Boshqa markaz enrollment'iga to'lov yozish mumkin emas."
            )

    if paid_at is None:
        paid_at = timezone.now()
    elif isinstance(paid_at, date) and not isinstance(paid_at, datetime):
        paid_at = datetime.combine(paid_at, datetime.min.time())

    if timezone.is_naive(paid_at):
        paid_at = timezone.make_aware(paid_at, timezone.get_current_timezone())

    local_paid_at = timezone.localtime(paid_at)

    _center = getattr(enrollment, "center", None)
    _explicit_start = start_month is not None

    if start_month is None:
        tm_earliest = find_earliest_unpaid_month(enrollment)
        start_month = tm_earliest.month
        # Agar eng eski oy yopiq bo'lsa — birinchi ochiq oyga o'tamiz
        _today_month = month_first_day(timezone.localdate())
        while is_month_closed_for_center(_center, start_month) and start_month <= _today_month:
            start_month = add_month(start_month, 1)
    else:
        start_month = month_first_day(start_month)

    # Faqat foydalanuvchi aniq yopiq oyni ko'rsatgan holda bloklaymiz.
    # Auto-detect da yopiq oylarni yuqorida o'tkazib ketamiz.
    if _explicit_start and is_month_closed_for_center(_center, start_month):
        raise ValueError(
            f"{start_month:%Y-%m} oyi mahkam (closed). Bu oyga to'lov yozish mumkin emas."
        )

    # Payment CREATE (robust)
    kwargs = {}

    if _model_has_field(Payment, "enrollment"):
        kwargs["enrollment"] = enrollment
    if _model_has_field(Payment, "student"):
        kwargs["student"] = enrollment.student
    if _model_has_field(Payment, "group"):
        kwargs["group"] = enrollment.group
    # center: enrollment.center → group.center zanjiridan aniqlaymiz
    if _model_has_field(Payment, "center"):
        _enr_center = getattr(enrollment, "center", None) or getattr(
            getattr(enrollment, "group", None), "center", None
        )
        if _enr_center:
            kwargs["center"] = _enr_center

    if _model_has_field(Payment, "cash_amount"):
        kwargs["cash_amount"] = cash_amount

    if _model_has_field(Payment, "card_amount_som"):
        kwargs["card_amount_som"] = card_amount_som
    elif _model_has_field(Payment, "card_amount"):
        kwargs["card_amount"] = card_amount_som

    if _model_has_field(Payment, "summa"):
        kwargs["summa"] = total

    if _model_has_field(Payment, "payment_type"):
        kwargs["payment_type"] = payment_type or infer_payment_type(cash_amount, card_amount_som)

    if _model_has_field(Payment, "paid_at"):
        kwargs["paid_at"] = local_paid_at
    else:
        if _model_has_field(Payment, "paid_date"):
            kwargs["paid_date"] = local_paid_at.date()
        if _model_has_field(Payment, "paid_time"):
            kwargs["paid_time"] = local_paid_at.time().replace(microsecond=0)
        if _model_has_field(Payment, "sana"):
            kwargs["sana"] = local_paid_at.date()
        if _model_has_field(Payment, "vaqt"):
            kwargs["vaqt"] = local_paid_at.time().replace(microsecond=0)

    if created_by and _model_has_field(Payment, "created_by"):
        kwargs["created_by"] = created_by

    if _model_has_field(Payment, "note"):
        kwargs["note"] = note

    payment = Payment.objects.create(**kwargs)

    _allocate_amount_forward(enrollment=enrollment, payment=payment, amount=total, start_month=start_month)

    return payment


# =========================
#  UPDATE PAYMENT + REALLOCATE
# =========================

@transaction.atomic
def update_payment_and_reallocate(
    *,
    payment: Payment,
    cash_amount: int,
    card_amount_som: int,
    start_month: Optional[date] = None
) -> Payment:
    """
    Payment summalarini yangilaydi va allocation'larini qayta taqsimlaydi.
    start_month:
      - berilsa: shu oydan boshlab forward allocate
      - berilmasa: eng oldingi unpaid oydan boshlab
    """
    enrollment = getattr(payment, "enrollment", None)
    if not enrollment:
        raise ValueError("Payment.enrollment topilmadi (modelda enrollment FK bo‘lishi kerak).")

    cash_amount = int(cash_amount or 0)
    card_amount_som = int(card_amount_som or 0)
    new_total = cash_amount + card_amount_som
    if new_total <= 0:
        raise ValueError("To‘lov summasi 0 bo‘lishi mumkin emas")

    old_total = int(getattr(payment, "summa", 0) or (_get_payment_card_amount(payment) + int(getattr(payment, "cash_amount", 0) or 0)))

    # 1) Paymentni update
    _set_payment_amounts(payment, cash_amount, card_amount_som, new_total)

    # 2) Shu payment allocationlarini o'chiramiz
    PaymentAllocation.objects.filter(payment=payment).delete()

    # 3) start_month tanlash
    if start_month is not None:
        start_month = month_first_day(start_month)
    else:
        # eng oldingi unpaid oydan boshlaymiz (yaxshiroq)
        first_tm = TuitionMonth.objects.filter(enrollment=enrollment).order_by("month").first()
        base = first_tm.month if first_tm else month_first_day(timezone.localdate())
        start_month = find_earliest_unpaid_month(enrollment, start_month=base).month

    # 4) allocate
    _allocate_amount_forward(enrollment=enrollment, payment=payment, amount=new_total, start_month=start_month)

    return payment


# =========================
#  FULL REALLOCATE (optional)
# =========================

@transaction.atomic
def reallocate_enrollment(enrollment: Enrollment) -> None:
    """
    Enrollment bo‘yicha hamma PaymentAllocation’larni 0 dan qayta hisoblaydi.
    Paymentlar ketma-ket (eskidan yangiga) yurib chiqiladi va allocation qayta taqsimlanadi.
    """
    # Payment modelida enrollment bo'lishi kutiladi. Bo'lmasa fallback qilish mumkin.
    if not _model_has_field(Payment, "enrollment"):
        raise ValueError("Payment modelida enrollment field yo'q, reallocate_enrollment ishlamaydi.")

    PaymentAllocation.objects.filter(payment__enrollment=enrollment).delete()

    payment_fields = {f.name for f in Payment._meta.get_fields()}
    order_by = ["id"]
    if "paid_at" in payment_fields:
        order_by = ["paid_at", "id"]
    elif "sana" in payment_fields and "vaqt" in payment_fields:
        order_by = ["sana", "vaqt", "id"]
    elif "created_at" in payment_fields:
        order_by = ["created_at", "id"]

    payments = Payment.objects.filter(enrollment=enrollment).order_by(*order_by)

    # hech bo‘lmasa current oy mavjud bo‘lsin
    ensure_tuition_month(enrollment, timezone.localdate())

    # Eng eski TuitionMonth oyi: enrollment uchun bir marta hisoblanadi.
    # Har payment'da qayta hisoblamaymiz — base o'zgarmaydi, faqat
    # find_earliest_unpaid har safar yangi "eng eski qarz"ni topadi
    # (chunki oldingi payment yopgan oylarni o'tkazib yuboradi).
    first_tm = TuitionMonth.objects.filter(enrollment=enrollment).order_by("month").first()
    base = first_tm.month if first_tm else month_first_day(timezone.localdate())

    for p in payments:
        cash = int(getattr(p, "cash_amount", 0) or 0)
        card = _get_payment_card_amount(p)
        total = cash + card
        if total <= 0:
            continue

        tm = find_earliest_unpaid_month(enrollment, start_month=base)
        _allocate_amount_forward(enrollment=enrollment, payment=p, amount=total, start_month=tm.month)


@transaction.atomic
def auto_net_student_credits(student) -> None:
    """
    Automagically net out a student's cross-group credit balances and unpaid debts.
    If Enrollment A has credit_balance > 0, and Enrollment B has unpaid TuitionMonth records,
    we transfer the credit to pay off the debt on Enrollment B.
    """
    # 1. Fetch active enrollments
    enrollments = list(
        Enrollment.objects.filter(
            student=student,
            is_active=True,
            group__is_deleted=False,
            group__is_archived=False,
        )
    )
    if len(enrollments) < 2:
        return

    # 2. Identify sources of credit (credit_balance > 0)
    credit_sources = [e for e in enrollments if (e.credit_balance or 0) > 0]
    if not credit_sources:
        return

    fee_field = tuition_month_fee_field()
    for source in credit_sources:
        # Get the latest payment for this source enrollment to allocate from
        latest_payment = Payment.objects.filter(enrollment=source, is_deleted=False).order_by("-id").first()
        if not latest_payment:
            continue

        # Get other active enrollments of the same student
        other_enrollments = [e for e in enrollments if e.id != source.id]
        for target in other_enrollments:
            # Find unpaid TuitionMonth records for this target
            unpaid_tms = TuitionMonth.objects.filter(
                enrollment=target,
                is_deleted=False,
            ).order_by("month")

            for tm in unpaid_tms:
                # Refresh source credit balance
                source.refresh_from_db(fields=["credit_balance"])
                source_credit = int(source.credit_balance or 0)
                if source_credit <= 0:
                    break

                # Calculate unpaid amount for this target month
                tm_fee = int(getattr(tm, fee_field, 0) or 0)
                if tm_fee <= 0:
                    continue

                tm_paid = get_month_paid(tm)
                tm_debt = max(0, tm_fee - tm_paid)
                if tm_debt <= 0:
                    continue

                # Transfer amount
                transfer_amount = min(source_credit, tm_debt)
                if transfer_amount > 0:
                    # Create allocation
                    PaymentAllocation.objects.create(
                        center=target.center,
                        payment=latest_payment,
                        tuition_month=tm,
                        amount=transfer_amount,
                    )
                    # Deduct from source credit_balance
                    Enrollment.objects.filter(pk=source.pk).update(
                        credit_balance=F("credit_balance") - transfer_amount
                    )
                    source.credit_balance = source_credit - transfer_amount

