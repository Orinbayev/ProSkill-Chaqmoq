from __future__ import annotations

import re
import secrets
import string
from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from accounts.duplicate_checks import StudentDuplicateKind, find_student_duplicates
from core.models import Notification
from .models import Lead, LeadActivity, LeadGroup, LeadStatus, Manba, Yonalish
from education.models import Student as EdStudent

User = get_user_model()


DEFAULT_SOURCES = [
    "Instagram",
    "Telegram",
    "Recommendation",
    "Banner",
    "Call",
    "Other",
]

DEFAULT_STATUS_CATALOG = [
    (LeadStatus.Code.NEW, "Yangi", 10),
    (LeadStatus.Code.CONTACTED, "Bog'lanildi", 20),
    (LeadStatus.Code.NO_ANSWER, "Javob bermadi", 30),
    (LeadStatus.Code.TRIAL_SCHEDULED, "Sinovga yozildi", 40),
    (LeadStatus.Code.TRIAL_ATTENDED, "Sinov darsda qatnashdi", 50),
    (LeadStatus.Code.REGISTERED, "Tasdiqlandi", 60),
    (LeadStatus.Code.LOST, "Bekor qilingan", 70),
]

DEFAULT_PIPELINE_STATUS_CHOICES = [
    (Lead.PipelineStatus.NEW, "Yangi", "blue"),
    (Lead.PipelineStatus.CONTACTED, "Bog‘lanildi", "amber"),
    (Lead.PipelineStatus.TRIAL, "Sinovga yozildi", "violet"),
    (Lead.PipelineStatus.CONFIRMED, "Tasdiqlandi", "green"),
    (Lead.PipelineStatus.CANCELED, "Bekor qilingan", "red"),
]

DEFAULT_SUBJECT_CATALOG = [
    (Lead.Subject.IELTS.label, "#3b82f6"),
    (Lead.Subject.GENERAL_ENGLISH.label, "#64748b"),
    (Lead.Subject.MATH.label, "#22c55e"),
    (Lead.Subject.RUSSIAN.label, "#f59e0b"),
    (Lead.Subject.OTHER.label, "#94a3b8"),
]

PIPELINE_STATUS_TO_LEAD_STATUS_CODE = {
    Lead.PipelineStatus.NEW: LeadStatus.Code.NEW,
    Lead.PipelineStatus.CONTACTED: LeadStatus.Code.CONTACTED,
    Lead.PipelineStatus.TRIAL: LeadStatus.Code.TRIAL_SCHEDULED,
    Lead.PipelineStatus.CONFIRMED: LeadStatus.Code.REGISTERED,
    Lead.PipelineStatus.CONVERTED: LeadStatus.Code.REGISTERED,
    Lead.PipelineStatus.CANCELED: LeadStatus.Code.LOST,
}

LEAD_STATUS_CODE_TO_PIPELINE = {
    LeadStatus.Code.NEW: Lead.PipelineStatus.NEW,
    LeadStatus.Code.CONTACTED: Lead.PipelineStatus.CONTACTED,
    LeadStatus.Code.NO_ANSWER: Lead.PipelineStatus.CONTACTED,
    LeadStatus.Code.TRIAL_SCHEDULED: Lead.PipelineStatus.TRIAL,
    LeadStatus.Code.TRIAL_ATTENDED: Lead.PipelineStatus.TRIAL,
    LeadStatus.Code.REGISTERED: Lead.PipelineStatus.CONFIRMED,
    LeadStatus.Code.LOST: Lead.PipelineStatus.CANCELED,
}

STATUS_NAME_FALLBACK_MAP = {
    "yangi": LeadStatus.Code.NEW,
    "new": LeadStatus.Code.NEW,
    "bog'lanildi": LeadStatus.Code.CONTACTED,
    "boglanildi": LeadStatus.Code.CONTACTED,
    "contacted": LeadStatus.Code.CONTACTED,
    "aloqa": LeadStatus.Code.CONTACTED,
    "javob bermadi": LeadStatus.Code.NO_ANSWER,
    "no answer": LeadStatus.Code.NO_ANSWER,
    "trial belgilandi": LeadStatus.Code.TRIAL_SCHEDULED,
    "trial scheduled": LeadStatus.Code.TRIAL_SCHEDULED,
    "trial qatnashdi": LeadStatus.Code.TRIAL_ATTENDED,
    "trial attended": LeadStatus.Code.TRIAL_ATTENDED,
    "tasdiqlandi": LeadStatus.Code.REGISTERED,
    "registered": LeadStatus.Code.REGISTERED,
    "bekor qilingan": LeadStatus.Code.LOST,
    "cancelled": LeadStatus.Code.LOST,
    "canceled": LeadStatus.Code.LOST,
    "rad etilgan": LeadStatus.Code.LOST,
    "yoqotildi": LeadStatus.Code.LOST,
    "lost": LeadStatus.Code.LOST,
}

CONVERTED_STATUS_PRESENTATION = {
    "value": Lead.PipelineStatus.CONVERTED,
    "label": "O‘quvchiga aylangan",
    "tone": "green",
}


def normalize_phone(phone: str) -> str:
    """Normalizes Uzbek phone numbers to +998XXXXXXXXX format when possible."""
    raw = (phone or "").strip()
    if not raw:
        return ""

    digits = re.sub(r"\D+", "", raw)
    if len(digits) == 9:
        return "+998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    if raw.startswith("+") and len(digits) >= 7:
        return raw
    return "+" + digits if len(digits) > 10 else raw


def infer_subject_from_text(value: str) -> str:
    normalized = re.sub(r"\s+", " ", (value or "").strip().lower())
    if not normalized:
        return Lead.Subject.OTHER
    if "ielts" in normalized:
        return Lead.Subject.IELTS
    if "matem" in normalized or "math" in normalized:
        return Lead.Subject.MATH
    if "rus" in normalized or "russian" in normalized:
        return Lead.Subject.RUSSIAN
    if "english" in normalized or "ingliz" in normalized:
        return Lead.Subject.GENERAL_ENGLISH
    return Lead.Subject.OTHER


def infer_subject_label_from_text(value: str) -> str:
    inferred = infer_subject_from_text(value)
    labels = {
        Lead.Subject.IELTS: Lead.Subject.IELTS.label,
        Lead.Subject.GENERAL_ENGLISH: Lead.Subject.GENERAL_ENGLISH.label,
        Lead.Subject.MATH: Lead.Subject.MATH.label,
        Lead.Subject.RUSSIAN: Lead.Subject.RUSSIAN.label,
        Lead.Subject.OTHER: Lead.Subject.OTHER.label,
    }
    return labels.get(inferred, (value or "").strip() or Lead.Subject.OTHER.label)


def default_subject_color(name: str) -> str:
    normalized = re.sub(r"\s+", " ", (name or "").strip().lower())
    for subject_name, color in DEFAULT_SUBJECT_CATALOG:
        if normalized == subject_name.lower():
            return color
    if "ielts" in normalized:
        return "#3b82f6"
    if "matem" in normalized or "math" in normalized:
        return "#22c55e"
    if "rus" in normalized or "russian" in normalized:
        return "#f59e0b"
    if "english" in normalized or "ingliz" in normalized:
        return "#64748b"
    return "#94a3b8"


def ensure_default_lead_subjects(center):
    if not center:
        return []

    names = [name for name, _ in DEFAULT_SUBJECT_CATALOG]
    existing = {
        s.nom: s for s in Yonalish.objects.filter(center=center, nom__in=names)
    }
    subjects = []
    for name, color in DEFAULT_SUBJECT_CATALOG:
        subject = existing.get(name)
        if subject:
            if not subject.color:
                subject.color = color
                subject.save(update_fields=["color"])
        else:
            subject, _ = Yonalish.objects.get_or_create(
                center=center,
                nom=name,
                defaults={"color": color, "is_active": True},
            )
        subjects.append(subject)
    return subjects


def get_or_create_lead_subject(*, center, name: str, color: str = ""):
    cleaned_name = re.sub(r"\s+", " ", (name or "").strip())
    if not center or not cleaned_name:
        return None

    subject = Yonalish.objects.filter(center=center, nom__iexact=cleaned_name).order_by("id").first()
    resolved_color = (color or "").strip() or default_subject_color(cleaned_name)
    if subject:
        changed = False
        if resolved_color and subject.color != resolved_color:
            subject.color = resolved_color
            changed = True
        if not subject.is_active:
            subject.is_active = True
            changed = True
        if changed:
            subject.save(update_fields=["color", "is_active"])
        return subject

    return Yonalish.objects.create(
        center=center,
        nom=cleaned_name,
        color=resolved_color,
        is_active=True,
    )


def build_dynamic_lead_status_choices(center):
    ensure_default_lead_catalog(center)
    if not center:
        return [
            {"value": value, "label": label, "tone": tone, "kind": "default"}
            for value, label, tone in DEFAULT_PIPELINE_STATUS_CHOICES
        ]

    active_statuses = {
        status.code: status
        for status in LeadStatus.objects.filter(center=center, is_active=True).order_by("order", "id")
    }
    default_choices = []
    for value, fallback_label, tone in DEFAULT_PIPELINE_STATUS_CHOICES:
        target_code = PIPELINE_STATUS_TO_LEAD_STATUS_CODE.get(value)
        status = active_statuses.get(target_code)
        if not status:
            continue
        default_choices.append(
            {
                "id": status.id,
                "value": value,
                "label": status.nom or fallback_label,
                "tone": tone,
                "kind": "default",
                "code": status.code,
                "is_active": bool(status.is_active),
            }
        )

    standard_codes = set(LEAD_STATUS_CODE_TO_PIPELINE.keys())
    custom_statuses = []
    for status in LeadStatus.objects.filter(center=center, is_active=True).order_by("order", "id"):
        resolved_code = resolve_status_code(status)
        if resolved_code in standard_codes:
            continue
        custom_statuses.append(
            {
                "value": f"custom:{status.id}",
                "label": status.nom,
                "tone": "gray",
                "kind": "custom",
                "id": status.id,
                "code": status.code,
                "is_active": bool(status.is_active),
            }
        )

    return default_choices + custom_statuses


def is_lead_confirmed(lead: Lead | None) -> bool:
    if not lead:
        return False
    if getattr(lead, "converted_to_student", False):
        return True
    if getattr(lead, "is_confirmed", False):
        return True
    return resolve_status_code(getattr(lead, "status", None)) == LeadStatus.Code.REGISTERED


def sync_lead_confirmation_state(*, lead: Lead, actor=None, save: bool = True) -> Lead:
    should_be_confirmed = bool(lead.converted_to_student) or resolve_status_code(lead.status) == LeadStatus.Code.REGISTERED
    update_fields: list[str] = []

    if should_be_confirmed:
        if not lead.is_confirmed:
            lead.is_confirmed = True
            update_fields.append("is_confirmed")
        if not lead.confirmed_at:
            lead.confirmed_at = timezone.now()
            update_fields.append("confirmed_at")
        if actor and lead.confirmed_by_id != getattr(actor, "id", None):
            lead.confirmed_by = actor
            update_fields.append("confirmed_by")
    elif not lead.converted_to_student:
        if lead.is_confirmed:
            lead.is_confirmed = False
            update_fields.append("is_confirmed")
        if lead.confirmed_at is not None:
            lead.confirmed_at = None
            update_fields.append("confirmed_at")
        if lead.confirmed_by_id is not None:
            lead.confirmed_by = None
            update_fields.append("confirmed_by")

    if save and update_fields:
        lead.save(update_fields=[*update_fields, "updated_at"])
    return lead


@transaction.atomic
def confirm_lead(*, lead: Lead, actor=None) -> Lead:
    previous_status_name = lead.status.nom if lead.status else ""
    target_status = get_or_create_pipeline_status(center=lead.center, pipeline_status=Lead.PipelineStatus.CONFIRMED)
    update_fields = []
    if target_status and lead.status_id != target_status.id:
        lead.status = target_status
        update_fields.append("status")
    if not lead.is_confirmed:
        lead.is_confirmed = True
        update_fields.append("is_confirmed")
    if not lead.confirmed_at:
        lead.confirmed_at = timezone.now()
        update_fields.append("confirmed_at")
    if actor and lead.confirmed_by_id != getattr(actor, "id", None):
        lead.confirmed_by = actor
        update_fields.append("confirmed_by")
    if update_fields:
        lead.save(update_fields=[*update_fields, "updated_at"])
    if target_status and previous_status_name != target_status.nom:
        log_lead_activity(
            lead=lead,
            action=LeadActivity.Action.STATUS_CHANGED,
            actor=actor,
            from_value=previous_status_name,
            to_value=target_status.nom,
            note="Lead tezkor tasdiqlandi.",
        )
    sync_lead_group_status(lead.lead_group)
    return lead


def sync_lead_group_status(lead_group: LeadGroup | None):
    if not lead_group or lead_group.is_archived:
        return lead_group

    if lead_group.converted_group_id:
        desired_status = LeadGroup.Status.CONVERTED
    else:
        active_count = Lead.objects.filter(lead_group=lead_group, is_archived=False).count()
        minimum = max(int(lead_group.min_students or 0), 1)
        desired_status = LeadGroup.Status.READY if active_count >= minimum else LeadGroup.Status.COLLECTING

    if lead_group.status != desired_status:
        lead_group.status = desired_status
        lead_group.save(update_fields=["status", "updated_at"])
    return lead_group


def sync_lead_group_statuses(*lead_groups):
    seen_ids = set()
    for lead_group in lead_groups:
        if not lead_group or getattr(lead_group, "id", None) in seen_ids:
            continue
        seen_ids.add(lead_group.id)
        sync_lead_group_status(lead_group)


def get_or_create_custom_lead_status(*, center, name: str):
    cleaned_name = re.sub(r"\s+", " ", (name or "").strip())
    if not center or not cleaned_name:
        return None

    existing = LeadStatus.objects.filter(center=center, nom__iexact=cleaned_name).order_by("id").first()
    if existing:
        changed = False
        if not existing.is_active:
            existing.is_active = True
            changed = True
        if changed:
            existing.save(update_fields=["is_active"])
        return existing

    base_slug = slugify(cleaned_name).replace("-", "_") or "status"
    code = f"custom_{base_slug[:20]}"
    suffix = 1
    while LeadStatus.objects.filter(center=center, code=code).exists():
        suffix += 1
        code = f"custom_{base_slug[:16]}_{suffix}"

    last_order = (
        LeadStatus.objects.filter(center=center).order_by("-order").values_list("order", flat=True).first() or 100
    )
    return LeadStatus.objects.create(
        center=center,
        nom=cleaned_name,
        code=code,
        order=last_order + 10,
        is_active=True,
    )


def resolve_dynamic_status_value(lead: Lead) -> str:
    if lead.converted_to_student:
        return Lead.PipelineStatus.CONVERTED
    if lead.is_confirmed:
        return Lead.PipelineStatus.CONFIRMED
    if not lead.status_id:
        return Lead.PipelineStatus.NEW

    resolved_code = resolve_status_code(lead.status)
    pipeline = LEAD_STATUS_CODE_TO_PIPELINE.get(resolved_code)
    if pipeline:
        return pipeline
    return f"custom:{lead.status_id}"


def resolve_dynamic_status_label(lead: Lead) -> str:
    if lead.converted_to_student:
        return CONVERTED_STATUS_PRESENTATION["label"]
    if getattr(lead, "status_id", None) and getattr(lead.status, "nom", ""):
        return lead.status.nom
    value = resolve_dynamic_status_value(lead)
    default_map = {item[0]: item[1] for item in DEFAULT_PIPELINE_STATUS_CHOICES}
    return default_map.get(value, "Holat belgilanmagan")


def resolve_dynamic_status_tone(lead: Lead) -> str:
    if lead.converted_to_student:
        return CONVERTED_STATUS_PRESENTATION["tone"]
    value = resolve_dynamic_status_value(lead)
    tone_map = {item[0]: item[2] for item in DEFAULT_PIPELINE_STATUS_CHOICES}
    return tone_map.get(value, "gray")


def resolve_pipeline_status(lead: Lead) -> str:
    return lead.pipeline_status


def resolve_status_code(status: LeadStatus | None) -> str:
    if not status:
        return ""
    if status.code:
        return status.code

    normalized_name = re.sub(r"\s+", " ", (status.nom or "").strip().lower())
    if normalized_name in STATUS_NAME_FALLBACK_MAP:
        return STATUS_NAME_FALLBACK_MAP[normalized_name]

    for key, value in STATUS_NAME_FALLBACK_MAP.items():
        if key in normalized_name:
            return value

    return ""


def ensure_default_lead_catalog(center) -> None:
    """Creates default source/status rows if center has an empty lead catalog."""
    if not center:
        return

    # Batch: check all sources in one query, only create missing ones
    existing_sources = set(
        Manba.objects.filter(center=center, nom__in=DEFAULT_SOURCES).values_list("nom", flat=True)
    )
    for source_name in DEFAULT_SOURCES:
        if source_name not in existing_sources:
            Manba.objects.get_or_create(center=center, nom=source_name)

    # Backfill code for legacy statuses first.
    for item in LeadStatus.objects.filter(center=center, code=""):
        resolved = resolve_status_code(item)
        if resolved:
            item.code = resolved
            item.save(update_fields=["code"])

    # Batch: fetch all default statuses in one query
    default_codes = [code for code, _, _ in DEFAULT_STATUS_CATALOG]
    existing_statuses = {
        s.code: s
        for s in LeadStatus.objects.filter(center=center, code__in=default_codes)
    }

    for code, name, order in DEFAULT_STATUS_CATALOG:
        status = existing_statuses.get(code)
        if status:
            if status.order != order:
                status.order = order
                status.save(update_fields=["order"])
            continue

        status, _ = LeadStatus.objects.get_or_create(
            center=center,
            nom=name,
            defaults={"code": code, "order": order, "is_active": True},
        )
        changed = False
        update_fields = []
        if not status.code:
            status.code = code
            update_fields.append("code")
            changed = True
        if status.order != order:
            status.order = order
            update_fields.append("order")
            changed = True
        if changed:
            status.save(update_fields=update_fields)


def log_lead_activity(
    *,
    lead: Lead,
    action: str,
    actor=None,
    from_value: str = "",
    to_value: str = "",
    note: str = "",
) -> LeadActivity:
    return LeadActivity.objects.create(
        center=lead.center,
        lead=lead,
        action=action,
        actor=actor,
        from_value=(from_value or "")[:255],
        to_value=(to_value or "")[:255],
        note=note or "",
    )


def _notify_user(*, recipient, title: str, message: str) -> None:
    if not recipient:
        return
    Notification.objects.create(
        center=getattr(recipient, "center", None),
        recipient=recipient,
        sender=None,
        title=title,
        message=message,
        type="system",
    )


def send_follow_up_notification_if_due(lead: Lead) -> None:
    if not lead.next_follow_up_date or not lead.assigned_manager_id:
        return
    if lead.next_follow_up_date != timezone.localdate():
        return

    dedupe_qs = Notification.objects.filter(
        recipient=lead.assigned_manager,
        type="system",
        title="Lead follow-up",
        created_at__date=timezone.localdate(),
        message__icontains=f"Lead #{lead.id}",
    )
    if dedupe_qs.exists():
        return

    _notify_user(
        recipient=lead.assigned_manager,
        title="Lead follow-up",
        message=f"Lead #{lead.id} ({lead.full_name}) uchun follow-up bugun belgilangan.",
    )


def _clean_for_login(text: str) -> str:
    s = (text or "").strip().lower()
    s = s.replace("o‘", "o").replace("o'", "o")
    s = s.replace("g‘", "g").replace("g'", "g")
    s = s.replace("’", "").replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _gen_default_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))


def _gen_unique_email_for_student(ism: str, familya: str) -> str:
    first_char = _clean_for_login(ism)[:1] or "s"
    last_part = _clean_for_login(familya)[:8]
    base = f"{first_char}.{last_part}" if last_part else first_char

    email = f"{base}@gmail.com"
    if not User.all_objects.filter(email=email).exists():
        return email

    for i in range(1, 1000):
        candidate = f"{base}{i}@gmail.com"
        if not User.all_objects.filter(email=candidate).exists():
            return candidate

    return f"{base}{secrets.token_hex(3)}@gmail.com"


def find_existing_student_for_lead(*, lead: Lead, target_center=None):
    """Returns an existing student that most likely matches lead identity."""
    target_center = target_center or lead.center
    best_match = None
    best_rank = -1
    seen_phones = set()
    phone_candidates = [
        normalize_phone(lead.telefon1),
        normalize_phone(lead.telefon2),
        normalize_phone(lead.parent_phone),
    ]
    rank_map = {
        StudentDuplicateKind.IDENTITY_MATCH: 1,
        StudentDuplicateKind.STRONG_IDENTITY_MATCH: 2,
    }

    for phone in phone_candidates:
        if not phone or phone in seen_phones:
            continue
        seen_phones.add(phone)

        duplicate_check = find_student_duplicates(
            center=target_center,
            ism=lead.ism,
            familya=lead.familya,
            telefon=phone,
            birth_date=lead.birth_date,
        )
        if not duplicate_check.can_link_existing_student or not duplicate_check.matches:
            continue

        current_rank = rank_map.get(duplicate_check.kind, 0)
        if current_rank > best_rank:
            best_rank = current_rank
            best_match = duplicate_check.matches[0]
        if current_rank == rank_map[StudentDuplicateKind.STRONG_IDENTITY_MATCH]:
            break

    if best_match:
        return best_match
    return None


def get_status_by_code(*, center, code: str) -> LeadStatus | None:
    if not center or not code:
        return None
    return LeadStatus.objects.filter(center=center, code=code, is_active=True).order_by("order", "id").first()


def get_or_create_pipeline_status(*, center, pipeline_status: str) -> LeadStatus | None:
    if not center or not pipeline_status:
        return None

    target_code = PIPELINE_STATUS_TO_LEAD_STATUS_CODE.get(pipeline_status, LeadStatus.Code.NEW)
    status = LeadStatus.objects.filter(center=center, code=target_code).order_by("order", "id").first()
    if status:
        changed = False
        if not status.is_active:
            status.is_active = True
            changed = True
        if changed:
            status.save(update_fields=["is_active"])
        return status

    ensure_default_lead_catalog(center)
    status = LeadStatus.objects.filter(center=center, code=target_code).order_by("order", "id").first()
    if status:
        if not status.is_active:
            status.is_active = True
            status.save(update_fields=["is_active"])
        return status

    for code, name, order in DEFAULT_STATUS_CATALOG:
        if code == target_code:
            status, _ = LeadStatus.objects.get_or_create(
                center=center,
                code=code,
                defaults={"nom": name, "order": order, "is_active": True},
            )
            return status
    return None


@transaction.atomic
def convert_lead_to_student_safe(lead: Lead, converted_by=None, target_center=None):
    """
    Converts a lead into student without creating duplicates.

    Return tuple: (user, password, created)
    """
    if not is_lead_confirmed(lead):
        raise ValueError("Faqat tasdiqlangan leadlar o‘quvchiga aylantiriladi")

    if lead.converted_user_id:
        if not lead.converted_to_student:
            lead.mark_converted(converted_user=lead.converted_user, converted_by=converted_by)
        return lead.converted_user, None, False

    target_center = target_center or lead.center

    existing_student = find_existing_student_for_lead(lead=lead, target_center=target_center)
    if existing_student:
        lead.converted_user = existing_student
        lead.converted_by = converted_by
        lead.converted_at = lead.converted_at or timezone.now()
        lead.converted_to_student = True
        lead.is_confirmed = True
        lead.confirmed_at = lead.confirmed_at or lead.converted_at
        if converted_by and not lead.confirmed_by_id:
            lead.confirmed_by = converted_by

        registered_status = get_status_by_code(center=target_center, code=LeadStatus.Code.REGISTERED)
        if registered_status and lead.status_id != registered_status.id:
            prev_status = lead.status.nom if lead.status else ""
            lead.status = registered_status
            log_lead_activity(
                lead=lead,
                action=LeadActivity.Action.STATUS_CHANGED,
                actor=converted_by,
                from_value=prev_status,
                to_value=registered_status.nom,
                note="Lead status avtomatik 'registered' qilindi (existing student match).",
            )

        if existing_student.is_archived:
            existing_student.is_archived = False
            existing_student.save(update_fields=["is_archived"])

        # ✅ Ensure education Student profile exists
        EdStudent.objects.get_or_create(user=existing_student, defaults={"center": target_center})
        lead.mark_converted(converted_user=existing_student, converted_by=converted_by)
        if registered_status:
            lead.status = registered_status
            lead.save(update_fields=["status", "updated_at"])
        sync_lead_group_status(lead.lead_group)
        log_lead_activity(
            lead=lead,
            action=LeadActivity.Action.CONVERTED,
            actor=converted_by,
            to_value=f"student#{existing_student.id}",
            note="Mavjud studentga bog'landi (duplicate oldi olindi).",
        )
        return existing_student, None, False

    password = _gen_default_password()
    student = User(
        role="student",
        center=target_center,
        email=_gen_unique_email_for_student(lead.ism, lead.familya),
        ism=lead.ism,
        familya=lead.familya,
        otchestvo=lead.otchestvo,
        birth_date=lead.birth_date,
        gender=lead.gender,
        passport_id=lead.passport_id,
        jshr=lead.jshr,
        address=lead.address,
    )

    tel1 = normalize_phone(lead.telefon1)
    tel2 = normalize_phone(lead.telefon2)
    if tel1:
        student.telefon1 = tel1
    if tel2:
        student.telefon2 = tel2

    student.set_password(password)
    student.save()

    # ✅ Create education Student profile
    EdStudent.objects.create(user=student, center=target_center)

    lead.converted_user = student
    lead.converted_by = converted_by
    lead.converted_at = timezone.now()
    lead.converted_to_student = True

    registered_status = get_status_by_code(center=target_center, code=LeadStatus.Code.REGISTERED)
    if registered_status:
        prev_status = lead.status.nom if lead.status else ""
        lead.status = registered_status
        log_lead_activity(
            lead=lead,
            action=LeadActivity.Action.STATUS_CHANGED,
            actor=converted_by,
            from_value=prev_status,
            to_value=registered_status.nom,
            note="Lead status avtomatik 'registered' qilindi (new student).",
        )

    lead.mark_converted(converted_user=student, converted_by=converted_by)
    if registered_status:
        lead.status = registered_status
        lead.save(update_fields=["status", "updated_at"])
    sync_lead_group_status(lead.lead_group)

    log_lead_activity(
        lead=lead,
        action=LeadActivity.Action.CONVERTED,
        actor=converted_by,
        to_value=f"student#{student.id}",
        note="Yangi student yaratilib bog'landi.",
    )

    _notify_user(
        recipient=converted_by,
        title="Lead konvertatsiya qilindi",
        message=f"Lead #{lead.id} muvaffaqiyatli studentga o'tkazildi.",
    )

    return student, password, True


def handle_lead_save_audit(
    *,
    lead: Lead,
    actor=None,
    is_create: bool = False,
    previous_status=None,
    previous_follow_up_date: date | None = None,
) -> None:
    if is_create:
        log_lead_activity(
            lead=lead,
            action=LeadActivity.Action.CREATED,
            actor=actor,
            note="Lead yaratildi.",
        )
    else:
        log_lead_activity(
            lead=lead,
            action=LeadActivity.Action.UPDATED,
            actor=actor,
            note="Lead ma'lumotlari yangilandi.",
        )

    if previous_status != lead.status_id:
        prev_name = ""
        if previous_status:
            prev = LeadStatus.objects.filter(pk=previous_status).first()
            prev_name = prev.nom if prev else ""
        cur_name = lead.status.nom if lead.status else ""
        log_lead_activity(
            lead=lead,
            action=LeadActivity.Action.STATUS_CHANGED,
            actor=actor,
            from_value=prev_name,
            to_value=cur_name,
        )

    if previous_follow_up_date != lead.next_follow_up_date:
        log_lead_activity(
            lead=lead,
            action=LeadActivity.Action.FOLLOW_UP_SET,
            actor=actor,
            from_value=str(previous_follow_up_date or ""),
            to_value=str(lead.next_follow_up_date or ""),
        )

    send_follow_up_notification_if_due(lead)


def follow_up_queryset(*, center, for_date: date | None = None):
    if not center:
        return Lead.objects.none()
    target_date = for_date or timezone.localdate()
    return (
        Lead.objects.filter(center=center, is_archived=False, next_follow_up_date=target_date)
        .select_related("assigned_manager", "status", "manba", "yonalish")
        .order_by("qoshilgan_sana")
    )
