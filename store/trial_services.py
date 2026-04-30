from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from core.models import Notification

from .lead_services import confirm_lead, convert_lead_to_student_safe, get_status_by_code, log_lead_activity
from .models import LeadActivity, LeadStatus, TrialLesson, TrialLessonActivity


def _notify(recipient, title: str, message: str, center=None):
    if not recipient:
        return
    Notification.objects.create(
        center=center or getattr(recipient, "center", None),
        recipient=recipient,
        sender=None,
        title=title,
        message=message,
        type="system",
    )


def log_trial_activity(
    *,
    trial: TrialLesson,
    action: str,
    actor=None,
    from_value: str = "",
    to_value: str = "",
    note: str = "",
):
    return TrialLessonActivity.objects.create(
        center=trial.center,
        trial_lesson=trial,
        action=action,
        actor=actor,
        from_value=(from_value or "")[:255],
        to_value=(to_value or "")[:255],
        note=note,
    )


@transaction.atomic
def handle_trial_created(*, trial: TrialLesson, actor=None):
    log_trial_activity(
        trial=trial,
        action=TrialLessonActivity.Action.CREATED,
        actor=actor,
        note="Trial dars yaratildi.",
    )

    if trial.lead:
        status = get_status_by_code(center=trial.center or trial.lead.center, code=LeadStatus.Code.TRIAL_SCHEDULED)
        if status and trial.lead.status_id != status.id:
            prev_status = trial.lead.status.nom if trial.lead.status else ""
            trial.lead.status = status
            trial.lead.save(update_fields=["status", "updated_at"])
            log_lead_activity(
                lead=trial.lead,
                action=LeadActivity.Action.STATUS_CHANGED,
                actor=actor,
                from_value=prev_status,
                to_value=status.nom,
                note="Trial belgilanishi bilan status yangilandi.",
            )

        log_lead_activity(
            lead=trial.lead,
            action=LeadActivity.Action.TRIAL_SCHEDULED,
            actor=actor,
            to_value=trial.scheduled_at.strftime("%Y-%m-%d %H:%M"),
            note="Lead uchun trial dars belgilandi.",
        )

    _notify(
        recipient=trial.teacher,
        center=trial.center,
        title="Yangi trial dars",
        message=f"{trial.lead.full_name} uchun trial {trial.scheduled_at:%d.%m.%Y %H:%M} ga belgilandi.",
    )
    if trial.lead and trial.lead.assigned_manager and trial.lead.assigned_manager_id != trial.teacher_id:
        _notify(
            recipient=trial.lead.assigned_manager,
            center=trial.center,
            title="Trial belgilandi",
            message=f"Lead #{trial.lead_id} uchun trial jadvalga tushdi.",
        )


@transaction.atomic
def handle_trial_updated(*, trial: TrialLesson, actor=None, previous_result: str = ""):
    log_trial_activity(
        trial=trial,
        action=TrialLessonActivity.Action.UPDATED,
        actor=actor,
        note="Trial ma'lumotlari yangilandi.",
    )

    if previous_result != trial.result_status:
        log_trial_activity(
            trial=trial,
            action=TrialLessonActivity.Action.RESULT_CHANGED,
            actor=actor,
            from_value=previous_result,
            to_value=trial.result_status,
            note="Trial natijasi o'zgardi.",
        )

    _apply_trial_result_effects(trial=trial, actor=actor)


@transaction.atomic
def _apply_trial_result_effects(*, trial: TrialLesson, actor=None):
    lead = trial.lead
    if not lead:
        return

    center = trial.center or lead.center
    current_status_name = lead.status.nom if lead.status else ""

    if trial.result_status == TrialLesson.ResultStatus.ATTENDED:
        target_status = get_status_by_code(center=center, code=LeadStatus.Code.TRIAL_ATTENDED)
        if trial.attended is None:
            trial.attended = True
            trial.save(update_fields=["attended", "updated_at"])
    elif trial.result_status == TrialLesson.ResultStatus.ABSENT:
        target_status = get_status_by_code(center=center, code=LeadStatus.Code.NO_ANSWER)
        if trial.attended is None:
            trial.attended = False
            trial.save(update_fields=["attended", "updated_at"])
    elif trial.result_status == TrialLesson.ResultStatus.NOT_INTERESTED:
        target_status = get_status_by_code(center=center, code=LeadStatus.Code.LOST)
        if not lead.lost_reason:
            lead.lost_reason = "Trialdan keyin qiziqish bildirmadi"
    elif trial.result_status == TrialLesson.ResultStatus.FOLLOW_UP_NEEDED:
        target_status = get_status_by_code(center=center, code=LeadStatus.Code.CONTACTED)
        if not lead.next_follow_up_date:
            lead.next_follow_up_date = timezone.localdate() + timedelta(days=1)
    elif trial.result_status == TrialLesson.ResultStatus.CONVERTED:
        target_status = get_status_by_code(center=center, code=LeadStatus.Code.REGISTERED)
        confirm_lead(lead=lead, actor=actor)
        user, _, _ = convert_lead_to_student_safe(lead, converted_by=actor, target_center=center)
        trial.registered_after_trial = True
        trial.attended = True
        trial.save(update_fields=["registered_after_trial", "attended", "updated_at"])
        log_trial_activity(
            trial=trial,
            action=TrialLessonActivity.Action.CONVERTED,
            actor=actor,
            to_value=f"student#{user.id}",
            note="Trial natijasi bo'yicha lead studentga o'tkazildi.",
        )
    else:
        target_status = None

    if target_status and lead.status_id != target_status.id:
        lead.status = target_status
        lead.save(update_fields=["status", "next_follow_up_date", "lost_reason", "updated_at"])
        log_lead_activity(
            lead=lead,
            action=LeadActivity.Action.STATUS_CHANGED,
            actor=actor,
            from_value=current_status_name,
            to_value=target_status.nom,
            note=f"Trial natijasi asosida status yangilandi ({trial.result_status}).",
        )
    else:
        # Status o'zgarmasa ham follow-up/lost reason kabi maydonlar saqlansin.
        lead.save(update_fields=["next_follow_up_date", "lost_reason", "updated_at"])

    log_lead_activity(
        lead=lead,
        action=LeadActivity.Action.TRIAL_RESULT_CHANGED,
        actor=actor,
        from_value=current_status_name,
        to_value=trial.result_status,
        note="Trial natijasi qayd etildi.",
    )


def build_trial_analytics(center, *, start=None, end=None):
    qs = TrialLesson.objects.filter(center=center)
    if start:
        qs = qs.filter(scheduled_at__date__gte=start)
    if end:
        qs = qs.filter(scheduled_at__date__lte=end)

    teacher_stats = (
        qs.values("teacher__id", "teacher__ism", "teacher__familya")
        .annotate(
            total=Count("id"),
            converted=Count("id", filter=Q(result_status=TrialLesson.ResultStatus.CONVERTED)),
        )
        .order_by("-converted", "-total")
    )

    course_stats = (
        qs.values("group__id", "group__nom")
        .annotate(total=Count("id"), converted=Count("id", filter=Q(result_status=TrialLesson.ResultStatus.CONVERTED)))
        .order_by("-total")
    )

    overall = {
        "total": qs.count(),
        "converted": qs.filter(result_status=TrialLesson.ResultStatus.CONVERTED).count(),
        "attended": qs.filter(result_status__in=[TrialLesson.ResultStatus.ATTENDED, TrialLesson.ResultStatus.CONVERTED]).count(),
        "absent": qs.filter(result_status=TrialLesson.ResultStatus.ABSENT).count(),
    }

    return {
        "overall": overall,
        "teacher_stats": list(teacher_stats),
        "course_stats": list(course_stats),
    }
