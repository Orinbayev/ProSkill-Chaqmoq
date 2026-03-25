# accounts/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import get_user_model, logout
from django.views.decorators.http import require_http_methods
from django import forms
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from .forms import AddUserForm, TeacherForm, ProfileEditForm, PasswordUpdateForm
from accounts.models import User, Center
from education.models import Group, Enrollment, Attendance
from core.tenant import get_request_center
from django.db.models import Q


U = get_user_model()

# --- ruxsat yordamchilari ---

def _can_add(u):
    return u.is_superuser or getattr(u, "role", None) in ("director", "manager")

def _is_staff_like(u):
    return u.is_superuser or getattr(u, "role", None) in ("director", "manager")


def _superadmin_only(request):
    return request.user.is_authenticated and request.user.is_superuser


# accounts/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from accounts.models import Center
from django.http import HttpResponseForbidden
from billing.models import SubscriptionPlan
from django.db.models import Count, Q, Prefetch
from accounts.models import User

def is_superadmin(user):
    return user.is_authenticated and user.is_superuser

@login_required
def center_picker(request):
    if not _superadmin_only(request):
        return HttpResponseForbidden("Forbidden")

    # Filters
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    
    # ✅ Optimized Queryset: Load needed fields only
    centers = Center.objects.filter(is_deleted=False).prefetch_related(
        'subscriptions__plan',
        Prefetch('user_set', queryset=User.objects.filter(role='director'), to_attr='directors')
    ).annotate(
        # Standard student count annotation
        student_count=Count('user', filter=Q(user__role='student', user__is_archived=False), distinct=True)
    ).order_by("-id")

    if q:
        centers = centers.filter(Q(name__icontains=q) | Q(address__icontains=q))
    if status:
        centers = centers.filter(status=status)

    # ✅ PLAN LOGIC FOR ONBOARDING
    # Fetch active plans, ordered by monthly_price
    # If multiple have same name, take the latest active version (by ID desc)
    # Using python dict to dedup by title/code if needed
    
    all_active_plans = SubscriptionPlan.objects.filter(active=True).order_by('monthly_price')
    deduped_plans = {}
    
    for p in all_active_plans:
        # Key by code or title (assuming code is unique per version?)
        # Requirement: "Show latest active version".
        # If code is same, model field 'code' is unique=True anyway.
        # So deduplication is implicitly handled by unique constraint on code.
        # But if user meant "Standard v2" replaces "Standard v1" with different codes...
        # Let's assume title-based grouping if codes differ.
        if p.title not in deduped_plans:
             deduped_plans[p.title] = p
        else:
             # Already have one? Prefer higher price/newer id?
             # View logic says: "latest active version".
             # Actually, if code is unique, maybe we just list all unique codes.
             # The user requirement: "Duplicate ko'rinmasin".
             # Assuming uniqueness by Title is the goal:
             existing = deduped_plans[p.title]
             if p.id > existing.id:
                 deduped_plans[p.title] = p

    final_plans = sorted(deduped_plans.values(), key=lambda x: x.monthly_price)
    
    # Serialize plans for JS
    import json
    plans_data = []
    for p in final_plans:
        plans_data.append({
            "id": p.id, 
            "code": p.code, 
            "title": p.title, 
            "monthly_price": p.monthly_price, 
            "max_students": p.max_students,
            "max_users": p.max_users,
            "max_groups": p.max_groups,
            "is_popular": p.is_popular,
            "discount_percent": p.discount_percent,
            "features": p.features
        })
    plans_json = json.dumps(plans_data)

    return render(request, "accounts/center_picker.html", {
        "centers": centers,
        "active_center_id": request.session.get("active_center_id"),
        "plans": final_plans,         # Still passed for potential template use
        "plans_json": plans_json,     # Passed for JS
        "statuses": Center.STATUS_CHOICES,
        "selected_status": status,
        "search_q": q,
    })

from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
import logging

logger = logging.getLogger(__name__)

@login_required
@require_http_methods(["GET", "POST"])
def center_switch(request):
    if not _superadmin_only(request):
        return HttpResponseForbidden("Forbidden")

    # 🔥 GET + POST ikkalasidan ham olish
    center_id = request.POST.get("center_id") or request.GET.get("center_id")
    next_url = request.POST.get("next") or request.GET.get("next") or "/"

    # 🔥 XAVFSIZLIK
    if not next_url.startswith("/"):
        next_url = "/"

    if not center_id:
        messages.error(request, "Center tanlanmadi.")
        return redirect("/")

    if center_id == "NONE":
        request.session.pop("active_center_id", None)
        logger.info("Center switch: NONE selected, session cleared.")
        return redirect(next_url)

    center = Center.objects.filter(id=center_id).first()

    if not center:
        messages.error(request, "Center topilmadi.")
        return redirect("/")

    if center.status != "ACTIVE":
        messages.error(request, f"Bu markaz faol emas (Status: {center.status})")
        return redirect("/")

    # 🔥 ENG MUHIM
    request.session["active_center_id"] = int(center.id)
    request.session.modified = True

    logger.info(f"Center switch OK: {center.id}")

    return redirect(next_url)

@login_required
@require_http_methods(["GET", "POST"])
def center_manage(request, pk: int):
    """
    Superadmin uchun:
    - Center haqida info
    - Director biriktirish (existing)
    - Director yaratish (new)
    """
    if not _superadmin_only(request):
        return HttpResponseForbidden("Forbidden")

    center = get_object_or_404(Center, pk=pk)

    # Mavjud director/managerlar (shu centerga biriktirilgan)
    staff = User.objects.filter(center=center, role__in=["director", "manager"]).order_by("role", "id")

    # Existing directorlarni tanlash uchun:
    # - role=director bo‘lganlar
    # - xohlasangiz: center=None bo‘lganlarni chiqarish mumkin, lekin amalda hammasini chiqaramiz
    all_directors = (
        User.objects
        .filter(role__in=["director", "manager"])
        .filter(Q(center__isnull=True) | Q(center=center))   # ✅ boshqa center’dan “o‘g‘irlab” bo‘lmaydi
        .order_by("role", "id")
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "assign_existing":
            user_id = request.POST.get("director_id") or request.POST.get("user_id")
            if not user_id:
                messages.error(request, "Director tanlanmadi.")
                return redirect("accounts:center_manage", pk=center.id)

            u = User.objects.filter(id=user_id, role__in=["director", "manager"]).first()
            if not u:
                messages.error(request, "Director topilmadi.")
                return redirect("accounts:center_manage", pk=center.id)

            u.center = center
            u.save(update_fields=["center"])
            messages.success(request, f"✅ Director biriktirildi: {getattr(u, 'email', u.id)}")
            return redirect("accounts:center_manage", pk=center.id)

        if action == "create_new":
            email = (request.POST.get("email") or "").strip().lower()
            password = (request.POST.get("password") or "").strip()
            ism = (request.POST.get("ism") or "").strip()
            familya = (request.POST.get("familya") or "").strip()

            if not email or not password:
                messages.error(request, "Email va parol talab qilinadi.")
                return redirect("accounts:center_manage", pk=center.id)

            if User.objects.filter(email=email).exists():
                messages.error(request, "Bu email allaqon mavjud.")
                return redirect("accounts:center_manage", pk=center.id)

            u = User.objects.create_user(
                email=email,
                password=password,
                role="director",
                ism=ism,
                familya=familya,
                center=center,
                is_staff=True  # Director bo'lsa staff bo'lishi kerak
            )
            messages.success(request, f"✅ Yangi director yaratildi: {email}")
            return redirect("accounts:center_manage", pk=center.id)

        if action == "edit_director":
            user_id = request.POST.get("user_id")
            email = (request.POST.get("email") or "").strip().lower()
            password = (request.POST.get("password") or "").strip()
            ism = (request.POST.get("ism") or "").strip()
            familya = (request.POST.get("familya") or "").strip()
            
            u = User.objects.filter(id=user_id, center=center, role__in=["director", "manager"]).first()
            if not u:
                messages.error(request, "Xodim topilmadi.")
                return redirect("accounts:center_manage", pk=center.id)
                
            if email and email != u.email:
                if User.objects.filter(email=email).exclude(id=u.id).exists():
                    messages.error(request, "Bu email allaqachon boshqa xodimda mavjud.")
                    return redirect("accounts:center_manage", pk=center.id)
                u.email = email
            
            u.ism = ism
            u.familya = familya
            
            if password:
                u.set_password(password)
                
            u.save()
            messages.success(request, f"✅ Xodim ma'lumotlari yangilandi: {u.email}")
            return redirect("accounts:center_manage", pk=center.id)

    return render(request, "accounts/center_manage.html", {
        "center": center,
        "staff": staff,
        "all_directors": all_directors,
    })


@login_required
@require_http_methods(["POST"])
def center_remove_staff(request, pk: int):
    if not _superadmin_only(request):
        return HttpResponseForbidden("Forbidden")
    
    center = get_object_or_404(Center, pk=pk)
    user_id = request.POST.get("user_id")
    u = get_object_or_404(User, id=user_id, center=center)

    u.center = None
    u.save(update_fields=["center"])
    messages.success(request, f"✅ Hodim {u.email} centerdan uzildi.")
    return redirect("accounts:center_manage", pk=center.id)

# --- Missing Views Restored ---

@login_required
def add_user(request):
    if not _can_add(request.user):
        return HttpResponseForbidden("Ruxsat yo'q.")

    form = AddUserForm(request.POST or None, request=request)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"✅ Foydalanuvchi {user.email} muvaffaqiyatli qo‘shildi.")
        return redirect("core:home")

    return render(request, "accounts/user_form.html", {
        'form': form,
        'title': "Yangi foydalanuvchi"
    })

@login_required
def user_edit(request, pk=None):
    if pk is None:
        user = request.user
    else:
        user = get_object_or_404(User, pk=pk)
    
    # Basic permission check
    if not _is_staff_like(request.user) and request.user != user:
        return HttpResponseForbidden()

    # Form handling
    profile_form = ProfileEditForm(request.POST or None, request.FILES or None, instance=user)
    password_form = PasswordUpdateForm(request.POST or None)

    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "update_profile":
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profil ma'lumotlari yangilandi. ✅")
                return redirect("accounts:profile")
        
        elif action == "update_password":
            if password_form.is_valid():
                user.set_password(password_form.cleaned_data["new_password"])
                user.save()
                messages.success(request, "Parol muvaffaqiyatli yangilandi. 🔒")
                return redirect("accounts:profile")

    return render(request, "accounts/user_edit.html", {
        "user_obj": user, # Renamed to user_obj to avoid conflict with request.user if needed
        "profile_form": profile_form,
        "password_form": password_form,
    })

@login_required
def delete_user(request, pk):
    if not _can_add(request.user):
         return HttpResponseForbidden()
    
    user = get_object_or_404(User, pk=pk)
    # Check if user belongs to same center if not superuser
    if not request.user.is_superuser and user.center != request.center:
        return HttpResponseForbidden()

    user.delete()
    messages.success(request, "O‘chirildi.")
    return redirect("core:home")

@login_required
def teacher_detail(request, user_id):
    teacher = get_object_or_404(User, id=user_id, role='teacher')
    return render(request, "accounts/teacher_detail.html", {'teacher': teacher})

@login_required
def student_detail(request, user_id):
    student = get_object_or_404(User, id=user_id, role='student')
    # Eski student_detail sahifasi o'rniga yagona premium student profiliga yo'naltiramiz.
    return redirect("core:user_view", pk=student.id)

@login_required
def logout_view(request):
    logout(request)
    return redirect("login")

def logout_now(request):
    from django.contrib.auth import logout
    from django.conf import settings
    logout(request)
    try:
        request.session.flush()
    except:
        pass
    
    response = redirect("login")
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    return response

@login_required
def center_stats_view(request, pk):
    if not _superadmin_only(request):
        return HttpResponseForbidden()
    center = get_object_or_404(Center, pk=pk)
    return render(request, "accounts/center_stats.html", {'center': center})

from django.http import HttpResponse
from django.db import connection
from core.tenant_context import get_current_tenant

def test_db(request):
    return HttpResponse(f"DB: {connection.alias}")


def test_center(request):
    tenant = get_current_tenant()
    return HttpResponse(f"Tenant: {tenant}")
