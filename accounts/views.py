# accounts/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import get_user_model, logout
from django.views.decorators.http import require_http_methods
from django import forms
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from .forms import AddUserForm, TeacherForm
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

def is_superadmin(user):
    return user.is_authenticated and user.is_superuser


@login_required
def center_picker(request):
    if not _superadmin_only(request):
        return HttpResponseForbidden("Forbidden")

    # Filters
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    
    centers = Center.objects.filter(is_deleted=False)
    
    if q:
        centers = centers.filter(Q(name__icontains=q) | Q(address__icontains=q))
    
    if status:
        centers = centers.filter(status=status)

    centers = centers.order_by("name")
    
    # ✅ Exclude user's own attached center (Asosiy markaz) if requested
    if request.user.center:
        centers = centers.exclude(id=request.user.center.id)

    active_center_id = request.session.get("active_center_id")

    # Fetch dynamic plans
    db_plans = SubscriptionPlan.objects.filter(active=True).order_by("monthly_price")

    return render(request, "accounts/center_picker.html", {
        "centers": centers,
        "active_center_id": active_center_id,
        "plans": Center.Plan.choices, # Keep for backward compatibility if needed, or remove
        "db_plans": db_plans,         # New dynamic list
        "statuses": Center.STATUS_CHOICES,
        "selected_status": status,
    })

@login_required
@require_http_methods(["GET", "POST"])
def center_switch(request):
    """
    ✅ POST asosiy (CSRF bilan).
    ✅ Admin listdan link bilan switch qilish uchun GET ham ruxsat (faqat superadmin).
    """
    if not _superadmin_only(request):
        return HttpResponseForbidden("Forbidden")

    center_id = request.POST.get("center_id") or request.GET.get("center_id")
    next_url = request.POST.get("next") or request.GET.get("next") or "/"

    if not center_id:
        messages.error(request, "Center tanlanmadi.")
        return redirect("accounts:center_picker")

    if center_id == "NONE":
        if "active_center_id" in request.session:
            del request.session["active_center_id"]
        messages.info(request, "Markaz tanlanmadi (Global).")
        return redirect("/")

    center = Center.objects.filter(id=center_id).first()
    if not center:
        messages.error(request, "Center topilmadi.")
        return redirect("accounts:center_picker")
    
    if center.status != "ACTIVE":
         messages.error(request, f"Bu markaz faol emas (Status: {center.status}). Iltimos avval uni faollashtiring.")
         return redirect("accounts:center_picker")

    request.session["active_center_id"] = int(center.id)
    request.session.modified = True
    messages.success(request, f"✅ Active center: {center.name}")

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
                messages.error(request, "Bu email allaqachon mavjud.")
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

    # ✅ Center ni aniqlaymiz (Robust method)
    center = get_request_center(request)
    
    # ✅ Guruhlarni filtrlaymiz
    if center:
        # Markaz xodimi: Faqat o'z markazi guruhlari
        groups = Group.objects.filter(center=center).order_by("nom")
    elif request.user.is_superuser:
        # Superadmin (Global mode): Hamma guruhlar (bu asosiyda chiqmaslik muammosini hal qiladi)
        groups = Group.objects.all().order_by("nom")
    else:
        groups = Group.objects.none()

    form = AddUserForm(request.POST or None, request=request)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        
        # ✅ Agar markaz tanlangan bo'lsa (yoki subdomen/sessionda bo'lsa) - o'shani o'rnatamiz
        if center:
            user.center = center
        
        # ✅ Manager/Director bo'lsa staff=True
        if user.role in ("manager", "director"):
            user.is_staff = True
            
        user.save()
        
        # ✅ Guruhga biriktirish (Enrollment)
        group_id = request.POST.get("group_id")
        if user.role == "student" and group_id:
            try:
                # Superadmin hamma guruhni ko'ra oladi, Manager esa faqat o'zinikini
                if center:
                    target_group = Group.objects.get(id=group_id, center=center)
                else:
                    target_group = Group.objects.get(id=group_id)
                
                # Agar superadmin bo'lsa va center hali set qilinmagan bo'lsa (global mode)
                # user.center ni guruhni centeriga moslaymiz
                if not user.center:
                    user.center = target_group.center
                    user.save(update_fields=['center'])

                Enrollment.objects.get_or_create(
                    group=target_group, 
                    student=user,
                    defaults={
                        'kurs_narhi': target_group.kurs_narxi,
                        'oqituvchi_foiz': target_group.oqituvchi_foiz,
                        'center': target_group.center
                    }
                )
            except Exception as e:
                import logging
                logging.error(f"Enrollment error in add_user: {e}")

        messages.success(request, f"✅ Foydalanuvchi {user.email} muvaffaqiyatli qo‘shildi.")
        return redirect("core:home")

    return render(request, "accounts/user_form.html", {
        'form': form,
        'groups': groups,
        'title': "Yangi foydalanuvchi"
    })

@login_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    # Basic permission check
    if not _is_staff_like(request.user) and request.user != user:
        return HttpResponseForbidden()

    # Simple edit logic or pass
    # Assuming incomplete previously
    if request.method == "POST":
        # Implementation depends on form usage
        pass
    
    return render(request, "accounts/user_edit.html", {"user": user})

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
    return render(request, "accounts/student_detail.html", {'student': student})

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
