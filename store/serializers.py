from __future__ import annotations

from django.template.defaultfilters import truncatechars
from django.utils import timezone

from .models import Lead, LeadGroup
from .lead_services import (
    build_dynamic_lead_status_choices,
    is_lead_confirmed,
    resolve_dynamic_status_label,
    resolve_dynamic_status_tone,
    resolve_dynamic_status_value,
)


def serialize_manager(user) -> dict | None:
    if not user:
        return None
    return {
        "id": user.id,
        "name": user.get_full_name() or user.email,
        "teacher_share_percent": int(getattr(user, "oqituvchi_foizi", 0) or 0),
    }


def serialize_group(group) -> dict:
    return {
        "id": group.id,
        "name": group.nom,
    }


def serialize_department(department) -> dict | None:
    if not department:
        return None
    return {
        "id": department.id,
        "name": department.name,
    }


def serialize_lead_group_option(lead_group) -> dict:
    return {
        "id": lead_group.id,
        "value": str(lead_group.id),
        "name": lead_group.name,
        "label": lead_group.name,
        "status": lead_group.status,
        "status_label": lead_group.get_status_display(),
    }


def serialize_lead_subject(subject) -> dict:
    return {
        "id": subject.id,
        "value": str(subject.id),
        "name": subject.nom,
        "label": subject.nom,
        "color": getattr(subject, "display_color", "#64748b"),
        "is_active": bool(getattr(subject, "is_active", True)),
    }


def serialize_lead_status(status) -> dict:
    if not status:
        return {}
    value = str(status.get("value", ""))
    return {
        "id": status.get("id"),
        "value": value,
        "name": status.get("label") or status.get("name") or value,
        "label": status.get("label") or status.get("name") or value,
        "tone": status.get("tone") or "gray",
        "kind": status.get("kind") or "default",
        "code": status.get("code") or "",
        "is_active": bool(status.get("is_active", True)),
    }


def serialize_lead_activity(activity) -> dict:
    actor = getattr(activity, "actor", None)
    created_at = timezone.localtime(activity.created_at) if activity.created_at else None
    return {
        "id": activity.id,
        "action": activity.action,
        "action_label": activity.get_action_display(),
        "actor": actor.get_full_name() if actor else "Tizim",
        "from_value": activity.from_value or "",
        "to_value": activity.to_value or "",
        "note": activity.note or "",
        "created_at": created_at.isoformat() if created_at else "",
        "created_at_label": created_at.strftime("%d.%m.%Y %H:%M") if created_at else "",
    }


def serialize_lead(lead: Lead) -> dict:
    created_at = timezone.localtime(lead.qoshilgan_sana) if lead.qoshilgan_sana else None
    added_to_group_at = timezone.localtime(lead.added_to_group_at) if lead.added_to_group_at else None
    archived_at = timezone.localtime(lead.archived_at) if lead.archived_at else None
    manager = serialize_manager(lead.assigned_manager)
    note = lead.note or ""
    status_value = resolve_dynamic_status_value(lead)
    return {
        "id": lead.id,
        "name": lead.full_name or lead.ism,
        "phone": lead.phone,
        "subject": str(lead.yonalish_id or ""),
        "subject_label": lead.subject_name,
        "subject_color": lead.subject_color,
        "status": status_value,
        "status_label": resolve_dynamic_status_label(lead),
        "status_tone": resolve_dynamic_status_tone(lead),
        "parent_name": lead.parent_name or "",
        "bilim_darajasi": lead.bilim_darajasi or "",
        "created_at": created_at.isoformat() if created_at else "",
        "created_at_label": created_at.strftime("%d.%m.%Y") if created_at else "",
        "created_at_full": created_at.strftime("%d.%m.%Y %H:%M") if created_at else "",
        "added_to_group_at": added_to_group_at.isoformat() if added_to_group_at else "",
        "added_to_group_at_label": added_to_group_at.strftime("%d.%m.%Y %H:%M") if added_to_group_at else "",
        "added_to_group_date_label": added_to_group_at.strftime("%d.%m.%Y") if added_to_group_at else "",
        "added_to_group_time_label": added_to_group_at.strftime("%H:%M") if added_to_group_at else "",
        "archived_at": archived_at.isoformat() if archived_at else "",
        "archived_at_label": archived_at.strftime("%d.%m.%Y %H:%M") if archived_at else "",
        "note": note,
        "note_short": truncatechars(note, 72),
        "manager": manager,
        "manager_name": manager["name"] if manager else "Biriktirilmagan",
        "lead_group_id": lead.lead_group_id,
        "lead_group_name": getattr(lead.lead_group, "name", "") or "",
        "lead_group": serialize_lead_group_option(lead.lead_group) if lead.lead_group_id else None,
        "is_confirmed": bool(is_lead_confirmed(lead)),
        "can_convert": bool(is_lead_confirmed(lead) and not lead.converted_to_student and not lead.is_archived),
        "is_converted": bool(lead.converted_to_student),
        "is_archived": bool(lead.is_archived),
    }


def serialize_lead_detail(lead: Lead) -> dict:
    payload = serialize_lead(lead)
    payload.update(
        {
            "note": lead.note or "",
            "source": getattr(lead.manba, "nom", "") or "",
            "course": getattr(lead.yonalish, "nom", "") or "",
            "subject_object": serialize_lead_subject(lead.yonalish) if lead.yonalish_id else None,
            "secondary_phone": lead.telefon2 or "",
            "parent_phone": lead.parent_phone or "",
            "history": [serialize_lead_activity(item) for item in lead.activities.select_related("actor").all()[:20]],
            "converted_user_id": lead.converted_user_id,
            "converted_user_name": lead.converted_user.get_full_name() if lead.converted_user_id else "",
            "confirmed_at": lead.confirmed_at.isoformat() if lead.confirmed_at else "",
            "confirmed_at_label": timezone.localtime(lead.confirmed_at).strftime("%d.%m.%Y %H:%M") if lead.confirmed_at else "",
            "confirmed_by_name": lead.confirmed_by.get_full_name() if lead.confirmed_by_id else "",
            "lead_group_object": serialize_lead_group_option(lead.lead_group) if lead.lead_group_id else None,
        }
    )
    return payload


def serialize_lead_status_choices(center) -> list[dict]:
    return [serialize_lead_status(item) for item in build_dynamic_lead_status_choices(center)]


def serialize_lead_group(lead_group: LeadGroup) -> dict:
    ann_lead = getattr(lead_group, "ann_lead_count", None)
    if ann_lead is not None:
        lead_count = ann_lead
        confirmed_count = getattr(lead_group, "ann_confirmed_count", 0)
    else:
        member_qs = lead_group.leads.filter(is_archived=False)
        lead_count = member_qs.count()
        confirmed_count = member_qs.filter(is_confirmed=True).count()
    created_at = timezone.localtime(lead_group.created_at) if lead_group.created_at else None
    archived_at = timezone.localtime(lead_group.archived_at) if lead_group.archived_at else None
    return {
        "id": lead_group.id,
        "name": lead_group.name,
        "subject_id": lead_group.subject_id,
        "subject_name": getattr(lead_group.subject, "nom", "") or "Fan belgilanmagan",
        "department_id": lead_group.department_id,
        "department_name": getattr(lead_group.department, "name", "") or "Bo‘lim belgilanmagan",
        "lead_count": lead_count,
        "lead_count_label": f"{lead_count} ta",
        "confirmed_count": confirmed_count,
        "min_students": int(lead_group.min_students or 0),
        "status": lead_group.status,
        "status_label": lead_group.get_status_display(),
        "note": lead_group.note or "",
        "created_by_name": lead_group.created_by.get_full_name() if lead_group.created_by_id else "",
        "created_at": created_at.isoformat() if created_at else "",
        "created_at_label": created_at.strftime("%d.%m.%Y") if created_at else "",
        "archived_at": archived_at.isoformat() if archived_at else "",
        "archived_at_label": archived_at.strftime("%d.%m.%Y %H:%M") if archived_at else "",
        "converted_group_id": lead_group.converted_group_id,
        "converted_group_name": getattr(lead_group.converted_group, "nom", "") or "",
        "is_archived": bool(lead_group.is_archived),
    }


def serialize_lead_group_member(lead: Lead) -> dict:
    payload = serialize_lead(lead)
    created_at = timezone.localtime(lead.qoshilgan_sana) if lead.qoshilgan_sana else None
    added_to_group_at = timezone.localtime(lead.added_to_group_at) if lead.added_to_group_at else None
    payload.update(
        {
            "subject": payload.get("subject") or "",
            "manager": payload.get("manager_name") or "Biriktirilmagan",
            "note": lead.note or "",
            "created_at": created_at.isoformat() if created_at else "",
            "created_at_label": created_at.strftime("%d.%m.%Y %H:%M") if created_at else "",
            "added_to_group_at": added_to_group_at.isoformat() if added_to_group_at else "",
            "added_to_group_at_label": added_to_group_at.strftime("%d.%m.%Y %H:%M") if added_to_group_at else "",
            "added_to_group_date_label": added_to_group_at.strftime("%d.%m.%Y") if added_to_group_at else "",
            "added_to_group_time_label": added_to_group_at.strftime("%H:%M") if added_to_group_at else "",
        }
    )
    return payload


def serialize_lead_group_detail(lead_group: LeadGroup, *, member_count: int) -> dict:
    payload = serialize_lead_group(lead_group)
    created_at = timezone.localtime(lead_group.created_at) if lead_group.created_at else None
    payload.update(
        {
            "member_count": int(member_count or 0),
            "member_count_label": f"{int(member_count or 0)} ta",
            "created_at_full_label": created_at.strftime("%d.%m.%Y %H:%M") if created_at else "",
        }
    )
    return payload


def serialize_pagination(page_obj) -> dict:
    return {
        "page": page_obj.number,
        "page_size": page_obj.paginator.per_page,
        "num_pages": page_obj.paginator.num_pages,
        "total": page_obj.paginator.count,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
        "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
        "previous_page": page_obj.previous_page_number() if page_obj.has_previous() else None,
    }
