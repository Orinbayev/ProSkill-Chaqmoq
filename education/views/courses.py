"""Course templates and expense views (extracted from legacy)."""
from __future__ import annotations

import json
import logging
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from accounts.models import Center
from core.tenant import get_request_center

from ..forms import CenterExpenseForm
from ..models import Category, CourseTemplate
from .helpers import _can_manage, _director_or_manager

logger = logging.getLogger(__name__)

@login_required
def expense_create(request):
    if not _director_or_manager(request.user):
        return HttpResponseForbidden("Sizda ruxsat yo'q.")

    from core.tenant import get_request_center

    center = get_request_center(request) or getattr(request.user, "center", None)
    if not center:
        raise PermissionDenied("Markaz topilmadi.")

    form = CenterExpenseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        expense.center = center
        expense.created_by = request.user
        expense.save()
        messages.success(request, "Xarajat saqlandi.")
        return redirect("core:financial_dashboard")

    return render(
        request,
        "education/expense_form.html",
        {
            "form": form,
            "center": center,
        },
    )


@login_required
def course_list(request):
    from core.tenant import get_request_center
    center = get_request_center(request)
    if not center:
        return redirect("core:director_boshqaruv")
    if not _can_manage(request.user):
        raise PermissionDenied

    courses = (
        CourseTemplate.objects
        .filter(center=center)
        .select_related("category_obj")
        .order_by("name")
    )
    return render(request, "education/course_list.html", {"courses": courses})


@login_required
def course_create(request):
    from core.tenant import get_request_center
    center = get_request_center(request)
    if not center:
        return redirect("core:director_boshqaruv")
    if not _can_manage(request.user):
        raise PermissionDenied

    from django.db.models import Q
    categories_qs = Category.objects.all().order_by("name")
    if center:
        first_center = Center.objects.order_by("id").first()
        if first_center and center.id == first_center.id:
            categories_qs = categories_qs.filter(Q(center=center) | Q(center__isnull=True))
        else:
            categories_qs = categories_qs.filter(center=center)
    else:
        categories_qs = categories_qs.none()

    categories = list(categories_qs)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        price = request.POST.get("price", "0").replace(" ", "").replace(",", "")
        teacher_percent = request.POST.get("teacher_percent", "40")
        lessons_per_month = request.POST.get("lessons_per_month", "12")
        category_id = request.POST.get("category_obj") or None
        is_active = request.POST.get("is_active") == "on"

        errors = []
        if not name:
            errors.append("Kurs nomi kiritilishi shart.")
        try:
            price = int(price)
            if price <= 0:
                errors.append("Narx musbat son bo'lishi kerak.")
        except (ValueError, TypeError):
            errors.append("Narx noto'g'ri formatda.")

        if not errors:
            cat = None
            if category_id:
                cat = categories_qs.filter(id=category_id).first()
            CourseTemplate.objects.create(
                center=center,
                name=name,
                price=price,
                teacher_percent=int(teacher_percent or 40),
                lessons_per_month=int(lessons_per_month or 12),
                category_obj=cat,
                is_active=is_active,
            )
            messages.success(request, f"✅ '{name}' kursi qo'shildi.")
            return redirect("education:course_list")

        for e in errors:
            messages.error(request, e)

    return render(request, "education/course_form.html", {
        "categories": categories,
        "action": "Yangi kurs",
    })


@login_required
def course_edit(request, pk):
    from core.tenant import get_request_center
    center = get_request_center(request)
    if not _can_manage(request.user):
        raise PermissionDenied
    course = get_object_or_404(CourseTemplate, pk=pk, center=center)
    
    from django.db.models import Q
    categories_qs = Category.objects.all().order_by("name")
    if center:
        first_center = Center.objects.order_by("id").first()
        if first_center and center.id == first_center.id:
            categories_qs = categories_qs.filter(Q(center=center) | Q(center__isnull=True))
        else:
            categories_qs = categories_qs.filter(center=center)
    else:
        categories_qs = categories_qs.none()

    categories = list(categories_qs)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        price = request.POST.get("price", "0").replace(" ", "").replace(",", "")
        teacher_percent = request.POST.get("teacher_percent", "40")
        lessons_per_month = request.POST.get("lessons_per_month", "12")
        category_id = request.POST.get("category_obj") or None
        is_active = request.POST.get("is_active") == "on"

        errors = []
        if not name:
            errors.append("Kurs nomi kiritilishi shart.")
        try:
            price = int(price)
            if price <= 0:
                errors.append("Narx musbat son bo'lishi kerak.")
        except (ValueError, TypeError):
            errors.append("Narx noto'g'ri formatda.")

        if not errors:
            cat = None
            if category_id:
                cat = categories_qs.filter(id=category_id).first()
            course.name = name
            course.price = price
            course.teacher_percent = int(teacher_percent or 40)
            course.lessons_per_month = int(lessons_per_month or 12)
            course.category_obj = cat
            course.is_active = is_active
            course.save()
            messages.success(request, f"✅ '{name}' kursi yangilandi.")
            return redirect("education:course_list")

        for e in errors:
            messages.error(request, e)

    return render(request, "education/course_form.html", {
        "course": course,
        "categories": categories,
        "action": "Kursni tahrirlash",
    })


@login_required
def course_delete(request, pk):
    from core.tenant import get_request_center
    center = get_request_center(request)
    if not _can_manage(request.user):
        raise PermissionDenied
    course = get_object_or_404(CourseTemplate, pk=pk, center=center)
    if request.method == "POST":
        name = course.name
        course.delete()
        messages.success(request, f"'{name}' kursi o'chirildi.")
    return redirect("education:course_list")


def course_price_api(request, pk):
    """AJAX: kurs narxi va parametrlarini qaytaradi — guruh formida narxni avtomatik to'ldirish uchun."""
    from core.tenant import get_request_center
    center = get_request_center(request)
    course = CourseTemplate.objects.filter(pk=pk, center=center, is_active=True).first()
    if not course:
        return JsonResponse({"ok": False}, status=404)
    return JsonResponse({
        "ok": True,
        "price": course.price,
        "teacher_percent": course.teacher_percent,
        "lessons_per_month": course.lessons_per_month,
        "name": course.name,
    })


