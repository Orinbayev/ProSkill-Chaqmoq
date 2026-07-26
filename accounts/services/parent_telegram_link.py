from __future__ import annotations

import secrets
from dataclasses import dataclass
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import ParentTelegramLinkToken, User, UserActivity


TOKEN_TTL_HOURS = 24


class ParentLinkError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ParentLinkInvite:
    token: str
    link: str
    telegram_share_url: str
    expires_at: object


def _bot_username() -> str:
    """Ota-ona ulanish linki uchun bot username.

    Ota-ona paneli (farzand ma'lumotlari + sayt login/parol) Family botда, shuning
    uchun link AYNAN Family botga yo'naltiriladi. Avval TELEGRAM_BOT_USERNAME_FAMILY,
    keyin oddiy TELEGRAM_BOT_USERNAME, oxirida esa xavfsiz default ishlatiladi —
    hech qachon "YOUR_BOT" (yaroqsiz link) qaytmaydi.
    """
    for attr in ("TELEGRAM_BOT_USERNAME_FAMILY", "TELEGRAM_BOT_USERNAME"):
        username = str(getattr(settings, attr, "") or "").strip().lstrip("@")
        if username and username.upper() != "YOUR_BOT":
            return username
    return "ChaqmoqApp_Student_Bot"


def _build_parent_link(token: str) -> str:
    return f"https://t.me/{_bot_username()}?start=parent_{token}"


def _build_share_url(link: str, student: User | None = None) -> str:
    label = student.get_full_name() if student else ""
    text = "Ota-ona botga ulanish havolasi"
    if label:
        text = f"{label} uchun ota-ona botga ulanish havolasi"
    return f"https://t.me/share/url?url={quote(link)}&text={quote(text)}"


def parent_link_status(student: User) -> dict:
    parent = None
    if student.parent_telegram_id:
        parent = (
            student.parents.filter(
                telegram_id=student.parent_telegram_id,
                is_telegram_linked=True,
            )
            .order_by("-id")
            .first()
        )
    if parent is None:
        parent = (
            student.parents.filter(is_telegram_linked=True)
            .exclude(telegram_id__isnull=True)
            .exclude(telegram_id="")
            .order_by("-id")
            .first()
        )

    telegram_id = student.parent_telegram_id or getattr(parent, "telegram_id", "") or ""
    username = student.parent_telegram_username or getattr(parent, "telegram_username", "") or ""
    linked_at = student.parent_telegram_linked_at

    if parent and telegram_id and not student.parent_telegram_id:
        student.parent_telegram_id = telegram_id
        student.parent_telegram_username = username
        if not linked_at:
            student.parent_telegram_linked_at = timezone.now()
            linked_at = student.parent_telegram_linked_at
        student.save(
            update_fields=[
                "parent_telegram_id",
                "parent_telegram_username",
                "parent_telegram_linked_at",
            ]
        )

    return {
        "is_linked": bool(telegram_id),
        "telegram_id": telegram_id,
        "telegram_username": username,
        "linked_at": linked_at,
        "parent_id": getattr(parent, "id", None),
        "parent_name": parent.get_full_name() if parent else "",
    }


def create_parent_telegram_invite(*, student: User, created_by: User | None = None) -> ParentLinkInvite:
    if student.role != "student":
        raise ParentLinkError("Faqat o'quvchi uchun ota-ona linki yaratiladi", status_code=400)

    now = timezone.now()
    with transaction.atomic():
        ParentTelegramLinkToken.objects.select_for_update().filter(
            student=student,
            used_at__isnull=True,
            expires_at__gt=now,
        ).update(expires_at=now)

        token = ParentTelegramLinkToken.objects.create(
            student=student,
            created_by=created_by if getattr(created_by, "is_authenticated", False) else None,
            token=_generate_unique_token(),
            expires_at=now + timezone.timedelta(hours=TOKEN_TTL_HOURS),
        )

    link = _build_parent_link(token.token)
    return ParentLinkInvite(
        token=token.token,
        link=link,
        telegram_share_url=_build_share_url(link, student),
        expires_at=token.expires_at,
    )


def _generate_unique_token() -> str:
    while True:
        token = secrets.token_urlsafe(32)
        if not ParentTelegramLinkToken.objects.filter(token=token).exists():
            return token


def _parent_email_for_telegram(*, telegram_id: str, center_id: int | None) -> str:
    base = f"parent-{telegram_id}"
    if center_id:
        base = f"{base}-{center_id}"
    email = f"{base}@telegram.chaqmoq.local"
    if not User.all_objects.filter(email=email).exists():
        return email

    while True:
        candidate = f"{base}-{secrets.token_hex(3)}@telegram.chaqmoq.local"
        if not User.all_objects.filter(email=candidate).exists():
            return candidate


def _get_or_create_parent_user(
    *,
    student: User,
    telegram_id: str,
    telegram_username: str = "",
    first_name: str = "",
    last_name: str = "",
) -> User:
    parent = (
        User.objects.select_for_update()
        .filter(
            role="parent",
            telegram_id=telegram_id,
            center=student.center,
        )
        .order_by("-is_telegram_linked", "-id")
        .first()
    )
    if parent is None:
        parent = User.objects.create_user(
            email=_parent_email_for_telegram(telegram_id=telegram_id, center_id=student.center_id),
            password=secrets.token_urlsafe(16),
            role="parent",
            center=student.center,
            ism=(first_name or "Ota-ona").strip(),
            familya=(last_name or student.familya or "").strip(),
            telegram_id=telegram_id,
            telegram_username=telegram_username or None,
            is_telegram_linked=True,
        )
    else:
        changed_fields = []
        if not parent.is_telegram_linked:
            parent.is_telegram_linked = True
            changed_fields.append("is_telegram_linked")
        if parent.telegram_username != (telegram_username or None):
            parent.telegram_username = telegram_username or None
            changed_fields.append("telegram_username")
        if changed_fields:
            parent.save(update_fields=changed_fields)
    return parent


def consume_parent_telegram_invite(
    *,
    raw_token: str,
    telegram_id: str,
    telegram_username: str = "",
    first_name: str = "",
    last_name: str = "",
) -> dict:
    token_value = (raw_token or "").strip()
    tg_id = str(telegram_id or "").strip()
    if not token_value or not tg_id:
        raise ParentLinkError("Token va Telegram ID majburiy", status_code=400)

    now = timezone.now()
    with transaction.atomic():
        # DIQQAT: bu yerda select_related("student__center") ISHLATMAYMIZ.
        # center (null=True) LEFT OUTER JOIN yaratadi va PostgreSQL
        # "FOR UPDATE cannot be applied to the nullable side of an outer join"
        # xatosini beradi. student baribir pastda alohida qayta olinadi.
        link_token = (
            ParentTelegramLinkToken.objects.select_for_update()
            .filter(token=token_value)
            .first()
        )
        if not link_token:
            raise ParentLinkError("Link topilmadi", status_code=404)
        if link_token.used_at:
            raise ParentLinkError("Bu link allaqachon ishlatilgan", status_code=409)
        if link_token.expires_at <= now:
            raise ParentLinkError("Link muddati tugagan", status_code=410)

        student = User.objects.select_for_update().get(pk=link_token.student_id)
        if student.role != "student":
            raise ParentLinkError("Token o'quvchiga tegishli emas", status_code=400)
        if student.parent_telegram_id and student.parent_telegram_id != tg_id:
            raise ParentLinkError("O'quvchiga ota-ona allaqachon ulangan", status_code=409)

        parent = _get_or_create_parent_user(
            student=student,
            telegram_id=tg_id,
            telegram_username=(telegram_username or "").strip(),
            first_name=(first_name or "").strip(),
            last_name=(last_name or "").strip(),
        )
        parent.children.add(student)

        student.parent_telegram_id = tg_id
        student.parent_telegram_username = (telegram_username or "").strip() or None
        student.parent_telegram_linked_at = now
        student.save(
            update_fields=[
                "parent_telegram_id",
                "parent_telegram_username",
                "parent_telegram_linked_at",
            ]
        )

        link_token.used_at = now
        link_token.used_by = parent
        link_token.used_by_telegram_id = tg_id
        link_token.save(update_fields=["used_at", "used_by", "used_by_telegram_id"])

        UserActivity.objects.create(
            user=student,
            action="Parent Telegram linked",
            device_info=f"TG ID: {tg_id}",
            created_at=now,
        )
        UserActivity.objects.create(
            user=parent,
            action="Telegram account linked via parent invite",
            device_info=f"Student ID: {student.id}",
            created_at=now,
        )

    return {
        "student": {
            "id": student.id,
            "full_name": student.get_full_name(),
            "center": student.center.name if student.center else "",
        },
        "parent": {
            "id": parent.id,
            "email": parent.email,
            "full_name": parent.get_full_name(),
            "telegram_id": parent.telegram_id,
            "telegram_username": parent.telegram_username or "",
        },
        "linked_at": now,
    }
