from __future__ import annotations

import json
import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from billing.decorators import require_feature
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods

from core.tenant import get_request_center
from store.models import Yonalish

from education.models import StaffProfile, TeacherAvailability
from education.services.hr import (
    build_staff_context,
    effective_employee_active,
    ensure_staff_profile,
    filter_available_teachers,
    hr_data_storage_state,
    normalize_string_list,
    parse_full_name,
    resolve_staff_role_label,
    resolve_staff_role_value,
    serialize_employee_detail,
    serialize_employee_row,
    staff_queryset_for_center,
    teacher_is_available,
)

User = get_user_model()

ALLOWED_HR_SYSTEM_ROLES = {"teacher", "manager", "director"}


def _tenant_api_url(center, path: str) -> str:
    if center and getattr(center, "slug", ""):
        return f"/{center.slug}{path}"
    return path


def _require_hr_access(request):
    if not request.user.is_authenticated:
        raise PermissionDenied
    center = get_request_center(request)
    if request.user.is_superuser:
        if not center:
            raise PermissionDenied
        return center
    if getattr(request.user, "role", "") not in {"director", "manager"}:
        raise PermissionDenied
    if not center:
        raise PermissionDenied
    return center


def _json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body.decode("utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _parse_weekdays(request) -> list[int]:
    raw_values = list(request.GET.getlist("day"))
    if not raw_values:
        raw_single = (request.GET.get("day") or "").strip()
        if raw_single:
            raw_values = raw_single.split(",")

    weekdays: list[int] = []
    for raw in raw_values:
        cleaned = str(raw or "").strip()
        if not cleaned or not cleaned.isdigit():
            continue
        value = int(cleaned)
        if 1 <= value <= 7 and value not in weekdays:
            weekdays.append(value)
    return weekdays


def _employee_subject_choices(center) -> list[dict]:
    return [
        {"id": item.id, "name": item.nom}
        for item in Yonalish.objects.filter(center=center, is_active=True).order_by("nom")
    ]


def _employee_role_choices() -> list[dict]:
    return [
        {"value": StaffProfile.Role.TEACHER, "label": "Ustoz"},
        {"value": StaffProfile.Role.MANAGER, "label": "Manager"},
        {"value": StaffProfile.Role.ADMIN, "label": "Admin"},
        {"value": StaffProfile.Role.OTHER, "label": "Boshqa"},
    ]


_LEVEL_DEFAULTS = ["Beginner", "Elementary", "Pre-Intermediate", "Intermediate", "Upper-Intermediate", "Advanced"]
_DIRECTION_DEFAULTS = ["IELTS", "Speaking", "Grammar", "Kids", "General English", "SAT", "TOEFL"]


def _aggregate_profile_choices(center, field: str, defaults: list[str]) -> list[str]:
    if not hr_data_storage_state()["profiles"]:
        return list(defaults)
    seen: dict[str, str] = {}
    for record in StaffProfile.objects.filter(tenant=center).values_list(field, flat=True):
        for raw in record or []:
            value = str(raw or "").strip()
            if not value:
                continue
            seen.setdefault(value.casefold(), value)
    for default in defaults:
        seen.setdefault(default.casefold(), default)
    return sorted(seen.values(), key=lambda v: v.casefold())


def _employee_level_choices(center) -> list[str]:
    return _aggregate_profile_choices(center, "levels", _LEVEL_DEFAULTS)


def _employee_direction_choices(center) -> list[str]:
    return _aggregate_profile_choices(center, "directions", _DIRECTION_DEFAULTS)


def _profile_role_to_system_role(role_value: str, *, allow_other: bool = False) -> str | None:
    role_value = str(role_value or "").strip().lower()
    if role_value == StaffProfile.Role.TEACHER:
        return "teacher"
    if role_value == StaffProfile.Role.MANAGER:
        return "manager"
    if role_value == StaffProfile.Role.ADMIN:
        return "director"
    if role_value == StaffProfile.Role.OTHER and allow_other:
        return None
    return None


def _generate_unique_employee_email(center, full_name: str) -> str:
    base = slugify(full_name or "") or "employee"
    domain = slugify(getattr(center, "slug", "") or "chaqmoq") or "chaqmoq"
    while True:
        suffix = secrets.token_hex(3)
        email = f"{base}-{suffix}@{domain}.local"
        if not User.objects.filter(email=email).exists():
            return email


def _normalize_phone(value: str) -> str:
    cleaned = "".join(ch for ch in str(value or "") if ch.isdigit() or ch == "+")
    if cleaned.startswith("998") and not cleaned.startswith("+998"):
        cleaned = f"+{cleaned}"
    if cleaned and not cleaned.startswith("+"):
        cleaned = f"+{cleaned}"
    return cleaned


def _resolve_subject_ids(center, raw_subjects) -> list[int]:
    if raw_subjects is None:
        return []
    if not isinstance(raw_subjects, (list, tuple)):
        raw_subjects = str(raw_subjects).split(",")
    ids: list[int] = []
    for item in raw_subjects:
        cleaned = str(item or "").strip()
        if cleaned.isdigit():
            ids.append(int(cleaned))
    return list(
        Yonalish.objects.filter(center=center, id__in=ids).values_list("id", flat=True)
    )


def _serialize_employee_collection(center, *, users=None, now=None) -> list[dict]:
    context = build_staff_context(center, users=users)
    rows: list[dict] = []
    for user in context["users"]:
        rows.append(
            serialize_employee_row(
                user,
                profile=context["profiles"].get(user.id),
                groups=context["groups"].get(user.id, []),
                availability_slots=context["availabilities"].get(user.id, []),
                now=now,
            )
        )
    return rows


def _filter_rows_by_query(
    rows: list[dict],
    *,
    role_value: str = "",
    active_value: str = "",
    availability_value: str = "",
    level_value: str = "",
    direction_value: str = "",
    slot_day_values: list[int] | None = None,
    slot_start_time=None,
    slot_end_time=None,
    center=None,
    user_map: dict[int, User] | None = None,
    profile_map: dict[int, StaffProfile] | None = None,
    groups_map: dict[int, list] | None = None,
    availability_map: dict[int, list] | None = None,
) -> list[dict]:
    role_value = str(role_value or "").strip().lower()
    active_value = str(active_value or "").strip().lower()
    availability_value = str(availability_value or "").strip().lower()
    level_value = str(level_value or "").strip().casefold()
    direction_value = str(direction_value or "").strip().casefold()
    weekdays = slot_day_values or []

    filtered = rows
    if role_value:
        filtered = [row for row in filtered if row.get("role") == role_value]

    if active_value == "active":
        filtered = [row for row in filtered if row.get("is_active")]
    elif active_value == "inactive":
        filtered = [row for row in filtered if not row.get("is_active")]

    if level_value:
        filtered = [
            row for row in filtered
            if any(level_value == str(v or "").casefold() for v in row.get("levels", []))
        ]

    if direction_value:
        filtered = [
            row for row in filtered
            if any(direction_value == str(v or "").casefold() for v in row.get("directions", []))
        ]

    if availability_value in {"free", "busy"} and user_map and center:
        temp: list[dict] = []
        for row in filtered:
            user = user_map.get(row["id"])
            if not user or getattr(user, "role", "") != "teacher":
                if availability_value == "busy":
                    continue
                if availability_value == "free" and weekdays and slot_start_time:
                    continue
                temp.append(row)
                continue

            profile = (profile_map or {}).get(user.id)
            groups = (groups_map or {}).get(user.id, [])
            slots = (availability_map or {}).get(user.id, [])

            if weekdays and slot_start_time:
                is_free = teacher_is_available(
                    user,
                    center=center,
                    weekdays=weekdays,
                    start_time=slot_start_time,
                    end_time=slot_end_time,
                    groups=groups,
                    availability_slots=slots,
                )
            else:
                is_free = row.get("busy_state") != "busy"

            if availability_value == "free" and is_free:
                temp.append(row)
            if availability_value == "busy" and not is_free:
                temp.append(row)
        filtered = temp

    return filtered


def _get_employee_or_404(center, employee_id: int):
    queryset = staff_queryset_for_center(center)
    return get_object_or_404(queryset, pk=employee_id)


def _sync_profile_and_user(
    *,
    user,
    center,
    payload: dict,
    profile: StaffProfile | None = None,
    create: bool = False,
) -> tuple[StaffProfile, list[int]]:
    storage_state = hr_data_storage_state()
    full_name = " ".join(str(payload.get("full_name") or "").split()).strip()
    if not full_name:
        raise ValidationError("Ism familiyani kiriting.")

    phone = _normalize_phone(payload.get("phone") or "")
    position = " ".join(str(payload.get("position") or "").split()).strip()
    role_value = str(payload.get("role") or "").strip().lower()
    if not role_value:
        role_value = resolve_staff_role_value(user)

    levels = normalize_string_list(payload.get("levels"))
    directions = normalize_string_list(payload.get("directions"))
    subject_ids = _resolve_subject_ids(center, payload.get("subjects"))
    note = str(payload.get("note") or "").strip()
    hire_date = parse_date(str(payload.get("hire_date") or "").strip()) if payload.get("hire_date") else None
    profile_active = payload.get("is_active")
    is_active = bool(profile_active if profile_active is not None else True)

    ism, familya = parse_full_name(full_name)
    if ism:
        user.ism = ism
    if familya or create:
        user.familya = familya or "-"
    if phone:
        user.telefon1 = phone
        user.phone_number = phone
    user.center = center
    user.is_active = is_active
    if position:
        user.lavozim = position

    requested_system_role = str(payload.get("system_role") or "").strip().lower()
    if requested_system_role:
        if requested_system_role not in ALLOWED_HR_SYSTEM_ROLES:
            raise ValidationError("System role noto'g'ri yuborildi.")
        user.role = requested_system_role
    else:
        mapped_role = _profile_role_to_system_role(role_value, allow_other=not create)
        if mapped_role:
            user.role = mapped_role
        elif create:
            raise ValidationError("Yangi xodim uchun mos system role tanlang.")

    user.save()

    if not storage_state["profiles"]:
        return None, []

    profile = profile or ensure_staff_profile(user, center)
    profile.tenant = center
    profile.full_name = full_name
    profile.phone = phone
    profile.role = role_value or resolve_staff_role_value(user)
    profile.position = position
    profile.hire_date = hire_date
    profile.levels = levels
    profile.directions = directions
    profile.is_active = is_active
    profile.note = note
    profile.save()
    return profile, subject_ids


def _sync_teacher_availability(*, user, center, payload: dict):
    storage_state = hr_data_storage_state()
    raw_slots = payload.get("availability_slots")
    if raw_slots is None:
        return

    if not isinstance(raw_slots, list):
        raise ValidationError("availability_slots list ko'rinishida bo'lishi kerak.")

    if not storage_state["availability"]:
        return

    TeacherAvailability.objects.filter(tenant=center, teacher=user).delete()
    if getattr(user, "role", "") != "teacher":
        return

    items_to_create: list[TeacherAvailability] = []
    for raw in raw_slots:
        if not isinstance(raw, dict):
            continue
        weekday_raw = str(raw.get("weekday") or "").strip()
        start_raw = str(raw.get("start_time") or "").strip()
        end_raw = str(raw.get("end_time") or "").strip()
        slot_type = str(raw.get("type") or TeacherAvailability.Type.AVAILABLE).strip().lower()
        note = str(raw.get("note") or "").strip()

        if not weekday_raw or not weekday_raw.isdigit():
            raise ValidationError("Bandlik kuni noto'g'ri.")
        weekday = int(weekday_raw)
        if weekday < 1 or weekday > 7:
            raise ValidationError("Bandlik kuni 1-7 oralig'ida bo'lishi kerak.")

        start_time = parse_time(start_raw)
        end_time = parse_time(end_raw)
        if not start_time or not end_time:
            raise ValidationError("Bandlik uchun boshlanish va tugash vaqtini kiriting.")
        if end_time <= start_time:
            raise ValidationError("Bandlik tugash vaqti boshlanishdan keyin bo'lishi kerak.")
        if slot_type not in {TeacherAvailability.Type.AVAILABLE, TeacherAvailability.Type.BUSY}:
            raise ValidationError("Bandlik turi noto'g'ri.")

        items_to_create.append(
            TeacherAvailability(
                tenant=center,
                teacher=user,
                weekday=weekday,
                start_time=start_time,
                end_time=end_time,
                type=slot_type,
                note=note,
            )
        )

    if items_to_create:
        TeacherAvailability.objects.bulk_create(items_to_create)


@login_required
@require_feature("hr")
def hr_dashboard(request):
    center = _require_hr_access(request)
    context = {
        "api_employees_url": _tenant_api_url(center, "/api/hr/employees/"),
        "api_employee_detail_base": _tenant_api_url(center, "/api/hr/employees/0/"),
        "api_available_teachers_url": _tenant_api_url(center, "/api/hr/teachers/available/"),
        "subject_choices": _employee_subject_choices(center),
        "role_choices": _employee_role_choices(),
        "level_choices": _employee_level_choices(center),
        "direction_choices": _employee_direction_choices(center),
    }
    return render(request, "education/hr_dashboard.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def employees_api(request):
    center = _require_hr_access(request)
    storage_state = hr_data_storage_state()

    if request.method == "GET":
        query = " ".join((request.GET.get("q") or "").split()).strip()
        role_value = request.GET.get("role") or ""
        subject_id = str(request.GET.get("subject") or "").strip()
        active_value = request.GET.get("active") or ""
        availability_value = request.GET.get("availability") or ""
        level_value = request.GET.get("level") or ""
        direction_value = request.GET.get("direction") or ""
        weekdays = _parse_weekdays(request)
        start_time = parse_time(str(request.GET.get("time") or "").strip()) if request.GET.get("time") else None
        end_time = parse_time(str(request.GET.get("end_time") or "").strip()) if request.GET.get("end_time") else None

        base_qs = staff_queryset_for_center(center)
        if query:
            search_filter = (
                Q(ism__icontains=query)
                | Q(familya__icontains=query)
                | Q(telefon1__icontains=query)
                | Q(phone_number__icontains=query)
                | Q(email__icontains=query)
            )
            if storage_state["profiles"]:
                search_filter |= Q(staff_profile__full_name__icontains=query) | Q(staff_profile__phone__icontains=query)
            base_qs = base_qs.filter(search_filter).distinct()
        if subject_id.isdigit() and storage_state["profile_subjects"]:
            base_qs = base_qs.filter(staff_profile__subjects__id=int(subject_id)).distinct()

        context = build_staff_context(center, users=base_qs)
        rows = [
            serialize_employee_row(
                user,
                profile=context["profiles"].get(user.id),
                groups=context["groups"].get(user.id, []),
                availability_slots=context["availabilities"].get(user.id, []),
                now=timezone.now(),
            )
            for user in context["users"]
        ]
        user_map = {user.id: user for user in context["users"]}
        rows = _filter_rows_by_query(
            rows,
            role_value=role_value,
            active_value=active_value,
            availability_value=availability_value,
            level_value=level_value,
            direction_value=direction_value,
            slot_day_values=weekdays,
            slot_start_time=start_time,
            slot_end_time=end_time,
            center=center,
            user_map=user_map,
            profile_map=context["profiles"],
            groups_map=context["groups"],
            availability_map=context["availabilities"],
        )

        summary = {
            "total": len(rows),
            "active": sum(1 for row in rows if row["is_active"]),
            "teachers": sum(1 for row in rows if row["role"] == StaffProfile.Role.TEACHER),
            "free_now": sum(1 for row in rows if row["busy_state"] == "free"),
        }
        return JsonResponse(
            {
                "results": rows,
                "count": len(rows),
                "summary": summary,
                "meta": {
                    "storage_ready": storage_state["profiles"] and storage_state["availability"] and storage_state["profile_subjects"],
                    "storage": storage_state,
                },
            }
        )

    payload = _json_body(request) or request.POST
    full_name = " ".join(str(payload.get("full_name") or "").split()).strip()
    if not full_name:
        return JsonResponse({"error": "Ism familiyani kiriting."}, status=400)

    role_value = str(payload.get("role") or "").strip().lower()
    system_role = _profile_role_to_system_role(role_value)
    if system_role is None:
        return JsonResponse({"error": "Yangi xodim uchun Ustoz, Manager yoki Admin rolini tanlang."}, status=400)

    email = str(payload.get("email") or "").strip().lower() or _generate_unique_employee_email(center, full_name)
    if User.objects.filter(email=email).exists():
        return JsonResponse({"error": "Bu email allaqachon ishlatilgan."}, status=400)

    generated_password = str(payload.get("password") or "").strip() or secrets.token_urlsafe(8)
    ism, familya = parse_full_name(full_name)
    phone = _normalize_phone(payload.get("phone") or "")

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=generated_password,
                role=system_role,
                center=center,
                ism=ism or "Xodim",
                familya=familya or "-",
                telefon1=phone,
                phone_number=phone,
                lavozim=" ".join(str(payload.get("position") or "").split()).strip(),
                is_active=bool(payload.get("is_active", True)),
            )
            profile, subject_ids = _sync_profile_and_user(
                user=user,
                center=center,
                payload={**payload, "system_role": system_role},
                create=True,
            )
            if profile is not None and subject_ids:
                profile.subjects.set(subject_ids)
            _sync_teacher_availability(user=user, center=center, payload=payload)
    except ValidationError as exc:
        return JsonResponse({"error": exc.message}, status=400)

    profile = ensure_staff_profile(user, center) if storage_state["profiles"] else None
    if profile is not None:
        profile.subjects.set(subject_ids if subject_ids and storage_state["profile_subjects"] else [])
    detail = serialize_employee_detail(
        user,
        profile=profile,
        groups=[],
        availability_slots=list(TeacherAvailability.objects.filter(tenant=center, teacher=user).order_by("weekday", "start_time")) if storage_state["availability"] else [],
    )
    return JsonResponse(
        {
            "employee": detail,
            "credentials": {
                "email": email,
                "password": generated_password,
            },
            "meta": {
                "storage_ready": storage_state["profiles"] and storage_state["availability"] and storage_state["profile_subjects"],
                "storage": storage_state,
            },
        },
        status=201,
    )


@login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def employee_detail_api(request, employee_id: int):
    center = _require_hr_access(request)
    user = _get_employee_or_404(center, employee_id)
    storage_state = hr_data_storage_state()
    profile = ensure_staff_profile(user, center) if storage_state["profiles"] else None

    if request.method == "GET":
        context = build_staff_context(center, users=staff_queryset_for_center(center).filter(id=user.id))
        detail = serialize_employee_detail(
            user,
            profile=context["profiles"].get(user.id, profile),
            groups=context["groups"].get(user.id, []),
            availability_slots=context["availabilities"].get(user.id, []),
        )
        return JsonResponse({"employee": detail})

    if request.method == "DELETE":
        if profile is not None:
            profile.is_active = False
            profile.save(update_fields=["is_active", "updated_at"])
        user.is_active = False
        user.save(update_fields=["is_active"])
        return JsonResponse({"ok": True, "message": "Xodim noaktiv qilindi."})

    payload = _json_body(request)
    try:
        with transaction.atomic():
            profile, subject_ids = _sync_profile_and_user(
                user=user,
                center=center,
                payload=payload,
                profile=profile,
                create=False,
            )
            if profile is not None and storage_state["profile_subjects"]:
                profile.subjects.set(subject_ids if subject_ids else [])
            _sync_teacher_availability(user=user, center=center, payload=payload)
    except ValidationError as exc:
        return JsonResponse({"error": exc.message}, status=400)

    context = build_staff_context(center, users=staff_queryset_for_center(center).filter(id=user.id))
    detail = serialize_employee_detail(
        user,
        profile=context["profiles"].get(user.id, profile),
        groups=context["groups"].get(user.id, []),
        availability_slots=context["availabilities"].get(user.id, []),
    )
    return JsonResponse({"employee": detail})


@login_required
@require_GET
def available_teachers_api(request):
    center = _require_hr_access(request)
    weekdays = _parse_weekdays(request)
    start_time = parse_time(str(request.GET.get("time") or "").strip()) if request.GET.get("time") else None
    end_time = parse_time(str(request.GET.get("end_time") or "").strip()) if request.GET.get("end_time") else None
    query = " ".join((request.GET.get("q") or "").split()).strip()
    exclude_group_id = request.GET.get("exclude_group_id")
    exclude_group = int(exclude_group_id) if str(exclude_group_id or "").isdigit() else None

    results = filter_available_teachers(
        center,
        weekdays=weekdays,
        start_time=start_time,
        end_time=end_time,
        search=query,
        exclude_group_id=exclude_group,
    )
    return JsonResponse({"results": results, "count": len(results)})
