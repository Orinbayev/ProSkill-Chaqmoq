from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from accounts.api_auth import record_activity
from accounts.models import User
from billing.services import (
    get_subscription_ui_state,
    get_user_subscription_dashboard_data,
    resolve_center_student_limit,
)
from chaqmoq.models import Ledger
from core.models import Notification
from education.models import (
    Attendance,
    CertificateRecord,
    Enrollment,
    Group,
    Payment,
    PaymentAllocation,
    TuitionMonth,
)
from education.services.expected_income_service import calculate_expected_income
from store.models import Lead, Product, PurchaseRequest, TrialLesson


def _json_error(message: str, *, status: int = 400, code: str | None = None) -> JsonResponse:
    payload = {"ok": False, "error": message}
    if code:
        payload["code"] = code
    return JsonResponse(payload, status=status)


def _parse_json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError):
        return {}


def _request_center(request):
    return getattr(request, "center", None) or getattr(request.user, "center", None)


def _full_name(user: User) -> str:
    return (getattr(user, "get_full_name", None) or user.full_name)() if callable(getattr(user, "get_full_name", None)) else user.full_name()


def _safe_media_url(request, field) -> str | None:
    try:
        url = getattr(field, "url", None)
    except Exception:
        url = None
    if not url:
        return None
    return request.build_absolute_uri(url)


def _money(value) -> int:
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    return int(value or 0)


def _serialize_center(center) -> dict | None:
    if not center:
        return None
    return {
        "id": center.id,
        "name": center.name,
        "slug": center.slug,
        "status": center.status,
        "plan": center.plan,
        "phone": center.phone,
        "address": center.address,
        "max_users": center.max_users,
        "max_groups": center.max_groups,
        "max_students": center.max_students,
        "effective_student_limit": getattr(center, "effective_student_limit", center.max_students),
        "features": center.features or {},
    }


def _serialize_user(request, user: User) -> dict:
    center = getattr(user, "center", None)
    return {
        "id": user.id,
        "email": user.email,
        "phone_number": user.phone_number,
        "telefon1": user.telefon1,
        "telefon2": user.telefon2,
        "full_name": user.get_full_name(),
        "ism": user.ism,
        "familya": user.familya,
        "otchestvo": user.otchestvo,
        "role": user.role,
        "avatar_url": _safe_media_url(request, user.avatar),
        "is_telegram_linked": user.is_telegram_linked,
        "telegram_username": user.telegram_username,
        "center": _serialize_center(center),
        "permissions": {
            "can_access_trash": bool(user.can_access_trash or (center and center.manager_can_access_trash and user.role == "manager")),
            "can_add_student": bool(
                user.is_superuser
                or user.role == "director"
                or (center and center.manager_can_add_student and user.role == "manager")
                or (center and center.teacher_can_add_student and user.role == "teacher")
            ),
            "can_remove_student": bool(
                user.is_superuser
                or user.role == "director"
                or (center and center.manager_can_remove_student and user.role == "manager")
                or (center and center.teacher_can_remove_student and user.role == "teacher")
            ),
            "can_view_director_dashboard": False,
            "can_manage_leads": bool(user.is_superuser or user.role in ("director", "manager")),
            "can_take_attendance": bool(user.is_superuser or user.role in ("director", "manager", "teacher")),
        },
    }


def _serialize_session(request, user: User) -> dict:
    return {
        "ok": True,
        "authenticated": True,
        "csrf_token": get_token(request),
        "user": _serialize_user(request, user),
    }


def _serialize_notification(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "title": notification.title,
        "message": notification.message,
        "type": notification.type,
        "is_read": notification.is_read,
        "created_at": timezone.localtime(notification.created_at).isoformat(),
    }


def _serialize_group(group: Group) -> dict:
    teacher = getattr(group, "oqituvchi", None)
    return {
        "id": group.id,
        "name": group.nom,
        "category": getattr(getattr(group, "category_obj", None), "name", ""),
        "teacher_id": teacher.id if teacher else None,
        "teacher_name": teacher.get_full_name() if teacher else "",
        "monthly_price": group.kurs_narxi,
        "teacher_share_percent": group.oqituvchi_foiz,
        "monthly_lessons": group.oy_dars_soni,
        "is_closed": bool(group.is_closed),
    }


def _serialize_product(request, product: Product) -> dict:
    first_image = product.rasmlar.first()
    return {
        "id": product.id,
        "name": product.nom,
        "price_chaqmoq": product.narx_chaqmoq,
        "price_som": product.narx_som,
        "sold_count": product.sotilgan_soni,
        "description": product.izoh,
        "image_url": _safe_media_url(request, getattr(first_image, "rasm", None)),
    }


def _student_balance(student: User, center) -> int:
    return Ledger.student_balansi(student.id, center=center)


def _student_open_debt(student: User, center) -> int:
    current_month = timezone.localdate().replace(day=1)
    enrollments = (
        Enrollment.objects.filter(student=student, group__center=center, is_active=True)
        .select_related("group")
        .prefetch_related("tuition_months__allocations")
    )
    total_debt = 0
    for enrollment in enrollments:
        tuition = enrollment.tuition_months.filter(month=current_month).first()
        if not tuition:
            continue
        paid = tuition.allocations.aggregate(total=Sum("amount"))["total"] or 0
        total_debt += max(0, _money(tuition.fee_amount) - _money(paid))
    return int(total_debt)


def _student_attendance_summary(student: User, center) -> dict:
    qs = Attendance.objects.filter(student=student, group__center=center)
    total = qs.count()
    present = qs.filter(Q(status="present") | Q(present=True) | Q(forced=True)).count()
    recent_qs = qs.filter(date__gte=timezone.localdate() - timezone.timedelta(days=30))
    recent_total = recent_qs.count()
    recent_present = recent_qs.filter(Q(status="present") | Q(present=True) | Q(forced=True)).count()
    return {
        "total_lessons": total,
        "present_lessons": present,
        "attendance_rate": round((present / total) * 100, 1) if total else 0,
        "recent_total_lessons": recent_total,
        "recent_present_lessons": recent_present,
        "recent_attendance_rate": round((recent_present / recent_total) * 100, 1) if recent_total else 0,
    }


def _student_groups(student: User, center) -> list[dict]:
    enrollments = (
        Enrollment.objects.filter(student=student, group__center=center)
        .select_related("group", "group__oqituvchi", "group__category_obj")
        .order_by("-is_active", "group__nom")
    )
    items = []
    for enrollment in enrollments:
        group = enrollment.group
        items.append(
            {
                **_serialize_group(group),
                "enrollment_id": enrollment.id,
                "is_active": enrollment.is_active,
                "paid_total": enrollment.jami_tolangan,
                "course_price": enrollment.kurs_narhi,
            }
        )
    return items


def _student_payments(student: User, center, *, limit: int = 5) -> list[dict]:
    payments = (
        Payment.objects.filter(student=student, center=center)
        .select_related("group")
        .order_by("-paid_date", "-id")[:limit]
    )
    return [
        {
            "id": payment.id,
            "group_name": payment.group.nom,
            "amount": payment.summa,
            "payment_type": payment.payment_type,
            "paid_date": payment.paid_date.isoformat(),
            "note": payment.note or "",
        }
        for payment in payments
    ]


def _student_certificates(student: User, center, *, limit: int = 5) -> list[dict]:
    certificates = (
        CertificateRecord.objects.filter(student=student, center=center, status=CertificateRecord.STATUS_ISSUED)
        .select_related("group")
        .order_by("-issue_date", "-id")[:limit]
    )
    return [
        {
            "id": cert.id,
            "type": cert.certificate_type,
            "number": cert.certificate_number,
            "group_name": cert.group.nom,
            "issue_date": cert.issue_date.isoformat(),
            "status": cert.status,
        }
        for cert in certificates
    ]


def _serialize_student_summary(student: User, center) -> dict:
    return {
        "id": student.id,
        "full_name": student.get_full_name(),
        "balance": _student_balance(student, center),
        "debt": _student_open_debt(student, center),
        "attendance": _student_attendance_summary(student, center),
        "groups": _student_groups(student, center),
        "payments": _student_payments(student, center),
        "certificates": _student_certificates(student, center),
    }


def _role_required(request, allowed_roles: tuple[str, ...]) -> JsonResponse | None:
    if request.user.is_superuser:
        return None
    if getattr(request.user, "role", None) not in allowed_roles:
        return _json_error("Permission denied", status=403, code="permission_denied")
    return None


@require_GET
@ensure_csrf_cookie
def mobile_auth_csrf(request):
    return JsonResponse({"ok": True, "csrf_token": get_token(request)})


@require_POST
def mobile_auth_login(request):
    data = _parse_json_body(request)
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    if not username or not password:
        return _json_error("username va password majburiy", code="missing_credentials")

    user = authenticate(request, username=username, password=password)
    if not user:
        return _json_error("Login yoki parol noto'g'ri", status=401, code="invalid_credentials")

    center = _request_center(request)
    if center and not user.is_superuser and getattr(user, "center_id", None) and user.center_id != center.id:
        return _json_error("Bu markaz uchun kirish ruxsati yo'q", status=403, code="center_mismatch")

    login(request, user)
    try:
        record_activity(user, "Login successful (Mobile API)", request=request)
    except Exception:
        pass
    return JsonResponse(_serialize_session(request, user))


@require_POST
def mobile_auth_logout(request):
    if request.user.is_authenticated:
        try:
            record_activity(request.user, "Logout (Mobile API)", request=request)
        except Exception:
            pass
    logout(request)
    return JsonResponse({"ok": True, "authenticated": False})


@require_GET
def mobile_auth_status(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": True, "authenticated": False, "csrf_token": get_token(request)})
    return JsonResponse(_serialize_session(request, request.user))


@require_GET
@login_required
def mobile_me(request):
    return JsonResponse({"ok": True, "user": _serialize_user(request, request.user), "csrf_token": get_token(request)})


@require_GET
@login_required
def mobile_role_home(request):
    role = "superadmin" if request.user.is_superuser else getattr(request.user, "role", "")
    center = _request_center(request)
    notifications_unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
    payload = {
        "ok": True,
        "role": role,
        "center": _serialize_center(center),
        "unread_notifications": notifications_unread,
    }

    if role in ("director", "manager", "superadmin"):
        groups_count = Group.objects.filter(center=center, is_archived=False).count() if center else 0
        active_students = (
            Enrollment.objects.filter(group__center=center, is_active=True).values("student_id").distinct().count()
            if center else 0
        )
        payload["summary"] = {
            "groups_count": groups_count,
            "active_students": active_students,
            "lead_count": Lead.objects.filter(center=center, is_archived=False).count() if center else 0,
            "trial_count": TrialLesson.objects.filter(center=center).count() if center else 0,
            "today_payments": Payment.objects.filter(center=center, paid_date=timezone.localdate()).aggregate(total=Sum("summa"))["total"] or 0 if center else 0,
        }
        return JsonResponse(payload)

    if role == "teacher":
        groups = Group.objects.filter(center=center, oqituvchi=request.user, is_archived=False).order_by("nom")
        payload["summary"] = {
            "groups_count": groups.count(),
            "students_count": Enrollment.objects.filter(group__in=groups, is_active=True).values("student_id").distinct().count(),
            "today_attendance_marked": Attendance.objects.filter(group__in=groups, date=timezone.localdate()).count(),
        }
        return JsonResponse(payload)

    if role == "student":
        payload["summary"] = _serialize_student_summary(request.user, center)
        return JsonResponse(payload)

    if role == "parent":
        payload["summary"] = {
            "children_count": request.user.children.count(),
            "children": [_serialize_student_summary(child, center) for child in request.user.children.all()[:5]],
        }
        return JsonResponse(payload)

    return JsonResponse(payload)


@require_GET
@login_required
def mobile_teacher_home(request):
    permission_error = _role_required(request, ("teacher", "director", "manager"))
    if permission_error:
        return permission_error
    center = _request_center(request)
    teacher = request.user
    if request.user.role in ("director", "manager") and request.GET.get("teacher_id"):
        teacher = get_object_or_404(User, pk=request.GET.get("teacher_id"), role="teacher", center=center)
    groups = (
        Group.objects.filter(center=center, oqituvchi=teacher, is_archived=False)
        .select_related("category_obj")
        .order_by("nom")
    )
    today = timezone.localdate()
    expected = calculate_expected_income(teacher=teacher, year=today.year, month=today.month, center=center)
    return JsonResponse(
        {
            "ok": True,
            "teacher": {
                "id": teacher.id,
                "full_name": teacher.get_full_name(),
            },
            "groups": [
                {
                    **_serialize_group(group),
                    "student_count": Enrollment.objects.filter(group=group, is_active=True).count(),
                    "today_attendance_count": Attendance.objects.filter(group=group, date=today).count(),
                }
                for group in groups
            ],
            "expected_income": expected,
        }
    )


@require_GET
@login_required
def mobile_student_home(request):
    if not request.user.is_superuser and request.user.role != "student":
        return _json_error("Permission denied", status=403, code="permission_denied")
    center = _request_center(request)
    return JsonResponse({"ok": True, "student": _serialize_student_summary(request.user, center)})


@require_GET
@login_required
def mobile_parent_home(request):
    if not request.user.is_superuser and request.user.role != "parent":
        return _json_error("Permission denied", status=403, code="permission_denied")
    center = _request_center(request)
    child_id = request.GET.get("child_id")
    children = request.user.children.all()
    if child_id:
        children = children.filter(pk=child_id)
    return JsonResponse(
        {
            "ok": True,
            "children": [_serialize_student_summary(child, center) for child in children],
        }
    )


@require_GET
@login_required
def mobile_notifications(request):
    page = max(int(request.GET.get("page") or 1), 1)
    per_page = min(max(int(request.GET.get("per_page") or 20), 1), 100)
    qs = Notification.objects.filter(recipient=request.user).order_by("-created_at")
    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)
    return JsonResponse(
        {
            "ok": True,
            "items": [_serialize_notification(item) for item in page_obj.object_list],
            "pagination": {
                "page": page_obj.number,
                "pages": paginator.num_pages,
                "total": paginator.count,
                "has_next": page_obj.has_next(),
            },
            "unread_count": qs.filter(is_read=False).count(),
        }
    )


@require_POST
@login_required
def mobile_notifications_read_all(request):
    updated_count = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True, "updated_count": updated_count})


@require_GET
@login_required
def mobile_billing_status(request):
    center = _request_center(request)
    user_subscription = get_user_subscription_dashboard_data(request.user)
    center_subscription = get_subscription_ui_state(center) if center else None
    limit_state = resolve_center_student_limit(center=center, actor=request.user, include_usage=True) if center else None
    return JsonResponse(
        {
            "ok": True,
            "center_subscription": center_subscription,
            "user_subscription": user_subscription,
            "student_limit": limit_state,
        }
    )


@require_GET
@login_required
def mobile_leads(request):
    permission_error = _role_required(request, ("director", "manager"))
    if permission_error:
        return permission_error
    center = _request_center(request)
    q = str(request.GET.get("q") or "").strip()
    qs = Lead.objects.filter(center=center, is_archived=False).select_related("manba", "status", "yonalish")
    if q:
        qs = qs.filter(Q(ism__icontains=q) | Q(familya__icontains=q) | Q(telefon1__icontains=q))
    status_code = str(request.GET.get("status") or "").strip()
    if status_code:
        qs = qs.filter(status__code=status_code)
    items = []
    for lead in qs.order_by("-updated_at", "-id")[:50]:
        items.append(
            {
                "id": lead.id,
                "full_name": lead.full_name,
                "phone": lead.telefon1,
                "source": lead.manba.nom if lead.manba else "",
                "status": lead.status.code if lead.status else "",
                "status_label": lead.status.nom if lead.status else "",
                "next_follow_up_date": lead.next_follow_up_date.isoformat() if lead.next_follow_up_date else None,
                "converted_to_student": lead.converted_to_student,
                "updated_at": timezone.localtime(lead.updated_at).isoformat(),
            }
        )
    return JsonResponse({"ok": True, "items": items})


@require_GET
@login_required
def mobile_store_products(request):
    center = _request_center(request)
    qs = Product.objects.filter(center=center, is_deleted=False).prefetch_related("rasmlar").order_by("-yaratilgan")
    return JsonResponse({"ok": True, "items": [_serialize_product(request, product) for product in qs[:100]]})


@require_GET
@login_required
def mobile_chaqmoq_history(request):
    center = _request_center(request)
    target_user = request.user
    student_id = request.GET.get("student_id")
    if student_id:
        if request.user.role == "parent":
            target_user = get_object_or_404(request.user.children.all(), pk=student_id)
        elif request.user.role in ("director", "manager", "teacher") or request.user.is_superuser:
            target_user = get_object_or_404(User, pk=student_id, role="student", center=center)
        else:
            return _json_error("Permission denied", status=403, code="permission_denied")
    elif not request.user.is_superuser and request.user.role != "student":
        return _json_error("Permission denied", status=403, code="permission_denied")

    qs = (
        Ledger.objects.filter(student=target_user)
        .filter(Q(group__center=center) | Q(rule__center=center) | Q(rule__center__isnull=True))
        .select_related("group", "beruvchi", "rule")
        .order_by("-sana", "-id")[:100]
    )
    items = [
        {
            "id": entry.id,
            "points": entry.ball,
            "rule_name": entry.rule_nom or (entry.rule.nom if entry.rule else ""),
            "group_name": entry.group.nom if entry.group else "",
            "giver_name": entry.beruvchi.get_full_name() if entry.beruvchi else "",
            "created_at": timezone.localtime(entry.sana).isoformat(),
        }
        for entry in qs
    ]
    return JsonResponse({"ok": True, "balance": _student_balance(target_user, center), "items": items})


@require_GET
@login_required
def mobile_purchase_requests(request):
    if request.user.role != "student" and not request.user.is_superuser:
        return _json_error("Permission denied", status=403, code="permission_denied")
    center = _request_center(request)
    qs = (
        PurchaseRequest.objects.filter(student=request.user, center=center)
        .select_related("product", "manager")
        .order_by("-sana")
    )
    return JsonResponse(
        {
            "ok": True,
            "items": [
                {
                    "id": item.id,
                    "product_id": item.product_id,
                    "product_name": item.product.nom if item.product else "",
                    "qty": item.qty,
                    "status": item.status,
                    "manager_name": item.manager.get_full_name() if item.manager else "",
                    "created_at": timezone.localtime(item.sana).isoformat(),
                }
                for item in qs[:100]
            ],
        }
    )


@require_POST
@login_required
def mobile_purchase_request_create(request):
    if request.user.role != "student" and not request.user.is_superuser:
        return _json_error("Permission denied", status=403, code="permission_denied")
    center = _request_center(request)
    data = _parse_json_body(request)
    product_id = data.get("product_id")
    qty = max(int(data.get("qty") or 1), 1)
    product = get_object_or_404(Product.objects.filter(center=center, is_deleted=False), pk=product_id)
    purchase = PurchaseRequest.objects.create(
        center=center,
        student=request.user,
        product=product,
        qty=qty,
    )
    return JsonResponse({"ok": True, "id": purchase.id, "status": purchase.status}, status=201)


@require_GET
@login_required
def mobile_student_debt_breakdown(request):
    if request.user.role not in ("student", "parent", "director", "manager") and not request.user.is_superuser:
        return _json_error("Permission denied", status=403, code="permission_denied")
    center = _request_center(request)
    target_user = request.user
    student_id = request.GET.get("student_id")
    if student_id:
        if request.user.role == "parent":
            target_user = get_object_or_404(request.user.children.all(), pk=student_id)
        else:
            target_user = get_object_or_404(User, pk=student_id, role="student", center=center)

    current_month = timezone.localdate().replace(day=1)
    enrollments = (
        Enrollment.objects.filter(student=target_user, group__center=center)
        .select_related("group")
        .prefetch_related("tuition_months__allocations")
    )
    items = []
    total = 0
    for enrollment in enrollments:
        tuition = enrollment.tuition_months.filter(month=current_month).first()
        fee = _money(tuition.fee_amount) if tuition else 0
        paid = tuition.allocations.aggregate(total=Sum("amount"))["total"] or 0 if tuition else 0
        debt = max(0, fee - _money(paid))
        total += debt
        items.append(
            {
                "group_id": enrollment.group_id,
                "group_name": enrollment.group.nom,
                "month": current_month.isoformat(),
                "fee": fee,
                "paid": _money(paid),
                "debt": debt,
            }
        )
    return JsonResponse({"ok": True, "total_debt": total, "items": items})
