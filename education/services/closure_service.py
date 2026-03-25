from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from education.models import GroupClosureWorkflow
from education.services.audit_service import log_education_event
from education.services.group_schedule_service import calculate_estimated_end_date
from education.services.ranking_service import build_group_completion_recommendations


CLOSURE_PROMPT_WINDOW_DAYS = 7


def get_or_create_group_closure_workflow(*, group):
    workflow, _ = GroupClosureWorkflow.objects.get_or_create(
        group=group,
        defaults={"center": group.center},
    )
    if not workflow.center_id and group.center_id:
        workflow.center = group.center
        workflow.save(update_fields=["center", "updated_at"])
    return workflow


def _estimated_end_date(group):
    if group.estimated_end_date:
        return group.estimated_end_date
    return calculate_estimated_end_date(
        course_start_date=group.course_start_date,
        duration_months=group.duration_months,
        lessons_per_week=group.lessons_per_week,
    )


def get_group_closure_state(*, group, on_date=None):
    on_date = on_date or timezone.localdate()
    workflow = get_or_create_group_closure_workflow(group=group)

    estimated_end = _estimated_end_date(group)
    days_to_end = None
    should_prompt = False
    if estimated_end:
        days_to_end = (estimated_end - on_date).days
        should_prompt = days_to_end <= CLOSURE_PROMPT_WINDOW_DAYS

    if workflow.status == GroupClosureWorkflow.STATUS_CLOSED:
        should_prompt = False

    if workflow.status == GroupClosureWorkflow.STATUS_REMIND_LATER and workflow.reminder_date:
        should_prompt = should_prompt and workflow.reminder_date <= on_date

    prompt_message = ""
    if should_prompt:
        if days_to_end is None:
            prompt_message = "Guruhni yopish bo‘yicha final tekshiruvga tayyormisiz?"
        elif days_to_end < 0:
            prompt_message = "Guruh taxminiy tugash muddatidan o‘tgan. Yopish workflowini boshlaysizmi?"
        else:
            prompt_message = f"Guruh tugashiga taxminan {days_to_end} kun qoldi. Yopishga tayyormisiz?"

    return {
        "workflow": workflow,
        "estimated_end_date": estimated_end,
        "days_to_end": days_to_end,
        "should_prompt": bool(should_prompt),
        "is_closed": workflow.status == GroupClosureWorkflow.STATUS_CLOSED,
        "prompt_message": prompt_message,
    }


@transaction.atomic
def apply_group_closure_action(*, group, actor, action: str, on_date=None, note: str = ""):
    on_date = on_date or timezone.localdate()
    workflow = get_or_create_group_closure_workflow(group=group)

    if action == "yes":
        workflow.status = GroupClosureWorkflow.STATUS_CLOSED
        workflow.decision_date = on_date
        workflow.closed_at = timezone.now()
        workflow.closed_by = actor
        workflow.note = note or workflow.note
        workflow.reminder_date = None
        workflow.save()

        build_group_completion_recommendations(
            group=group,
            on_date=on_date,
            actor=actor,
            persist=True,
        )

        log_education_event(
            center=group.center,
            actor=actor,
            action_type="group_closed",
            entity=workflow,
            payload={"group_id": group.id, "action": "yes"},
        )
        return workflow

    if action == "no":
        workflow.status = GroupClosureWorkflow.STATUS_CONTINUE
        workflow.decision_date = on_date
        workflow.reminder_date = None
        workflow.note = note or workflow.note
        workflow.save()
        log_education_event(
            center=group.center,
            actor=actor,
            action_type="group_closure_continue",
            entity=workflow,
            payload={"group_id": group.id, "action": "no"},
        )
        return workflow

    workflow.status = GroupClosureWorkflow.STATUS_REMIND_LATER
    workflow.decision_date = on_date
    workflow.reminder_date = on_date + timedelta(days=CLOSURE_PROMPT_WINDOW_DAYS)
    workflow.note = note or workflow.note
    workflow.save()
    log_education_event(
        center=group.center,
        actor=actor,
        action_type="group_closure_remind_later",
        entity=workflow,
        payload={"group_id": group.id, "action": "later", "reminder_date": str(workflow.reminder_date)},
    )
    return workflow
