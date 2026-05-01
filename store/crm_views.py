from __future__ import annotations

import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from billing.decorators import require_feature
from billing.services import get_feature_flags
from core.tenant import get_request_center, require_center

from .forms import (
    LeadApiFilterForm,
    LeadApiForm,
    LeadAssignLeadGroupForm,
    LeadConvertForm,
    LeadForm,
    LeadGroupConvertForm,
    LeadGroupForm,
    LeadStatusForm,
    LeadSubjectForm,
    TrialLessonForm,
)
from .lead_services import (
    build_dynamic_lead_status_choices,
    confirm_lead,
    convert_lead_to_student_safe,
    ensure_default_lead_subjects,
    follow_up_queryset,
    get_or_create_pipeline_status,
    handle_lead_save_audit,
    is_lead_confirmed,
    log_lead_activity,
    resolve_dynamic_status_value,
    resolve_status_code,
    sync_lead_confirmation_state,
    sync_lead_group_status,
    sync_lead_group_statuses,
)
from .models import Lead, LeadActivity, LeadGroup, LeadStatus, TrialLesson, Yonalish
from .serializers import (
    serialize_department,
    serialize_group,
    serialize_lead,
    serialize_lead_detail,
    serialize_lead_group,
    serialize_lead_group_detail,
    serialize_lead_group_member,
    serialize_lead_group_option,
    serialize_lead_status,
    serialize_lead_status_choices,
    serialize_lead_subject,
    serialize_manager,
)
from .trial_services import build_trial_analytics, handle_trial_created, handle_trial_updated


def _lead_staff_guard(request):
    if request.user.is_superuser or request.user.is_staff:
        return
    if getattr(request.user, "role", "") not in ("manager", "director", "admin"):
        raise PermissionDenied


def _get_center_or_redirect(request):
    try:
        return require_center(request)
    except Exception:
        messages.error(request, "Markaz aniqlanmadi.")
        return None


def _base_leads_qs(center, *, archived=False):
    queryset = (
        Lead.objects.filter(center=center, is_archived=archived)
        .select_related(
            "status",
            "manba",
            "yonalish",
            "assigned_manager",
            "converted_user",
            "confirmed_by",
            "lead_group",
        )
    )
    if archived:
        return queryset.order_by("-archived_at", "-updated_at", "-id")
    return queryset.order_by("-qoshilgan_sana", "-id")


def _base_lead_groups_qs(center, *, archived=False):
    queryset = (
        LeadGroup.objects.filter(center=center, is_archived=archived)
        .select_related("subject", "department", "created_by", "converted_group")
    )
    if archived:
        return queryset.order_by("-archived_at", "-updated_at", "-id")
    return queryset.order_by("-created_at", "-id")


def _lead_group_members_qs(center, lead_group):
    return (
        Lead.objects.filter(center=center, lead_group=lead_group)
        .select_related("status", "yonalish", "assigned_manager", "lead_group")
        .order_by("-added_to_group_at", "-qoshilgan_sana", "-id")
    )


def _query_bool(request, key: str, default: bool = False) -> bool:
    raw_value = str(request.GET.get(key, "")).strip().lower()
    if raw_value in {"1", "true", "yes", "y"}:
        return True
    if raw_value in {"0", "false", "no", "n"}:
        return False
    return default


def _json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _manager_options(center):
    return [
        serialize_manager(manager)
        for manager in request_user_model().objects.filter(
            center=center,
            role="manager",
            is_archived=False,
        ).order_by("ism", "familya")
    ]


def request_user_model():
    return Lead._meta.get_field("assigned_manager").remote_field.model


def _teacher_options(center):
    return [
        serialize_manager(teacher)
        for teacher in request_user_model().objects.filter(
            center=center,
            role="teacher",
            is_archived=False,
        ).order_by("ism", "familya")
    ]


def _department_options(center):
    from education.models import Category

    return [
        serialize_department(category)
        for category in Category.objects.filter(center=center).order_by("name")
    ]


def _lead_group_options(center):
    return [serialize_lead_group_option(item) for item in _base_lead_groups_qs(center, archived=False)]


def _resolve_default_lead_manager(center, actor):
    manager_queryset = request_user_model().objects.filter(
        center=center,
        role="manager",
        is_archived=False,
    ).order_by("ism", "familya", "id")
    if actor and getattr(actor, "role", "") == "manager":
        return manager_queryset.filter(pk=actor.pk).first()
    return manager_queryset.first()


def _tenant_url(center, path: str) -> str:
    if not center or not getattr(center, "slug", ""):
        return path
    return f"/{center.slug}{path}"


def _resolve_teacher_share_percent(teacher) -> int:
    try:
        share = int(getattr(teacher, "oqituvchi_foizi", 0) or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, share))


def _can_override_teacher_share(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_superuser)


def _parse_teacher_share_override(raw_value) -> int | None:
    if raw_value in (None, ""):
        return None
    try:
        share = int(str(raw_value).strip())
    except (TypeError, ValueError):
        raise ValueError("O‘qituvchi ulushi 0 dan 100 gacha bo‘lgan son bo‘lishi kerak.")
    if share < 0 or share > 100:
        raise ValueError("O‘qituvchi ulushi 0 dan 100 gacha bo‘lishi kerak.")
    return share


def _teacher_share_error_payload(message: str) -> dict:
    return {
        "teacher_share": [
            {
                "message": message,
                "code": "invalid",
            }
        ]
    }


def _lead_subject_choices(center):
    ensure_default_lead_subjects(center)
    return [
        serialize_lead_subject(subject)
        for subject in Yonalish.objects.filter(center=center, is_active=True).order_by("nom")
    ]


def _lead_status_choices(center):
    return serialize_lead_status_choices(center)


def _lead_group_payload(center, *, lead_group=None, archived=False, status_code=200):
    queryset = _base_lead_groups_qs(center, archived=archived)
    results = [serialize_lead_group(item) for item in queryset]
    payload = {
        "results": results,
        "count": len(results),
        "total_count": len(results),
        "archived": bool(archived),
        "options": _lead_group_options(center),
    }
    if lead_group is not None:
        payload["lead_group"] = serialize_lead_group(lead_group)
    return JsonResponse(payload, status=status_code)


def _subject_response_payload(center, *, subject=None, status_code=200):
    results = _lead_subject_choices(center)
    payload = {
        "results": results,
        "count": len(results),
    }
    if subject is not None:
        payload["subject"] = serialize_lead_subject(subject)
    return JsonResponse(payload, status=status_code)


def _status_payload_for_instance(center, status_obj):
    choices = _lead_status_choices(center)
    payload = next((item for item in choices if item.get("id") == status_obj.id), None)
    if payload:
        return payload, choices

    matched_value = f"custom:{status_obj.id}"
    resolved_code = resolve_status_code(status_obj)
    if resolved_code == LeadStatus.Code.NEW:
        matched_value = Lead.PipelineStatus.NEW
    elif resolved_code in {LeadStatus.Code.CONTACTED, LeadStatus.Code.NO_ANSWER}:
        matched_value = Lead.PipelineStatus.CONTACTED
    elif resolved_code in {LeadStatus.Code.TRIAL_SCHEDULED, LeadStatus.Code.TRIAL_ATTENDED}:
        matched_value = Lead.PipelineStatus.TRIAL
    elif resolved_code == LeadStatus.Code.REGISTERED:
        matched_value = Lead.PipelineStatus.CONFIRMED
    elif resolved_code == LeadStatus.Code.LOST:
        matched_value = Lead.PipelineStatus.CANCELED

    return (
        serialize_lead_status(
            {
                "id": status_obj.id,
                "value": matched_value,
                "label": status_obj.nom,
                "tone": "gray",
                "kind": "custom" if matched_value.startswith("custom:") else "default",
                "code": status_obj.code,
                "is_active": bool(status_obj.is_active),
            }
        ),
        choices,
    )


def _lead_api_access(request):
    try:
        _lead_staff_guard(request)
    except PermissionDenied:
        return None, JsonResponse({"error": "Sizda leadlarni ko‘rish huquqi yo‘q."}, status=403)

    center = get_request_center(request)
    if not center:
        return None, JsonResponse({"error": "Markaz aniqlanmadi."}, status=400)

    if not request.user.is_superuser:
        flags = get_feature_flags(center)
        if "leads" not in flags:
            return None, JsonResponse({"error": "Leadlar moduli bu markaz uchun faol emas."}, status=403)

    return center, None


def _page_link(request, *, page_number: int | None, center) -> str | None:
    if not page_number:
        return None
    params = request.GET.copy()
    params["page"] = page_number
    return f"{_tenant_url(center, reverse('store:leads_api'))}?{params.urlencode()}"


def _apply_lead_filters(qs, cleaned_data: dict):
    q = (cleaned_data.get("q") or "").strip()
    subjects = cleaned_data.get("subjects") or []
    statuses = cleaned_data.get("statuses") or []
    date_preset = cleaned_data.get("date_preset") or ""
    date_from = cleaned_data.get("date_from")
    date_to = cleaned_data.get("date_to")

    if subjects:
        qs = qs.filter(yonalish__in=subjects)

    if statuses:
        status_q = Q()
        custom_status_ids = []
        for item in statuses:
            if str(item).startswith("custom:"):
                raw_id = str(item).split(":", 1)[1].strip()
                if raw_id.isdigit():
                    custom_status_ids.append(int(raw_id))
                continue
            if item == Lead.PipelineStatus.NEW:
                status_q |= (
                    Q(status__code=LeadStatus.Code.NEW)
                    | Q(status__isnull=True)
                    | Q(status__code="")
                ) & Q(converted_to_student=False)
            elif item == Lead.PipelineStatus.CONTACTED:
                status_q |= Q(status__code__in=[LeadStatus.Code.CONTACTED, LeadStatus.Code.NO_ANSWER], converted_to_student=False)
            elif item == Lead.PipelineStatus.TRIAL:
                status_q |= Q(status__code__in=[LeadStatus.Code.TRIAL_SCHEDULED, LeadStatus.Code.TRIAL_ATTENDED], converted_to_student=False)
            elif item == Lead.PipelineStatus.CONFIRMED:
                status_q |= Q(status__code=LeadStatus.Code.REGISTERED, converted_to_student=False)
            elif item == Lead.PipelineStatus.CANCELED:
                status_q |= Q(status__code=LeadStatus.Code.LOST, converted_to_student=False)
        if custom_status_ids:
            status_q |= Q(status_id__in=custom_status_ids, converted_to_student=False)
        qs = qs.filter(status_q)

    today = timezone.localdate()
    if date_preset == "today":
        qs = qs.filter(qoshilgan_sana__date=today)
    elif date_preset == "7":
        qs = qs.filter(qoshilgan_sana__date__gte=today - timedelta(days=6))
    elif date_preset == "30":
        qs = qs.filter(qoshilgan_sana__date__gte=today - timedelta(days=29))
    elif date_preset == "custom":
        if date_from:
            qs = qs.filter(qoshilgan_sana__date__gte=date_from)
        if date_to:
            qs = qs.filter(qoshilgan_sana__date__lte=date_to)
    else:
        if date_from:
            qs = qs.filter(qoshilgan_sana__date__gte=date_from)
        if date_to:
            qs = qs.filter(qoshilgan_sana__date__lte=date_to)

    if q:
        phone_q = (
            Q(telefon1__icontains=q)
            | Q(telefon2__icontains=q)
            | Q(parent_phone__icontains=q)
        )
        text_q = (
            Q(ism__istartswith=q)
            | Q(familya__istartswith=q)
            | Q(yonalish__nom__icontains=q)
            | Q(status__nom__icontains=q)
        )
        tokens = [token.strip() for token in q.split() if token.strip()]
        if len(tokens) > 1:
            token_q = Q()
            for token in tokens:
                token_phone_q = (
                    Q(telefon1__icontains=token)
                    | Q(telefon2__icontains=token)
                    | Q(parent_phone__icontains=token)
                )
                token_q &= (
                    Q(ism__istartswith=token)
                    | Q(familya__istartswith=token)
                    | Q(yonalish__nom__icontains=token)
                    | Q(status__nom__icontains=token)
                    | token_phone_q
                )
            qs = qs.filter(token_q)
        else:
            qs = qs.filter(text_q | phone_q)

    return qs


def _pipeline_counts(qs):
    counts = {}
    for lead in qs:
        status_value = resolve_dynamic_status_value(lead)
        counts[status_value] = counts.get(status_value, 0) + 1
    return counts


@transaction.atomic
def _convert_lead_only(*, lead, converted_by, center):
    student, password, created = convert_lead_to_student_safe(
        lead=lead,
        converted_by=converted_by,
        target_center=center,
    )

    return {
        "student": student,
        "password": password,
        "created": created,
        "used_existing_student": not created,
    }


def _infer_group_category_code(department) -> str:
    from education.models import Group

    department_name = (getattr(department, "name", "") or "").strip().lower()
    if "it" in department_name or "kompyuter" in department_name or "coding" in department_name:
        return Group.IT
    return Group.LANG


@transaction.atomic
def _convert_lead_group_to_real_group(*, lead_group, payload, actor, center):
    from education.models import Enrollment, Group, GroupSchedule, GroupStudent
    from education.services.enrollment_service import EnrollmentService

    form = LeadGroupConvertForm(payload, center=center)
    if not form.is_valid():
        return None, form.errors.get_json_data()

    cleaned = form.cleaned_data
    department = cleaned.get("department") or lead_group.department
    teacher_share = _resolve_teacher_share_percent(cleaned["teacher"])
    group_note = (lead_group.note or "").strip()
    lesson_time_label = cleaned["lesson_time"].strftime("%H:%M") if cleaned.get("lesson_time") else ""
    if lesson_time_label and "Dars vaqti:" not in group_note:
        group_note = f"{group_note}\nDars vaqti: {lesson_time_label}".strip()
    if _can_override_teacher_share(actor):
        try:
            override_share = _parse_teacher_share_override((payload or {}).get("teacher_share"))
        except ValueError as exc:
            return None, _teacher_share_error_payload(str(exc))
        if override_share is not None:
            teacher_share = override_share

    group = Group.objects.create(
        center=center,
        nom=cleaned["name"],
        izoh=group_note,
        category=_infer_group_category_code(department),
        category_obj=department,
        oqituvchi=cleaned["teacher"],
        kurs_narxi=cleaned["price"],
        oqituvchi_foiz=teacher_share,
        course_start_date=cleaned["start_date"],
    )

    for weekday in cleaned["lesson_days"]:
        GroupSchedule.objects.create(
            center=center,
            group=group,
            weekday=int(weekday),
            start_time=cleaned["lesson_time"],
            end_time=cleaned.get("lesson_end_time"),
        )

    leads = list(
        Lead.objects.filter(center=center, lead_group=lead_group, is_archived=False)
        .select_related("status", "converted_user")
        .order_by("qoshilgan_sana", "id")
    )

    converted_count = 0
    skipped_unconfirmed = 0
    created_student_count = 0
    linked_existing_student_count = 0
    added_to_group_count = 0
    duplicate_group_membership_count = 0
    converted_lead_ids = []

    for lead in leads:
        if not is_lead_confirmed(lead):
            skipped_unconfirmed += 1
            continue

        student, _, student_created = convert_lead_to_student_safe(
            lead=lead,
            converted_by=actor,
            target_center=center,
        )
        if student_created:
            created_student_count += 1
        else:
            linked_existing_student_count += 1

        converted_count += 1
        converted_lead_ids.append(lead.id)

        already_in_group = Enrollment.objects.filter(
            student=student,
            group=group,
            is_active=True,
        ).exists()
        if already_in_group:
            GroupStudent.objects.get_or_create(
                center=center,
                group=group,
                student=student,
            )
            duplicate_group_membership_count += 1
            continue

        enrollment = EnrollmentService.enroll_student(
            student=student,
            group=group,
            kurs_narxi=group.kurs_narxi,
            oqituvchi_foiz=group.oqituvchi_foiz,
            start_date=cleaned["start_date"],
            monthly_lessons=getattr(group, "oy_dars_soni", 0) or 12,
        )
        if department and enrollment.course_id != department.id:
            enrollment.course = department
            enrollment.save(update_fields=["course"])
        GroupStudent.objects.get_or_create(
            center=center,
            group=group,
            student=student,
        )
        added_to_group_count += 1

    lead_group.converted_group = group
    lead_group.status = LeadGroup.Status.CONVERTED
    lead_group.save(update_fields=["converted_group", "status", "updated_at"])

    return {
        "group": group,
        "converted_count": converted_count,
        "skipped_unconfirmed": skipped_unconfirmed,
        "created_student_count": created_student_count,
        "linked_existing_student_count": linked_existing_student_count,
        "added_to_group_count": added_to_group_count,
        "duplicate_group_membership_count": duplicate_group_membership_count,
        "converted_lead_ids": converted_lead_ids,
    }, None


@login_required
@require_feature("leads")
def lead_list(request):
    _lead_staff_guard(request)

    center = _get_center_or_redirect(request)
    if not center:
        return redirect("core:home")

    ensure_default_lead_subjects(center)
    filter_form = LeadApiFilterForm(request.GET or None, center=center)
    filter_form.is_valid()
    initial_filters = {
        "subjects": [str(item.id) for item in filter_form.cleaned_data.get("subjects", [])] if filter_form.is_bound else [],
        "statuses": filter_form.cleaned_data.get("statuses", []) if filter_form.is_bound else [],
        "date_preset": filter_form.cleaned_data.get("date_preset", "") if filter_form.is_bound else "",
        "date_from": (
            filter_form.cleaned_data.get("date_from").isoformat()
            if filter_form.is_bound and filter_form.cleaned_data.get("date_from")
            else ""
        ),
        "date_to": (
            filter_form.cleaned_data.get("date_to").isoformat()
            if filter_form.is_bound and filter_form.cleaned_data.get("date_to")
            else ""
        ),
        "q": filter_form.cleaned_data.get("q", "") if filter_form.is_bound else "",
        "view": filter_form.cleaned_data.get("view", "table") if filter_form.is_bound else "table",
        "page_size": filter_form.cleaned_data.get("page_size", 20) if filter_form.is_bound else 20,
    }

    manager_options = _manager_options(center)
    default_manager = _resolve_default_lead_manager(center, request.user)

    context = {
        "subject_choices": _lead_subject_choices(center),
        "status_choices": _lead_status_choices(center),
        "manager_options": manager_options,
        "lead_group_options": _lead_group_options(center),
        "teacher_options": _teacher_options(center),
        "department_options": _department_options(center),
        "initial_filters": initial_filters,
        "default_manager_id": getattr(default_manager, "id", "") or "",
        "lead_manager_locked": getattr(request.user, "role", "") == "manager",
        "api_list_url": _tenant_url(center, reverse("store:leads_api")),
        "api_detail_base": _tenant_url(center, reverse("store:lead_api_detail", args=[0])),
        "api_confirm_base": _tenant_url(center, reverse("store:lead_api_confirm", args=[0])),
        "api_assign_lead_group_base": _tenant_url(center, reverse("store:lead_api_assign_lead_group", args=[0])),
        "api_archive_base": _tenant_url(center, reverse("store:lead_api_archive", args=[0])),
        "api_restore_base": _tenant_url(center, reverse("store:lead_api_restore", args=[0])),
        "api_lead_groups_url": _tenant_url(center, reverse("store:lead_groups_api")),
        "api_lead_group_detail_base": _tenant_url(center, reverse("store:lead_group_detail_api", args=[0])),
        "api_lead_group_archive_base": _tenant_url(center, reverse("store:lead_group_archive_api", args=[0])),
        "api_lead_group_restore_base": _tenant_url(center, reverse("store:lead_group_restore_api", args=[0])),
        "api_lead_group_convert_base": _tenant_url(center, reverse("store:lead_group_convert_api", args=[0])),
        "api_subjects_url": _tenant_url(center, reverse("store:lead_subjects_api")),
        "api_statuses_url": _tenant_url(center, reverse("store:lead_statuses_api")),
        "can_override_teacher_share": _can_override_teacher_share(request.user),
    }
    return render(request, "store/lead_list.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def leads_api(request):
    center, error = _lead_api_access(request)
    if error:
        return error

    if request.method == "GET":
        archived = _query_bool(request, "archived", default=False)
        filter_form = LeadApiFilterForm(request.GET, center=center)
        if not filter_form.is_valid():
            return JsonResponse({"errors": filter_form.errors.get_json_data()}, status=400)

        cleaned = filter_form.cleaned_data
        base_qs = _base_leads_qs(center, archived=archived)
        leads_qs = _apply_lead_filters(base_qs, cleaned)
        view_name = cleaned.get("view") or "table"
        counts = _pipeline_counts(leads_qs)

        if view_name == "kanban":
            results = [serialize_lead(lead) for lead in leads_qs]
            return JsonResponse(
                {
                    "results": results,
                    "count": len(results),
                    "total_count": base_qs.count(),
                    "archived": bool(archived),
                    "next": None,
                    "previous": None,
                    "page": 1,
                    "page_size": cleaned.get("page_size") or len(results) or 20,
                    "num_pages": 1,
                    "counts": counts,
                }
            )

        page_size = cleaned.get("page_size") or 20
        paginator = Paginator(leads_qs, page_size)
        page_obj = paginator.get_page(cleaned.get("page") or 1)

        return JsonResponse(
            {
                "results": [serialize_lead(lead) for lead in page_obj.object_list],
                "count": paginator.count,
                "total_count": base_qs.count(),
                "archived": bool(archived),
                "next": _page_link(request, page_number=page_obj.next_page_number() if page_obj.has_next() else None, center=center),
                "previous": _page_link(request, page_number=page_obj.previous_page_number() if page_obj.has_previous() else None, center=center),
                "page": page_obj.number,
                "page_size": paginator.per_page,
                "num_pages": paginator.num_pages,
                "counts": counts,
            }
        )

    payload = _json_body(request) or request.POST
    form = LeadApiForm(payload, center=center)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    lead = form.save(actor=request.user)
    sync_lead_confirmation_state(lead=lead, actor=request.user)
    sync_lead_group_status(lead.lead_group)
    handle_lead_save_audit(lead=lead, actor=request.user, is_create=True)

    return JsonResponse({"lead": serialize_lead_detail(lead)}, status=201)


@login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def lead_api_detail(request, pk: int):
    center, error = _lead_api_access(request)
    if error:
        return error

    lead = _base_leads_qs(center).filter(pk=pk).first()
    if not lead:
        return JsonResponse({"error": "Lead topilmadi."}, status=404)

    if request.method == "GET":
        return JsonResponse({"lead": serialize_lead_detail(lead)})

    if request.method == "DELETE":
        lead.mark_archived(by_user=request.user)
        sync_lead_group_status(lead.lead_group)
        log_lead_activity(
            lead=lead,
            action=LeadActivity.Action.ARCHIVED,
            actor=request.user,
            note="Lead dashboard orqali arxivlandi.",
        )
        return JsonResponse({"success": True, "message": "Lead arxivlandi"})

    payload = _json_body(request)
    form = LeadApiForm(payload, center=center, instance=lead)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    previous_status = lead.status_id
    previous_follow_up = lead.next_follow_up_date
    previous_lead_group = lead.lead_group

    lead = form.save(actor=request.user)
    sync_lead_confirmation_state(lead=lead, actor=request.user)
    sync_lead_group_statuses(previous_lead_group, lead.lead_group)
    handle_lead_save_audit(
        lead=lead,
        actor=request.user,
        is_create=False,
        previous_status=previous_status,
        previous_follow_up_date=previous_follow_up,
    )

    return JsonResponse({"lead": serialize_lead_detail(lead)})


@login_required
@require_POST
def lead_api_archive(request, pk: int):
    center, error = _lead_api_access(request)
    if error:
        return error

    lead = (
        Lead.objects.filter(center=center, pk=pk)
        .select_related("status", "manba", "yonalish", "assigned_manager", "converted_user", "lead_group")
        .first()
    )
    if not lead:
        return JsonResponse({"error": "Lead topilmadi."}, status=404)
    if lead.is_archived:
        return JsonResponse({"error": "Lead allaqachon arxivlangan."}, status=400)

    lead.mark_archived(by_user=request.user)
    sync_lead_group_status(lead.lead_group)
    log_lead_activity(
        lead=lead,
        action=LeadActivity.Action.ARCHIVED,
        actor=request.user,
        note="Lead arxivga yuborildi.",
    )
    return JsonResponse(
        {
            "success": True,
            "message": "Lead arxivlandi",
            "lead": serialize_lead_detail(lead),
        }
    )


@login_required
@require_POST
def lead_api_restore(request, pk: int):
    center, error = _lead_api_access(request)
    if error:
        return error

    lead = (
        Lead.objects.filter(center=center, pk=pk, is_archived=True)
        .select_related("status", "manba", "yonalish", "assigned_manager", "converted_user", "lead_group")
        .first()
    )
    if not lead:
        return JsonResponse({"error": "Arxivlangan lead topilmadi."}, status=404)

    lead.restore()
    sync_lead_group_status(lead.lead_group)
    log_lead_activity(
        lead=lead,
        action=LeadActivity.Action.UPDATED,
        actor=request.user,
        note="Lead arxivdan qayta tiklandi.",
    )
    return JsonResponse(
        {
            "success": True,
            "message": "Qayta tiklandi",
            "lead": serialize_lead_detail(lead),
        }
    )


@login_required
@require_POST
def lead_api_convert(request, pk: int):
    center, error = _lead_api_access(request)
    if error:
        return error

    lead = (
        Lead.objects.filter(center=center, pk=pk)
        .select_related("status", "manba", "yonalish", "assigned_manager", "converted_user")
        .first()
    )
    if not lead:
        return JsonResponse({"error": "Lead topilmadi."}, status=404)
    if lead.converted_to_student or lead.converted_user_id:
        return JsonResponse({"error": "Lead allaqachon o‘quvchiga aylantirilgan."}, status=400)
    if lead.is_archived:
        return JsonResponse({"error": "Arxivlangan leadni aylantirib bo‘lmaydi."}, status=400)
    if not is_lead_confirmed(lead):
        return JsonResponse({"error": "Faqat tasdiqlangan leadlar o‘quvchiga aylantiriladi"}, status=400)

    payload = _json_body(request) or request.POST or {}
    form = LeadConvertForm(payload, center=center)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    try:
        result = _convert_lead_only(
            lead=lead,
            converted_by=request.user,
            center=center,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    lead.refresh_from_db()
    student = result["student"]
    message = "Lead o‘quvchiga aylantirildi"
    if result["used_existing_student"]:
        message = "Lead mavjud o‘quvchiga bog‘landi"

    return JsonResponse(
        {
            "success": True,
            "student_id": student.id if student else None,
            "message": message,
            "lead": serialize_lead_detail(lead),
            "student": {
                "id": student.id if student else None,
                "name": student.get_full_name() if student else "",
                "password": result["password"] or "",
                "created": bool(result["created"]),
            },
        }
    )


@login_required
@require_POST
def lead_api_confirm(request, pk: int):
    center, error = _lead_api_access(request)
    if error:
        return error

    lead = _base_leads_qs(center).filter(pk=pk).first()
    if not lead:
        return JsonResponse({"error": "Lead topilmadi."}, status=404)
    if lead.is_archived:
        return JsonResponse({"error": "Arxivlangan leadni o‘quvchiga aylantirib bo‘lmaydi."}, status=400)
    if lead.converted_to_student or lead.converted_user_id:
        return JsonResponse({"error": "Bu lead allaqachon o‘quvchiga aylantirilgan."}, status=400)

    confirm_lead(lead=lead, actor=request.user)
    student, password, created = convert_lead_to_student_safe(
        lead=lead,
        converted_by=request.user,
        target_center=center,
    )
    lead.refresh_from_db()
    message = "Lead o‘quvchiga aylantirildi"
    if not created:
        message = "Lead mavjud o‘quvchiga bog‘landi"
    return JsonResponse(
        {
            "success": True,
            "student_id": student.id if student else None,
            "message": message,
            "lead": serialize_lead_detail(lead),
            "student": {
                "id": student.id if student else None,
                "name": student.get_full_name() if student else "",
                "password": password or "",
                "created": bool(created),
            },
        }
    )


@login_required
@require_POST
def lead_api_assign_lead_group(request, pk: int):
    center, error = _lead_api_access(request)
    if error:
        return error

    lead = _base_leads_qs(center).filter(pk=pk).first()
    if not lead:
        return JsonResponse({"error": "Lead topilmadi."}, status=404)

    payload = _json_body(request) or request.POST or {}
    if isinstance(payload, dict) and payload.get("lead_group_id") and not payload.get("lead_group"):
        payload = {**payload, "lead_group": payload.get("lead_group_id")}
    form = LeadAssignLeadGroupForm(payload, center=center)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    previous_group = lead.lead_group
    lead.lead_group = form.cleaned_data.get("lead_group")
    lead.save(update_fields=["lead_group", "updated_at"])
    sync_lead_group_statuses(previous_group, lead.lead_group)
    log_lead_activity(
        lead=lead,
        action=LeadActivity.Action.UPDATED,
        actor=request.user,
        note=lead.lead_group.name if lead.lead_group_id else "Lead guruhi olib tashlandi.",
    )

    return JsonResponse(
        {
            "success": True,
            "message": "Lead guruhi yangilandi",
            "lead": serialize_lead_detail(lead),
            "options": _lead_group_options(center),
        }
    )


@login_required
@require_http_methods(["GET", "POST"])
def lead_groups_api(request):
    center, error = _lead_api_access(request)
    if error:
        return error

    if request.method == "GET":
        archived = _query_bool(request, "archived", default=False)
        return _lead_group_payload(center, archived=archived)

    payload = _json_body(request) or request.POST
    form = LeadGroupForm(payload, center=center)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    lead_group = form.save(actor=request.user)
    sync_lead_group_status(lead_group)
    return _lead_group_payload(center, lead_group=lead_group, status_code=201)


@login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def lead_group_detail_api(request, pk: int):
    center, error = _lead_api_access(request)
    if error:
        return error

    lead_group = _base_lead_groups_qs(center).filter(pk=pk).first()
    if not lead_group:
        return JsonResponse({"error": "Lead guruhi topilmadi."}, status=404)

    if request.method == "GET":
        leads = list(_lead_group_members_qs(center, lead_group))
        return JsonResponse(
            {
                "lead_group": serialize_lead_group_detail(lead_group, member_count=len(leads)),
                "leads": [serialize_lead_group_member(lead) for lead in leads],
                "count": len(leads),
            }
        )

    if request.method == "DELETE":
        lead_group.mark_archived(by_user=request.user)
        return _lead_group_payload(center, lead_group=lead_group)

    payload = _json_body(request) or request.POST
    form = LeadGroupForm(payload, center=center, instance=lead_group)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    lead_group = form.save(actor=request.user)
    sync_lead_group_status(lead_group)
    return _lead_group_payload(center, lead_group=lead_group)


@login_required
@require_POST
def lead_group_archive_api(request, pk: int):
    center, error = _lead_api_access(request)
    if error:
        return error

    lead_group = LeadGroup.objects.filter(center=center, pk=pk).select_related("subject", "department", "created_by", "converted_group").first()
    if not lead_group:
        return JsonResponse({"error": "Lead guruhi topilmadi."}, status=404)
    if lead_group.is_archived:
        return JsonResponse({"error": "Lead guruhi allaqachon arxivlangan."}, status=400)

    lead_group.mark_archived(by_user=request.user)
    return JsonResponse(
        {
            "success": True,
            "message": "Lead guruhi arxivlandi",
            "lead_group": serialize_lead_group(lead_group),
        }
    )


@login_required
@require_POST
def lead_group_restore_api(request, pk: int):
    center, error = _lead_api_access(request)
    if error:
        return error

    lead_group = LeadGroup.objects.filter(center=center, pk=pk, is_archived=True).select_related("subject", "department", "created_by", "converted_group").first()
    if not lead_group:
        return JsonResponse({"error": "Arxivlangan lead guruhi topilmadi."}, status=404)

    lead_group.restore()
    sync_lead_group_status(lead_group)
    return JsonResponse(
        {
            "success": True,
            "message": "Qayta tiklandi",
            "lead_group": serialize_lead_group(lead_group),
        }
    )


@login_required
@require_POST
def lead_group_convert_api(request, pk: int):
    center, error = _lead_api_access(request)
    if error:
        return error

    lead_group = _base_lead_groups_qs(center).filter(pk=pk).first()
    if not lead_group:
        return JsonResponse({"error": "Lead guruhi topilmadi."}, status=404)
    if lead_group.status == LeadGroup.Status.CONVERTED and lead_group.converted_group_id:
        return JsonResponse({"error": "Bu lead guruhi allaqachon real guruhga aylantirilgan."}, status=400)

    result, errors = _convert_lead_group_to_real_group(
        lead_group=lead_group,
        payload=_json_body(request) or request.POST,
        actor=request.user,
        center=center,
    )
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    lead_group.refresh_from_db()
    message = (
        f"Real guruh yaratildi. {result['converted_count']} ta tasdiqlangan lead o‘quvchiga aylantirildi. "
        f"{result['skipped_unconfirmed']} ta tasdiqlanmagan lead o‘tkazib yuborildi."
    )
    if result["added_to_group_count"]:
        message += f" {result['added_to_group_count']} ta student yangi real guruhga biriktirildi."
    if result["linked_existing_student_count"]:
        message += f" {result['linked_existing_student_count']} ta lead mavjud studentga bog‘landi."
    if result["duplicate_group_membership_count"]:
        message += (
            f" {result['duplicate_group_membership_count']} ta duplicate student allaqachon shu guruhda bo‘lgani uchun skip qilindi."
        )

    return JsonResponse(
        {
            "success": True,
            "message": message,
            "lead_group": serialize_lead_group(lead_group),
            "group": serialize_group(result["group"]),
            "converted_count": result["converted_count"],
            "skipped_unconfirmed": result["skipped_unconfirmed"],
            "created_student_count": result["created_student_count"],
            "linked_existing_student_count": result["linked_existing_student_count"],
            "added_to_group_count": result["added_to_group_count"],
            "duplicate_group_membership_count": result["duplicate_group_membership_count"],
            "results": [serialize_lead_group(item) for item in _base_lead_groups_qs(center)],
            "options": _lead_group_options(center),
        }
    )


@login_required
@require_http_methods(["GET", "POST"])
def lead_subjects_api(request):
    center, error = _lead_api_access(request)
    if error:
        return error

    ensure_default_lead_subjects(center)
    if request.method == "GET":
        return _subject_response_payload(center)

    payload = _json_body(request) or request.POST
    form = LeadSubjectForm(payload, center=center)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    subject = form.save()
    return _subject_response_payload(center, subject=subject, status_code=201)


@login_required
@require_http_methods(["PATCH", "DELETE"])
def lead_subject_detail_api(request, pk: int):
    center, error = _lead_api_access(request)
    if error:
        return error

    subject = Yonalish.objects.filter(center=center, pk=pk).first()
    if not subject:
        return JsonResponse({"error": "Fan topilmadi."}, status=404)

    if request.method == "DELETE":
        if subject.is_active:
            subject.is_active = False
            subject.save(update_fields=["is_active"])
        return _subject_response_payload(center, subject=subject)

    payload = _json_body(request) or request.POST
    form = LeadSubjectForm(payload, center=center, instance=subject)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    subject = form.save()
    return _subject_response_payload(center, subject=subject)


@login_required
@require_http_methods(["GET", "POST"])
def lead_statuses_api(request):
    center, error = _lead_api_access(request)
    if error:
        return error

    if request.method == "GET":
        statuses = _lead_status_choices(center)
        return JsonResponse(
            {
                "results": statuses,
                "count": len(statuses),
            }
        )

    payload = _json_body(request) or request.POST
    form = LeadStatusForm(payload, center=center)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    status = form.save()
    serialized_status, statuses = _status_payload_for_instance(center, status)
    return JsonResponse(
        {
            "status": serialized_status,
            "results": statuses,
            "count": len(statuses),
        },
        status=201,
    )


@login_required
@require_http_methods(["PATCH", "DELETE"])
def lead_status_detail_api(request, pk: int):
    center, error = _lead_api_access(request)
    if error:
        return error

    status_obj = LeadStatus.objects.filter(center=center, pk=pk).first()
    if not status_obj:
        return JsonResponse({"error": "Holat topilmadi."}, status=404)

    if request.method == "DELETE":
        if status_obj.is_active:
            status_obj.is_active = False
            status_obj.save(update_fields=["is_active"])
        _, statuses = _status_payload_for_instance(center, status_obj)
        return JsonResponse(
            {
                "status": serialize_lead_status(
                    {
                        "id": status_obj.id,
                        "value": f"custom:{status_obj.id}",
                        "label": status_obj.nom,
                        "tone": "gray",
                        "kind": "custom",
                        "code": status_obj.code,
                        "is_active": False,
                    }
                ),
                "results": statuses,
                "count": len(statuses),
            }
        )

    payload = _json_body(request) or request.POST
    form = LeadStatusForm(payload, center=center, instance=status_obj)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    status_obj = form.save()
    serialized_status, statuses = _status_payload_for_instance(center, status_obj)
    return JsonResponse(
        {
            "status": serialized_status,
            "results": statuses,
            "count": len(statuses),
        }
    )


@login_required
@require_feature("leads")
def lead_create(request):
    _lead_staff_guard(request)

    center = _get_center_or_redirect(request)
    if not center:
        return redirect("core:home")

    if request.method == "POST":
        form = LeadForm(request.POST, center=center)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.center = center
            lead.created_by = request.user
            if not lead.assigned_manager_id and request.user.role == "manager":
                lead.assigned_manager = request.user

            if lead.birth_date:
                today = timezone.localdate()
                lead.yosh = today.year - lead.birth_date.year - (
                    (today.month, today.day) < (lead.birth_date.month, lead.birth_date.day)
                )
            else:
                lead.yosh = 0

            lead.save()
            sync_lead_confirmation_state(lead=lead, actor=request.user)
            handle_lead_save_audit(lead=lead, actor=request.user, is_create=True)
            messages.success(request, "Yangi lead qo'shildi.")

            return redirect("store:lead_list")
    else:
        form = LeadForm(center=center)

    return render(request, "store/lead_create.html", {"form": form})


@login_required
@require_feature("leads")
def lead_edit(request, pk):
    _lead_staff_guard(request)

    center = _get_center_or_redirect(request)
    if not center:
        return redirect("core:home")

    lead = get_object_or_404(Lead, pk=pk, center=center, is_archived=False)

    if request.method == "POST":
        previous_status = lead.status_id
        previous_follow_up = lead.next_follow_up_date

        form = LeadForm(request.POST, instance=lead, center=center)
        if form.is_valid():
            lead = form.save(commit=False)
            if lead.birth_date:
                today = timezone.localdate()
                lead.yosh = today.year - lead.birth_date.year - (
                    (today.month, today.day) < (lead.birth_date.month, lead.birth_date.day)
                )
            else:
                lead.yosh = lead.yosh or 0

            lead.save()
            sync_lead_confirmation_state(lead=lead, actor=request.user)
            handle_lead_save_audit(
                lead=lead,
                actor=request.user,
                is_create=False,
                previous_status=previous_status,
                previous_follow_up_date=previous_follow_up,
            )
            messages.success(request, "Lead ma'lumotlari yangilandi.")

            return redirect("store:lead_list")
    else:
        form = LeadForm(instance=lead, center=center)

    return render(request, "store/lead_edit.html", {"form": form, "lead": lead})


@login_required
@require_feature("leads")
def lead_detail(request, pk):
    _lead_staff_guard(request)

    center = _get_center_or_redirect(request)
    if not center:
        return redirect("core:home")

    lead = get_object_or_404(
        Lead.objects.select_related("status", "manba", "yonalish", "assigned_manager", "converted_user"),
        pk=pk,
        center=center,
        is_archived=False,
    )
    activities = lead.activities.select_related("actor")[:20]
    trials = lead.trial_lessons.select_related("group", "teacher")[:10]

    return render(
        request,
        "store/lead_detail.html",
        {
            "lead": lead,
            "activities": activities,
            "trials": trials,
        },
    )


@login_required
@require_feature("leads")
def lead_delete(request, pk):
    _lead_staff_guard(request)

    center = _get_center_or_redirect(request)
    if not center:
        return redirect("core:home")

    lead = get_object_or_404(Lead, pk=pk, center=center, is_archived=False)
    if request.method == "POST":
        lead.mark_archived(by_user=request.user)
        log_lead_activity(
            lead=lead,
            action=LeadActivity.Action.ARCHIVED,
            actor=request.user,
            note="Lead soft archive qilindi.",
        )
        messages.success(request, "Lead arxivga olindi.")
        return redirect("store:lead_list")

    return render(request, "store/lead_delete.html", {"lead": lead})


@require_POST
@login_required
@require_feature("leads")
def lead_convert(request, pk):
    _lead_staff_guard(request)

    center = get_request_center(request)
    lead = get_object_or_404(Lead, pk=pk, center=center, is_archived=False)

    if not is_lead_confirmed(lead):
        messages.error(request, "Faqat tasdiqlangan leadlar o‘quvchiga aylantiriladi.")
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("store:lead_list")
        return redirect(next_url)

    try:
        user, password, created = convert_lead_to_student_safe(
            lead,
            converted_by=request.user,
            target_center=center,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("store:lead_list")
        return redirect(next_url)

    if created:
        messages.success(request, f"Lead studentga o'tkazildi. Login: {user.email} | Parol: {password}")
    else:
        messages.info(request, f"Lead mavjud studentga bog'landi: {user.email}")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("store:lead_list")
    return redirect(next_url)


@login_required
@require_feature("leads")
def lead_settings(request):
    _lead_staff_guard(request)

    center = _get_center_or_redirect(request)
    if not center:
        return redirect("core:home")

    manbalar = Manba.objects.filter(center=center).order_by("nom")
    statuses = LeadStatus.objects.filter(center=center).order_by("order", "nom")
    yonalishlar = Yonalish.objects.filter(center=center).order_by("nom")

    return render(
        request,
        "store/lead_settings.html",
        {
            "manbalar": manbalar,
            "yonalishlar": yonalishlar,
            "statuses": statuses,
        },
    )


@require_POST
@login_required
@require_feature("leads")
def lead_config_add(request):
    _lead_staff_guard(request)

    center = _get_center_or_redirect(request)
    if not center:
        return redirect("core:home")

    conf_type = request.POST.get("type")
    nom = (request.POST.get("nom") or "").strip()

    if not nom:
        messages.error(request, "Nom kiritilmadi.")
        return redirect("store:lead_settings")

    try:
        if conf_type == "manba":
            Manba.objects.get_or_create(center=center, nom=nom)
            messages.success(request, f"Manba qo'shildi: {nom}")
        elif conf_type == "yonalish":
            Yonalish.objects.get_or_create(center=center, nom=nom)
            messages.success(request, f"Yo'nalish qo'shildi: {nom}")
        elif conf_type == "status":
            LeadStatus.objects.get_or_create(center=center, nom=nom)
            messages.success(request, f"Status qo'shildi: {nom}")
        else:
            messages.warning(request, "Noma'lum sozlama turi.")
    except Exception as exc:
        messages.error(request, f"Xatolik: {exc}")

    return redirect("store:lead_settings")


@login_required
@require_feature("leads")
def lead_config_delete(request, type_code, pk):
    _lead_staff_guard(request)

    center = _get_center_or_redirect(request)
    if not center:
        return redirect("core:home")

    if type_code == "manba":
        model = Manba
    elif type_code == "yonalish":
        model = Yonalish
    elif type_code == "status":
        model = LeadStatus
    else:
        messages.error(request, "Noto'g'ri tur.")
        return redirect("store:lead_settings")

    obj = get_object_or_404(model, pk=pk, center=center)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "O'chirildi.")

    return redirect("store:lead_settings")


@login_required
@require_feature("leads")
def lead_followups_today(request):
    _lead_staff_guard(request)

    center = _get_center_or_redirect(request)
    if not center:
        return redirect("core:home")

    leads = follow_up_queryset(center=center, for_date=timezone.localdate())
    return render(
        request,
        "store/lead_followups_today.html",
        {
            "leads": leads,
            "today": timezone.localdate(),
        },
    )


@login_required
@require_feature("leads")
def trial_list(request):
    _lead_staff_guard(request)

    center = _get_center_or_redirect(request)
    if not center:
        return redirect("core:home")

    qs = (
        TrialLesson.objects.filter(center=center)
        .select_related("lead", "group", "teacher", "created_by")
        .order_by("-scheduled_at")
    )

    result = (request.GET.get("result") or "").strip()
    teacher_id = (request.GET.get("teacher") or "").strip()
    q = (request.GET.get("q") or "").strip()

    if result:
        qs = qs.filter(result_status=result)
    if teacher_id:
        qs = qs.filter(teacher_id=teacher_id)
    if q:
        qs = qs.filter(
            Q(lead__ism__icontains=q)
            | Q(lead__familya__icontains=q)
            | Q(lead__telefon1__icontains=q)
            | Q(group__nom__icontains=q)
            | Q(teacher__ism__icontains=q)
            | Q(teacher__familya__icontains=q)
        )

    analytics = build_trial_analytics(center)

    page_obj = Paginator(qs, 15).get_page(request.GET.get("page"))

    return render(
        request,
        "store/trial_list.html",
        {
            "page_obj": page_obj,
            "trials": page_obj.object_list,
            "result": result,
            "teacher_id": teacher_id,
            "q": q,
            "analytics": analytics,
            "teachers": request.user.__class__.objects.filter(center=center, role="teacher", is_archived=False).order_by("ism", "familya"),
            "result_choices": TrialLesson.ResultStatus.choices,
        },
    )


@login_required
@require_feature("leads")
def trial_create(request):
    _lead_staff_guard(request)

    center = _get_center_or_redirect(request)
    if not center:
        return redirect("core:home")

    if request.method == "POST":
        form = TrialLessonForm(request.POST, center=center)
        if form.is_valid():
            trial = form.save(commit=False)
            trial.center = center
            trial.created_by = request.user
            trial.updated_by = request.user
            if not trial.teacher_id and trial.group and trial.group.oqituvchi_id:
                trial.teacher = trial.group.oqituvchi
            trial.save()

            handle_trial_created(trial=trial, actor=request.user)
            messages.success(request, "Sinov dars muvaffaqiyatli belgilandi.")
            return redirect("store:trial_list")
    else:
        form = TrialLessonForm(center=center)

    return render(request, "store/trial_form.html", {"form": form, "title": "Sinov dars belgilash"})


@login_required
@require_feature("leads")
def trial_edit(request, pk):
    _lead_staff_guard(request)

    center = _get_center_or_redirect(request)
    if not center:
        return redirect("core:home")

    trial = get_object_or_404(TrialLesson, pk=pk, center=center)

    if request.method == "POST":
        previous_result = trial.result_status
        form = TrialLessonForm(request.POST, instance=trial, center=center)
        if form.is_valid():
            trial = form.save(commit=False)
            trial.updated_by = request.user
            trial.save()
            handle_trial_updated(trial=trial, actor=request.user, previous_result=previous_result)
            messages.success(request, "Sinov dars ma'lumotlari yangilandi.")
            return redirect("store:trial_list")
    else:
        form = TrialLessonForm(instance=trial, center=center)

    return render(
        request,
        "store/trial_form.html",
        {
            "form": form,
            "title": "Sinov darsni tahrirlash",
            "trial": trial,
        },
    )
