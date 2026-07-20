"""
Auto-split from education/views.py (phase 7 god-file reduction).
Public API re-exported via education.views package.
"""
from __future__ import annotations

from .common import *  # noqa: F403


@login_required
@require_feature("imtihon")
def exam_settings_view(request):
    from core.tenant import get_request_center
    center = get_request_center(request)
    if not center:
        raise Http404("Center not found")

    if not _teacher_can_view_settings(request.user):
        return HttpResponseForbidden("Sizda bu bo'limga ruxsat yo'q.")

    from ..forms import CenterExamSettingForm
    from education.services.exam_service import get_or_create_center_exam_settings

    settings_obj = get_or_create_center_exam_settings(center)
    can_edit = _director_or_manager(request.user)
    form = CenterExamSettingForm(request.POST or None, instance=settings_obj)

    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("Teacher bu sozlamalarni o'zgartira olmaydi.")
        if form.is_valid():
            obj = form.save(commit=False)
            obj.center = center
            obj.updated_by = request.user
            obj.save()
            from education.services.audit_service import log_education_event
            log_education_event(
                center=center,
                actor=request.user,
                action_type="director_settings_change",
                entity=obj,
                message="Exam settings updated",
            )
            messages.success(request, "Imtihon sozlamalari saqlandi.")
            return redirect("education:exam_settings")

    return render(
        request,
        "education/exam_settings.html",
        {"form": form, "settings_obj": settings_obj, "can_edit": can_edit},
    )



@login_required
@require_POST
@require_feature("imtihon")
def exam_reminder_action(request, group_id: int):
    from core.tenant import get_request_center
    center = get_request_center(request)

    qs = Group.objects.all()
    if center:
        qs = qs.filter(center=center)
    group = get_object_or_404(qs, pk=group_id)

    if not _teacher_or_management_can_access_group(request.user, group):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    from education.models import ExamReminderLog
    from education.services.exam_service import (
        create_or_get_exam_session_from_reminder,
        create_or_update_exam_session_decision,
        get_exam_reminder_state,
        log_exam_reminder_action,
    )

    action = (request.POST.get("action") or "").strip().lower()
    date_str = request.POST.get("date")
    selected_date = parse_date(date_str) if date_str else localdate()
    note = (request.POST.get("note") or "").strip()

    if action not in {ExamReminderLog.ACTION_YES, ExamReminderLog.ACTION_NO, ExamReminderLog.ACTION_LATER}:
        messages.error(request, "Noto'g'ri action.")
        return redirect("education:group_detail", pk=group.id)

    reminder_state = get_exam_reminder_state(group=group, on_date=selected_date)
    target_checkpoint = int(reminder_state.get("target_lesson_number") or 0)

    if action == ExamReminderLog.ACTION_YES:
        if not reminder_state.get("enabled"):
            messages.info(request, "Imtihon tizimi o'chiq. Sozlamani director yoqishi kerak.")
            return redirect("education:group_detail", pk=group.id)
        if not reminder_state.get("due"):
            messages.info(request, "Hozircha majburiy imtihon darsi emas, lekin davomat davom etadi.")
            return redirect("education:group_detail", pk=group.id)
        session = create_or_get_exam_session_from_reminder(
            group=group,
            teacher=request.user,
            attendance_date=selected_date,
            created_by=request.user,
            decision_note=note,
            lesson_number_reference=target_checkpoint or reminder_state.get("target_lesson_number"),
        )
        messages.success(request, "Imtihon sessiyasi ochildi. Natijalarni kiriting.")
        return redirect("education:exam_session_entry", session_id=session.id)

    if not reminder_state.get("enabled"):
        messages.info(request, "Imtihon tizimi o'chiq. Sozlamani director yoqishi kerak.")
        return redirect("education:group_detail", pk=group.id)
    if not reminder_state.get("due"):
        messages.info(request, "Hozircha bu nazorat bosqichi bo'yicha amal talab qilinmaydi.")
        return redirect("education:group_detail", pk=group.id)

    decision_session = None
    if action != ExamReminderLog.ACTION_LATER:
        decision_session = create_or_update_exam_session_decision(
            group=group,
            teacher=request.user,
            attendance_date=selected_date,
            actor=request.user,
            decision=action,
            decision_note=note,
            lesson_number_reference=target_checkpoint,
        )

    log_exam_reminder_action(
        group=group,
        teacher=request.user,
        action=action,
        attendance_date=selected_date,
        note=note,
        metadata={
            "session_id": decision_session.id if decision_session else None,
            "target_checkpoint": target_checkpoint,
        },
    )

    if action == ExamReminderLog.ACTION_NO:
        messages.warning(request, "Imtihon o'tkazilmagan deb qayd etildi.")
    else:
        messages.info(request, "Imtihon eslatmasi keyinroq uchun saqlandi.")
    return redirect("education:group_detail", pk=group.id)



@login_required
@require_feature("imtihon")
def exam_list(request):
    from core.tenant import get_request_center
    from education.models import ExamResult, ExamSession

    try:
        center = get_request_center(request)
        if not center:
            raise Http404("Center not found")
        disabled_response = _ensure_center_ui_feature(
            request,
            center,
            FEATURE_UI_EXAM_SESSIONS,
            message="Imtihon sessiyalari bo'limi bu markaz uchun o'chirilgan.",
        )
        if disabled_response:
            return disabled_response

        if not _director_or_manager(request.user):
            return HttpResponseForbidden("Sizda ruxsat yo'q.")

        group_id = _get_int(request.GET, "group", 0)
        teacher_id = _get_int(request.GET, "teacher", 0)
        status_filter = (request.GET.get("status") or "").strip()
        month_filter = (request.GET.get("month") or "").strip()

        sessions_qs = (
            ExamSession.objects.filter(center=center)
            .select_related("group", "teacher")
            .prefetch_related("results")
            .annotate(
                students_count=Count("results", distinct=True),
                passed_count=Count(
                    "results",
                    filter=Q(results__passed=True, results__absent_in_exam=False),
                    distinct=True,
                ),
                failed_count=Count(
                    "results",
                    filter=(
                        Q(results__passed=False)
                        & (
                            Q(results__score__isnull=False)
                            | Q(results__percent__isnull=False)
                            | Q(results__absent_in_exam=True)
                        )
                    ),
                    distinct=True,
                ),
                avg_percent=Avg("results__percent", filter=Q(results__percent__isnull=False)),
            )
            .order_by("-exam_date", "-id")
        )

        if group_id:
            sessions_qs = sessions_qs.filter(group_id=group_id)
        if teacher_id:
            sessions_qs = sessions_qs.filter(teacher_id=teacher_id)
        if status_filter in {
            ExamSession.STATUS_DRAFT,
            ExamSession.STATUS_COMPLETED,
            ExamSession.STATUS_CANCELLED,
        }:
            sessions_qs = sessions_qs.filter(status=status_filter)
        if month_filter:
            parsed_month = parse_month_str(month_filter)
            if parsed_month:
                sessions_qs = sessions_qs.filter(
                    exam_date__year=parsed_month.year,
                    exam_date__month=parsed_month.month,
                )

        examined_results = ExamResult.objects.filter(session__in=sessions_qs).filter(
            Q(absent_in_exam=True) | Q(score__isnull=False) | Q(percent__isnull=False)
        )
        total_examined = examined_results.count()
        passed_examined = examined_results.filter(passed=True, absent_in_exam=False).count()
        avg_pass_rate = round((passed_examined / total_examined * 100), 1) if total_examined else 0

        paginator = Paginator(sessions_qs, 20)
        sessions = paginator.get_page(request.GET.get("page"))

        groups_list = Group.objects.filter(center=center).order_by("nom")
        teachers_list = User.objects.filter(
            center=center,
            role="teacher",
            is_archived=False,
        ).order_by("ism", "familya")

        return render(
            request,
            "education/exam_list.html",
            {
                "sessions": sessions,
                "groups_list": groups_list,
                "teachers_list": teachers_list,
                "filters": {
                    "group": group_id,
                    "teacher": teacher_id,
                    "status": status_filter,
                    "month": month_filter,
                },
                "total_stats": {
                    "total_sessions": sessions_qs.count(),
                    "completed": sessions_qs.filter(status=ExamSession.STATUS_COMPLETED).count(),
                    "avg_pass_rate": avg_pass_rate,
                    "total_students_examined": total_examined,
                },
            },
        )
    except Http404:
        raise
    except Exception:
        logger.exception("exam_list failed")
        messages.error(request, "Imtihon sessiyalari ro'yxatini yuklashda xatolik yuz berdi.")
        return redirect("core:director_boshqaruv")



@login_required
@require_feature("imtihon")
def exam_create(request, group_id=None):
    from core.tenant import get_request_center
    from education.models import ExamResult, ExamSession
    from education.services.exam_service import (
        get_group_exam_sequence_number,
        get_group_lesson_number,
    )

    try:
        center = get_request_center(request)
        if not center:
            raise Http404("Center not found")
        disabled_response = _ensure_center_ui_feature(
            request,
            center,
            FEATURE_UI_EXAM_SESSIONS,
            message="Imtihon sessiyalari bo'limi bu markaz uchun o'chirilgan.",
        )
        if disabled_response:
            return disabled_response

        role = getattr(request.user, "role", None)
        if not request.user.is_superuser and role not in ("teacher", "manager", "director"):
            return HttpResponseForbidden("Sizda ruxsat yo'q.")

        groups_qs = Group.objects.filter(center=center).select_related("oqituvchi").order_by("nom")
        if role == "teacher" and not request.user.is_superuser:
            groups_qs = groups_qs.filter(oqituvchi=request.user)

        selected_group = None
        if group_id is not None:
            selected_group = get_object_or_404(groups_qs, pk=group_id)

        selected_exam_date = request.POST.get("exam_date") or timezone.localdate().isoformat()
        assignment_description = (request.POST.get("assignment_description") or "").strip()

        if request.method == "POST":
            target_group = selected_group
            if target_group is None:
                selected_group_id = _get_int(request.POST, "group", 0)
                if not selected_group_id:
                    messages.error(request, "Guruhni tanlang.")
                    return render(
                        request,
                        "education/exam_create.html",
                        {
                            "groups_list": groups_qs,
                            "selected_group": selected_group,
                            "selected_exam_date": selected_exam_date,
                            "assignment_description": assignment_description,
                        },
                    )
                target_group = get_object_or_404(groups_qs, pk=selected_group_id)

            exam_date = parse_date(selected_exam_date) or timezone.localdate()
            teacher_user = request.user if role == "teacher" else target_group.oqituvchi
            lesson_number_reference = get_group_lesson_number(group=target_group, on_date=exam_date)

            with transaction.atomic():
                session = ExamSession.objects.create(
                    center=center,
                    group=target_group,
                    teacher=teacher_user,
                    attendance_date=exam_date,
                    exam_date=exam_date,
                    lesson_number_reference=lesson_number_reference,
                    exam_sequence_number=get_group_exam_sequence_number(target_group),
                    teacher_decision=ExamSession.DECISION_LATER,
                    decision_note=_encode_exam_session_note(assignment_description, ""),
                    status=ExamSession.STATUS_DRAFT,
                    created_by=request.user,
                    updated_by=request.user,
                )

                students = Enrollment.objects.filter(
                    group=target_group,
                    center=center,
                    is_active=True,
                ).select_related("student")
                ExamResult.objects.bulk_create(
                    [
                        ExamResult(
                            center=center,
                            session=session,
                            group=target_group,
                            student=enrollment.student,
                            teacher=teacher_user,
                            exam_date=session.exam_date,
                            lesson_number_reference=session.lesson_number_reference,
                            assignment_description=assignment_description,
                            created_by=request.user,
                            updated_by=request.user,
                        )
                        for enrollment in students
                    ],
                    ignore_conflicts=True,
                )

            messages.success(request, "Yangi imtihon sessiyasi yaratildi.")
            return redirect("education:exam_session_entry", session_id=session.id)

        return render(
            request,
            "education/exam_create.html",
            {
                "groups_list": groups_qs,
                "selected_group": selected_group,
                "selected_exam_date": selected_exam_date,
                "assignment_description": assignment_description,
            },
        )
    except Http404:
        raise
    except Exception:
        logger.exception("exam_create failed: group_id=%s", group_id)
        messages.error(request, "Imtihon sessiyasini yaratishda xatolik yuz berdi.")
        return redirect("education:teacher_exam_history")



@login_required
@require_feature("imtihon")
def exam_session_entry(request, session_id: int):
    from core.tenant import get_request_center
    from ..forms import ExamResultRowForm
    from education.models import ExamSession, ExamResult
    from education.services.certificate_service import auto_check_certificate_eligibility
    from education.services.exam_service import (
        get_exam_session_progress,
        get_or_create_center_exam_settings,
        notify_exam_results,
        save_exam_session_task_files,
        save_exam_results_batch,
    )

    try:
        center = get_request_center(request)
        disabled_response = _ensure_center_ui_feature(
            request,
            center,
            FEATURE_UI_EXAM_SESSIONS,
            message="Imtihon sessiyalari bo'limi bu markaz uchun o'chirilgan.",
        )
        if disabled_response:
            return disabled_response
        qs = ExamSession.objects.select_related("group", "teacher", "center").prefetch_related("task_files")
        if center:
            qs = qs.filter(center=center)
        session = get_object_or_404(qs, pk=session_id)

        if not _teacher_or_management_can_access_group(request.user, session.group):
            return HttpResponseForbidden("Sizda ruxsat yo'q.")

        settings_obj = get_or_create_center_exam_settings(session.center)
        try:
            max_score = Decimal(str(request.GET.get("max_score") or request.POST.get("max_score") or "100"))
            if max_score <= 0:
                raise ValueError
        except Exception:
            max_score = Decimal("100")
        passing_percent = Decimal(str(settings_obj.passing_score_percent or 60))

        enrollments = (
            Enrollment.objects.filter(group=session.group, is_active=True)
            .select_related("student")
            .order_by("student__ism", "student__familya")
        )
        existing_results = {
            result.student_id: result
            for result in ExamResult.objects.filter(session=session).select_related("student")
        }
        for enrollment in enrollments:
            enrollment.existing_result = existing_results.get(enrollment.student_id)

        parsed_note = _decode_exam_session_note(session.decision_note)
        session_task_default = parsed_note["task"]
        session_comment_default = parsed_note["comment"]

        if request.method == "POST":
            action = (request.POST.get("action") or "save").strip().lower()
            is_finalize = action == "finalize"
            was_completed = session.status == ExamSession.STATUS_COMPLETED

            session_task = (request.POST.get("session_task") or "").strip()
            session_comment = (request.POST.get("session_comment") or "").strip()
            session_note = _encode_exam_session_note(session_task, session_comment)
            note_updated = False
            if session.decision_note != session_note:
                session.decision_note = session_note
                session.updated_by = request.user
                session.save(update_fields=["decision_note", "updated_by", "updated_at"])
                note_updated = True

            session_task_default = session_task
            session_comment_default = session_comment

            uploaded_task_file_count = 0
            session_task_files = request.FILES.getlist("session_task_files") or []
            if session_task_files and settings_obj.exam_file_upload_enabled:
                try:
                    uploaded_task_file_count = save_exam_session_task_files(
                        session=session,
                        actor=request.user,
                        files=session_task_files,
                    )
                    if uploaded_task_file_count:
                        messages.success(request, f"{uploaded_task_file_count} ta umumiy task fayli yuklandi.")
                except ValueError as exc:
                    messages.error(request, str(exc))
            elif session_task_files and not settings_obj.exam_file_upload_enabled:
                messages.warning(request, "Task fayl yuklash markaz sozlamasida o'chiq.")

            rows = []
            row_errors = []
            for enrollment in enrollments:
                sid = enrollment.student_id
                work_files = request.FILES.getlist(f"work_files_{sid}") or []
                task_files = request.FILES.getlist(f"task_files_{sid}") or []
                raw_score = (request.POST.get(f"score_{sid}") or "").strip()
                raw_percent = (request.POST.get(f"percent_{sid}") or "").strip()
                raw_comment = (request.POST.get(f"teacher_comment_{sid}") or "").strip()
                absent_in_exam = bool(request.POST.get(f"absent_{sid}"))
                retake_recommended = bool(request.POST.get(f"retake_{sid}"))

                if absent_in_exam:
                    raw_score = ""
                    raw_percent = ""
                elif raw_score and not raw_percent:
                    try:
                        computed_percent = (Decimal(raw_score) / max_score) * Decimal("100")
                        raw_percent = str(max(Decimal("0"), min(computed_percent, Decimal("100"))).quantize(Decimal("0.1")))
                    except Exception:
                        raw_percent = ""

                has_any_input = bool(
                    raw_score
                    or raw_percent
                    or raw_comment
                    or absent_in_exam
                    or retake_recommended
                    or work_files
                    or task_files
                )
                if not has_any_input:
                    continue

                row_form = ExamResultRowForm(
                    {
                        "score": raw_score,
                        "percent": raw_percent,
                        "teacher_comment": raw_comment or session_comment,
                        "assignment_description": session_task,
                        "absent_in_exam": absent_in_exam,
                        "retake_recommended": retake_recommended,
                    },
                    require_result=bool(settings_obj.exam_result_required or is_finalize),
                )
                if not row_form.is_valid():
                    row_errors.append((enrollment.student.get_full_name(), row_form.errors.as_text()))
                    continue

                rows.append(
                    {
                        "student": enrollment.student,
                        "score": row_form.cleaned_data.get("score"),
                        "percent": row_form.cleaned_data.get("percent"),
                        "teacher_comment": row_form.cleaned_data.get("teacher_comment"),
                        "assignment_description": row_form.cleaned_data.get("assignment_description"),
                        "absent_in_exam": row_form.cleaned_data.get("absent_in_exam"),
                        "retake_recommended": row_form.cleaned_data.get("retake_recommended"),
                        "work_files": work_files,
                        "task_files": task_files,
                    }
                )

            if row_errors:
                for student_name, err in row_errors:
                    messages.error(request, f"{student_name}: {err}")
            else:
                saved_count = 0
                if rows:
                    try:
                        saved_count = save_exam_results_batch(
                            session=session,
                            actor=request.user,
                            rows=rows,
                            finalize=is_finalize,
                        )
                    except ValueError as exc:
                        messages.error(request, str(exc))
                        saved_count = -1
                elif is_finalize:
                    session_progress = get_exam_session_progress(session=session)
                    session.status = (
                        ExamSession.STATUS_COMPLETED
                        if session_progress["is_completed"]
                        else ExamSession.STATUS_DRAFT
                    )
                    if session.teacher_decision != ExamSession.DECISION_YES:
                        session.teacher_decision = ExamSession.DECISION_YES
                    session.updated_by = request.user
                    session.save(update_fields=["status", "teacher_decision", "updated_by", "updated_at"])

                if saved_count >= 0:
                    session.refresh_from_db()
                    session_progress = get_exam_session_progress(session=session)

                    if is_finalize:
                        if not session_progress["is_completed"]:
                            messages.error(
                                request,
                                "Sessiyani yakunlash uchun barcha o'quvchilar bo'yicha ball yoki qatnashmagan holati kiritilishi kerak.",
                            )
                        else:
                            if not was_completed and session.status == ExamSession.STATUS_COMPLETED:
                                notify_exam_results(session)
                                auto_check_certificate_eligibility(session)
                                messages.success(request, "Sessiya yakunlandi. Bildirishnomalar va sertifikat tekshiruvi ishga tushdi.")
                            else:
                                messages.info(request, "Sessiya allaqachon yakunlangan.")
                        return redirect(_exam_entry_url(session.id, max_score))

                    if saved_count > 0:
                        messages.success(request, f"{saved_count} ta o'quvchi bo'yicha imtihon natijalari saqlandi.")
                        return redirect(_exam_entry_url(session.id, max_score))
                    if uploaded_task_file_count or note_updated:
                        messages.success(request, "Sessiya ma'lumotlari yangilandi.")
                        return redirect(_exam_entry_url(session.id, max_score))
                    messages.info(request, "Hozircha saqlash uchun yangi natija yo'q.")

        session_progress = get_exam_session_progress(session=session)

        return render(
            request,
            "education/exam_session_entry.html",
            {
                "session": session,
                "group": session.group,
                "enrollments": enrollments,
                "existing_results": existing_results,
                "exam_settings": settings_obj,
                "session_task_default": session_task_default,
                "session_comment_default": session_comment_default,
                "session_progress": session_progress,
                "max_score": max_score,
                "passing_percent": passing_percent,
            },
        )
    except Http404:
        raise
    except Exception:
        logger.exception("exam_session_entry failed: session_id=%s", session_id)
        messages.error(request, "Imtihon sessiyasi bilan ishlashda xatolik yuz berdi.")
        return redirect("education:teacher_exam_history")



@login_required
@require_feature("imtihon")
def group_exam_history(request, group_id: int):
    from core.tenant import get_request_center
    from education.models import ExamSession

    center = get_request_center(request)
    disabled_response = _ensure_center_ui_feature(
        request,
        center,
        FEATURE_UI_EXAM_SESSIONS,
        message="Imtihon sessiyalari bo'limi bu markaz uchun o'chirilgan.",
    )
    if disabled_response:
        return disabled_response
    group_qs = Group.objects.all()
    if center:
        group_qs = group_qs.filter(center=center)
    group = get_object_or_404(group_qs, pk=group_id)

    if not _teacher_or_management_can_access_group(request.user, group):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    sessions = ExamSession.objects.filter(group=group).select_related("teacher", "created_by").order_by("-exam_date", "-id")
    status_filter = (request.GET.get("status") or "").strip()
    if status_filter in {ExamSession.STATUS_DRAFT, ExamSession.STATUS_COMPLETED, ExamSession.STATUS_CANCELLED}:
        sessions = sessions.filter(status=status_filter)

    return render(
        request,
        "education/group_exam_history.html",
        {
            "group": group,
            "sessions": sessions,
            "status_filter": status_filter,
        },
    )



@login_required
@require_feature("imtihon")
def teacher_exam_history(request):
    from core.tenant import get_request_center
    from education.models import ExamSession

    center = get_request_center(request)
    disabled_response = _ensure_center_ui_feature(
        request,
        center,
        FEATURE_UI_EXAM_SESSIONS,
        message="Imtihon sessiyalari bo'limi bu markaz uchun o'chirilgan.",
    )
    if disabled_response:
        return disabled_response
    role = getattr(request.user, "role", None)
    if not request.user.is_superuser and role not in ("director", "manager", "teacher"):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    sessions = ExamSession.objects.select_related("group", "teacher", "center").order_by("-exam_date", "-id")
    if center:
        sessions = sessions.filter(center=center)

    if role == "teacher" and not request.user.is_superuser:
        sessions = sessions.filter(teacher=request.user)
    else:
        teacher_id = _get_int(request.GET, "teacher", 0)
        if teacher_id:
            sessions = sessions.filter(teacher_id=teacher_id)

    group_id = _get_int(request.GET, "group", 0)
    if group_id:
        sessions = sessions.filter(group_id=group_id)

    back_group_id = _get_int(request.GET, "back_group", 0)
    if not back_group_id and group_id:
        back_group_id = group_id

    date_from = parse_date(request.GET.get("date_from") or "")
    date_to = parse_date(request.GET.get("date_to") or "")
    if date_from:
        sessions = sessions.filter(exam_date__gte=date_from)
    if date_to:
        sessions = sessions.filter(exam_date__lte=date_to)

    teachers = User.objects.filter(role="teacher", center=center).order_by("ism", "familya") if center else User.objects.none()
    groups = Group.objects.filter(center=center).order_by("nom") if center else Group.objects.none()
    return render(
        request,
        "education/teacher_exam_history.html",
        {
            "sessions": sessions,
            "teachers": teachers,
            "groups": groups,
            "back_group_id": back_group_id,
            "filters": {
                "teacher": _get_int(request.GET, "teacher", 0),
                "group": group_id,
                "back_group": back_group_id,
                "date_from": date_from.isoformat() if date_from else "",
                "date_to": date_to.isoformat() if date_to else "",
            },
        },
    )



@login_required
@require_feature("imtihon")
def exam_session_detail(request, session_id: int):
    from core.tenant import get_request_center
    from education.models import ExamResult, ExamSession

    center = get_request_center(request)
    disabled_response = _ensure_center_ui_feature(
        request,
        center,
        FEATURE_UI_EXAM_SESSIONS,
        message="Imtihon sessiyalari bo'limi bu markaz uchun o'chirilgan.",
    )
    if disabled_response:
        return disabled_response
    qs = ExamSession.objects.select_related("group", "teacher", "center")
    if center:
        qs = qs.filter(center=center)
    session = get_object_or_404(qs, pk=session_id)

    if not _teacher_or_management_can_access_group(request.user, session.group):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    results = (
        ExamResult.objects.filter(session=session)
        .select_related("student", "teacher")
        .prefetch_related("files")
        .order_by("student__ism", "student__familya")
    )

    return render(
        request,
        "education/exam_session_detail.html",
        {
            "session": session,
            "group": session.group,
            "results": results,
        },
    )



@login_required
@require_feature("imtihon")
def failed_students_list(request):
    from core.tenant import get_request_center
    from ..forms import ExamResultFollowUpForm
    from education.models import ExamResult
    from education.services.audit_service import log_education_event

    try:
        role = getattr(request.user, "role", None)
        if not request.user.is_superuser and role not in ("director", "manager", "teacher"):
            return HttpResponseForbidden("Sizda ruxsat yo'q.")

        center = get_request_center(request)
        disabled_response = _ensure_center_ui_feature(
            request,
            center,
            FEATURE_UI_FAILED_STUDENTS,
            message="Zaif o'quvchilar bo'limi bu markaz uchun o'chirilgan.",
        )
        if disabled_response:
            return disabled_response
        qs = ExamResult.objects.select_related("student", "group", "teacher", "session")
        if center:
            qs = qs.filter(center=center)
        qs = qs.filter(passed=False).filter(
            Q(absent_in_exam=True) | Q(score__isnull=False) | Q(percent__isnull=False)
        )

        if role == "teacher" and not request.user.is_superuser:
            qs = qs.filter(teacher=request.user)

        group_id = _get_int(request.GET, "group", 0)
        teacher_id = _get_int(request.GET, "teacher", 0)
        date_from = parse_date(request.GET.get("date_from") or "")
        date_to = parse_date(request.GET.get("date_to") or "")
        percent_min = request.GET.get("percent_min")
        percent_max = request.GET.get("percent_max")
        follow_up_status = (request.GET.get("follow_up_status") or "").strip()
        follow_up_pending = (request.GET.get("follow_up_pending") or "").strip().lower() in {"1", "true", "yes", "on"}

        if group_id:
            qs = qs.filter(group_id=group_id)
        if teacher_id and role != "teacher":
            qs = qs.filter(teacher_id=teacher_id)
        if date_from:
            qs = qs.filter(exam_date__gte=date_from)
        if date_to:
            qs = qs.filter(exam_date__lte=date_to)
        if percent_min not in (None, ""):
            try:
                qs = qs.filter(percent__gte=Decimal(str(percent_min)))
            except Exception:
                pass
        if percent_max not in (None, ""):
            try:
                qs = qs.filter(percent__lte=Decimal(str(percent_max)))
            except Exception:
                pass
        valid_follow_statuses = {choice[0] for choice in ExamResult.FOLLOW_UP_CHOICES}
        if follow_up_status in valid_follow_statuses:
            qs = qs.filter(follow_up_status=follow_up_status)
        if follow_up_pending:
            qs = qs.filter(follow_up_status=ExamResult.FOLLOW_UP_PENDING)

        if request.method == "POST":
            result_id = _get_int(request.POST, "result_id", 0)
            result = get_object_or_404(qs, pk=result_id)
            follow_form = ExamResultFollowUpForm(request.POST, instance=result)
            if follow_form.is_valid():
                updated = follow_form.save(commit=False)
                updated.follow_up_updated_by = request.user
                updated.follow_up_updated_at = timezone.now()
                updated.save(
                    update_fields=[
                        "follow_up_status",
                        "follow_up_note",
                        "follow_up_updated_by",
                        "follow_up_updated_at",
                        "updated_at",
                    ]
                )
                log_education_event(
                    center=updated.center,
                    actor=request.user,
                    action_type="exam_followup_updated",
                    entity=updated,
                    payload={"follow_up_status": updated.follow_up_status},
                )
                messages.success(request, "Nazorat holati yangilandi.")
            else:
                messages.error(request, "Nazorat formasi xato.")
            q = request.META.get("QUERY_STRING")
            return redirect(f"{request.path}?{q}" if q else request.path)

        rows = qs.order_by("-exam_date", "-id")
        summary_counts = {
            "total": rows.count(),
            "pending": rows.filter(follow_up_status=ExamResult.FOLLOW_UP_PENDING).count(),
            "absent": rows.filter(absent_in_exam=True).count(),
        }
        groups = Group.objects.filter(center=center).order_by("nom") if center else Group.objects.none()
        if role == "teacher" and not request.user.is_superuser:
            groups = groups.filter(oqituvchi=request.user)
        if role == "teacher" and not request.user.is_superuser:
            teachers = User.objects.filter(pk=request.user.pk)
            teacher_id = request.user.id
        else:
            teachers = (
                User.objects.filter(role="teacher", center=center, is_archived=False).order_by("ism", "familya")
                if center
                else User.objects.none()
            )
        follow_up_choices = ExamResult.FOLLOW_UP_CHOICES

        return render(
            request,
            "education/failed_students_list.html",
            {
                "rows": rows,
                "summary_counts": summary_counts,
                "groups": groups,
                "teachers": teachers,
                "follow_up_choices": follow_up_choices,
                "filters": {
                    "group": group_id,
                    "teacher": teacher_id,
                    "date_from": date_from.isoformat() if date_from else "",
                    "date_to": date_to.isoformat() if date_to else "",
                    "percent_min": percent_min or "",
                    "percent_max": percent_max or "",
                    "follow_up_status": follow_up_status,
                    "follow_up_pending": follow_up_pending,
                },
                "can_edit_follow_up": _director_or_manager(request.user),
            },
        )
    except Http404:
        raise
    except Exception:
        logger.exception("failed_students_list failed")
        messages.error(request, "Zaif o'quvchilar ro'yxatini yuklashda xatolik yuz berdi.")
        return redirect("education:teacher_exam_history")



@login_required
@require_feature("imtihon")
def group_internal_ranking(request, group_id: int):
    from core.tenant import get_request_center
    from education.services.ranking_service import INTERNAL_RANKING_WEIGHTS, build_group_internal_ranking

    center = get_request_center(request)
    group_qs = Group.objects.all()
    if center:
        group_qs = group_qs.filter(center=center)
    group = get_object_or_404(group_qs, pk=group_id)

    if not _teacher_or_management_can_access_group(request.user, group):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    selected_date = parse_date(request.GET.get("date") or "") or localdate()
    rows = build_group_internal_ranking(
        group=group,
        on_date=selected_date,
        actor=request.user,
        persist=True,
    )

    return render(
        request,
        "education/group_internal_ranking.html",
        {
            "group": group,
            "selected_date": selected_date,
            "rows": rows,
            "weights": INTERNAL_RANKING_WEIGHTS,
        },
    )



@login_required
@require_feature("imtihon")
def group_completion_recommendations(request, group_id: int):
    from core.tenant import get_request_center
    from education.services.ranking_service import build_group_completion_recommendations

    center = get_request_center(request)
    group_qs = Group.objects.all()
    if center:
        group_qs = group_qs.filter(center=center)
    group = get_object_or_404(group_qs, pk=group_id)

    if not _teacher_or_management_can_access_group(request.user, group):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    selected_date = parse_date(request.GET.get("date") or "") or localdate()
    recommendation_payload = build_group_completion_recommendations(
        group=group,
        on_date=selected_date,
        actor=request.user,
        persist=True,
    )
    rows = recommendation_payload["rows"]
    selected_status = (request.GET.get("status") or "").strip()
    valid_statuses = {"eligible", "needs_review", "not_eligible"}
    if selected_status in valid_statuses:
        rows = [row for row in rows if row["completion_recommendation"] == selected_status]

    days_to_estimated_end = None
    days_to_estimated_end_abs = None
    if group.estimated_end_date:
        days_to_estimated_end = (group.estimated_end_date - selected_date).days
        days_to_estimated_end_abs = abs(days_to_estimated_end)

    return render(
        request,
        "education/group_completion_recommendations.html",
        {
            "group": group,
            "selected_date": selected_date,
            "rows": rows,
            "thresholds": recommendation_payload["thresholds"],
            "selected_status": selected_status,
            "days_to_estimated_end": days_to_estimated_end,
            "days_to_estimated_end_abs": days_to_estimated_end_abs,
        },
    )



@login_required
@require_POST
@require_feature("imtihon")
def group_closure_action(request, group_id: int):
    from core.tenant import get_request_center
    from education.services.closure_service import apply_group_closure_action

    center = get_request_center(request)
    group_qs = Group.objects.all()
    if center:
        group_qs = group_qs.filter(center=center)
    group = get_object_or_404(group_qs, pk=group_id)

    if not _teacher_or_management_can_access_group(request.user, group):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    action = (request.POST.get("action") or "").strip().lower()
    if action not in {"yes", "no", "later"}:
        messages.error(request, "Noto'g'ri action.")
        return redirect("education:group_detail", pk=group.id)

    if action == "yes" and not _director_or_manager(request.user):
        return HttpResponseForbidden("Guruhni yopish faqat director/manager uchun ruxsat etilgan.")

    selected_date = parse_date(request.POST.get("date") or "") or localdate()
    note = (request.POST.get("note") or "").strip()

    workflow = apply_group_closure_action(
        group=group,
        actor=request.user,
        action=action,
        on_date=selected_date,
        note=note,
    )

    if workflow.status == workflow.STATUS_CLOSED:
        messages.success(request, "Guruhni yopish jarayoni yakunlandi. Tarixiy ma'lumotlar saqlandi.")
    elif workflow.status == workflow.STATUS_CONTINUE:
        messages.info(request, "Guruh davom etadi. Attendance va payment flow o'zgarmaydi.")
    else:
        messages.info(request, "Closure eslatmasi keyinga qoldirildi.")
    return redirect("education:group_detail", pk=group.id)



@login_required
@require_feature("sertifikat")
def certificate_templates_view(request):
    from core.tenant import get_request_center
    from ..forms import CertificateTemplateForm
    from education.models import CertificateTemplate
    from education.services.audit_service import log_education_event

    center = get_request_center(request)
    if not center:
        raise Http404("Center not found")
    disabled_response = _ensure_center_ui_feature(
        request,
        center,
        FEATURE_UI_CERTIFICATES,
        message="Sertifikatlar bo'limi bu markaz uchun o'chirilgan.",
    )
    if disabled_response:
        return disabled_response

    if not _director_or_manager(request.user):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    form = CertificateTemplateForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.center = center
        obj.uploaded_by = request.user
        obj.save()
        if obj.is_active:
            CertificateTemplate.objects.filter(center=center, template_type=obj.template_type).exclude(pk=obj.pk).update(
                is_active=False
            )
        log_education_event(
            center=center,
            actor=request.user,
            action_type="certificate_template_uploaded",
            entity=obj,
            payload={"template_type": obj.template_type},
        )
        messages.success(request, "Shablon saqlandi.")
        return redirect("education:certificate_templates")

    templates = CertificateTemplate.objects.filter(center=center).order_by("-updated_at")
    groups_overview = (
        Group.objects.filter(center=center, is_archived=False)
        .select_related("oqituvchi")
        .annotate(
            active_students_count=Count(
                "enrollments",
                filter=Q(enrollments__is_active=True, enrollments__is_deleted=False),
                distinct=True,
            ),
            issued_certificates_count=Count(
                "certificates",
                filter=Q(certificates__status="issued"),
                distinct=True,
            ),
        )
        .order_by("nom")
    )
    return render(
        request,
        "education/certificate_templates.html",
        {
            "form": form,
            "templates": templates,
            "groups_overview": groups_overview,
            "active_templates_count": templates.filter(is_active=True).count(),
        },
    )



@login_required
@require_POST
@require_feature("sertifikat")
def certificate_template_activate(request, template_id: int):
    from core.tenant import get_request_center
    from education.models import CertificateTemplate
    from education.services.audit_service import log_education_event

    if not _director_or_manager(request.user):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    center = get_request_center(request)
    disabled_response = _ensure_center_ui_feature(
        request,
        center,
        FEATURE_UI_CERTIFICATES,
        message="Sertifikatlar bo'limi bu markaz uchun o'chirilgan.",
    )
    if disabled_response:
        return disabled_response
    qs = CertificateTemplate.objects.all()
    if center:
        qs = qs.filter(center=center)
    template = get_object_or_404(qs, pk=template_id)

    CertificateTemplate.objects.filter(center=template.center, template_type=template.template_type).update(is_active=False)
    template.is_active = True
    template.save(update_fields=["is_active", "updated_at"])

    log_education_event(
        center=template.center,
        actor=request.user,
        action_type="certificate_template_activated",
        entity=template,
        payload={"template_type": template.template_type},
    )
    messages.success(request, "Shablon faol qilib belgilandi.")
    return redirect("education:certificate_templates")



@login_required
@require_feature("sertifikat")
def group_certificate_candidates(request, group_id: int):
    from core.tenant import get_request_center
    from education.models import CertificateRecord
    from education.services.ranking_service import build_group_completion_recommendations

    try:
        center = get_request_center(request)
        disabled_response = _ensure_center_ui_feature(
            request,
            center,
            FEATURE_UI_CERTIFICATES,
            message="Sertifikatlar bo'limi bu markaz uchun o'chirilgan.",
        )
        if disabled_response:
            return disabled_response
        group_qs = Group.objects.all()
        if center:
            group_qs = group_qs.filter(center=center)
        group = get_object_or_404(group_qs, pk=group_id)

        if not _teacher_or_management_can_access_group(request.user, group):
            return HttpResponseForbidden("Sizda ruxsat yo'q.")

        selected_date = parse_date(request.GET.get("date") or "") or localdate()
        recommendation_payload = build_group_completion_recommendations(
            group=group,
            on_date=selected_date,
            actor=request.user,
            persist=True,
        )
        rows = recommendation_payload["rows"]
        existing_certs = {}
        for cert in (
            CertificateRecord.objects.filter(
                group=group,
                status__in=[CertificateRecord.STATUS_DRAFT, CertificateRecord.STATUS_ISSUED],
            )
            .select_related("student")
            .order_by("student_id", "-created_at", "-id")
        ):
            current = existing_certs.get(cert.student_id)
            if current is None or (current.status != CertificateRecord.STATUS_ISSUED and cert.status == CertificateRecord.STATUS_ISSUED):
                existing_certs[cert.student_id] = cert

        for row in rows:
            row["certificate"] = existing_certs.get(row["student"].id)

        return render(
            request,
            "education/group_certificate_candidates.html",
            {
                "group": group,
                "selected_date": selected_date,
                "rows": rows,
                "thresholds": recommendation_payload["thresholds"],
                "can_issue": _director_or_manager(request.user),
            },
        )
    except Http404:
        raise
    except Exception:
        logger.exception("group_certificate_candidates failed: group_id=%s", group_id)
        messages.error(request, "Sertifikat nomzodlarini yuklashda xatolik yuz berdi.")
        return redirect("education:group_detail", pk=group_id)



@login_required
@require_POST
@require_feature("sertifikat")
def issue_certificate_action(request, group_id: int, student_id: int):
    from core.tenant import get_request_center
    from ..forms import CertificateIssueForm
    from education.services.certificate_service import issue_certificate_for_student

    try:
        if not _director_or_manager(request.user):
            return HttpResponseForbidden("Sizda ruxsat yo'q.")

        center = get_request_center(request)
        disabled_response = _ensure_center_ui_feature(
            request,
            center,
            FEATURE_UI_CERTIFICATES,
            message="Sertifikatlar bo'limi bu markaz uchun o'chirilgan.",
        )
        if disabled_response:
            return disabled_response
        group_qs = Group.objects.all()
        if center:
            group_qs = group_qs.filter(center=center)
        group = get_object_or_404(group_qs, pk=group_id)
        student_qs = User.objects.filter(role="student")
        if center:
            student_qs = student_qs.filter(center=center)
        student = get_object_or_404(student_qs, pk=student_id)

        if not Enrollment.objects.filter(group=group, student=student).exists():
            return HttpResponseForbidden("Student bu guruhga biriktirilmagan.")

        form = CertificateIssueForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Sertifikat berish formasi xato.")
            return redirect("education:group_certificate_candidates", group_id=group.id)

        cert = issue_certificate_for_student(
            group=group,
            student=student,
            actor=request.user,
            certificate_type=form.cleaned_data["certificate_type"],
            note=form.cleaned_data.get("note", ""),
            request=request,
        )
        messages.success(request, f"Sertifikat tasdiqlandi: {cert.certificate_number}")
        return redirect("education:certificate_detail", certificate_id=cert.id)
    except Http404:
        raise
    except Exception:
        logger.exception(
            "issue_certificate_action failed: group_id=%s student_id=%s",
            group_id,
            student_id,
        )
        messages.error(request, "Sertifikatni tasdiqlashda xatolik yuz berdi.")
        return redirect("education:group_certificate_candidates", group_id=group_id)



@login_required
@require_feature("sertifikat")
def certificate_detail(request, certificate_id: int):
    from core.tenant import get_request_center
    from education.models import CertificateRecord
    from education.services.certificate_service import user_can_view_certificate

    center = get_request_center(request)
    disabled_response = _ensure_center_ui_feature(
        request,
        center,
        FEATURE_UI_CERTIFICATES,
        message="Sertifikatlar bo'limi bu markaz uchun o'chirilgan.",
    )
    if disabled_response:
        return disabled_response
    qs = CertificateRecord.objects.select_related("group", "student", "center", "template", "summary")
    if center:
        qs = qs.filter(center=center)
    cert = get_object_or_404(qs, pk=certificate_id)

    if not user_can_view_certificate(request.user, cert):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    return render(
        request,
        "education/certificate_detail.html",
        {
            "cert": cert,
        },
    )



@login_required
@require_feature("sertifikat")
def certificate_download_pdf(request, certificate_id: int):
    from core.tenant import get_request_center
    from education.models import CertificateRecord
    from education.services.certificate_service import (
        PDF_LAYOUT_VERSION,
        regenerate_certificate_pdf,
        user_can_view_certificate,
    )

    center = get_request_center(request)
    disabled_response = _ensure_center_ui_feature(
        request,
        center,
        FEATURE_UI_CERTIFICATES,
        message="Sertifikatlar bo'limi bu markaz uchun o'chirilgan.",
    )
    if disabled_response:
        return disabled_response
    qs = CertificateRecord.objects.select_related("group", "student", "center", "summary")
    if center:
        qs = qs.filter(center=center)
    cert = get_object_or_404(qs, pk=certificate_id)

    if not user_can_view_certificate(request.user, cert):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    metadata = cert.metadata if isinstance(cert.metadata, dict) else {}
    layout_version = metadata.get("pdf_layout_version")
    if (not cert.pdf_file) or layout_version != PDF_LAYOUT_VERSION:
        cert = regenerate_certificate_pdf(record=cert, request=request)

    cert.pdf_file.open("rb")
    return FileResponse(
        cert.pdf_file,
        as_attachment=True,
        filename=f"{cert.certificate_number}.pdf",
        content_type="application/pdf",
    )



def certificate_verify(request, certificate_number: str):
    from education.models import CertificateRecord
    from education.services.certificate_service import record_verification_hit

    cert = get_object_or_404(
        CertificateRecord.objects.select_related("group", "student", "center"),
        certificate_number=certificate_number,
    )

    record_verification_hit(record=cert, request=request)
    return render(
        request,
        "education/certificate_verify.html",
        {
            "cert": cert,
        },
    )



@login_required
def student_exam_report(request, student_id: int):
    from core.tenant import get_request_center, get_tenant_object_or_404

    center = get_request_center(request)
    student = get_tenant_object_or_404(User, request, pk=student_id, role="student")

    viewer = request.user
    if viewer.role == "student" and viewer.id != student.id:
        return HttpResponseForbidden("Siz faqat o'zingizning natijangizni ko'ra olasiz.")
    if viewer.role == "parent" and student not in viewer.children.all():
        return HttpResponseForbidden("Siz faqat farzandingizning natijalarini ko'ra olasiz.")
    if viewer.role == "teacher":
        teaches_student = Enrollment.objects.filter(
            student=student,
            group__oqituvchi=viewer,
            is_active=True,
        ).exists()
        if not teaches_student:
            return HttpResponseForbidden("Siz bu o'quvchining natijasini ko'ra olmaysiz.")
    if viewer.role not in ("student", "parent", "teacher", "director", "manager") and not viewer.is_superuser:
        return HttpResponseForbidden("Ruxsat yo'q.")

    from education.models import ExamResult
    from education.services.exam_service import get_student_exam_summary
    from education.services.ranking_service import get_student_academic_summaries

    qs = ExamResult.objects.select_related("group", "teacher", "session").filter(student=student)
    if center:
        qs = qs.filter(center=center)
    certificate_qs = CertificateRecord.objects.select_related("group", "center").filter(student=student)
    if center:
        certificate_qs = certificate_qs.filter(center=center)

    summary = get_student_exam_summary(student=student)
    academic_summaries = get_student_academic_summaries(student=student, center=center)
    return render(
        request,
        "education/student_exam_report.html",
        {
            "student": student,
            "results": qs.order_by("-exam_date", "-id"),
            "summary": summary,
            "academic_summaries": academic_summaries,
            "certificates": certificate_qs.order_by("-created_at", "-id"),
        },
    )

