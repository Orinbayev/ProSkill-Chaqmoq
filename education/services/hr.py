from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Iterable

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models import Prefetch, Q
from django.utils import timezone

from education.models import Group, GroupSchedule, StaffProfile, TeacherAvailability

User = get_user_model()

DEFAULT_LESSON_DURATION_MINUTES = 90

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
    1: "D",
    2: "S",
    3: "Ch",
    4: "P",
    5: "J",
    6: "Sh",
    7: "Ya",
}


def hr_data_storage_state() -> dict[str, bool]:
    try:
        table_names = set(connection.introspection.table_names())
    except Exception:
        return {
            "profiles": False,
            "availability": False,
            "profile_subjects": False,
        }

    return {
        "profiles": StaffProfile._meta.db_table in table_names,
        "availability": TeacherAvailability._meta.db_table in table_names,
        "profile_subjects": StaffProfile.subjects.through._meta.db_table in table_names,
    }


def profile_subject_items(
    profile: StaffProfile | None,
    *,
    storage_state: dict[str, bool] | None = None,
):
    if profile is None or not getattr(profile, "pk", None):
        return []
    storage = storage_state or hr_data_storage_state()
    if not storage.get("profile_subjects"):
        return []
    return list(profile.subjects.all())


def parse_full_name(value: str) -> tuple[str, str]:
    parts = [item.strip() for item in str(value or "").split() if item.strip()]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def normalize_string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        raw_items = value
    else:
        raw_items = str(value).replace("\n", ",").split(",")

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = " ".join(str(item or "").split()).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def resolve_staff_role_value(user) -> str:
    role = str(getattr(user, "role", "") or "").strip().lower()
    if role == "teacher":
        return StaffProfile.Role.TEACHER
    if role == "manager":
        return StaffProfile.Role.MANAGER
    if role == "director" or getattr(user, "is_superuser", False):
        return StaffProfile.Role.ADMIN
    return StaffProfile.Role.OTHER


def resolve_staff_role_label(user, profile: StaffProfile | None = None) -> str:
    role_value = (getattr(profile, "role", "") or resolve_staff_role_value(user)).strip().lower()
    return {
        StaffProfile.Role.TEACHER: "Ustoz",
        StaffProfile.Role.MANAGER: "Manager",
        StaffProfile.Role.ADMIN: "Admin",
        StaffProfile.Role.OTHER: "Boshqa",
    }.get(role_value, "Boshqa")


def default_position_for_user(user) -> str:
    explicit = " ".join(str(getattr(user, "lavozim", "") or "").split()).strip()
    if explicit:
        return explicit
    role_value = resolve_staff_role_value(user)
    return {
        StaffProfile.Role.TEACHER: "Ustoz",
        StaffProfile.Role.MANAGER: "Manager",
        StaffProfile.Role.ADMIN: "Admin",
    }.get(role_value, "Xodim")


def default_staff_profile_payload(user, center=None) -> dict:
    tenant = center or getattr(user, "center", None)
    phone = (
        getattr(user, "telefon1", "")
        or getattr(user, "phone_number", "")
        or getattr(user, "telefon2", "")
        or ""
    )
    return {
        "tenant": tenant,
        "full_name": user.get_full_name() or getattr(user, "email", "") or "",
        "phone": phone,
        "role": resolve_staff_role_value(user),
        "position": default_position_for_user(user),
        "is_active": bool(getattr(user, "is_active", True) and not getattr(user, "is_archived", False)),
        "levels": [],
        "directions": [],
        "note": "",
    }


def ensure_staff_profile(user, center=None) -> StaffProfile:
    defaults = default_staff_profile_payload(user, center=center)
    profile, created = StaffProfile.objects.get_or_create(user=user, defaults=defaults)

    update_fields: list[str] = []
    if not profile.tenant_id and defaults["tenant"] is not None:
        profile.tenant = defaults["tenant"]
        update_fields.append("tenant")
    if created:
        return profile
    if not profile.full_name:
        profile.full_name = defaults["full_name"]
        update_fields.append("full_name")
    if not profile.phone and defaults["phone"]:
        profile.phone = defaults["phone"]
        update_fields.append("phone")
    if not profile.position and defaults["position"]:
        profile.position = defaults["position"]
        update_fields.append("position")
    if not profile.role:
        profile.role = defaults["role"]
        update_fields.append("role")
    if update_fields:
        profile.save(update_fields=update_fields)
    return profile


def effective_employee_active(user, profile: StaffProfile | None = None) -> bool:
    profile_active = True if profile is None else bool(profile.is_active)
    return bool(
        profile_active
        and getattr(user, "is_active", True)
        and not getattr(user, "is_archived", False)
        and not getattr(user, "is_deleted", False)
    )


def time_to_minutes(value: time | None) -> int:
    if value is None:
        return 0
    return (int(value.hour) * 60) + int(value.minute)


def minutes_to_time(value: int) -> time:
    normalized = max(0, min(24 * 60, int(value)))
    hours, minutes = divmod(normalized, 60)
    if hours >= 24:
        hours = 23
        minutes = 59
    return time(hour=hours, minute=minutes)


def resolve_end_time(start_time: time | None, end_time: time | None) -> time | None:
    if start_time is None:
        return None
    if end_time is not None:
        return end_time
    fallback_dt = datetime.combine(date.today(), start_time) + timedelta(minutes=DEFAULT_LESSON_DURATION_MINUTES)
    return fallback_dt.time()


def interval_tuple(start_time: time | None, end_time: time | None) -> tuple[int, int]:
    resolved_end = resolve_end_time(start_time, end_time)
    return time_to_minutes(start_time), time_to_minutes(resolved_end)


def merge_intervals(intervals: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    cleaned = sorted((max(0, start), max(0, end)) for start, end in intervals if end > start)
    if not cleaned:
        return []

    merged: list[list[int]] = [[cleaned[0][0], cleaned[0][1]]]
    for start, end in cleaned[1:]:
        last = merged[-1]
        if start <= last[1]:
            last[1] = max(last[1], end)
            continue
        merged.append([start, end])
    return [(start, end) for start, end in merged]


def subtract_intervals(
    base_intervals: Iterable[tuple[int, int]],
    blocked_intervals: Iterable[tuple[int, int]],
) -> list[tuple[int, int]]:
    remaining = merge_intervals(base_intervals)
    blocked = merge_intervals(blocked_intervals)
    if not remaining or not blocked:
        return remaining

    result: list[tuple[int, int]] = []
    for base_start, base_end in remaining:
        segments = [(base_start, base_end)]
        for block_start, block_end in blocked:
            next_segments: list[tuple[int, int]] = []
            for seg_start, seg_end in segments:
                if block_end <= seg_start or block_start >= seg_end:
                    next_segments.append((seg_start, seg_end))
                    continue
                if block_start > seg_start:
                    next_segments.append((seg_start, block_start))
                if block_end < seg_end:
                    next_segments.append((block_end, seg_end))
            segments = next_segments
            if not segments:
                break
        result.extend(segments)
    return [(start, end) for start, end in result if end > start]


def intervals_overlap(
    start_a: time | None,
    end_a: time | None,
    start_b: time | None,
    end_b: time | None,
) -> bool:
    a_start, a_end = interval_tuple(start_a, end_a)
    b_start, b_end = interval_tuple(start_b, end_b)
    return a_start < b_end and b_start < a_end


def format_time_range(start_time: time | None, end_time: time | None, *, approximate: bool = False) -> str:
    if start_time is None:
        return "—"
    resolved_end = resolve_end_time(start_time, end_time)
    start_label = start_time.strftime("%H:%M")
    end_label = resolved_end.strftime("%H:%M") if resolved_end else start_label
    suffix = " (taxminiy)" if approximate and end_time is None else ""
    return f"{start_label} - {end_label}{suffix}"


def format_minutes_range(start_minutes: int, end_minutes: int) -> str:
    start_label = minutes_to_time(start_minutes).strftime("%H:%M")
    end_label = minutes_to_time(end_minutes).strftime("%H:%M")
    return f"{start_label} - {end_label}"


def staff_queryset_for_center(center):
    return (
        User.objects.filter(center=center)
        .exclude(role__in=("student", "parent"))
        .filter(is_deleted=False)
        .order_by("ism", "familya", "id")
    )


def build_staff_context(center, *, users=None) -> dict:
    user_qs = users or staff_queryset_for_center(center)
    user_list = list(user_qs)
    user_ids = [user.id for user in user_list]
    storage_state = hr_data_storage_state()

    profile_map: dict[int, StaffProfile] = {}
    if storage_state["profiles"]:
        profiles_qs = StaffProfile.objects.filter(tenant=center, user_id__in=user_ids).select_related("user", "tenant")
        if storage_state["profile_subjects"]:
            profiles_qs = profiles_qs.prefetch_related("subjects")
        profile_map = {profile.user_id: profile for profile in profiles_qs}

    group_prefetch = Prefetch(
        "schedules",
        queryset=GroupSchedule.objects.filter(center=center).order_by("weekday", "start_time"),
    )
    groups = (
        Group.objects.filter(
            center=center,
            oqituvchi_id__in=user_ids,
            is_archived=False,
            is_closed=False,
        )
        .select_related("category_obj")
        .prefetch_related(group_prefetch)
        .order_by("nom", "id")
    )
    groups_map: dict[int, list[Group]] = defaultdict(list)
    for group in groups:
        if group.oqituvchi_id:
            groups_map[group.oqituvchi_id].append(group)

    availability_map: dict[int, list[TeacherAvailability]] = defaultdict(list)
    if storage_state["availability"]:
        availability_slots = (
            TeacherAvailability.objects.filter(tenant=center, teacher_id__in=user_ids)
            .order_by("weekday", "start_time", "id")
        )
        for slot in availability_slots:
            availability_map[slot.teacher_id].append(slot)

    return {
        "users": user_list,
        "profiles": profile_map,
        "groups": groups_map,
        "availabilities": availability_map,
        "storage": storage_state,
    }


def teacher_busy_now(teacher, *, groups=None, availability_slots=None, now=None) -> bool:
    if getattr(teacher, "role", "") != "teacher":
        return False
    current_time = timezone.localtime(now or timezone.now())
    weekday = current_time.isoweekday()
    time_value = current_time.time().replace(second=0, microsecond=0)
    probe_end = (datetime.combine(date.today(), time_value) + timedelta(minutes=1)).time()

    for group in groups or []:
        for schedule in getattr(group, "schedules").all():
            if schedule.weekday != weekday:
                continue
            if intervals_overlap(time_value, probe_end, schedule.start_time, schedule.end_time):
                return True

    for slot in availability_slots or []:
        if slot.weekday != weekday or slot.type != TeacherAvailability.Type.BUSY:
            continue
        if intervals_overlap(time_value, probe_end, slot.start_time, slot.end_time):
            return True

    return False


def compute_today_free_label(
    teacher,
    *,
    groups=None,
    availability_slots=None,
    now=None,
) -> str:
    """Bugun uchun ustozning birinchi bo'sh oraligini qisqa label sifatida qaytaradi."""
    if getattr(teacher, "role", "") != "teacher":
        return ""
    current_time = timezone.localtime(now or timezone.now())
    weekday = current_time.isoweekday()

    available_today = [
        slot for slot in (availability_slots or [])
        if slot.weekday == weekday and slot.type == TeacherAvailability.Type.AVAILABLE
    ]

    busy_intervals: list[tuple[int, int]] = []
    for group in groups or []:
        for schedule in getattr(group, "schedules").all():
            if schedule.weekday != weekday:
                continue
            busy_intervals.append(interval_tuple(schedule.start_time, schedule.end_time))
    for slot in (availability_slots or []):
        if slot.weekday == weekday and slot.type == TeacherAvailability.Type.BUSY:
            busy_intervals.append(interval_tuple(slot.start_time, slot.end_time))

    busy_intervals = merge_intervals(busy_intervals)

    if not available_today:
        # No declared availability today — derive from busy intervals
        if busy_intervals:
            return "Bugun band"
        return "Jadval kiritilmagan"

    free_pieces: list[tuple[int, int]] = []
    for slot in available_today:
        free_pieces.extend(
            subtract_intervals([interval_tuple(slot.start_time, slot.end_time)], busy_intervals)
        )
    free_pieces = merge_intervals(free_pieces)

    if not free_pieces:
        return "Bugun band"

    # Prefer next upcoming interval relative to "now"; otherwise the first one
    now_minutes = current_time.hour * 60 + current_time.minute
    upcoming = [piece for piece in free_pieces if piece[1] > now_minutes]
    target = upcoming[0] if upcoming else free_pieces[0]
    return f"Bo'sh: {format_minutes_range(target[0], target[1])}"


def build_weekly_schedule(
    teacher,
    *,
    groups: Iterable[Group] | None = None,
    availability_slots: Iterable[TeacherAvailability] | None = None,
) -> list[dict]:
    teacher_groups = list(groups or [])
    slots = list(availability_slots or [])

    schedules_by_day: dict[int, list[dict]] = {day: [] for day in WEEKDAY_LABELS}
    group_busy_by_day: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for group in teacher_groups:
        for schedule in getattr(group, "schedules").all():
            approximate = schedule.end_time is None
            schedules_by_day[schedule.weekday].append(
                {
                    "group_id": group.id,
                    "group_name": group.nom,
                    "course_name": getattr(getattr(group, "category_obj", None), "name", "") or "",
                    "time_range": format_time_range(schedule.start_time, schedule.end_time, approximate=approximate),
                    "start_time": schedule.start_time.strftime("%H:%M") if schedule.start_time else "",
                    "end_time": resolve_end_time(schedule.start_time, schedule.end_time).strftime("%H:%M")
                    if schedule.start_time
                    else "",
                    "room": schedule.room or "",
                    "approximate": approximate,
                }
            )
            group_busy_by_day[schedule.weekday].append(interval_tuple(schedule.start_time, schedule.end_time))

    slots_by_day: dict[int, list[TeacherAvailability]] = defaultdict(list)
    for slot in slots:
        slots_by_day[slot.weekday].append(slot)

    weekly_data: list[dict] = []
    for weekday, label in WEEKDAY_LABELS.items():
        available_intervals: list[tuple[int, int]] = []
        busy_intervals: list[tuple[int, int]] = list(group_busy_by_day.get(weekday, []))
        available_slots: list[dict] = []
        busy_slots: list[dict] = []

        for slot in slots_by_day.get(weekday, []):
            interval = interval_tuple(slot.start_time, slot.end_time)
            payload = {
                "id": slot.id,
                "type": slot.type,
                "type_label": slot.get_type_display(),
                "time_range": format_time_range(slot.start_time, slot.end_time),
                "start_time": slot.start_time.strftime("%H:%M"),
                "end_time": slot.end_time.strftime("%H:%M"),
                "note": slot.note or "",
            }
            if slot.type == TeacherAvailability.Type.AVAILABLE:
                available_intervals.append(interval)
                available_slots.append(payload)
            else:
                busy_intervals.append(interval)
                busy_slots.append(payload)

        free_slots = [
            {
                "time_range": format_minutes_range(start, end),
                "start_time": minutes_to_time(start).strftime("%H:%M"),
                "end_time": minutes_to_time(end).strftime("%H:%M"),
            }
            for start, end in subtract_intervals(available_intervals, busy_intervals)
        ] if available_intervals else []

        weekly_data.append(
            {
                "weekday": weekday,
                "weekday_label": label,
                "groups": schedules_by_day.get(weekday, []),
                "available_slots": available_slots,
                "busy_slots": busy_slots,
                "free_slots": free_slots,
                "has_defined_availability": bool(available_slots),
            }
        )

    return weekly_data


def teacher_is_available(
    teacher,
    *,
    center,
    weekdays: Iterable[int],
    start_time: time | None,
    end_time: time | None = None,
    exclude_group_id: int | None = None,
    groups: Iterable[Group] | None = None,
    availability_slots: Iterable[TeacherAvailability] | None = None,
) -> bool:
    if getattr(teacher, "role", "") != "teacher":
        return False
    profile = getattr(teacher, "staff_profile", None)
    if profile and not effective_employee_active(teacher, profile):
        return False
    if not getattr(teacher, "is_active", True) or getattr(teacher, "is_archived", False):
        return False
    if start_time is None:
        return True

    day_values = [int(value) for value in weekdays if int(value) in WEEKDAY_LABELS]
    if not day_values:
        return True

    if groups is None:
        groups = (
            Group.objects.filter(
                center=center,
                oqituvchi=teacher,
                is_archived=False,
                is_closed=False,
            )
            .prefetch_related(
                Prefetch(
                    "schedules",
                    queryset=GroupSchedule.objects.filter(center=center).order_by("weekday", "start_time"),
                )
            )
            .order_by("id")
        )
    if availability_slots is None:
        availability_slots = TeacherAvailability.objects.filter(tenant=center, teacher=teacher).order_by("weekday", "start_time", "id")

    teacher_groups = [group for group in groups if not exclude_group_id or group.id != exclude_group_id]
    slots = list(availability_slots)

    for weekday in day_values:
        day_available_slots = [
            slot for slot in slots if slot.weekday == weekday and slot.type == TeacherAvailability.Type.AVAILABLE
        ]
        day_busy_slots = [
            slot for slot in slots if slot.weekday == weekday and slot.type == TeacherAvailability.Type.BUSY
        ]

        if day_available_slots and not any(
            time_to_minutes(slot.start_time) <= time_to_minutes(start_time)
            and time_to_minutes(resolve_end_time(start_time, end_time)) <= time_to_minutes(slot.end_time)
            for slot in day_available_slots
        ):
            return False

        if any(intervals_overlap(start_time, end_time, slot.start_time, slot.end_time) for slot in day_busy_slots):
            return False

        for group in teacher_groups:
            for schedule in getattr(group, "schedules").all():
                if schedule.weekday != weekday:
                    continue
                if intervals_overlap(start_time, end_time, schedule.start_time, schedule.end_time):
                    return False

    return True


def serialize_availability_slot(slot: TeacherAvailability) -> dict:
    return {
        "id": slot.id,
        "weekday": slot.weekday,
        "weekday_label": WEEKDAY_LABELS.get(slot.weekday, ""),
        "start_time": slot.start_time.strftime("%H:%M"),
        "end_time": slot.end_time.strftime("%H:%M"),
        "time_range": format_time_range(slot.start_time, slot.end_time),
        "type": slot.type,
        "type_label": slot.get_type_display(),
        "note": slot.note or "",
    }


def serialize_employee_row(
    user,
    *,
    profile: StaffProfile | None = None,
    groups: Iterable[Group] | None = None,
    availability_slots: Iterable[TeacherAvailability] | None = None,
    now=None,
) -> dict:
    storage_state = hr_data_storage_state()
    active = effective_employee_active(user, profile)
    teacher_groups = list(groups or [])
    availability_items = list(availability_slots or [])
    subject_items = profile_subject_items(profile, storage_state=storage_state)
    busy_now = teacher_busy_now(user, groups=teacher_groups, availability_slots=availability_items, now=now)
    today_free_label = compute_today_free_label(
        user, groups=teacher_groups, availability_slots=availability_items, now=now
    )
    role_label = resolve_staff_role_label(user, profile)
    day_values = sorted(
        {
            int(schedule.weekday)
            for group in teacher_groups
            for schedule in getattr(group, "schedules").all()
            if int(getattr(schedule, "weekday", 0) or 0) in WEEKDAY_SHORT_LABELS
        }
        | {
            int(slot.weekday)
            for slot in availability_items
            if int(getattr(slot, "weekday", 0) or 0) in WEEKDAY_SHORT_LABELS
        }
    )

    return {
        "id": user.id,
        "full_name": (
            getattr(profile, "full_name", "")
            or user.get_full_name()
            or getattr(user, "email", "")
            or ""
        ),
        "phone": (
            getattr(profile, "phone", "")
            or getattr(user, "telefon1", "")
            or getattr(user, "phone_number", "")
            or ""
        ),
        "role": getattr(profile, "role", "") or resolve_staff_role_value(user),
        "role_label": role_label,
        "position": getattr(profile, "position", "") or default_position_for_user(user),
        "hire_date": profile.hire_date.isoformat() if profile and profile.hire_date else "",
        "subjects": [{"id": item.id, "name": item.nom} for item in subject_items],
        "subject_names": [item.nom for item in subject_items],
        "groups_count": len(teacher_groups),
        "busy_state": "busy" if busy_now else ("free" if getattr(user, "role", "") == "teacher" else "na"),
        "busy_state_label": "Band" if busy_now else ("Bo'sh" if getattr(user, "role", "") == "teacher" else "—"),
        "is_active": active,
        "active_label": "Aktiv" if active else "Noaktiv",
        "note": getattr(profile, "note", "") or "",
        "levels": list(getattr(profile, "levels", []) or []),
        "directions": list(getattr(profile, "directions", []) or []),
        "today_free_label": today_free_label,
        "schedule_days": [
            {
                "weekday": day_value,
                "label": WEEKDAY_SHORT_LABELS.get(day_value, ""),
                "full_label": WEEKDAY_LABELS.get(day_value, ""),
            }
            for day_value in day_values
        ],
    }


def serialize_employee_detail(
    user,
    *,
    profile: StaffProfile | None = None,
    groups: Iterable[Group] | None = None,
    availability_slots: Iterable[TeacherAvailability] | None = None,
) -> dict:
    row = serialize_employee_row(
        user,
        profile=profile,
        groups=groups,
        availability_slots=availability_slots,
    )
    teacher_groups = list(groups or [])
    slots = list(availability_slots or [])
    row.update(
        {
            "email": getattr(user, "email", "") or "",
            "system_role": getattr(user, "role", "") or "",
            "system_role_label": getattr(user, "get_role_display", lambda: getattr(user, "role", ""))(),
            "current_groups": [
                {
                    "id": group.id,
                    "name": group.nom,
                    "course_name": getattr(getattr(group, "category_obj", None), "name", "") or "",
                }
                for group in teacher_groups
            ],
            "weekly_schedule": build_weekly_schedule(user, groups=teacher_groups, availability_slots=slots),
            "availability_slots": [serialize_availability_slot(slot) for slot in slots],
            "hire_date_label": profile.hire_date.strftime("%d.%m.%Y") if profile and profile.hire_date else "—",
            "created_at": profile.created_at.isoformat() if profile and profile.created_at else "",
            "updated_at": profile.updated_at.isoformat() if profile and profile.updated_at else "",
        }
    )
    return row


def filter_available_teachers(
    center,
    *,
    weekdays: Iterable[int],
    start_time: time | None,
    end_time: time | None = None,
    search: str = "",
    exclude_group_id: int | None = None,
) -> list[dict]:
    storage_state = hr_data_storage_state()
    teacher_qs = staff_queryset_for_center(center).filter(role="teacher")
    if search:
        search_filter = (
            Q(ism__icontains=search)
            | Q(familya__icontains=search)
            | Q(telefon1__icontains=search)
            | Q(email__icontains=search)
        )
        if storage_state["profiles"]:
            search_filter |= Q(staff_profile__full_name__icontains=search) | Q(staff_profile__phone__icontains=search)
        teacher_qs = teacher_qs.filter(search_filter).distinct()

    context = build_staff_context(center, users=teacher_qs)
    results: list[dict] = []
    for teacher in context["users"]:
        profile = context["profiles"].get(teacher.id)
        if not effective_employee_active(teacher, profile):
            continue
        teacher_groups = context["groups"].get(teacher.id, [])
        slots = context["availabilities"].get(teacher.id, [])
        if not teacher_is_available(
            teacher,
            center=center,
            weekdays=weekdays,
            start_time=start_time,
            end_time=end_time,
            exclude_group_id=exclude_group_id,
            groups=teacher_groups,
            availability_slots=slots,
        ):
            continue
        results.append(
            {
                "id": teacher.id,
                "name": (
                    getattr(profile, "full_name", "")
                    or teacher.get_full_name()
                    or getattr(teacher, "email", "")
                    or ""
                ),
                "phone": (
                    getattr(profile, "phone", "")
                    or getattr(teacher, "telefon1", "")
                    or getattr(teacher, "phone_number", "")
                    or ""
                ),
                "subjects": [item.nom for item in profile_subject_items(profile, storage_state=storage_state)],
                "group_count": len(teacher_groups),
                "teacher_share_percent": int(getattr(teacher, "oqituvchi_foizi", 0) or 0),
            }
        )
    return results
