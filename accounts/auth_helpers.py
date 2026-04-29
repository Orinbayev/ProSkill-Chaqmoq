from __future__ import annotations

import re
from dataclasses import dataclass

from django.contrib.auth import authenticate
from django.db.models import Q, QuerySet

from accounts.models import User
from accounts.utils import normalize_phone


@dataclass(frozen=True)
class LoginAttemptResult:
    user: User | None
    code: str


def normalized_phone_candidate(identifier: str) -> str:
    raw_value = str(identifier or "").strip()
    if not raw_value:
        return ""
    if "@" in raw_value or re.search(r"[A-Za-z]", raw_value):
        return ""
    return normalize_phone(raw_value)


def build_login_lookup_query(identifier: str) -> Q:
    normalized_identifier = str(identifier or "").strip()
    normalized_phone = normalized_phone_candidate(normalized_identifier)

    query = Q(email__iexact=normalized_identifier) | Q(
        telegram_username__iexact=normalized_identifier,
    )
    if normalized_phone:
        query |= (
            Q(phone_number=normalized_phone)
            | Q(telefon1=normalized_phone)
            | Q(telefon2=normalized_phone)
        )
    return query


def find_login_users(
    identifier: str,
    *,
    center=None,
    active_only: bool = False,
) -> QuerySet[User]:
    queryset = User.objects.filter(
        build_login_lookup_query(identifier),
    ).select_related("center")
    if active_only:
        queryset = queryset.filter(is_active=True)
    if center is not None:
        queryset = queryset.filter(center=center)
    return queryset.order_by("id")


def authenticate_login_identifier(
    identifier: str,
    password: str,
    *,
    request=None,
    center=None,
) -> User | None:
    return resolve_login_attempt(
        identifier,
        password,
        request=request,
        center=center,
    ).user


def resolve_login_attempt(
    identifier: str,
    password: str,
    *,
    request=None,
    center=None,
) -> LoginAttemptResult:
    authenticated_user = authenticate(request, username=identifier, password=password)
    if authenticated_user:
        return LoginAttemptResult(user=authenticated_user, code="success")

    candidates = list(find_login_users(identifier, center=center, active_only=False))
    if not candidates:
        return LoginAttemptResult(user=None, code="user_not_found")

    active_candidates = [candidate for candidate in candidates if candidate.is_active]
    if not active_candidates:
        return LoginAttemptResult(user=None, code="inactive_user")

    for candidate in active_candidates:
        if candidate.check_password(password):
            return LoginAttemptResult(user=candidate, code="success")
    return LoginAttemptResult(user=None, code="invalid_password")


def mask_login_identifier(identifier: str) -> str:
    value = str(identifier or "").strip()
    if not value:
        return ""

    if "@" in value:
        local, _, domain = value.partition("@")
        if len(local) <= 2:
            masked_local = f"{local[:1]}*"
        else:
            masked_local = f"{local[:2]}{'*' * max(1, len(local) - 2)}"
        return f"{masked_local}@{domain}"

    normalized_phone = normalized_phone_candidate(value)
    if normalized_phone:
        return f"{normalized_phone[:4]}***{normalized_phone[-2:]}"

    if len(value) <= 2:
        return f"{value[:1]}*"
    return f"{value[:2]}{'*' * max(1, len(value) - 4)}{value[-2:]}"
