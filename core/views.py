# core/views.py
from __future__ import annotations

import re
import secrets
import string
import datetime
from datetime import date

import openpyxl
from openpyxl.styles import Font, Alignment
from openpyxl import load_workbook

from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import FieldError, PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.utils.timezone import localdate
from django.views.decorators.http import require_POST

from accounts.models import User
from accounts.forms import TeacherForm, ParentForm
from chaqmoq.models import Ledger
from education.models import Group, Enrollment, TuitionMonth, Category
from store.models import Product, PurchaseRequest, Sale

from .forms import ProfileForm

U = get_user_model()


# =============================================================================
# TENANT HELPERS
# =============================================================================

def _get_center(request):
    """
    TenantMiddleware request.center qo'yadi.
    fallback: request.user.center
    """
    return getattr(request, "center", None) or getattr(getattr(request, "user", None), "center", None)


def _has_field(model, name: str) -> bool:
    try:
        return any(f.name == name for f in model._meta.fields)
    except Exception:
        return False


def _try_center_filter(qs, center, lookups: list[str]):
    """
    Turli modellarda center bog‘lanishi har xil bo‘lishi mumkin.
    Lookuplarni ketma-ket sinab ko‘ramiz.
    Birortasi ishlasa -> filtered qs.
    Hech biri ishlamasa -> qs.none() (leak bo‘lmasin).
    """
    if not center:
        return qs.none()
    for lk in lookups:
        try:
            return qs.filter(**{lk: center})
        except FieldError:
            continue
    return qs.none()


def _filter_center(qs, center):
    """
    Har xil modellarda center bo‘lmasligi mumkin.
    - center field bo‘lsa -> center=center
    - student field bo‘lsa -> student__center=center
    - group field bo‘lsa -> group__center=center
    """
    if center is None:
        return qs.none()

    m = qs.model
    if _has_field(m, "center"):
        return qs.filter(center=center)
    if _has_field(m, "student"):
        return qs.filter(student__center=center)
    if _has_field(m, "group"):
        return qs.filter(group__center=center)

    return qs.none()  # ✅ leak bo'lmasin


def _staff_only(request) -> bool:
    u = request.user
    return bool(u and (u.is_superuser or getattr(u, "role", None) in ("manager", "director")))


def _tenant_or_403(request):
    """
    Center yo‘q bo‘lsa — stats/listlarda leak bo‘lmasligi uchun qat'iy to‘xtatamiz.
    Student/Teacher dashboardlarida ham center kerak bo'lsa shu ishlatiladi.
    """
    center = _get_center(request)
    if not center and not request.user.is_superuser:
        raise PermissionDenied("Center biriktirilmagan.")
    return center


def _assert_same_center(obj, center):
    """
    Obj'ekt boshqa centerga tegishli bo'lsa 404 qaytaramiz (security).
    """
    if not center:
        return
    if hasattr(obj, "center_id"):
        if obj.center_id != center.id:
            raise PermissionDenied("Boshqa center ma'lumotiga ruxsat yo‘q.")


# =============================================================================
# DASHBOARD STATS
# =============================================================================

def _build_stats(center):
    """
    ✅ Tenant scoped stats.
    center None bo‘lsa -> hammasi 0.
    """
    if not center:
        return {
            "managers": 0,
            "teachers": 0,
            "students": 0,
            "products": 0,
            "pending_requests": 0,
            "total_chaqmoq": 0,
            "sales_today": 0,
        }

    users = U.objects.filter(center=center)

    products_qs = _try_center_filter(Product.objects.all(), center, ["center"])
    pr_qs = _try_center_filter(PurchaseRequest.objects.all(), center, ["center", "student__center", "manager__center"])
    ledger_qs = _try_center_filter(Ledger.objects.all(), center, ["center", "student__center", "group__center"])
    sales_qs = _try_center_filter(Sale.objects.all(), center, ["center", "student__center", "manager__center"])

    # Sale modeli field nomi: "sana" bo'lishi mumkin, ba'zida "created_at"
    if _has_field(Sale, "sana"):
        sales_today_qs = sales_qs.filter(sana__date=localdate())
    elif _has_field(Sale, "created_at"):
        sales_today_qs = sales_qs.filter(created_at__date=localdate())
    else:
        sales_today_qs = sales_qs.none()

    # PurchaseRequest status konstantasi bo'lmasligi mumkin — fallback:
    pending_status = getattr(PurchaseRequest, "PENDING", "pending")

    return {
        "managers": users.filter(role="manager").count(),
        "teachers": users.filter(role="teacher").count(),
        "students": users.filter(role="student").count(),
        "products": products_qs.count(),
        "pending_requests": pr_qs.filter(status=pending_status).count(),
        "total_chaqmoq": ledger_qs.aggregate(s=Sum("ball"))["s"] or 0,
        "sales_today": sales_today_qs.count(),
    }


# =============================================================================
# HOME / DASHBOARDS
# =============================================================================

@login_required
def home(request):
    u = request.user
    role = getattr(u, "role", None)
    if (not role) and u.is_superuser:
        role = "director"

    center = _get_center(request)
    
    # ✅ SUPERADMIN FIX: Center tanlanmagan bo‘lsa -> Super Admin Dashboard’ga yuboramiz
    if u.is_superuser and not center:
        return redirect("accounts:superadmin_dashboard")

    stats = _build_stats(center)

    ctx = {
        "stats": stats,
        "center": center,
    }

    if role == "director":
        return render(request, "core/dashboard_director.html", ctx)

    if role == "manager":
        return render(request, "core/dashboard_manager.html", ctx)

    if role == "teacher":
        return render(request, "core/dashboard_teacher.html", ctx)

    if role == "student":
        balance = Ledger.student_balansi(u.id)
        last_actions = _student_last_actions(u.id, center=center)
        return render(request, "core/dashboard_student.html", {
            "balance": balance,
            "last_actions": last_actions,
            "center": center,
        })

    if role == "parent":
        return redirect("core:dashboard_parent")

    return redirect("/admin/accounts/user/")


# =============================================================================
# TEACHERS (tenant scoped)
# =============================================================================

@login_required
def teacher_list(request):
    if not _staff_only(request):
        return render(request, "core/dashboard_guest.html")

    center = _get_center(request)
    qs = User.objects.filter(role="teacher")
    qs = _try_center_filter(qs, center, ["center"])  # ✅ tenant

    # Search filter
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(ism__icontains=q) | Q(familya__icontains=q) | Q(email__icontains=q) | Q(telefon1__icontains=q))

    # Sizda teacher->group relation nomi har xil bo'lishi mumkin.
    # Oldingi annotate(Count('group')) noto'g'ri bo'lish ehtimoli katta.
    # Shuning uchun xavfsiz yo'l: groups oqituvchi bo'yicha sanaladi.
    teachers = qs.annotate(group_count=Count("group", distinct=True)) if _has_field(Group, "oqituvchi") else qs
    teachers_count = qs.count()

    return render(request, "core/teacher_list.html", {"teachers": teachers, "teachers_count": teachers_count})


@login_required
def teacher_detail(request, pk):
    if not _staff_only(request):
        return render(request, "core/dashboard_guest.html")

    center = _get_center(request)

    teacher = get_object_or_404(User, pk=pk, role="teacher")
    _assert_same_center(teacher, center)

    # groups tenant + teacher filter
    groups_qs = Group.objects.all()
    groups_qs = _try_center_filter(groups_qs, center, ["center"])
    groups = groups_qs.filter(oqituvchi=teacher) if _has_field(Group, "oqituvchi") else groups_qs.none()

    return render(request, "core/teacher_detail.html", {"teacher": teacher, "groups": groups})


@login_required
def teacher_edit(request, pk):
    if not _staff_only(request):
        return render(request, "core/dashboard_guest.html")

    center = _get_center(request)

    teacher = get_object_or_404(User, pk=pk)
    _assert_same_center(teacher, center)

    if request.method == "POST":
        form = TeacherForm(request.POST, instance=teacher)
        if form.is_valid():
            teacher = form.save(commit=False)

            teacher.otchestvo = form.cleaned_data.get("otchestvo")

            tel1 = form.cleaned_data.get("telefon1", "") or ""
            tel2 = form.cleaned_data.get("telefon2", "") or ""

            if tel1:
                teacher.telefon1 = "+998" + tel1.replace("+998", "").replace(" ", "").replace("-", "")
            if tel2:
                teacher.telefon2 = "+998" + tel2.replace("+998", "").replace(" ", "").replace("-", "")

            # ✅ Password Update (Manual)
            new_pass = request.POST.get("new_password")
            if new_pass and new_pass.strip():
                teacher.set_password(new_pass.strip())
                messages.success(request, "Parol yangilandi.")

            teacher.save()

            yangi_foiz = getattr(teacher, "oqituvchi_foizi", None)

            # ✅ tenant: faqat shu teacher ning o'z group/enrollmentlari
            if yangi_foiz is not None:
                if _has_field(Group, "oqituvchi") and _has_field(Group, "oqituvchi_foiz"):
                    Group.objects.filter(oqituvchi=teacher).update(oqituvchi_foiz=yangi_foiz)

                # Enrollment modelida field mavjud bo'lsa update
                if _has_field(Enrollment, "oqituvchi_foiz"):
                    Enrollment.objects.filter(group__oqituvchi=teacher).update(oqituvchi_foiz=yangi_foiz)

            return redirect("core:teacher_list")
    else:
        form = TeacherForm(instance=teacher)

    return render(request, "core/teacher_edit.html", {"form": form, "teacher": teacher})


@login_required
def teacher_delete(request, pk):
    if request.user.role not in ("manager", "director") and not request.user.is_superuser:
        messages.error(request, "Ruxsat yo‘q.")
        return redirect("core:teacher_list")

    center = _get_center(request)

    teacher = get_object_or_404(User, pk=pk, role="teacher")
    _assert_same_center(teacher, center)

    if request.method == "POST":
        teacher.delete()
        messages.success(request, "O‘qituvchi o‘chirildi ✅")
        return redirect("core:teacher_list")

    return redirect("core:teacher_list")


# =============================================================================
# STUDENT last actions (tenant safe)
# =============================================================================

def _safe_user_label(user_obj) -> str:
    if not user_obj:
        return "Tizim"
    ism = getattr(user_obj, "ism", "") or ""
    fam = getattr(user_obj, "familya", "") or ""
    full = (ism + " " + fam).strip()
    return full or str(user_obj)


def _ledger_title(ledger_obj) -> str:
    rule = getattr(ledger_obj, "rule", None)
    if rule:
        for attr in ("nom", "name", "title"):
            v = getattr(rule, attr, None)
            if v:
                return str(v)
    return "Harakat"


def _student_last_actions(student_id: int, center=None):
    """
    Oxirgi 10 ta Ledger yozuvini dict ko‘rinishida qaytaradi.
    ✅ Tenant safe: center bo'lsa, ledger'ni center scope qilamiz.
    """
    field_names = {f.name for f in Ledger._meta.fields}

    sr = []
    for f in ("rule", "group", "beruvchi"):
        if f in field_names:
            sr.append(f)

    qs = Ledger.objects.filter(student_id=student_id)

    # tenant scope (Ledger'da center bo'lmasa student__center orqali)
    qs = _try_center_filter(qs, center, ["center", "student__center", "group__center"]) if center else qs

    # ordering field: created_at yoki sana
    if _has_field(Ledger, "created_at"):
        qs = qs.order_by("-created_at")
    elif _has_field(Ledger, "sana"):
        qs = qs.order_by("-sana")
    else:
        qs = qs.order_by("-id")

    qs = qs.select_related(*sr)[:10]

    out = []
    for x in qs:
        delta = int(getattr(x, "ball", 0) or 0)
        sign = "+" if delta >= 0 else "-"

        actor_obj = getattr(x, "beruvchi", None)

        grp = ""
        if getattr(x, "group", None):
            grp = getattr(x.group, "nom", "") or ""

        created_at = None
        if hasattr(x, "created_at") and getattr(x, "created_at"):
            created_at = x.created_at
        elif hasattr(x, "sana") and getattr(x, "sana"):
            created_at = x.sana
        else:
            created_at = timezone.now()

        out.append({
            "title": _ledger_title(x),
            "who": _safe_user_label(actor_obj),
            "created_at": created_at,
            "delta": delta,
            "sign": sign,
            "abs_delta": abs(delta),
            "group": grp,
        })
    return out


# =============================================================================
# PARENTS MANAGEMENT
# =============================================================================

@login_required
def stat_parents(request):
    if not _staff_only(request):
        return render(request, "core/dashboard_guest.html")

    q = request.GET.get("q", "").strip()
    center = _get_center(request)
    rows = U.objects.filter(role="parent")
    rows = _try_center_filter(rows, center, ["center"]) if center else rows.none()

    if q:
        rows = rows.filter(Q(ism__icontains=q) | Q(familya__icontains=q) | Q(email__icontains=q) | Q(telefon1__icontains=q))

    page_size = 9999
    paginator = Paginator(rows.order_by("ism", "familya", "id"), page_size)
    page_obj = paginator.get_page(1)
    start_index = page_obj.start_index() if page_obj.paginator.count else 0

    return render(request, "core/stats_users.html", {
        "title": "Ota-onalar",
        "page_obj": page_obj,
        "total_count": rows.count(),
        "user_kind": "parents",
        "no_pagination": True,
        "start_index": start_index,
        "page_size": page_size,
        "center": center,  # ✅ Add center to context
    })


@login_required
@require_POST
def update_center_donation_settings(request):
    if not _staff_only(request):
        raise PermissionDenied
    
    center = _get_center(request)
    if not center:
        messages.error(request, "Markaz topilmadi.")
        return redirect("core:stat_parents")

    center.donation_enabled = request.POST.get("donation_enabled") == "on"
    center.donation_card_number = request.POST.get("donation_card_number", "").strip()
    center.donation_card_holder = request.POST.get("donation_card_holder", "").strip()
    
    if "donation_qr_image" in request.FILES:
        center.donation_qr_image = request.FILES["donation_qr_image"]
    
    center.save()
    messages.success(request, "Donat sozlamalari yangilandi.")
    return redirect("core:stat_parents")


@login_required
def parent_add(request):
    if not _staff_only(request):
        raise PermissionDenied
    
    if request.method == "POST":
        form = ParentForm(request.POST, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, "Ota-ona muvaffaqiyatli qo'shildi ✅")
            return redirect("core:stat_parents")
    else:
        form = ParentForm(request=request)
    
    return render(request, "core/parent_form.html", {"form": form, "title": "Ota-ona qo'shish"})


@login_required
def parent_edit(request, pk):
    if not _staff_only(request):
        raise PermissionDenied
    
    center = _get_center(request)
    parent = get_object_or_404(User, pk=pk, role="parent")
    _assert_same_center(parent, center)
    
    if request.method == "POST":
        form = ParentForm(request.POST, instance=parent, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, "Ota-ona ma'lumotlari yangilandi ✅")
            return redirect("core:stat_parents")
    else:
        form = ParentForm(instance=parent, request=request)
    
    return render(request, "core/parent_form.html", {"form": form, "title": "Ota-onani tahrirlash", "is_edit": True})


@login_required
def parent_delete(request, pk):
    if not _staff_only(request):
        raise PermissionDenied
        
    center = _get_center(request)
    parent = get_object_or_404(User, pk=pk, role="parent")
    _assert_same_center(parent, center)
    
    if request.method == "POST":
        parent.delete()
        messages.success(request, "Ota-ona o'chirildi ✅")
        return redirect("core:stat_parents")
    return redirect("core:stat_parents")


@login_required
def dashboard_parent(request):
    if getattr(request.user, "role", None) != "parent":
        return redirect("core:home")
    
    center = _get_center(request)
    children = request.user.children.all()

    # Calculate stats for each child
    for child in children:
        # Balance
        child.calculated_balance = Ledger.objects.filter(
            student=child
        ).filter(
            Q(group__center=center) | Q(rule__center=center)
        ).aggregate(Sum('ball'))['ball__sum'] or 0

        # Rank
        child.calculated_rank = Ledger.objects.filter(
            Q(group__center=center) | Q(rule__center=center),
            student__role='student'
        ).values('student').annotate(
            total_points=Sum('ball')
        ).filter(total_points__gt=child.calculated_balance).count() + 1
    
    # Parent can also search other students
    q = request.GET.get("q", "").strip()
    search_results = []
    if q:
        search_results = User.objects.filter(role="student", center=center, is_archived=False).filter(
            Q(ism__icontains=q) | Q(familya__icontains=q)
        ).distinct()[:10]

        for s in search_results:
            # Check if already child
            s.is_my_child = s in children

            # Calculate Stats (Same logic)
            s_balance = Ledger.objects.filter(
                student=s
            ).filter(
                Q(group__center=center) | Q(rule__center=center)
            ).aggregate(Sum('ball'))['ball__sum'] or 0
            
            s.calculated_balance = s_balance

            s.calculated_rank = Ledger.objects.filter(
                Q(group__center=center) | Q(rule__center=center),
                student__role='student'
            ).values('student').annotate(
                total_points=Sum('ball')
            ).filter(total_points__gt=s_balance).count() + 1
        
    return render(request, "core/dashboard_parent.html", {
        "children": children,
        "search_results": search_results,
        "center": center,
        "title": "Ota-ona paneli",
    })

@login_required
@require_POST
def toggle_child(request, student_id):
    if getattr(request.user, "role", None) != "parent":
        raise PermissionDenied
    
    student = get_object_or_404(User, pk=student_id, role="student")
    parent = request.user
    
    if student in parent.children.all():
        parent.children.remove(student)
        messages.warning(request, f"{student.get_full_name()} farzandlaringiz safidan olib tashlandi.")
    else:
        parent.children.add(student)
        messages.success(request, f"{student.get_full_name()} farzandlaringiz safiga qo‘shildi.")
        
    return redirect(request.META.get('HTTP_REFERER', 'core:dashboard_parent'))


# =============================================================================
# STATS USERS (tenant scoped)
# =============================================================================

@login_required
def stat_managers(request):
    # ✅ Manager bu bo‘limga kirmasin (URL orqali ham)
    if getattr(request.user, "role", None) == "manager":
        return render(request, "no_permission.html", {"message": "Sizda bu bo‘limga kirish huquqi yo‘q."})

    if not (request.user.is_superuser or getattr(request.user, "role", None) in ("director", "admin")):
        return render(request, "core/dashboard_guest.html")

    q = request.GET.get("q", "").strip()

    center = _get_center(request)
    rows = U.objects.filter(role="manager")
    rows = _try_center_filter(rows, center, ["center"]) if center else rows.none()

    if q:
        rows = rows.filter(Q(ism__icontains=q) | Q(familya__icontains=q) | Q(email__icontains=q))

    page_size = 9999
    paginator = Paginator(rows.order_by("ism", "familya", "id"), page_size)
    page_obj = paginator.get_page(1)
    start_index = page_obj.start_index() if page_obj.paginator.count else 0

    return render(request, "core/stats_users.html", {
        "title": "Managerlar",
        "page_obj": page_obj,
        "total_count": rows.count(),
        "page_size": page_size,
        "start_index": start_index,
        "no_pagination": True,
        "user_kind": "managers",
        "center": center,
    })


@login_required
def stat_teachers(request):
    if not _staff_only(request):
        return render(request, "core/dashboard_guest.html")

    q = request.GET.get("q", "").strip()
    page_size = 9999

    center = _get_center(request)

    rows = U.objects.filter(role="teacher")
    rows = _try_center_filter(rows, center, ["center"]) if center else rows.none()

    if q:
        rows = rows.filter(Q(ism__icontains=q) | Q(familya__icontains=q) | Q(email__icontains=q))

    paginator = Paginator(rows.order_by("id"), page_size)
    page_obj = paginator.get_page(1)
    start_index = page_obj.start_index() if page_obj.paginator.count else 0

    return render(request, "core/stats_users.html", {
        "title": "O‘qituvchilar",
        "page_obj": page_obj,
        "total_count": rows.count(),
        "start_index": start_index,
        "page_size": page_size,
        "no_pagination": True,
        "user_kind": "teachers",
        "center": center,
    })


@login_required
def stat_students(request):
    if not _staff_only(request):
        return render(request, "core/dashboard_guest.html")

    q = request.GET.get("q", "").strip()
    gender = request.GET.get("gender", "").strip()
    section_id = request.GET.get("section", "").strip()
    status = request.GET.get("status", "active").strip() # default active

    page_size = request.GET.get("size", "10")
    try:
        page_size = int(page_size)
    except Exception:
        page_size = 10

    center = _get_center(request)
    
    # 1. Categories for filter
    categories = Category.objects.all()
    if center:
        categories = categories.filter(Q(center=center) | Q(center__isnull=True))

    rows = U.objects.filter(role="student")
    rows = _try_center_filter(rows, center, ["center"]) if center else rows.none()

    # ✅ Calculate Counts (for Tabs)
    active_count = rows.filter(is_archived=False).count()
    archived_count = rows.filter(is_archived=True).count()

    # Apply Status Filter
    if status == "archived":
        rows = rows.filter(is_archived=True)
    else:
        rows = rows.filter(is_archived=False)

    # ledger relation nomi: "ledger" bo'lishi shart emas, sizda annotate ishlagan.
    from django.db.models.functions import Coalesce
    from django.db.models import Prefetch
    from education.models import Enrollment

    # ✅ Isolate data by center (Coins and Groups)
    rows = rows.annotate(
        jami_chaqmoq=Coalesce(
            Sum("ledger__ball"),
            0
        )
    ).prefetch_related(
        Prefetch("enrollment_set", queryset=Enrollment.objects.filter(group__center=center).select_related("group"))
    ).order_by("-id")

    if q:
        rows = rows.filter(Q(ism__icontains=q) | Q(familya__icontains=q) | Q(email__icontains=q))
    
    if gender:
        rows = rows.filter(gender=gender)
        
    if section_id:
        if section_id.isdigit():
             rows = rows.filter(enrollment__group__category_obj__id=int(section_id)).distinct()
        else:
             # Fallback for string names
             rows = rows.filter(enrollment__group__category_obj__name=section_id).distinct()

    paginator = Paginator(rows, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    start_index = page_obj.start_index() if page_obj.paginator.count else 0

    context = {
        "title": "O‘quvchilar",
        "page_obj": page_obj,
        "total_count": rows.count(),
        "start_index": start_index,
        "page_size": page_size,
        "categories": categories,
        "user_kind": "students",
        "current_status": status,
        "active_count": active_count,
        "archived_count": archived_count,
        "center": center,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, "core/includes/student_list_table.html", context)

    return render(request, "core/stats_users.html", context)


@login_required
@require_POST
def archive_student(request, pk):
    """
    Students Soft Delete (Archive)
    - Remove from groups (or mark inactive)
    - Set is_archived = True
    """
    if not _staff_only(request):
        raise PermissionDenied

    center = _get_center(request)
    student = get_object_or_404(U, pk=pk, role="student")
    _assert_same_center(student, center)

    with transaction.atomic():
        # 1. Archive User
        student.is_archived = True
        student.save(update_fields=["is_archived"])

        # 2. Deactivate Enrollments (Remove from active groups lists)
        # Enrollment has is_active field? Let's check model. 
        # Yes, education/models.py Enrollment has is_active field.
        Enrollment.objects.filter(student=student, is_active=True).update(is_active=False)

    return HttpResponse(status=200)


@login_required
@require_POST
def restore_student(request, pk):
    """
    Restore Student from Archive
    """
    if not _staff_only(request):
        raise PermissionDenied

    center = _get_center(request)
    student = get_object_or_404(U, pk=pk, role="student")
    _assert_same_center(student, center)

    with transaction.atomic():
        student.is_archived = False
        student.save(update_fields=["is_archived"])
        
        # ✅ Restore enrollments (activate them back)
        Enrollment.objects.filter(student=student, center=center).update(is_active=True)

    return HttpResponse(status=200)


@login_required
@require_POST
def hard_delete_student(request, pk):
    """
    Hard Delete Student (Permanent)
    """
    if not _staff_only(request):
        raise PermissionDenied

    center = _get_center(request)
    student = get_object_or_404(U, pk=pk, role="student")
    _assert_same_center(student, center)

    if not student.is_archived:
        # Safety check: should usually differ hard delete to archived users only?
        # Requirement doesn't strictly say, but usually safer.
        pass

    student.delete()
    return HttpResponse(status=200)


# =============================================================================
# USER CRUD (tenant scoped)
# =============================================================================

def _first_day_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _parse_month_yyyy_mm(s: str) -> date | None:
    """
    "2026-01" -> date(2026,1,1)
    xato bo'lsa None
    """
    try:
        s = (s or "").strip()
        if not s:
            return None
        y, m = s.split("-")
        y = int(y)
        m = int(m)
        if m < 1 or m > 12:
            return None
        return date(y, m, 1)
    except Exception:
        return None


@login_required
def user_view(request, pk):
    role = getattr(request.user, "role", None)
    if not (_staff_only(request) or role == "parent"):
        return render(request, "core/dashboard_guest.html")

    center = _get_center(request)
    user = get_object_or_404(User, pk=pk)
    _assert_same_center(user, center)

    # ✅ Handle Password Reset (Admin/Staff only)
    if request.method == "POST" and "new_password" in request.POST:
        if not _staff_only(request):
            raise PermissionDenied
        new_pass = request.POST.get("new_password")
        if new_pass:
            user.set_password(new_pass)
            user.save()
            messages.success(request, f"{user.get_full_name()} paroli muvaffaqiyatli o'zgartirildi.")
            return redirect("core:user_view", pk=user.pk)

    # ✅ Chaqmoq balance (ONLY FOR THIS CENTER)
    balance = Ledger.objects.filter(
        student=user
    ).filter(
        Q(group__center=center) | Q(rule__center=center)
    ).aggregate(Sum('ball'))['ball__sum'] or 0
    
    # ✅ Chaqmoq history with Pagination (ONLY FOR THIS CENTER)
    all_actions = Ledger.objects.filter(
        student=user
    ).filter(
        Q(group__center=center) | Q(rule__center=center)
    ).select_related('beruvchi', 'group').order_by("-id")
    page_number = request.GET.get('page', 1)
    paginator = Paginator(all_actions, 10)  # 10 items per page
    actions_page = paginator.get_page(page_number)

    # ✅ Attendance Stats (ONLY FOR THIS CENTER)
    from education.models import Attendance, Enrollment
    total_lessons = Attendance.objects.filter(student=user, group__center=center).count()
    present_days = Attendance.objects.filter(student=user, group__center=center, present=True).count()
    missed_days = total_lessons - present_days
    
    attendance_rate = 0
    if total_lessons > 0:
        attendance_rate = int((present_days / total_lessons) * 100)

    # ✅ Detailed Group Attendance (Calendar View)
    import calendar
    from datetime import date
    now = timezone.now()
    
    # Handle month/year filter
    try:
        selected_year = int(request.GET.get('year', now.year))
        selected_month = int(request.GET.get('month', now.month))
    except (ValueError, TypeError):
        selected_year, selected_month = now.year, now.month
    
    # Month list for filter
    available_months = [
        (1, "Yanvar"), (2, "Fevral"), (3, "Mart"), (4, "Aprel"), (5, "May"), (6, "Iyun"),
        (7, "Iyul"), (8, "Avgust"), (9, "Sentyabr"), (10, "Oktyabr"), (11, "Noyabr"), (12, "Dekabr")
    ]
    available_years = range(now.year - 1, now.year + 1)
    
    # Get the month grid
    month_calendar = calendar.monthcalendar(selected_year, selected_month) # [[0,0,1,2,3,4,5], ...]
    
    # ✅ Enrollments (ONLY FOR THIS CENTER)
    enrollments = Enrollment.objects.filter(
        student=user, 
        group__center=center
    ).select_related('group', 'group__category_obj', 'group__oqituvchi').order_by("-id")
    
    for enr in enrollments:
        # Stats (Total)
        enr.total = Attendance.objects.filter(student=user, group=enr.group).count()
        enr.present = Attendance.objects.filter(student=user, group=enr.group, present=True).count()
        enr.rate = int((enr.present / enr.total * 100)) if enr.total > 0 else 0
        
        # Monthly Stats
        enr.month_present = Attendance.objects.filter(
            student=user, group=enr.group, present=True, 
            date__year=selected_year, date__month=selected_month
        ).count()
        enr.month_absent = Attendance.objects.filter(
            student=user, group=enr.group, present=False, 
            date__year=selected_year, date__month=selected_month
        ).count()
        
        # Attendance records for this group in selected month
        month_atts = {att.date.day: att.present for att in Attendance.objects.filter(
            student=user, group=enr.group, date__year=selected_year, date__month=selected_month
        )}
        
        # Generate final grid for template
        grid = []
        for week in month_calendar:
            week_days = []
            for day in week:
                if day == 0:
                    week_days.append({"day": "", "status": "empty"})
                else:
                    status = "none" # default: no lesson
                    if day in month_atts:
                        status = "present" if month_atts[day] else "absent"
                    
                    week_days.append({
                        "day": day,
                        "status": status,
                        "is_today": (day == now.day and selected_month == now.month and selected_year == now.year)
                    })
            grid.append(week_days)
        enr.calendar_grid = grid
        enr.selected_month_name = next(m[1] for m in available_months if m[0] == selected_month)
    
    # ✅ Rank Calculation
    rank = Ledger.objects.filter(
        Q(group__center=center) | Q(rule__center=center),
        student__role='student'
    ).values('student').annotate(
        total_points=Sum('ball')
    ).filter(total_points__gt=balance).count() + 1

    context = {
        "u": user,
        "balance": balance,
        "rank": rank,
        "actions": actions_page,
        "total_lessons": total_lessons,
        "present_days": present_days,
        "missed_days": missed_days,
        "attendance_rate": attendance_rate,
        "enrollments": enrollments,
        "selected_month": selected_month,
        "selected_year": selected_year,
        "available_months": available_months,
        "available_years": available_years,
    }

    return render(request, "core/user_view.html", context)


@login_required
def user_delete(request, pk):
    if not _staff_only(request):
        return render(request, "core/dashboard_guest.html")

    center = _get_center(request)

    user = get_object_or_404(U, pk=pk)
    _assert_same_center(user, center)

    if request.method == "POST":
        role = getattr(user, "role", "student")
        user.delete()
        if role == "manager":
            return redirect("core:stat_managers")
        elif role == "teacher":
            return redirect("core:stat_teachers")
        return redirect("core:stat_students")

    return render(request, "core/user_delete.html", {"user": user})


@login_required
def user_edit(request, pk):
    if not _staff_only(request):
        return render(request, "core/dashboard_guest.html")

    center = _get_center(request)

    user = get_object_or_404(U, id=pk)
    _assert_same_center(user, center)

    all_groups = Group.objects.all()
    all_groups = _try_center_filter(all_groups, center, ["center"]) if center else Group.objects.none()

    # ✅ enrollments ham tenant: enrollment -> group__center
    enrollments = Enrollment.objects.filter(student=user).select_related("group")
    enrollments = _try_center_filter(enrollments, center, ["group__center"])

    # Determine default redirect based on role
    default_next = "/stat/students/"
    if user.role == "manager":
        default_next = "/stat/managers/"
    elif user.role == "teacher":
        default_next = "/stat/teachers/"
    elif user.role == "parent":
        default_next = "/stat/parents/"

    next_url = request.POST.get("next") or request.GET.get("next") or default_next

    month_str = request.POST.get("month") or request.GET.get("month") or ""
    selected_month = _parse_month_yyyy_mm(month_str) or _first_day_of_month(timezone.localdate())

    if request.method == "POST":
        user.ism = (request.POST.get("ism") or "").strip()
        user.familya = (request.POST.get("familya") or "").strip()
        user.otchestvo = (request.POST.get("otchestvo") or "").strip()
        user.email = (request.POST.get("email") or "").strip()
        user.telefon1 = (request.POST.get("telefon1") or "").strip()
        user.telefon2 = (request.POST.get("telefon2") or "").strip()

        # ✅ rolni o'zgartirishni xavfsiz qiling (xohlasangiz)
        new_role = (request.POST.get("role") or "").strip()
        if new_role:
            user.role = new_role

        password = request.POST.get("password")
        if password:
            user.set_password(password)

        # ✅ Save new student fields
        user.birth_date = request.POST.get("birth_date") or None
        user.gender = request.POST.get("gender") or None
        user.passport_id = (request.POST.get("passport_id") or "").strip() or None
        user.jshr = (request.POST.get("jshr") or "").strip() or None
        user.address = (request.POST.get("address") or "").strip() or None

        user.save()

        # 2) Mavjud enrollmentlar bo‘yicha narxlarni yangilash / o‘chirish
        for enroll in enrollments:
            if request.POST.get(f"delete_group_{enroll.id}") == "on":
                if hasattr(enroll, "is_active"):
                    enroll.is_active = False
                    enroll.save(update_fields=["is_active"])
                elif hasattr(enroll, "status"):
                    enroll.status = "inactive"
                    enroll.save(update_fields=["status"])
                else:
                    enroll.delete()
                continue

            field = f"kurs_narhi_{enroll.id}"
            new_price_raw = request.POST.get(field)

            if new_price_raw is not None and str(new_price_raw).strip() != "":
                try:
                    enroll.kurs_narhi = int(new_price_raw)
                    enroll.save(update_fields=["kurs_narhi"])

                    TuitionMonth.objects.update_or_create(
                        enrollment=enroll,
                        month=selected_month,
                        defaults={"fee_amount": enroll.kurs_narhi},
                    )
                except ValueError:
                    pass

        # 3) Yangi guruhga qo‘shish (tenant check bilan!)
        yangi_group_id = request.POST.get("yangi_group_id")
        yangi_group_price = request.POST.get("yangi_group_price")

        if yangi_group_id:
            group = get_object_or_404(Group, id=yangi_group_id)
            # ✅ boshqa center guruhini qo'shib yubormasin
            if center and getattr(group, "center_id", None) != center.id:
                messages.error(request, "Bu guruh boshqa centerga tegishli.")
                return redirect(next_url)

            enroll, _created = Enrollment.objects.get_or_create(student=user, group=group)
            if yangi_group_price:
                try:
                    enroll.kurs_narhi = int(yangi_group_price)
                except ValueError:
                    pass
            enroll.save()

            TuitionMonth.objects.update_or_create(
                enrollment=enroll,
                month=selected_month,
                defaults={"fee_amount": enroll.kurs_narhi or 0},
            )

        return redirect(next_url)

    return render(request, "core/user_edit.html", {
        "user_obj": user,
        "enrollments": enrollments,
        "groups": all_groups,
        "next": next_url,
        "month": month_str,
        "selected_month": selected_month,
    })


# =============================================================================
# EXCEL IMPORT/EXPORT (tenant scoped)
# =============================================================================

def _normalize_header(x: str) -> str:
    return (str(x or "").strip().lower()
            .replace("’", "").replace("'", "").replace("`", "")
            .replace(" ", "").replace("_", "").replace("-", ""))


def _pick_col(headers_map, *aliases):
    for a in aliases:
        key = _normalize_header(a)
        if key in headers_map:
            return headers_map[key]
    return None


def _cell_to_str(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v)).strip()
    return str(v).strip()


def _clean_for_login(text: str) -> str:
    s = (text or "").strip().lower()
    s = s.replace("o‘", "o").replace("o'", "o")
    s = s.replace("g‘", "g").replace("g'", "g")
    s = s.replace("’", "").replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _normalize_phone(p: str) -> str:
    if not p: return ""
    return re.sub(r"\D", "", str(p))


def _gen_default_password():
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))


def _gen_unique_gmail_like_email(UModel, ism: str, familya: str) -> str:
    first = _clean_for_login(ism) or "user"
    last = _clean_for_login(familya)
    base = f"{first}.{last}" if last else first

    for _ in range(80):
        suffix = secrets.randbelow(9000) + 1000
        email = f"{base}{suffix}@gmail.com"
        if not UModel.objects.filter(email=email).exists():
            return email

    token = secrets.token_hex(3)
    return f"{base}{token}@gmail.com"


def _normalize_gender(val: str) -> str | None:
    if not val:
        return None
    s = str(val).strip().lower()
    if s in ["erkak", "male", "o'gil", "o‘gil", "m"]:
        return "male"
    if s in ["ayol", "female", "qiz", "f"]:
        return "female"
    return None


@login_required
@require_POST
def _process_user_import(request, role="student"):
    """
    Generic User Import logic.
    """
    mode = "create_only"

    # Normalize role (handle plurals)
    role_map = {
        "students": "student",
        "teachers": "teacher",
        "managers": "manager"
    }
    role = role_map.get(role, role)

    # Determie redirect URL
    redirect_map = {
        "student": "core:stat_students",
        "teacher": "core:teacher_list",
        "manager": "core:stat_managers"
    }
    # Fallback to Referer if role not found, then Home
    default_url = request.META.get("HTTP_REFERER", "core:home")
    success_url = redirect_map.get(role, default_url)

    if not _staff_only(request):
        return render(request, "core/dashboard_guest.html")

    center = _get_center(request)
    if not center:
        messages.error(request, "Active center tanlanmagan.")
        return redirect(success_url)

    f = request.FILES.get("file")
    if not f:
        messages.error(request, "Excel fayl tanlanmadi.")
        return redirect(success_url)

    if not f.name.lower().endswith(".xlsx"):
        messages.error(request, "Faqat .xlsx format qabul qilinadi.")
        return redirect(success_url)

    try:
        wb = load_workbook(filename=f, data_only=True)
        ws = wb.active
        found_ws = False
        for sn in wb.sheetnames:
            sheet = wb[sn]
            sample_rows = list(sheet.iter_rows(max_row=10, values_only=True))
            for r in sample_rows:
                row_str = " ".join([str(x).lower() for x in r if x])
                if any(k in row_str for k in ["ism", "familya", "f.i.sh", "name"]):
                    ws = sheet
                    found_ws = True
                    break
            if found_ws: break
    except Exception as e:
        messages.error(request, f"Excel xatosi: {e}")
        return redirect(success_url)

    all_rows = list(ws.iter_rows(values_only=True))
    if not all_rows:
        messages.error(request, "Excel bo‘sh.")
        return redirect(success_url)

    # Header detection
    headers_map = {}
    header_idx = 0
    for i in range(min(15, len(all_rows))):
        temp_map = {}
        for idx, val in enumerate(all_rows[i]):
            key = _normalize_header(val)
            if key: temp_map[key] = idx
        if _pick_col(temp_map, "ism", "name", "fish") is not None:
            header_idx = i
            headers_map = temp_map
            break

    col_ism = _pick_col(headers_map, "ism", "firstname", "name")
    col_fam = _pick_col(headers_map, "familya", "familiya", "lastname")
    col_fish = _pick_col(headers_map, "fish", "f.i.sh", "fullname")
    col_otch = _pick_col(headers_map, "otchestvo", "middlename")
    col_tel1 = _pick_col(headers_map, "telefon", "telefon1", "phone", "tel")
    col_tel2 = _pick_col(headers_map, "telefon2", "phone2", "tel2")
    col_birth_date = _pick_col(headers_map, "tugilgankun", "birthdate", "birth date", "tug'ilgan sana")
    col_gender = _pick_col(headers_map, "jinsi", "gender")
    col_email = _pick_col(headers_map, "email", "login")
    col_pass = _pick_col(headers_map, "parol", "password")
    col_chaqmoq = _pick_col(headers_map, "chaqmoq", "coins", "ball")
    col_lavozim = _pick_col(headers_map, "lavozim", "position", "role")

    created = 0
    updated = 0
    skipped = 0
    skipped_names = [] 
    problems = []

    center_users = U.objects.filter(role=role, center=center)
    by_email = {s.email.lower(): s for s in center_users if s.email}
    all_known_emails = set(U.objects.values_list("email", flat=True))

    total_data_rows = 0
    for r_i, r in enumerate(all_rows[header_idx + 1:], start=header_idx + 2):
        if not r or all(v is None for v in r): continue
        total_data_rows += 1

        ism = _cell_to_str(r[col_ism]) if (col_ism is not None and col_ism < len(r)) else ""
        fam = _cell_to_str(r[col_fam]) if (col_fam is not None and col_fam < len(r)) else ""
        otch = _cell_to_str(r[col_otch]) if (col_otch is not None and col_otch < len(r)) else ""
        
        if col_fish is not None and not ism:
            fish = _cell_to_str(r[col_fish])
            if fish:
                parts = fish.split()
                ism = parts[0] if len(parts) > 0 else ""
                fam = parts[1] if len(parts) > 1 else ""
                otch = " ".join(parts[2:]) if len(parts) > 2 else ""

        if not ism or not fam:
            skipped += 1
            problems.append(f"{r_i}-qator: Ism/Familiya yo'q.")
            continue

        tel1 = _cell_to_str(r[col_tel1]) if (col_tel1 is not None and col_tel1 < len(r)) else ""
        norm_tel1 = _normalize_phone(tel1)
        email_val = _cell_to_str(r[col_email]) if (col_email is not None and col_email < len(r)) else ""

        # Identification
        u = None
        if email_val: u = by_email.get(email_val.lower())

        # Skip if exists in same center/role
        if u:
            skipped += 1
            skipped_names.append(f"{ism} {fam}")
            continue

        try:
            with transaction.atomic():
                # Global Uniqueness check
                # Global Uniqueness check
                if email_val and email_val.lower() in all_known_emails:
                    # Instead of skipping, let's make email unique
                    prefix = email_val.split('@')[0]
                    cand = f"{prefix}{secrets.randbelow(9000)+1000}@gmail.com"
                    while cand in all_known_emails:
                        cand = f"{prefix}{secrets.randbelow(9000)+1000}@gmail.com"
                    email_val = cand

                if not email_val:
                    prefix = _clean_for_login(ism) or role
                    cand = f"{prefix}{secrets.randbelow(9000)+1000}@gmail.com"
                    while cand in all_known_emails:
                        cand = f"{prefix}{secrets.randbelow(9000)+1000}@gmail.com"
                    email_val = cand
                
                u = U.objects.create(
                    email=email_val, role=role, center=center,
                    ism=ism, familya=fam, first_name=ism, last_name=fam,
                    otchestvo=otch, telefon1=tel1
                )
                all_known_emails.add(email_val.lower())

                # Lavozim (if applicable)
                lav = _cell_to_str(r[col_lavozim]) if (col_lavozim is not None and col_lavozim < len(r)) else ""
                if lav:
                    u.lavozim = lav

                # Birth, Gender
                gv = _cell_to_str(r[col_gender]) if (col_gender is not None and col_gender < len(r)) else ""
                norm_g = _normalize_gender(gv)
                if norm_g: u.gender = norm_g
                
                # Date parsing logic
                bv = r[col_birth_date] if (col_birth_date is not None and col_birth_date < len(r)) else None
                if isinstance(bv, (datetime.date, datetime.datetime)): 
                    u.birth_date = bv
                elif isinstance(bv, str) and bv.strip():
                    for fmt in ["%m.%d.%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y.%m.%d"]:
                        try:
                            u.birth_date = datetime.datetime.strptime(bv.strip(), fmt).date()
                            break
                        except: continue

                # Chaqmoq (Only for students usually, but logic can stay)
                cv = _cell_to_str(r[col_chaqmoq]) if (col_chaqmoq is not None and col_chaqmoq < len(r)) else ""
                try:
                    ball = int(float(cv))
                    if ball != 0:
                        Ledger.objects.create(student=u, ball=ball, beruvchi=request.user, rule_nom="Excel Import")
                except: pass

                # Password
                pv = _cell_to_str(r[col_pass]) if (col_pass is not None and col_pass < len(r)) else ""
                final_p = pv if pv and pv != "***" else _gen_default_password()
                u.set_password(final_p)
                u.save()
                created += 1

        except Exception as e:
            skipped += 1
            problems.append(f"{r_i}-qator: {str(e)[:30]}")

    # Results
    messages.success(request, f"Import yakunlandi: {total_data_rows} ta qator topildi.")
    messages.info(request, f"📊 Natija: Yangi: {created}, O‘tkazib yuborildi: {skipped}")

    if skipped_names:
        names_text = ", ".join(skipped_names[:15])
        if len(skipped_names) > 15: names_text += f"... (+{len(skipped_names)-15} ta)"
        messages.warning(request, f"⚠️ Mavjud bo'lgani uchun tashlab ketildi: {names_text}")

    if problems:
        messages.error(request, f"⚠️ Xatolar: {' | '.join(problems[:5])}")

    return redirect(success_url)


    return redirect("core:stat_students")


@login_required
def students_download_template(request):
    """O‘quvchilarni import qilish uchun shablon Excel faylini yuklab beradi."""
    if not _staff_only(request):
        return HttpResponse("Ruxsat yo‘q", status=403)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Student Template"

    # Headers
    headers = [
        "Ism", "Familya", "Otchestvo", 
        "Telefon", "Telefon2", 
        "Tegulgankun", "Jinsi", 
        "Email", "Parol", "Chaqmoq"
    ]
    ws.append(headers)

    # Style headers
    header_font = Font(bold=True, color="FFFFFF")
    header_alignment = Alignment(horizontal="center", vertical="center")
    header_fill = openpyxl.styles.PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")

    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = header_font
        cell.alignment = header_alignment
        cell.fill = header_fill
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 18

    # Sample row
    ws.append([
        "Ali", "Valiyev", "G‘anisher o‘g‘li", 
        "+998901234567", "", 
        "2010.05.15", "erkak", 
        "ali123@gmail.com", "password123", "50"
    ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="chaqmoq_students_template.xlsx"'
    wb.save(response)
    return response


@login_required
def stat_users_export_excel(request):
    """
    Generic export for different user roles.
    """
    if not _staff_only(request):
        return HttpResponse("Ruxsat yo‘q", status=403)

    role = request.GET.get("role", "student")
    
    # Normalize role
    role_map = {
        "students": "student",
        "teachers": "teacher",
        "managers": "manager",
        "parents": "parent"
    }
    role = role_map.get(role, role)
    
    center = _get_center(request)
    if not center:
        return HttpResponse("Active center tanlanmagan", status=400)

    status = request.GET.get("status", "active").strip()
    rows = U.objects.filter(role=role, center=center)
    
    if status == "archived":
        rows = rows.filter(is_archived=True)
    else:
        rows = rows.filter(is_archived=False)
        
    rows = rows.order_by("id")
    
    if role == "student":
        rows = rows.annotate(jami_chaqmoq=Sum("ledger__ball"))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = role.capitalize() + "lar"

    # Define headers based on role
    if role == "student":
        headers = ["Ism", "Familya", "Otchestvo", "Telefon", "Telefon2", "Tug'ilgan sana", "Jinsi (male/female)", "Email", "Parol", "Chaqmoq"]
    else:
        # Teachers / Managers
        headers = ["Ism", "Familya", "Otchestvo", "Telefon", "Telefon2", "Tug'ilgan sana", "Email", "Parol"]
    
    ws.append(headers)

    # Style
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = openpyxl.styles.PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = header_font
        cell.fill = header_fill
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 20

    # Data
    for u in rows:
        if role == "student":
            ws.append([
                u.ism, u.familya, u.otchestvo or "", 
                u.telefon1 or "", u.telefon2 or "", 
                u.birth_date.strftime("%Y-%m-%d") if u.birth_date else "",
                u.gender or "", u.email, "***", u.jami_chaqmoq or 0
            ])
        else:
            ws.append([
                u.ism, u.familya, u.otchestvo or "", 
                u.telefon1 or "", u.telefon2 or "", 
                u.birth_date.strftime("%Y-%m-%d") if u.birth_date else "",
                u.email, "***"
            ])

    filename = f"{role.capitalize()}s_{center.name}"
    if status == "archived":
        filename += "_Arxiv"
    
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    wb.save(response)
    return response

@login_required
def users_download_template(request):
    """
    Generic template download with sample data.
    """
    role = request.GET.get("role", "student")
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Shablon"

    if role == "student":
        headers = ["Ism", "Familya", "Otchestvo", "Telefon", "Telefon2", "Tug'ilgan sana", "Jinsi (male/female)", "Email", "Parol"]
        sample = ["Amirxon", "O'rinbayev", "Temur o'g'li", "901234567", "", "2005-05-15", "male", "amirxon@gmail.com", "12345678"]
    else:
        # Teachers / Managers
        headers = ["Ism", "Familya", "Otchestvo", "Telefon", "Telefon2", "Tug'ilgan sana", "Email", "Parol"]
        sample = ["Amirxon", "O'rinbayev", "Vali o'g'li", "901234567", "", "2000-01-01", "amirxon@gmail.com", "12345678"]

    ws.append(headers)
    ws.append(sample)
    
    # Simple style
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = Font(bold=True)
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 25

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{role}_template.xlsx"'
    wb.save(response)
    return response

@login_required
@require_POST
def users_import_excel(request):
    """
    Generic import placeholder. For now, redirects to student import if role is student.
    In future, can be expanded for managers.
    """
    role = request.POST.get("role") or request.GET.get("role", "student")
    return _process_user_import(request, role=role)
    messages.warning(request, f"{role.capitalize()}lar uchun import hozircha mavjud emas.")
    return redirect(f"core:stat_{role}s" if role != "teacher" else "core:stat_teachers")


# =============================================================================
# PRODUCTS / REQUESTS / LEDGER (tenant scoped)
# =============================================================================

@login_required
def stat_products(request):
    if not _staff_only(request):
        return render(request, "core/dashboard_guest.html")

    center = _get_center(request)
    q = request.GET.get("q", "").strip()

    rows = Product.objects.all()
    rows = _try_center_filter(rows, center, ["center"]) if center else rows.none()

    # field names nom/izoh har xil bo'lishi mumkin
    if q:
        f1 = "nom__icontains" if _has_field(Product, "nom") else "name__icontains"
        f2 = "izoh__icontains" if _has_field(Product, "izoh") else "description__icontains"
        try:
            rows = rows.filter(Q(**{f1: q}) | Q(**{f2: q}))
        except Exception:
            rows = rows.filter(Q(id__isnull=False))  # no-op fallback

    order_field = "-yaratilgan" if _has_field(Product, "yaratilgan") else "-id"
    rows = rows.order_by(order_field)

    return render(request, "core/stats_products.html", {"title": "Mahsulotlar", "rows": rows})


@login_required
def stat_requests(request):
    if not _staff_only(request):
        return render(request, "core/dashboard_guest.html")

    center = _get_center(request)
    status = request.GET.get("status", "").strip()

    rows = PurchaseRequest.objects.select_related("student", "product", "manager")
    rows = _try_center_filter(rows, center, ["center", "student__center", "manager__center"]) if center else rows.none()

    if status in ("pending", "approved", "rejected"):
        rows = rows.filter(status=status)

    # ordering field sana/created_at
    if _has_field(PurchaseRequest, "sana"):
        rows = rows.order_by("-sana")
    elif _has_field(PurchaseRequest, "created_at"):
        rows = rows.order_by("-created_at")
    else:
        rows = rows.order_by("-id")

    return render(request, "core/stats_requests.html", {
        "title": "Kutilayotgan so‘rovlar",
        "rows": rows,
        "status": status
    })


@login_required
def stat_ledger(request):
    if not _staff_only(request):
        return render(request, "core/dashboard_guest.html")

    center = _get_center(request)

    ledger_qs = Ledger.objects.all()
    ledger_qs = _try_center_filter(ledger_qs, center, ["center", "student__center", "group__center"]) if center else ledger_qs.none()

    leaderboard = (ledger_qs
                   .values("student__id", "student__ism", "student__familya")
                   .annotate(jami=Sum("ball"))
                   .order_by("-jami"))

    last = ledger_qs.select_related("student", "rule", "group")

    if _has_field(Ledger, "sana"):
        last = last.order_by("-sana")[:50]
    elif _has_field(Ledger, "created_at"):
        last = last.order_by("-created_at")[:50]
    else:
        last = last.order_by("-id")[:50]

    jami = ledger_qs.aggregate(s=Sum("ball"))["s"] or 0

    return render(request, "core/stats_ledger.html", {
        "leaderboard": leaderboard,
        "last": last,
        "sum_all": jami
    })


# =============================================================================
# PROFILE
# =============================================================================

@login_required
def profile_view(request):
    user = request.user

    pform = ProfileForm(instance=user)
    pass_form = PasswordChangeForm(user=user)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "profile":
            pform = ProfileForm(request.POST, request.FILES, instance=user)
            if pform.is_valid():
                pform.save()
                messages.success(request, "✅ Profil yangilandi")
                return redirect("core:profile")
            else:
                messages.error(request, "❌ Profilni saqlashda xatolik bor")

        elif action == "password":
            pass_form = PasswordChangeForm(user=user, data=request.POST)
            if pass_form.is_valid():
                u = pass_form.save()
                update_session_auth_hash(request, u)
                messages.success(request, "✅ Parol yangilandi")
                return redirect("core:profile")
            else:
                messages.error(request, "❌ Parolni o‘zgartirishda xatolik bor")

    return render(request, "core/profile_manager.html", {
        "pform": pform,
        "pass_form": pass_form,
    })
