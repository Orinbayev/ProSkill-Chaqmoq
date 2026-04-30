from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db.models import Q

from accounts.utils import normalize_phone

User = get_user_model()


class StudentDuplicateKind:
    NONE = "none"
    PHONE_ONLY = "phone_only"
    IDENTITY_MATCH = "identity_match"
    STRONG_IDENTITY_MATCH = "strong_identity_match"


@dataclass(frozen=True)
class StudentDuplicateCheck:
    kind: str = StudentDuplicateKind.NONE
    title: str = ""
    message: str = ""
    matches: tuple = ()
    match_count: int = 0

    @property
    def exists(self) -> bool:
        return self.kind != StudentDuplicateKind.NONE

    @property
    def requires_confirmation(self) -> bool:
        return self.exists

    @property
    def is_strong(self) -> bool:
        return self.kind == StudentDuplicateKind.STRONG_IDENTITY_MATCH

    @property
    def can_link_existing_student(self) -> bool:
        return self.kind in {
            StudentDuplicateKind.IDENTITY_MATCH,
            StudentDuplicateKind.STRONG_IDENTITY_MATCH,
        }


def empty_student_duplicate_check() -> StudentDuplicateCheck:
    return StudentDuplicateCheck()


def find_student_duplicates(
    *,
    center=None,
    ism: str = "",
    familya: str = "",
    telefon: str = "",
    birth_date=None,
    exclude_user_id=None,
    limit: int = 5,
) -> StudentDuplicateCheck:
    normalized_phone = normalize_phone(telefon)
    if not normalized_phone:
        return empty_student_duplicate_check()

    queryset = User.objects.filter(role="student")
    if center is not None:
        queryset = queryset.filter(center=center)
    if exclude_user_id:
        queryset = queryset.exclude(pk=exclude_user_id)

    phone_matches = queryset.filter(
        Q(telefon1=normalized_phone)
        | Q(telefon2=normalized_phone)
        | Q(phone_number=normalized_phone)
    ).order_by("-id")
    if not phone_matches.exists():
        return empty_student_duplicate_check()

    normalized_name = (ism or "").strip()
    normalized_family = (familya or "").strip()
    identity_matches = phone_matches.none()
    if normalized_name and normalized_family:
        identity_matches = phone_matches.filter(
            ism__iexact=normalized_name,
            familya__iexact=normalized_family,
        )
        if birth_date:
            strong_matches = identity_matches.filter(birth_date=birth_date)
            if strong_matches.exists():
                return StudentDuplicateCheck(
                    kind=StudentDuplicateKind.STRONG_IDENTITY_MATCH,
                    title="Kuchli duplicate ehtimoli",
                    message=(
                        "Ism, familiya, telefon va tug'ilgan sana bir xil bo'lgan o'quvchi topildi. "
                        "Baribir yangi o'quvchi sifatida qo'shilsinmi?"
                    ),
                    matches=tuple(strong_matches[:limit]),
                    match_count=strong_matches.count(),
                )

        if identity_matches.exists():
            return StudentDuplicateCheck(
                kind=StudentDuplicateKind.IDENTITY_MATCH,
                title="O'xshash o'quvchi topildi",
                message=(
                    "Ism, familiya va telefon bir xil bo'lgan o'quvchi mavjud. "
                    "Baribir yangi o'quvchi sifatida qo'shilsinmi?"
                ),
                matches=tuple(identity_matches[:limit]),
                match_count=identity_matches.count(),
            )

    return StudentDuplicateCheck(
        kind=StudentDuplicateKind.PHONE_ONLY,
        title="Telefon raqam mos keldi",
        message=(
            "Bu telefon raqam bilan boshqa o'quvchi mavjud. "
            "Baribir yangi o'quvchi sifatida qo'shilsinmi?"
        ),
        matches=tuple(phone_matches[:limit]),
        match_count=phone_matches.count(),
    )


def serialize_student_duplicate_check(check: StudentDuplicateCheck) -> dict:
    def _serialize_user(user) -> dict:
        return {
            "id": user.id,
            "name": user.get_full_name() or f"{user.ism} {user.familya}".strip(),
            "primary_phone": user.telefon1 or user.phone_number or "",
            "secondary_phone": user.telefon2 or "",
            "birth_date": user.birth_date.isoformat() if user.birth_date else "",
            "is_archived": bool(user.is_archived),
        }

    return {
        "kind": check.kind,
        "title": check.title,
        "message": check.message,
        "match_count": check.match_count,
        "is_strong": check.is_strong,
        "requires_confirmation": check.requires_confirmation,
        "confirm_label": "Yangi o'quvchi qilib qo'shish",
        "cancel_label": "Bekor qilish",
        "students": [_serialize_user(user) for user in check.matches],
    }
