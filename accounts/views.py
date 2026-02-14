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
    
    # ✅ Optimized Queryset
    centers = Center.objects.filter(is_deleted=False).select_related(
        'subscription', 'subscription__plan'
    ).prefetch_related(
        Prefetch('user_set', queryset=User.objects.filter(role='director'), to_attr='directors')
    ).annotate(
        student_count=Count('user', filter=Q(user__role='student', user__is_archived=False), distinct=True)
    )
    
    if q:
        centers = centers.filter(Q(name__icontains=q) | Q(address__icontains=q))
    
    if status:
        centers = centers.filter(status=status)

    centers = centers.order_by("-id") # Newest first is usually better for admin

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
    Switch to a specific center. Construct subdomain URL.
    """
    if not _superadmin_only(request):
        return HttpResponseForbidden("Forbidden")

    center_id = request.POST.get("center_id") or request.GET.get("center_id")
    if not center_id:
        messages.error(request, "Center tanlanmadi.")
        return redirect("accounts:center_picker")

    if center_id == "NONE":
        if "active_center_id" in request.session:
            del request.session["active_center_id"]
        # Redirect to root platform
        return redirect("http://localhost:8000/platform/")

    center = Center.objects.filter(id=center_id).first()
    if not center:
        messages.error(request, "Center topilmadi.")
        return redirect("accounts:center_picker")
    
    if center.status != "ACTIVE":
         messages.error(request, f"Bu markaz faol emas (Status: {center.status}). Iltimos avval uni faollashtiring.")
         return redirect("accounts:center_picker")

    # Set session so we know we are in "switch" mode even if subdomain fails or for auth
    request.session["active_center_id"] = int(center.id)
    request.session.modified = True
    
    # Construct subdomain URL
    # Use request.get_host() to get the current domain (e.g. localhost:8000 or proskill.chaqmoq.uz)
    host_port = request.get_host() # e.g. "localhost:8000"
    host = host_port.split(':')[0]
    
    port_suffix = ""
    if ':' in host_port:
        port_suffix = f":{host_port.split(':')[1]}"
    
    # Check if we are on Render or Custom Domain
    if "onrender.com" in host:
        # If using Render's default domain, we might need a different strategy 
        # because wildcards *.onrender.com are not free usually.
        # But if you have custom domain mapped:
        root_domain = host # Default assumption if no dots found
        parts = host.split('.')
        
        # If tenant.app.onrender.com (4 parts) -> Root is app.onrender.com
        # If app.onrender.com (3 parts) -> Root is app.onrender.com
        if len(parts) >= 3:
             # Basic heuristic: Main app is always the root
             # If we are already on a subdomain, strip it? 
             # Simplify: Just assume the base domain is the ROOT_DOMAIN or current host structure
             pass
        
        # PROD FIX: If on Render, usually stick to session-based logical separation 
        # optimized for single-domain if wildcard not available.
        # However, user requested subdomain.
        
        # If strict subdomain is requested, we assume we have a wildcard DNS.
        # Let's try to strip existing subdomain if present.
        # center.slug + "." + base_domain
        
        # Determine Base Domain
        # If "proskill-chaqmoq.onrender.com" is the main, and we want "tenant.proskill-chaqmoq.onrender.com"
        # Render doesn't support nested subdomains easily on free tier.
        
        # BETTER STRATEGY FOR RENDER (Free): 
        # Redirect to Root + Session (which we already set above)
        # But if Custom Domain is active (chaqmoq.uz), build "proskill.chaqmoq.uz"
        
        if "chaqmoq.uz" in host:
             base = "chaqmoq.uz"
             target_url = f"https://{center.slug}.{base}/"
        else:
             # Just reload to root, middleware uses session
             target_url = f"https://{host}/"
             
    elif "localhost" in host or host == "127.0.0.1":
        # Localhost logic - Support Port
        # Strip existing subdomain if any (e.g. oldtenant.localhost -> localhost)
        parts = host.split('.')
        if len(parts) > 1 and "localhost" in parts[-1]:
             base = ".".join(parts[1:]) # localhost
        else:
             base = host # localhost
        
        target_url = f"http://{center.slug}.{base}{port_suffix}/"
        
    else:
        # Fallback for custom domains
        # e.g. example.com
        # Strip potential existing subdomain
        parts = host.split('.')
        if len(parts) > 2:
             base = ".".join(parts[1:])
        else:
             base = host
        target_url = f"http://{center.slug}.{base}{port_suffix}/"
        if request.is_secure():
             target_url = target_url.replace("http://", "https://")

    messages.success(request, f"✅ Markazga o'tildi: {center.name}")
    return redirect(target_url)


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
