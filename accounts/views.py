# accounts/views.py
import json
import logging
import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import get_user_model, logout
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from django import forms
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.template.loader import render_to_string
from django.utils.text import slugify

from .duplicate_checks import serialize_student_duplicate_check
from .forms import AddUserForm, TeacherForm, ProfileEditForm, PasswordUpdateForm
from accounts.models import BranchRequest, Center, DirectorCenterAccess, User
from education.models import Group, Enrollment, Attendance
from core.tenant import get_request_center
from django.db.models import Q


U = get_user_model()

# --- ruxsat yordamchilari ---

def _can_add(u):
    return u.is_superuser or getattr(u, "role", None) in ("director", "manager")


def _can_add_student(request) -> bool:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    center = get_request_center(request) or getattr(user, "center", None)
    role = getattr(user, "role", None)
    if role == "director":
        return True
    if role == "manager":
        return bool(center and center.manager_can_add_student)

    if role == "teacher":
        return bool(center and center.teacher_can_add_student)

    return False


def _is_staff_like(u):
    return u.is_superuser or getattr(u, "role", None) in ("director", "manager")


def _safe_next_url(value: str | None) -> str | None:
    value = (value or "").strip()
    return value if value.startswith("/") else None


def _normalize_role_value(value: str | None) -> str:
    value = (value or "").strip().lower()
    return "student" if value == "students" else value


def _is_user_drawer_request(request) -> bool:
    return request.GET.get("drawer") == "1"


def _is_role_switch_drawer_request(request) -> bool:
    return _is_user_drawer_request(request) and request.GET.get("role_switch") == "1"


def _get_allowed_add_roles(request) -> list[str]:
    ordered_roles = ["director", "manager", "teacher", "student", "parent"]
    allowed = []

    if _can_add(getattr(request, "user", None)):
        allowed.extend(ordered_roles)
    elif _can_add_student(request):
        allowed.append("student")

    result = []
    seen = set()
    for role in allowed:
        if role in seen:
            continue
        seen.add(role)
        result.append(role)
    return result


def _generate_user_email(ism: str, familya: str) -> str:
    first = slugify(ism or "").replace("-", "") or "u"
    last = slugify(familya or "").replace("-", "") or "student"
    prefix = f"{first[:1]}.{last[:10]}"
    for _ in range(40):
        candidate = f"{prefix}{random.randint(100, 999)}@gmail.com"
        if not User._base_manager.filter(email=candidate).exists():
            return candidate
    return f"{prefix}{random.randint(1000, 9999)}@gmail.com"


def _generate_user_password() -> str:
    return str(random.randint(10000000, 99999999))


def _render_student_drawer_form(
    request,
    *,
    form,
    student_limit_state,
    next_url,
    drawer_center_value,
):
    return render_to_string(
        "accounts/partials/student_drawer_form.html",
        {
            "form": form,
            "student_limit_state": student_limit_state,
            "next_url": next_url,
            "drawer_center_value": drawer_center_value,
        },
        request=request,
    )


def _render_user_drawer_form(
    request,
    *,
    form,
    student_limit_state,
    next_url,
    drawer_center_value,
    current_role,
    allow_role_switch,
    available_roles,
):
    return render_to_string(
        "accounts/partials/user_drawer_form.html",
        {
            "form": form,
            "student_limit_state": student_limit_state,
            "next_url": next_url,
            "drawer_center_value": drawer_center_value,
            "current_role": current_role,
            "allow_role_switch": allow_role_switch,
            "available_roles": available_roles,
        },
        request=request,
    )


def _superadmin_only(request):
    return request.user.is_authenticated and request.user.is_superuser


# accounts/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from accounts.models import Center
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
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods

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


def _send_branch_request_to_telegram(branch_request: BranchRequest) -> str | None:
    """BranchRequest ni Telegram admin guruhiga yuboradi. Message ID qaytaradi."""
    from html import escape

    import requests
    from django.conf import settings
    from django.utils import timezone

    token = str(getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    chat_id = str(getattr(settings, "TELEGRAM_GROUP_ID", "") or "").strip()
    if not token or not chat_id:
        logger.warning("Telegram config yo'q, branch request yuborilmadi")
        return None

    created_at = timezone.localtime(branch_request.created_at).strftime("%d.%m.%Y %H:%M")
    requester_name = escape(branch_request.requester.get_full_name() or branch_request.requester.email)
    parent_center_name = escape(branch_request.parent_center.name)
    center_name = escape(branch_request.name)
    center_address = escape(branch_request.address or "—")
    center_phone = escape(branch_request.phone or "—")

    payload = {
        "chat_id": chat_id,
        "text": (
            f"🏢 <b>YANGI FILIAL SO'ROVI</b> #{branch_request.id}\n\n"
            f"👤 Direktor: {requester_name}\n"
            f"🏫 Asosiy markaz: {parent_center_name}\n\n"
            f"📋 <b>Yangi markaz ma'lumotlari:</b>\n"
            f"• Nomi: <code>{center_name}</code>\n"
            f"• Manzil: {center_address}\n"
            f"• Telefon: {center_phone}\n\n"
            f"⏰ Vaqt: {created_at}\n\n"
            "Quyidagi tugmalardan birini bosing:"
        ),
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "✅ Tasdiqlash", "callback_data": f"branch_approve:{branch_request.id}"},
                {"text": "❌ Rad etish", "callback_data": f"branch_reject:{branch_request.id}"},
            ]]
        },
    }

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=10,
        )
        data = response.json()
        if data.get("ok"):
            return str(data["result"]["message_id"])
        logger.warning("Branch request Telegram yuborilmadi: %s", data)
    except Exception:
        logger.exception("Branch request Telegram send error")
    return None


def _notify_branch_deactivated(center, actor) -> None:
    """Filial bloklanganligi haqida Telegram admin guruhiga xabar yuboradi."""
    from html import escape
    import requests
    from django.conf import settings
    from django.utils import timezone

    token   = str(getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    chat_id = str(getattr(settings, "TELEGRAM_GROUP_ID", "") or "").strip()
    if not token or not chat_id:
        return

    parent_name  = escape(center.parent_center.name if center.parent_center else "—")
    branch_name  = escape(center.name)
    actor_name   = escape(actor.get_full_name() or actor.email)
    now          = timezone.localtime(timezone.now()).strftime("%d.%m.%Y %H:%M")

    text = (
        "🔒 <b>FILIAL BLOKLANDI</b>\n\n"
        f"📌 Filial: <b>{branch_name}</b>\n"
        f"🏢 Asosiy markaz: {parent_name}\n"
        f"👤 Kim blokladi: {actor_name}\n"
        f"⏰ Vaqt: {now}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=8,
        )
    except Exception:
        logger.exception("Branch deactivated Telegram notify failed")


@login_required
def director_my_centers(request):
    """Director uchun: o'z markazlari ro'yxati (JSON)."""
    user = request.user
    if not (user.is_superuser or getattr(user, "role", None) == "director"):
        return JsonResponse({"ok": False, "error": "Ruxsat yo'q"}, status=403)

    current_center = getattr(request, "center", None) or getattr(user, "center", None)

    def _center_dict(center, is_primary):
        parent = center.parent_center
        return {
            "id": center.id,
            "name": center.name,
            "slug": center.slug,
            "address": center.address or "",
            "phone": center.phone or "",
            "is_current": bool(current_center and current_center.id == center.id),
            "is_primary": is_primary,
            "is_branch": parent is not None,
            "parent_center_id": parent.id if parent else None,
            "parent_center_name": parent.name if parent else None,
        }

    centers: list[dict] = []
    if user.center_id:
        own_center = Center.objects.select_related("parent_center").filter(
            pk=user.center_id, is_deleted=False
        ).first()
        if own_center:
            centers.append(_center_dict(own_center, is_primary=True))

    extra_accesses = (
        DirectorCenterAccess.objects
        .filter(director=user, is_active=True, center__is_deleted=False)
        .select_related("center", "center__parent_center")
    )
    for access in extra_accesses:
        center = access.center
        if any(item["id"] == center.id for item in centers):
            continue
        centers.append(_center_dict(center, is_primary=False))

    pending_requests = list(
        BranchRequest.objects
        .filter(requester=user, status=BranchRequest.Status.PENDING)
        .values("id", "name", "address", "phone", "created_at")
    )

    return JsonResponse({
        "ok": True,
        "centers": centers,
        "current_id": current_center.id if current_center else None,
        "pending_requests": pending_requests,
    })


@login_required
def director_switch_center(request):
    """Director o'ziga tegishli boshqa markazga o'tadi."""
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)

    user = request.user
    if not (user.is_superuser or getattr(user, "role", None) == "director"):
        return JsonResponse({"ok": False, "error": "Ruxsat yo'q"}, status=403)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Yaroqsiz JSON"}, status=400)

    center_id = data.get("center_id")
    if not center_id:
        return JsonResponse({"ok": False, "error": "center_id kiritilmagan"}, status=400)

    try:
        center_id = int(center_id)
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "center_id noto'g'ri"}, status=400)

    is_primary = bool(user.center and user.center.id == center_id)
    has_access = user.is_superuser or is_primary or DirectorCenterAccess.objects.filter(
        director=user,
        center_id=center_id,
        is_active=True,
    ).exists()
    if not has_access:
        return JsonResponse({"ok": False, "error": "Bu markazga ruxsat yo'q"}, status=403)

    center = Center.objects.filter(pk=center_id, is_deleted=False).first()
    if not center:
        return JsonResponse({"ok": False, "error": "Markaz topilmadi"}, status=404)

    request.session["active_center_id"] = center_id
    request.session.modified = True

    return JsonResponse({
        "ok": True,
        "center_id": center_id,
        "center_name": center.name,
        "center_slug": center.slug,
        "redirect_url": f"/{center.slug}{reverse('core:director_boshqaruv')}",
    })


@login_required
def director_branch_request(request):
    """Director yangi markaz ochish so'rovini yuboradi."""
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)

    user = request.user
    if not (user.is_superuser or getattr(user, "role", None) == "director"):
        return JsonResponse({"ok": False, "error": "Faqat direktor"}, status=403)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Yaroqsiz JSON"}, status=400)

    name = (data.get("name") or "").strip()
    address = (data.get("address") or "").strip()
    phone = (data.get("phone") or "").strip()

    if not name:
        return JsonResponse({"ok": False, "error": "Markaz nomi kiritilmagan"}, status=400)
    if len(name) < 3:
        return JsonResponse({"ok": False, "error": "Markaz nomi juda qisqa (min 3 harf)"}, status=400)

    current_center = getattr(request, "center", None) or getattr(user, "center", None)
    if not current_center:
        return JsonResponse({"ok": False, "error": "Asosiy markaz aniqlanmadi"}, status=400)

    # Root (asosiy) markazni aniqlaymiz — limit tekshiruvi shu yerda
    root_center = current_center.get_root_center()

    # Tarif limiti tekshiruvi
    try:
        from billing.services import can_add_branch
        ok, reason = can_add_branch(root_center)
        if not ok:
            return JsonResponse({"ok": False, "error": reason}, status=400)
    except Exception:
        pass  # Tekshiruv ishlamasa ham davom etamiz

    pending_count = BranchRequest.objects.filter(
        requester=user,
        status=BranchRequest.Status.PENDING,
    ).count()
    if pending_count >= 3:
        return JsonResponse({
            "ok": False,
            "error": "Maksimum 3 ta kutilayotgan so'rov bo'lishi mumkin",
        }, status=400)

    branch_request = BranchRequest.objects.create(
        requester=user,
        parent_center=root_center,  # Har doim root center ga bog'laymiz
        name=name,
        address=address,
        phone=phone,
        status=BranchRequest.Status.PENDING,
    )

    message_id = _send_branch_request_to_telegram(branch_request)
    if message_id:
        branch_request.telegram_message_id = str(message_id)
        branch_request.save(update_fields=["telegram_message_id"])

    return JsonResponse({
        "ok": True,
        "request_id": branch_request.id,
        "message": "So'rovingiz adminga yuborildi. Tasdiqlangandan keyin yangi markaz ochiladi.",
    })


@login_required
@require_http_methods(["POST"])
def director_branch_edit(request, center_id: int):
    """Director o'z filialini tahrirlaydi (faqat nom, manzil, telefon)."""
    user = request.user
    if not (user.is_superuser or getattr(user, "role", None) == "director"):
        return JsonResponse({"ok": False, "error": "Faqat direktor"}, status=403)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON xato"}, status=400)

    # Markazni topamiz va direktorning ruxsatini tekshiramiz
    try:
        center = Center.objects.select_related("parent_center").get(pk=center_id, is_deleted=False)
    except Center.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Markaz topilmadi"}, status=404)

    # Ruxsatni tekshirish:
    # 1) DirectorCenterAccess orqali (bot orqali qo'shilgan filiallar)
    # 2) user.center orqali (superadmin yaratib bergan filiallar)
    has_access = (
        DirectorCenterAccess.objects.filter(director=user, center=center, is_active=True).exists()
        or (getattr(user, "center_id", None) == center_id)
    )
    if not has_access:
        return JsonResponse({"ok": False, "error": "Ruxsat yo'q"}, status=403)

    if not center.parent_center_id:
        return JsonResponse({"ok": False, "error": "Faqat filiallarni tahrirlash mumkin"}, status=400)

    name = (data.get("name") or "").strip()
    if not name or len(name) < 3:
        return JsonResponse({"ok": False, "error": "Nom kamida 3 ta harf bo'lishi kerak"}, status=400)

    center.name = name
    center.address = (data.get("address") or "").strip()
    center.phone = (data.get("phone") or "").strip()
    center.save(update_fields=["name", "address", "phone"])

    return JsonResponse({
        "ok": True,
        "center": {
            "id": center.id,
            "name": center.name,
            "address": center.address,
            "phone": center.phone,
        },
    })


@login_required
@require_http_methods(["POST"])
def director_branch_deactivate(request, center_id: int):
    """Director o'z filialini deaktivatsiya qiladi (soft-block)."""
    user = request.user
    if not (user.is_superuser or getattr(user, "role", None) == "director"):
        return JsonResponse({"ok": False, "error": "Faqat direktor"}, status=403)

    try:
        center = Center.objects.get(pk=center_id, is_deleted=False)
    except Center.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Markaz topilmadi"}, status=404)

    # Ruxsatni tekshirish
    has_access = (
        DirectorCenterAccess.objects.filter(director=user, center=center, is_active=True).exists()
        or (getattr(user, "center_id", None) == center_id)
    )
    if not has_access:
        return JsonResponse({"ok": False, "error": "Ruxsat yo'q"}, status=403)

    if not center.parent_center_id:
        return JsonResponse({"ok": False, "error": "Asosiy markazni o'chirib bo'lmaydi"}, status=400)

    # Soft-block: filialni bloklash (ma'lumotlar saqlanadi)
    center.status = Center.STATUS_BLOCKED
    center.save(update_fields=["status"])

    # Barcha aktiv DirectorCenterAccess larni o'chiramiz
    DirectorCenterAccess.objects.filter(center=center, is_active=True).update(is_active=False)

    # Telegram admin guruhiga xabar yuborish (background, xato bo'lsa e'tibor bermaslik)
    try:
        _notify_branch_deactivated(center, actor=user)
    except Exception:
        logger.exception("Branch deactivate telegram notify failed silently")

    reload_needed = str(request.session.get("current_center_id")) == str(center_id)
    return JsonResponse({"ok": True, "message": f"'{center.name}' filiali bloklandi", "reload": reload_needed})


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

    def _redirect_center_manage():
        return redirect("platform_global:center_manage", pk=center.id)

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
                return _redirect_center_manage()

            u = User.objects.filter(id=user_id, role__in=["director", "manager"]).first()
            if not u:
                messages.error(request, "Director topilmadi.")
                return _redirect_center_manage()

            u.center = center
            u.save(update_fields=["center"])
            messages.success(request, f"✅ Director biriktirildi: {getattr(u, 'email', u.id)}")
            return _redirect_center_manage()

        if action == "create_new":
            email = (request.POST.get("email") or "").strip().lower()
            password = (request.POST.get("password") or "").strip()
            ism = (request.POST.get("ism") or "").strip()
            familya = (request.POST.get("familya") or "").strip()

            if not email or not password:
                messages.error(request, "Email va parol talab qilinadi.")
                return _redirect_center_manage()

            if User.objects.filter(email=email).exists():
                messages.error(request, "Bu email allaqon mavjud.")
                return _redirect_center_manage()

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
            return _redirect_center_manage()

        if action == "edit_director":
            user_id = request.POST.get("user_id")
            email = (request.POST.get("email") or "").strip().lower()
            password = (request.POST.get("password") or "").strip()
            ism = (request.POST.get("ism") or "").strip()
            familya = (request.POST.get("familya") or "").strip()
            
            u = User.objects.filter(id=user_id, center=center, role__in=["director", "manager"]).first()
            if not u:
                messages.error(request, "Xodim topilmadi.")
                return _redirect_center_manage()
                
            if email and email != u.email:
                if User.objects.filter(email=email).exclude(id=u.id).exists():
                    messages.error(request, "Bu email allaqachon boshqa xodimda mavjud.")
                    return _redirect_center_manage()
                u.email = email
            
            u.ism = ism
            u.familya = familya
            
            if password:
                u.set_password(password)
                
            u.save()
            messages.success(request, f"✅ Xodim ma'lumotlari yangilandi: {u.email}")
            return _redirect_center_manage()

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
    return redirect("platform_global:center_manage", pk=center.id)

# --- Missing Views Restored ---

@login_required
def add_user(request):
    is_user_drawer = _is_user_drawer_request(request)
    allow_role_switch = _is_role_switch_drawer_request(request)

    if is_user_drawer:
        allowed_roles = _get_allowed_add_roles(request)
        if not allowed_roles:
            return HttpResponseForbidden("Ruxsat yo'q.")
    elif not _can_add(request.user):
        return HttpResponseForbidden("Ruxsat yo'q.")
    else:
        allowed_roles = []

    next_url = _safe_next_url(request.POST.get("next") or request.GET.get("next"))

    role_param = _normalize_role_value(request.GET.get("role"))
    posted_role = _normalize_role_value(request.POST.get("role"))
    requested_role = posted_role or role_param

    if is_user_drawer:
        allow_role_switch = allow_role_switch and len(allowed_roles) > 1
        if allow_role_switch:
            current_role = requested_role if requested_role in allowed_roles else allowed_roles[0]
        else:
            current_role = role_param if role_param in allowed_roles else allowed_roles[0]
    else:
        current_role = requested_role

    initial = {}
    if current_role:
        initial["role"] = current_role

    active_center = getattr(request, "center", None) or getattr(request.user, "center", None)
    selected_center_id = request.POST.get("center") or request.GET.get("center")
    selected_group_id = request.POST.get("group") or request.GET.get("group")
    selected_group = None
    if selected_group_id:
        selected_group = Group.objects.filter(id=selected_group_id, is_archived=False).select_related("center").first()
        if selected_group:
            if active_center and selected_group.center_id != active_center.id:
                selected_group = None
            else:
                initial["group"] = selected_group.id
                if not active_center:
                    active_center = selected_group.center
    if not active_center and selected_center_id:
        active_center = Center.objects.filter(id=selected_center_id).first()
    if active_center and "center" not in initial:
        initial["center"] = active_center.id

    form_data = request.POST.copy() if request.method == "POST" else None
    if is_user_drawer and form_data is not None:
        form_data["role"] = current_role
        if active_center and not form_data.get("center"):
            form_data["center"] = str(active_center.id)
        if not (form_data.get("email") or "").strip():
            form_data["email"] = _generate_user_email(
                form_data.get("ism", ""),
                form_data.get("familya", ""),
            )
        if not (form_data.get("password") or "").strip():
            form_data["password"] = _generate_user_password()

    form = AddUserForm(
        form_data or None,
        request=request,
        initial=initial,
        allow_initial_group_assignment=(is_user_drawer and current_role == "student"),
        allowed_roles=(
            allowed_roles
            if is_user_drawer and allow_role_switch
            else ([current_role] if is_user_drawer and current_role else None)
        ),
    )
    student_limit_state = None

    if active_center and current_role == "student":
        from billing.services import resolve_center_student_limit

        student_limit_state = resolve_center_student_limit(
            center=active_center,
            actor=request.user,
            include_usage=True,
        )

    drawer_center_value = ""
    if active_center and getattr(active_center, "id", None):
        drawer_center_value = str(active_center.id)
    elif selected_center_id:
        drawer_center_value = str(selected_center_id)

    pending_duplicate_check = None
    if request.method == "POST" and form.is_valid():
        duplicate_check = form.get_student_duplicate_check()
        if duplicate_check.requires_confirmation and not form.duplicate_override_requested():
            pending_duplicate_check = serialize_student_duplicate_check(duplicate_check)
            if is_user_drawer:
                return JsonResponse(
                    {
                        "ok": False,
                        "duplicate_check": pending_duplicate_check,
                    },
                    status=409,
                )
        try:
            user = form.save()
        except forms.ValidationError as e:
            err_msg = " ".join(e.messages) if hasattr(e, "messages") else str(e)
            if is_user_drawer:
                return JsonResponse({"ok": False, "error": err_msg}, status=400)
            form.add_error(None, e)
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).exception("add_user: form.save() failed")
            err_msg = f"Saqlashda xatolik yuz berdi: {e}"
            if is_user_drawer:
                return JsonResponse({"ok": False, "error": err_msg}, status=500)
            raise
        else:
            messages.success(request, f"✅ Foydalanuvchi {user.email} muvaffaqiyatli qo’shildi.")
            if is_user_drawer:
                return JsonResponse({
                    "ok": True,
                    "user": {
                        "id": user.id,
                        "full_name": user.get_full_name() or f"{user.ism} {user.familya}".strip(),
                        "email": user.email,
                    },
                })
            return redirect(next_url or "core:home")

    role_titles = {
        "director": "Yangi direktor",
        "student": "Yangi o'quvchi",
        "teacher": "Yangi o'qituvchi",
        "manager": "Yangi manager",
        "parent": "Yangi ota-ona",
    }

    if is_user_drawer:
        if current_role == "student" and not allow_role_switch:
            html = _render_student_drawer_form(
                request,
                form=form,
                student_limit_state=student_limit_state,
                next_url=next_url,
                drawer_center_value=drawer_center_value,
            )
        else:
            html = _render_user_drawer_form(
                request,
                form=form,
                student_limit_state=student_limit_state,
                next_url=next_url,
                drawer_center_value=drawer_center_value,
                current_role=current_role,
                allow_role_switch=allow_role_switch,
                available_roles=allowed_roles,
            )
        if request.method == "POST":
            return JsonResponse({"ok": False, "html": html}, status=400)
        return HttpResponse(html)

    return render(request, "accounts/user_form.html", {
        'form': form,
        'title': role_titles.get(current_role, "Yangi foydalanuvchi"),
        'student_limit_state': student_limit_state,
        'duplicate_check': pending_duplicate_check,
        'next_url': next_url,
        'cancel_url': next_url or reverse("core:home"),
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
@require_http_methods(["GET", "POST"])
def student_edit_ajax(request, pk):
    from django.utils.dateparse import parse_date as _parse_date
    from core.tenant import get_request_center

    if not _is_staff_like(request.user):
        return JsonResponse({"ok": False, "error": "Ruxsat yo'q."}, status=403)

    student = get_object_or_404(User, pk=pk)

    # ── Group search (autocomplete for "add to group") ──
    if request.method == "GET" and request.GET.get("action") == "search_groups":
        from education.models import Group as EduGroup
        q = request.GET.get("q", "").strip()
        center = get_request_center(request)
        qs = EduGroup.objects.filter(center=center) if center else EduGroup.objects.none()
        if q:
            qs = qs.filter(nom__icontains=q)
        results = [{"id": g.pk, "nom": g.nom, "kurs_narxi": g.kurs_narxi} for g in qs.order_by("nom")[:15]]
        return JsonResponse({"ok": True, "results": results})

    # ── Full student data GET ──
    if request.method == "GET":
        from education.models import Enrollment
        enrollments = (
            Enrollment.objects.filter(student=student, is_active=True)
            .select_related("group")
            .order_by("group__nom")
        )
        enr_data = [
            {
                "id": enr.pk,
                "group_id": enr.group_id,
                "group_name": enr.group.nom,
                "kurs_narhi": enr.kurs_narhi,
                "joined_at": enr.joined_at.strftime("%Y-%m-%d") if enr.joined_at else "",
                "lesson_pattern": enr.lesson_pattern or "group",
            }
            for enr in enrollments
        ]
        return JsonResponse({
            "ok": True,
            "data": {
                "id": student.pk,
                "role": student.role,
                "ism": student.ism,
                "familya": student.familya,
                "otchestvo": student.otchestvo or "",
                "email": student.email,
                "telefon1": student.telefon1,
                "telefon2": student.telefon2,
                "birth_date": student.birth_date.strftime("%Y-%m-%d") if student.birth_date else "",
                "gender": student.gender or "",
                "passport_id": student.passport_id or "",
                "jshr": student.jshr or "",
                "address": student.address or "",
                "telegram_username": student.telegram_username or "",
                "instagram_username": student.instagram_username or "",
                "avatar_url": student.avatar.url if student.avatar else None,
                "full_name": student.get_full_name(),
                "enrollments": enr_data,
            }
        })

    action = request.POST.get("action")

    # ── Profile update ──
    if action == "update_profile":
        student.ism     = (request.POST.get("ism")     or "").strip() or student.ism
        student.familya = (request.POST.get("familya") or "").strip() or student.familya
        student.otchestvo        = (request.POST.get("otchestvo")        or "").strip()
        
        tel1 = (request.POST.get("telefon1") or "").strip()
        tel2 = (request.POST.get("telefon2") or "").strip()
        
        if tel1:
            tel1_digits = "".join(filter(str.isdigit, tel1))
            if tel1_digits.startswith("998") and len(tel1_digits) == 12:
                student.telefon1 = "+" + tel1_digits
            elif len(tel1_digits) == 9:
                student.telefon1 = "+998" + tel1_digits
            else:
                student.telefon1 = tel1
        else:
            student.telefon1 = ""

        if tel2:
            tel2_digits = "".join(filter(str.isdigit, tel2))
            if tel2_digits.startswith("998") and len(tel2_digits) == 12:
                student.telefon2 = "+" + tel2_digits
            elif len(tel2_digits) == 9:
                student.telefon2 = "+998" + tel2_digits
            else:
                student.telefon2 = tel2
        else:
            student.telefon2 = ""

        student.passport_id      = (request.POST.get("passport_id")      or "").strip()
        student.jshr             = (request.POST.get("jshr")             or "").strip()
        student.address          = (request.POST.get("address")          or "").strip()
        student.telegram_username  = (request.POST.get("telegram_username")  or "").strip()
        student.instagram_username = (request.POST.get("instagram_username") or "").strip()
        gender = (request.POST.get("gender") or "").strip()
        student.gender = gender or None
        birth_raw = (request.POST.get("birth_date") or "").strip()
        if birth_raw:
            student.birth_date = _parse_date(birth_raw)
        else:
            student.birth_date = None
        if "avatar" in request.FILES:
            student.avatar = request.FILES["avatar"]
        student.save()
        return JsonResponse({
            "ok": True,
            "message": "Profil yangilandi ✅",
            "full_name": student.get_full_name(),
            "avatar_url": student.avatar.url if student.avatar else None,
        })

    # ── Password change ──
    if action == "update_password":
        form = PasswordUpdateForm(request.POST)
        if form.is_valid():
            student.set_password(form.cleaned_data["new_password"])
            student.save()
            return JsonResponse({"ok": True, "message": "Parol yangilandi 🔒"})
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)

    # ── Enrollment: remove from group ──
    if action == "enrollment_remove":
        from education.models import Enrollment
        from education.services.enrollment_service import EnrollmentService
        enr = get_object_or_404(Enrollment, pk=request.POST.get("enrollment_id"), student=student)
        group_name = enr.group.nom
        EnrollmentService.remove_student(student, enr.group)
        return JsonResponse({"ok": True, "message": f"'{group_name}' guruhidan chiqarildi ✅"})

    # ── Enrollment: update price / date / pattern ──
    if action == "enrollment_update":
        from education.models import Enrollment
        enr = get_object_or_404(Enrollment, pk=request.POST.get("enrollment_id"), student=student)
        raw_price = (request.POST.get("kurs_narhi") or "").strip()
        if raw_price.isdigit():
            enr.kurs_narhi = int(raw_price)
        joined_raw = (request.POST.get("joined_at") or "").strip()
        if joined_raw:
            enr.joined_at = _parse_date(joined_raw)
        pattern = (request.POST.get("lesson_pattern") or "").strip()
        if pattern:
            enr.lesson_pattern = pattern
        enr.save(update_fields=["kurs_narhi", "joined_at", "lesson_pattern"])
        return JsonResponse({
            "ok": True,
            "message": "Guruh ma'lumotlari yangilandi ✅",
            "enrollment": {
                "id": enr.pk,
                "kurs_narhi": enr.kurs_narhi,
                "joined_at": enr.joined_at.strftime("%Y-%m-%d") if enr.joined_at else "",
                "lesson_pattern": enr.lesson_pattern or "group",
            },
        })

    # ── Enrollment: add to group ──
    if action == "enrollment_add":
        from education.models import Group as EduGroup, Enrollment
        from education.services.enrollment_service import EnrollmentService
        center = get_request_center(request)
        group_id = (request.POST.get("group_id") or "").strip()
        if not group_id:
            return JsonResponse({"ok": False, "error": "Guruh tanlanmagan."}, status=400)
        group = get_object_or_404(EduGroup, pk=group_id, center=center)
        raw_price = (request.POST.get("kurs_narhi") or "").strip()
        kurs_narxi = int(raw_price) if raw_price.isdigit() else group.kurs_narxi
        joined_raw = (request.POST.get("joined_at") or "").strip()
        start_date = _parse_date(joined_raw) if joined_raw else None
        if Enrollment.objects.filter(group=group, student=student, is_active=True).exists():
            return JsonResponse({"ok": False, "error": f"O'quvchi allaqachon '{group.nom}' guruhida bor."})
        enr = EnrollmentService.enroll_student(
            student=student,
            group=group,
            kurs_narxi=kurs_narxi,
            oqituvchi_foiz=group.oqituvchi_foiz or 40,
            start_date=start_date,
        )
        return JsonResponse({
            "ok": True,
            "message": f"'{group.nom}' guruhiga qo'shildi ✅",
            "enrollment": {
                "id": enr.pk,
                "group_id": group.pk,
                "group_name": group.nom,
                "kurs_narhi": enr.kurs_narhi,
                "joined_at": enr.joined_at.strftime("%Y-%m-%d") if enr.joined_at else "",
                "lesson_pattern": enr.lesson_pattern or "group",
            },
        })

    return JsonResponse({"ok": False, "error": "Noto'g'ri so'rov."}, status=400)


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
    if not _is_staff_like(request.user):
        return HttpResponseForbidden("Ruxsat yo'q.")

    teacher_qs = User.objects.filter(role='teacher')
    if not request.user.is_superuser:
        center = get_request_center(request)
        teacher_qs = teacher_qs.filter(center=center)
    teacher = get_object_or_404(teacher_qs, id=user_id)
    return render(request, "accounts/teacher_detail.html", {'teacher': teacher})

@login_required
def student_detail(request, user_id):
    role = getattr(request.user, "role", None)
    if not (_is_staff_like(request.user) or role == "parent"):
        return HttpResponseForbidden("Ruxsat yo'q.")

    student_qs = User.objects.filter(role='student')
    if not request.user.is_superuser:
        center = get_request_center(request)
        student_qs = student_qs.filter(center=center)
    student = get_object_or_404(student_qs, id=user_id)
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

@login_required
@user_passes_test(lambda u: u.is_superuser)
def test_db(request):
    return HttpResponse(f"DB: {connection.alias}")


@login_required
@user_passes_test(lambda u: u.is_superuser)
def test_center(request):
    tenant = get_current_tenant()
    return HttpResponse(f"Tenant: {tenant}")
