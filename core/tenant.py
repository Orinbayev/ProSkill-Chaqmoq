# core/tenant.py
"""
Tenant (center) isolation helpers.

Use these instead of bare get_object_or_404(Model, id=...) so objects from
other centers cannot be read or mutated (IDOR protection).
"""
from __future__ import annotations

from django.db.models import Model, Q, QuerySet
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect


def get_request_center(request):
    """Active centerni requestdan yoki userdan oladi."""
    return getattr(request, "center", None) or getattr(
        getattr(request, "user", None), "center", None
    )


def require_center(request):
    """
    request.center bo'lmasa - superadmin bo'lsa pickerga, boshqalar bo'lsa 404.
    """
    center = get_request_center(request)
    if center is None:
        user = getattr(request, "user", None)
        if user and user.is_authenticated and user.is_superuser:
            return redirect("platform_global:superadmin_dashboard")
        raise Http404("Center not found")
    return center


def ensure_obj_center(request, obj_center_id):
    """
    obj.center_id bilan request.center.id mosligini tekshiradi.
    Global obyektlarga (center=None) ruxsat beriladi.
    """
    center = require_center(request)
    # require_center may return a redirect Response for superuser
    if not hasattr(center, "id"):
        return center
    if obj_center_id and obj_center_id != center.id:
        raise Http404("Object not found")
    return True


def _object_center_id(obj, center_field: str = "center"):
    """Resolve center pk from a model instance."""
    if obj is None:
        return None
    attr = f"{center_field}_id"
    if hasattr(obj, attr):
        return getattr(obj, attr, None)
    related = getattr(obj, center_field, None)
    if related is None:
        return None
    return getattr(related, "pk", related)


def assert_same_center(request, obj, *, center_field: str = "center", allow_global: bool = False):
    """
    Raise Http404 if obj does not belong to the request's active center.

    - No active center (e.g. superuser on platform): no-op (caller decides).
    - allow_global: objects with center=NULL are allowed.
    """
    center = get_request_center(request)
    if center is None:
        return

    obj_center_id = _object_center_id(obj, center_field)
    if obj_center_id is None:
        if allow_global:
            return
        raise Http404("Object not found")
    if int(obj_center_id) != int(center.id):
        raise Http404("Object not found")


def tenant_filter_qs(qs: QuerySet, request, *, center_field: str = "center", allow_global: bool = False) -> QuerySet:
    """
    Restrict a queryset to the active center when one is bound on the request.
    """
    center = get_request_center(request)
    if center is None:
        return qs
    if allow_global:
        return qs.filter(
            Q(**{center_field: center}) | Q(**{f"{center_field}__isnull": True})
        )
    return qs.filter(**{center_field: center})


def get_tenant_object_or_404(
    klass,
    request,
    *args,
    center_field: str = "center",
    allow_global: bool = False,
    **kwargs,
):
    """
    get_object_or_404 + tenant isolation.

    klass: Model class or QuerySet.
    When request has an active center, only objects for that center match.
    Missing/other-center objects raise Http404 (same status for both → no IDOR leak).
    """
    if isinstance(klass, QuerySet):
        qs = klass
    elif isinstance(klass, type) and issubclass(klass, Model):
        qs = klass._default_manager.all()
    else:
        qs = klass

    qs = tenant_filter_qs(
        qs, request, center_field=center_field, allow_global=allow_global
    )
    return get_object_or_404(qs, *args, **kwargs)
