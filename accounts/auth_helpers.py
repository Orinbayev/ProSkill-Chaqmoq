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
        query |= Q(phone_number=normalized_phone)
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
    """
    Authenticate by email/phone/username.

    Anti-enumeration notes:
    - ``user_not_found`` and ``invalid_password`` should be surfaced to clients
      as the same public error (see mobile/web login handlers).
    - ``inactive_user`` is returned only when the password is correct, so
      attackers cannot probe account existence without credentials.
    """
    authenticated_user = authenticate(request, username=identifier, password=password)
    if authenticated_user:
        if not authenticated_user.is_active:
            return LoginAttemptResult(user=None, code="inactive_user")
        return LoginAttemptResult(user=authenticated_user, code="success")

    candidates = list(find_login_users(identifier, center=center, active_only=False))
    if not candidates:
        return LoginAttemptResult(user=None, code="user_not_found")

    # Check password against all candidates (active + inactive) so inactive
    # accounts do not short-circuit with a distinguishable response.
    password_matches = [c for c in candidates if c.check_password(password)]
    if not password_matches:
        return LoginAttemptResult(user=None, code="invalid_password")

    active_matches = [c for c in password_matches if c.is_active]
    if not active_matches:
        return LoginAttemptResult(user=None, code="inactive_user")

    return LoginAttemptResult(user=active_matches[0], code="success")


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
