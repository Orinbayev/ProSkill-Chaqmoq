"""O'qituvchi Imtihon paneli: hub, yillik baholar, savollar banki."""
from __future__ import annotations

import logging
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from core.center_features import FEATURE_UI_EXAM_SESSIONS
from core.tenant import get_request_center
from education.models import ExamQuestion, ExamResult, ExamSession, Group
from education.services.exam_service import (
    get_annual_exam_grades,
    get_or_create_center_exam_settings,
    get_teacher_due_exam_groups,
)

logger = logging.getLogger(__name__)


def _ensure_exam_feature(request, center):
    from education.views.legacy import _ensure_center_ui_feature

    return _ensure_center_ui_feature(
        request,
        center,
        FEATURE_UI_EXAM_SESSIONS,
        message="Imtihon bo'limi bu markaz uchun o'chirilgan. Director/superadmin yoqishi mumkin.",
    )


def _is_teacher_or_mgmt(user) -> bool:
    role = getattr(user, "role", None)
    return bool(user.is_superuser or role in ("teacher", "director", "manager"))


@login_required
def exam_hub(request):
    """O'qituvchi / menejer imtihon bosh sahifasi."""
    from billing.services import center_has_feature

    center = get_request_center(request)
    if not center:
        raise Http404("Center not found")
    if not _is_teacher_or_mgmt(request.user):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")
    if not center_has_feature(center, "imtihon"):
        messages.warning(request, "Imtihon moduli tarif rejasida yoqilmagan.")
        return redirect("core:home")
    disabled = _ensure_exam_feature(request, center)
    if disabled:
        return disabled

    settings_obj = get_or_create_center_exam_settings(center)
    role = getattr(request.user, "role", None)
    is_teacher = role == "teacher" and not request.user.is_superuser

    due_rows = []
    if is_teacher:
        due_rows = get_teacher_due_exam_groups(center=center, teacher=request.user)
    else:
        # Director/manager: barcha guruhlar (eslatma due bo'lganlar)
        from education.services.exam_service import get_exam_reminder_state

        groups = Group.objects.filter(
            center=center, is_archived=False, is_closed=False
        ).select_related("oqituvchi")[:80]
        for g in groups:
            st = get_exam_reminder_state(group=g)
            if st.get("enabled") and st.get("due"):
                due_rows.append({"group": g, "state": st})

    sessions_qs = ExamSession.objects.filter(center=center).select_related(
        "group", "teacher"
    )
    if is_teacher:
        sessions_qs = sessions_qs.filter(
            models_Q_teacher(request.user)
        )
    recent_sessions = list(sessions_qs.order_by("-exam_date", "-id")[:8])

    results_qs = ExamResult.objects.filter(center=center)
    if is_teacher:
        results_qs = results_qs.filter(
            models_Q_teacher_results(request.user)
        )
    stats = {
        "due_count": sum(1 for r in due_rows if r["state"].get("due")),
        "sessions_total": sessions_qs.count(),
        "sessions_open": sessions_qs.filter(status=ExamSession.STATUS_DRAFT).count(),
        "avg_percent": None,
        "questions_count": ExamQuestion.objects.filter(
            center=center, is_active=True
        ).count(),
    }
    avg = results_qs.exclude(percent__isnull=True).aggregate(a=Avg("percent"))["a"]
    if avg is not None:
        stats["avg_percent"] = round(float(avg), 1)

    return render(
        request,
        "education/exam_hub.html",
        {
            "settings_obj": settings_obj,
            "due_rows": due_rows,
            "recent_sessions": recent_sessions,
            "stats": stats,
            "is_teacher": is_teacher,
            "every_n": settings_obj.exam_every_n_lessons or 12,
        },
    )


def models_Q_teacher(user):
    from django.db.models import Q

    return Q(teacher=user) | Q(group__oqituvchi=user)


def models_Q_teacher_results(user):
    from django.db.models import Q

    return Q(teacher=user) | Q(session__teacher=user) | Q(group__oqituvchi=user)


@login_required
def exam_annual_grades(request):
    """Yillik baholar — chiroyli hisobot."""
    from billing.services import center_has_feature

    center = get_request_center(request)
    if not center:
        raise Http404("Center not found")
    if not _is_teacher_or_mgmt(request.user):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")
    if not center_has_feature(center, "imtihon"):
        messages.warning(request, "Imtihon moduli tarif rejasida yoqilmagan.")
        return redirect("core:home")
    disabled = _ensure_exam_feature(request, center)
    if disabled:
        return disabled

    today = date.today()
    try:
        year = int(request.GET.get("year") or today.year)
    except (TypeError, ValueError):
        year = today.year
    group_id = request.GET.get("group") or ""
    group = None
    if group_id:
        group = get_object_or_404(Group, pk=group_id, center=center)

    role = getattr(request.user, "role", None)
    teacher = request.user if role == "teacher" and not request.user.is_superuser else None

    data = get_annual_exam_grades(
        center=center, year=year, teacher=teacher, group=group
    )
    years = list(range(today.year, today.year - 5, -1))

    return render(
        request,
        "education/exam_annual_grades.html",
        {
            "data": data,
            "year": year,
            "years": years,
            "selected_group_id": int(group_id) if str(group_id).isdigit() else 0,
            "is_teacher": teacher is not None,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def exam_questions(request):
    """Savollar banki — o'qituvchi qo'shadi / yuklaydi."""
    from billing.services import center_has_feature

    center = get_request_center(request)
    if not center:
        raise Http404("Center not found")
    if not _is_teacher_or_mgmt(request.user):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")
    if not center_has_feature(center, "imtihon"):
        messages.warning(request, "Imtihon moduli tarif rejasida yoqilmagan.")
        return redirect("core:home")
    disabled = _ensure_exam_feature(request, center)
    if disabled:
        return disabled

    settings_obj = get_or_create_center_exam_settings(center)
    role = getattr(request.user, "role", None)
    is_teacher = role == "teacher" and not request.user.is_superuser

    groups = Group.objects.filter(center=center, is_archived=False).order_by("nom")
    if is_teacher:
        groups = groups.filter(oqituvchi=request.user)

    if request.method == "POST":
        action = (request.POST.get("action") or "create").strip()
        if action == "delete":
            qid = request.POST.get("question_id")
            qs = ExamQuestion.objects.filter(center=center, pk=qid)
            if is_teacher:
                qs = qs.filter(teacher=request.user)
            deleted, _ = qs.delete()
            if deleted:
                messages.success(request, "Savol o'chirildi.")
            return redirect("education:exam_questions")

        body = (request.POST.get("body") or "").strip()
        title = (request.POST.get("title") or "").strip()
        group_id = request.POST.get("group") or ""
        try:
            points = max(1, int(request.POST.get("points") or 1))
        except (TypeError, ValueError):
            points = 1
        if not body:
            messages.error(request, "Savol matni majburiy.")
            return redirect("education:exam_questions")

        group = None
        if group_id:
            group = groups.filter(pk=group_id).first()
            if group_id and group is None:
                messages.error(request, "Guruh topilmadi yoki ruxsat yo'q.")
                return redirect("education:exam_questions")

        attachment = request.FILES.get("attachment")
        if attachment and not settings_obj.exam_file_upload_enabled:
            messages.warning(request, "Fayl yuklash markaz sozlamasida o'chiq.")
            attachment = None
        if attachment and attachment.size > 10 * 1024 * 1024:
            messages.error(request, "Fayl 10 MB dan oshmasin.")
            return redirect("education:exam_questions")

        ExamQuestion.objects.create(
            center=center,
            group=group,
            teacher=request.user if is_teacher else (
                request.user if role == "teacher" else None
            ),
            title=title[:200],
            body=body,
            points=points,
            attachment=attachment,
        )
        messages.success(request, "Savol qo'shildi.")
        return redirect("education:exam_questions")

    questions = ExamQuestion.objects.filter(center=center, is_active=True).select_related(
        "group", "teacher"
    )
    if is_teacher:
        questions = questions.filter(teacher=request.user)
    group_filter = request.GET.get("group") or ""
    if group_filter.isdigit():
        questions = questions.filter(group_id=int(group_filter))

    return render(
        request,
        "education/exam_questions.html",
        {
            "questions": questions[:200],
            "groups": groups,
            "settings_obj": settings_obj,
            "selected_group_id": int(group_filter) if group_filter.isdigit() else 0,
            "is_teacher": is_teacher,
        },
    )
