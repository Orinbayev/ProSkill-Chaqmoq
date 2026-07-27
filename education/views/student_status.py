"""O'quvchi HOLATI sahifasi (bo'limlar kesimida to'liq tarix)."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from core.tenant import get_request_center, get_tenant_object_or_404
from education.services.student_status import build_student_status

User = get_user_model()


def _can_view_status(user) -> bool:
    """Moliyaviy va chaqmoq tarixini birga ko'radi — faqat boshqaruv."""
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or getattr(user, "role", None) in ("director", "manager"))
    )


@login_required
def student_status(request, student_id: int):
    if not _can_view_status(request.user):
        raise PermissionDenied("Bu bo'limni faqat direktor va menejer ko'ra oladi.")

    center = get_request_center(request)
    if not center:
        raise PermissionDenied("Faol markaz tanlanmagan.")

    # Boshqa markaz o'quvchisi → 404 (IDOR himoyasi).
    student = get_tenant_object_or_404(User, request, pk=student_id, role="student")

    data = build_student_status(student, center)
    return render(request, "education/student_status.html", data)
