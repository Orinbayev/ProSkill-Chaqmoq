from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from billing.decorators import require_feature
from core.tenant import get_request_center, require_center

from .forms import LeadForm, TrialLessonForm
from .lead_services import (
    convert_lead_to_student_safe,
    follow_up_queryset,
    handle_lead_save_audit,
    log_lead_activity,
    resolve_status_code,
)
from .models import Lead, LeadActivity, LeadStatus, Manba, TrialLesson, Yonalish
from .trial_services import build_trial_analytics, handle_trial_created, handle_trial_updated


def _lead_staff_guard(request):
    if request.user.is_superuser:
        return
    if getattr(request.user, "role", "") not in ("manager", "director"):
        raise PermissionDenied


def _get_center_or_redirect(request):
    try:
        return require_center(request)
    except Exception:
        messages.error(request, "Markaz aniqlanmadi.")
        return None


def _base_leads_qs(center):
    return (
        Lead.objects.filter(center=center, is_archived=False)
        .select_related("status", "manba", "yonalish", "assigned_manager", "converted_user")
        .order_by("-qoshilgan_sana")
    )


@login_required
@require_feature("leads")
def lead_list(request):
    _lead_staff_guard(request)

    center = _get_center_or_redirect(request)
    if not center:
        return redirect("core:home")

    status_id = (request.GET.get("status") or "").strip()
    manager_id = (request.GET.get("manager") or "").strip()
    source_id = (request.GET.get("source") or "").strip()
    follow_up = (request.GET.get("follow_up") or "").strip()
    q = (request.GET.get("q") or "").strip()

    base_qs = _base_leads_qs(center)
    leads = base_qs

    if status_id:
        leads = leads.filter(status_id=status_id)
    if manager_id:
        leads = leads.filter(assigned_manager_id=manager_id)
    if source_id:
        leads = leads.filter(manba_id=source_id)

    today = timezone.localdate()
    if follow_up == "today":
        leads = leads.filter(next_follow_up_date=today)
    elif follow_up == "overdue":
        leads = leads.filter(next_follow_up_date__lt=today)
    elif follow_up == "week":
        leads = leads.filter(next_follow_up_date__range=(today, today + timedelta(days=7)))
    elif follow_up == "none":
        leads = leads.filter(next_follow_up_date__isnull=True)

    if q:
        leads = leads.filter(
            Q(ism__icontains=q)
            | Q(familya__icontains=q)
            | Q(telefon1__icontains=q)
            | Q(parent_phone__icontains=q)
            | Q(yonalish__nom__icontains=q)
            | Q(manba__nom__icontains=q)
        )

    statuses = (
        LeadStatus.objects.filter(center=center, is_active=True)
        .annotate(
            leads_count=Count("lead", filter=Q(lead__is_archived=False), distinct=True),
            converted_count=Count(
                "lead",
                filter=Q(lead__is_archived=False, lead__converted_to_student=True),
                distinct=True,
            ),
        )
        .order_by("order", "nom")
    )

    managers = (
        request.user.__class__.objects.filter(center=center, role="manager", is_archived=False)
        .order_by("ism", "familya")
    )
    sources = Manba.objects.filter(center=center).order_by("nom")

    total_count = base_qs.count()
    total_converted = base_qs.filter(converted_to_student=True).count()
    today_followups = base_qs.filter(next_follow_up_date=today).count()
    overdue_followups = base_qs.filter(next_follow_up_date__lt=today).count()
    conversion_rate = round((total_converted / total_count) * 100, 1) if total_count else 0

    source_analytics = (
        base_qs.values("manba__nom")
        .annotate(total=Count("id"), converted=Count("id", filter=Q(converted_to_student=True)))
        .order_by("-total")[:6]
    )

    manager_analytics = (
        base_qs.values("assigned_manager__ism", "assigned_manager__familya")
        .annotate(total=Count("id"), converted=Count("id", filter=Q(converted_to_student=True)))
        .order_by("-total")[:6]
    )

    page_num = request.GET.get("page", 1)
    page_size = request.GET.get("page_size", "10")
    if page_size == "all":
        paginator = Paginator(leads, max(1, leads.count()))
    else:
        try:
            page_size = int(page_size)
            if page_size < 1:
                page_size = 10
        except ValueError:
            page_size = 10
        paginator = Paginator(leads, page_size)

    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        "leads": page_obj.object_list,
        "page_obj": page_obj,
        "page_size": page_size,
        "statuses": statuses,
        "selected_status": status_id,
        "selected_manager": manager_id,
        "selected_source": source_id,
        "selected_follow_up": follow_up,
        "q": q,
        "managers": managers,
        "sources": sources,
        "total_count": total_count,
        "total_converted": total_converted,
        "today_followups": today_followups,
        "overdue_followups": overdue_followups,
        "conversion_rate": conversion_rate,
        "source_analytics": source_analytics,
        "manager_analytics": manager_analytics,
        "leads_count_filtered": leads.count(),
        "converted_count_filtered": leads.filter(converted_to_student=True).count(),
    }
    return render(request, "store/lead_list.html", context)


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
            handle_lead_save_audit(lead=lead, actor=request.user, is_create=True)

            status_code = resolve_status_code(lead.status)
            if status_code == LeadStatus.Code.REGISTERED:
                user, password, created = convert_lead_to_student_safe(lead, converted_by=request.user, target_center=center)
                if created:
                    messages.success(request, f"Lead studentga o'tkazildi. Login: {user.email} | Parol: {password}")
                else:
                    messages.info(request, f"Lead mavjud studentga bog'landi: {user.email}")
            else:
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
            handle_lead_save_audit(
                lead=lead,
                actor=request.user,
                is_create=False,
                previous_status=previous_status,
                previous_follow_up_date=previous_follow_up,
            )

            status_code = resolve_status_code(lead.status)
            if status_code == LeadStatus.Code.REGISTERED and not lead.converted_to_student:
                user, password, created = convert_lead_to_student_safe(lead, converted_by=request.user, target_center=center)
                if created:
                    messages.success(request, f"Lead studentga o'tkazildi. Login: {user.email} | Parol: {password}")
                else:
                    messages.info(request, f"Lead mavjud studentga bog'landi: {user.email}")
            else:
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

    if not lead.status_id:
        registered = LeadStatus.objects.filter(center=center, code=LeadStatus.Code.REGISTERED).first()
        if registered:
            lead.status = registered
            lead.save(update_fields=["status", "updated_at"])

    user, password, created = convert_lead_to_student_safe(
        lead,
        converted_by=request.user,
        target_center=center,
    )

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
