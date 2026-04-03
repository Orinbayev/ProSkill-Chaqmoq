from __future__ import annotations

import re
import secrets
import string
from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import Notification
from .models import Lead, LeadActivity, LeadStatus, Manba
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
    (LeadStatus.Code.TRIAL_SCHEDULED, "Trial belgilandi", 40),
    (LeadStatus.Code.TRIAL_ATTENDED, "Trial qatnashdi", 50),
    (LeadStatus.Code.REGISTERED, "Tasdiqlandi", 60),
    (LeadStatus.Code.LOST, "Yoqotildi", 70),
]

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
    "rad etilgan": LeadStatus.Code.LOST,
    "yoqotildi": LeadStatus.Code.LOST,
    "lost": LeadStatus.Code.LOST,
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

    for source_name in DEFAULT_SOURCES:
        Manba.objects.get_or_create(center=center, nom=source_name)

    # Backfill code for legacy statuses first.
    for item in LeadStatus.objects.filter(center=center, code=""):
        resolved = resolve_status_code(item)
        if resolved:
            item.code = resolved
            item.save(update_fields=["code"])

    for code, name, order in DEFAULT_STATUS_CATALOG:
        status = LeadStatus.objects.filter(center=center, code=code).first()
        if status:
            changed = False
            if status.order != order:
                status.order = order
                changed = True
            if not status.is_active:
                status.is_active = True
                changed = True
            if changed:
                status.save(update_fields=["order", "is_active"])
            continue

        status, _ = LeadStatus.objects.get_or_create(
            center=center,
            nom=name,
            defaults={"code": code, "order": order, "is_active": True},
        )
        if not status.code:
            status.code = code
            status.order = order
            status.is_active = True
            status.save(update_fields=["code", "order", "is_active"])


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
    if not User.objects.filter(email=email).exists():
        return email

    for i in range(1, 1000):
        candidate = f"{base}{i}@gmail.com"
        if not User.objects.filter(email=candidate).exists():
            return candidate

    return f"{base}{secrets.token_hex(3)}@gmail.com"


def find_existing_student_for_lead(*, lead: Lead, target_center=None):
    """Returns an existing student that most likely matches lead identity."""
    qs = User.objects.filter(role="student")
    if target_center:
        qs = qs.filter(center=target_center)

    phones = {
        normalize_phone(lead.telefon1),
        normalize_phone(lead.telefon2),
        normalize_phone(lead.parent_phone),
    }
    phones = {p for p in phones if p}
    if phones:
        phone_q = Q()
        for phone in phones:
            phone_q |= Q(telefon1=phone) | Q(telefon2=phone) | Q(phone_number=phone)
        existing = qs.filter(phone_q).order_by("-id").first()
        if existing:
            return existing

    if lead.birth_date and lead.ism and lead.familya:
        existing = qs.filter(
            ism__iexact=(lead.ism or "").strip(),
            familya__iexact=(lead.familya or "").strip(),
            birth_date=lead.birth_date,
        ).order_by("-id").first()
        if existing:
            return existing

    return None


def get_status_by_code(*, center, code: str) -> LeadStatus | None:
    if not center or not code:
        return None
    return LeadStatus.objects.filter(center=center, code=code, is_active=True).order_by("order", "id").first()


@transaction.atomic
def convert_lead_to_student_safe(lead: Lead, converted_by=None, target_center=None):
    """
    Converts a lead into student without creating duplicates.

    Return tuple: (user, password, created)
    """
    if lead.converted_user_id:
        if not lead.converted_to_student:
            lead.converted_to_student = True
            lead.save(update_fields=["converted_to_student", "updated_at"])
        return lead.converted_user, None, False

    target_center = target_center or lead.center

    existing_student = find_existing_student_for_lead(lead=lead, target_center=target_center)
    if existing_student:
        lead.converted_user = existing_student
        lead.converted_by = converted_by
        lead.converted_at = lead.converted_at or timezone.now()
        lead.converted_to_student = True

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

        lead.save(
            update_fields=[
                "converted_user",
                "converted_by",
                "converted_at",
                "converted_to_student",
                "status",
                "updated_at",
            ]
        )
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
        student.phone_number = tel1
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

    lead.save(
        update_fields=[
            "converted_user",
            "converted_by",
            "converted_at",
            "converted_to_student",
            "status",
            "updated_at",
        ]
    )

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
