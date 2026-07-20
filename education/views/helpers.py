"""Shared view helpers for education.views (extracted from legacy)."""
from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from core.center_features import center_ui_feature_enabled

def _redirect_disabled_module(request, *, message: str):
    messages.warning(request, message)
    return redirect("core:home")


def _ensure_center_ui_feature(request, center, feature_code: str, *, message: str):
    if center_ui_feature_enabled(center, feature_code):
        return None
    return _redirect_disabled_module(request, message=message)


def _can_manage(u):
    return u.is_superuser or getattr(u, "role", None) in ("director", "manager")


def _can_give_points(user, g: Group):
    return (
        user.is_superuser
        or user.role in ("director", "manager")
        or (user.role == "teacher" and g.oqituvchi_id == user.id)
    )

    return user.is_superuser or user.role in ("director", "manager") or (
        user.role == "teacher" and g.oqituvchi_id == user.id
    )


def get_active_center(request):
    """
    Returns the active center for the current request.
    Now fully handled by TenantMiddleware.
    """
    return getattr(request, 'center', None)


def _can_manage(u: User) -> bool:
    return u.is_superuser or getattr(u, "role", None) in ("director", "manager")


def _teacher_can(user: User, g: Group) -> bool:
    return (
        user.is_superuser
        or getattr(user, "role", None) in ("director", "manager")
        or (getattr(user, "role", None) == "teacher" and getattr(g, "oqituvchi_id", None) == user.id)
    )


def _can_give_points(user: User, g: Group) -> bool:
    return _teacher_can(user, g)


def _director_or_manager(user):
    return user.is_superuser or getattr(user, "role", None) in ("director", "manager")


def _teacher_can_view_settings(user):
    return user.is_superuser or getattr(user, "role", None) in ("director", "manager", "teacher")


def _teacher_or_management_can_access_group(user, group: Group):
    if user.is_superuser or getattr(user, "role", None) in ("director", "manager"):
        return True
    if getattr(user, "role", None) == "teacher":
        return group.oqituvchi_id == user.id or group.support_teacher_id == user.id
    return False


