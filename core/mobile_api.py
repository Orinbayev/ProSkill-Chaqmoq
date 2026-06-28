from __future__ import annotations

import json
import calendar
import hashlib
import html
import logging
import os
import re
import secrets
from datetime import date, timedelta
from decimal import Decimal
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, Paginator
from django.core.validators import validate_email
from django.db.models import Avg, Q, Sum
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.api_auth import record_activity
from accounts.auth_helpers import (
    authenticate_login_identifier,
    mask_login_identifier,
    resolve_login_attempt,
)
from accounts.models import Center, DirectorCenterAccess, User
from billing.services import (
    get_subscription_ui_state,
    get_user_subscription_dashboard_data,
    resolve_center_student_limit,
)
from chaqmoq.models import Ledger
from core.models import MobileAccessToken, Notification, NotificationPreference
from core.tenant_context import clear_current_tenant, set_current_tenant
from education.models import (
    Attendance,
    CertificateRecord,
    Enrollment,
    ExamResult,
    Group,
    Payment,
    PaymentAllocation,
    StudentAcademicSummary,
    TuitionMonth,
)
from education.services.expected_income_service import calculate_expected_income
from education.services.tuition import (
    calculate_enrollment_debt_snapshots,
    ensure_tuition_month,
)
from education.services.progress_service import build_timeline as build_progress_timeline
from store.models import Lead, Product, PurchaseRequest, TrialLesson


logger = logging.getLogger(__name__)


def _mobile_debug_enabled() -> bool:
    return bool(settings.DEBUG or os.getenv("MOBILE_AUTH_DEBUG") == "1")


def _mobile_debug(message: str, **extra) -> None:
    if not _mobile_debug_enabled():
        return
    logger.info("mobile_auth_debug: %s %s", message, extra)


def _json_error(message: str, *, status: int = 400, code: str | None = None) -> JsonResponse:
    payload = {"ok": False, "error": message}
    if code:
        payload["code"] = code
    return JsonResponse(payload, status=status)


def _mobile_json_error(
    message: str,
    *,
    status: int = 400,
    code: str | None = None,
    extra: dict | None = None,
) -> JsonResponse:
    payload = {"ok": False, "error": message, "message": message}
    if code:
        payload["code"] = code
    if extra:
        payload.update(extra)
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


def _request_payload(request) -> dict:
    request_data = getattr(request, "data", None)
    if request_data and hasattr(request_data, "items"):
        return {str(key): value for key, value in request_data.items()}

    json_payload = _parse_json_body(request)
    if json_payload:
        return json_payload

    if request.POST:
        return request.POST.dict()
    return {}


def _normalize_center_slug(value) -> str:
    return str(value or "").strip().strip("/").lower()


def _requested_center_slug(request, data: dict) -> str:
    for key in ("center_slug", "slug", "center"):
        slug = _normalize_center_slug(data.get(key))
        if slug:
            return slug

    header_slug = _normalize_center_slug(request.headers.get("X-Center-Slug"))
    if header_slug:
        return header_slug

    url_slug = _normalize_center_slug(getattr(request, "url_center_slug", ""))
    if url_slug:
        return url_slug

    if settings.DEBUG:
        return _normalize_center_slug(os.getenv("LOCAL_DEFAULT_CENTER_SLUG"))
    return ""


def _bind_request_center(request, center) -> None:
    request.center = center
    request.active_center = center
    if center is not None:
        set_current_tenant(center)


def _print_center_debug(center_slug: str, center) -> None:
    if not _mobile_debug_enabled():
        return
    print("CENTER SLUG:", center_slug)
    print("FOUND CENTER:", center)


def _center_not_found_extra(center_slug: str) -> dict:
    extra = {"received_slug": center_slug}
    if _mobile_debug_enabled():
        extra["available_centers"] = list(
            Center.objects.filter(is_deleted=False)
            .order_by("name")
            .values("name", "slug")
        )
    return extra


def _user_has_center_access(user: User, center) -> bool:
    if center is None or user.is_superuser:
        return True
    if getattr(user, "center_id", None) == center.id:
        return True
    if getattr(user, "role", "") == "director":
        return DirectorCenterAccess.objects.filter(
            director=user,
            center=center,
            is_active=True,
        ).exists()
    return False


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _bearer_token(request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        return ""
    return header.split(" ", 1)[1].strip()


def _authenticate_mobile_token(request) -> User | None:
    raw_token = _bearer_token(request)
    if not raw_token:
        return None

    key_hash = _hash_token(raw_token)
    token = (
        MobileAccessToken.objects
        .select_related("user", "user__center", "center")
        .filter(
            key_hash=key_hash,
            is_revoked=False,
            expires_at__gt=timezone.now(),
            user__is_active=True,
        )
        .first()
    )
    if not token:
        return None

    token.last_used_at = timezone.now()
    token.save(update_fields=["last_used_at"])
    request.mobile_access_token = token
    request.user = token.user
    if token.center_id:
        _bind_request_center(request, token.center)
    elif getattr(token.user, "center_id", None):
        _bind_request_center(request, token.user.center)
    return token.user


def mobile_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        try:
            if not request.user.is_authenticated:
                _authenticate_mobile_token(request)
            center = _request_center(request)
            if center is not None:
                _bind_request_center(request, center)
            if not request.user.is_authenticated:
                return _mobile_json_error(
                    "Sessiya yakunlandi. Qayta tizimga kiring.",
                    status=401,
                    code="not_authenticated",
                )
            return view_func(request, *args, **kwargs)
        finally:
            clear_current_tenant()

    return _wrapped


def _create_mobile_access_token(request, user: User, center, data: dict) -> tuple[str, MobileAccessToken]:
    raw_token = secrets.token_urlsafe(40)
    token = MobileAccessToken.objects.create(
        user=user,
        center=center,
        key_prefix=raw_token[:16],
        key_hash=_hash_token(raw_token),
        device_name=str(data.get("device_name") or "")[:120],
        device_platform=str(data.get("device_platform") or "")[:32],
        expires_at=timezone.now() + timezone.timedelta(days=180),
    )
    request.mobile_access_token = token
    return raw_token, token


def _center_from_login_payload(request, data: dict):
    slug = _requested_center_slug(request, data)
    if not slug:
        center = getattr(request, "center", None)
        if center is not None:
            _bind_request_center(request, center)
        return None, center

    center = Center.objects.filter(slug=slug, is_deleted=False).first()
    _print_center_debug(slug, center)
    if center is not None:
        _bind_request_center(request, center)
    return slug, center


def _resolve_login_user(request, data: dict):
    identifier = str(
        data.get("login")
        or data.get("phone")
        or data.get("phone_number")
        or data.get("username")
        or data.get("email")
        or ""
    ).strip()
    password = str(data.get("password") or "")
    requested_slug, center = _center_from_login_payload(request, data)
    masked_identifier = mask_login_identifier(identifier)
    _mobile_debug("login_received", login=identifier, center_slug=requested_slug or None)
    if not identifier or not password:
        logger.info(
            "mobile_login outcome=missing_credentials identifier=%s center_slug=%s",
            masked_identifier or "-",
            requested_slug or "-",
        )
        _mobile_debug("login_missing_credentials", login=identifier, center_slug=requested_slug or None)
        return None, None, _mobile_json_error(
            "Login va parol majburiy",
            code="missing_credentials",
        )

    _mobile_debug(
        "login_center_resolved",
        login=identifier,
        center_slug=requested_slug or None,
        center=getattr(center, "slug", None),
    )
    if requested_slug and not center:
        logger.info(
            "mobile_login outcome=center_not_found identifier=%s center_slug=%s",
            masked_identifier or "-",
            requested_slug or "-",
        )
        _mobile_debug("login_center_not_found", login=identifier, center_slug=requested_slug)
        return None, None, _mobile_json_error(
            "Markaz topilmadi",
            status=404,
            code="center_not_found",
            extra=_center_not_found_extra(requested_slug),
        )

    login_result = resolve_login_attempt(
        identifier,
        password,
        request=request,
        center=center,
    )
    authenticated_user = login_result.user

    if not authenticated_user:
        error_map = {
            "inactive_user": (
                403,
                "inactive_user",
                "Akkaunt faol emas. Administrator bilan bog‘laning.",
            ),
            "user_not_found": (
                404,
                "user_not_found",
                "Bunday foydalanuvchi topilmadi",
            ),
            "invalid_password": (
                401,
                "invalid_password",
                "Parol noto‘g‘ri",
            ),
        }
        status, code, error_message = error_map.get(
            login_result.code,
            (401, "invalid_credentials", "Login yoki parol noto‘g‘ri"),
        )
        logger.info(
            "mobile_login outcome=%s identifier=%s center_slug=%s",
            code,
            masked_identifier or "-",
            requested_slug or "-",
        )
        _mobile_debug(
            "login_auth_failed",
            login=identifier,
            center_slug=requested_slug or None,
            code=code,
        )
        return None, None, _mobile_json_error(
            error_message,
            status=status,
            code=code,
        )

    if not authenticated_user.is_superuser and getattr(authenticated_user, "center", None) is None:
        logger.info(
            "mobile_login outcome=center_required identifier=%s user_id=%s",
            masked_identifier or "-",
            authenticated_user.id,
        )
        _mobile_debug("login_center_required", login=identifier, user_id=authenticated_user.id)
        return None, None, _mobile_json_error(
            "Siz hech qaysi o‘quv markazga biriktirilmagansiz.",
            status=403,
            code="center_required",
        )
    if not authenticated_user.is_superuser and not (getattr(authenticated_user, "role", "") or "").strip():
        logger.info(
            "mobile_login outcome=role_required identifier=%s user_id=%s",
            masked_identifier or "-",
            authenticated_user.id,
        )
        _mobile_debug("login_role_required", login=identifier, user_id=authenticated_user.id)
        return None, None, _mobile_json_error(
            "Sizga rol biriktirilmagan.",
            status=403,
            code="role_required",
        )

    user_center = getattr(authenticated_user, "center", None)
    if center and not _user_has_center_access(authenticated_user, center):
        logger.info(
            "mobile_login outcome=center_mismatch identifier=%s user_id=%s requested_center=%s actual_center=%s",
            masked_identifier or "-",
            authenticated_user.id,
            getattr(center, "slug", None) or "-",
            getattr(user_center, "slug", None) or "-",
        )
        _mobile_debug(
            "login_center_mismatch",
            login=identifier,
            user_id=authenticated_user.id,
            user_center=getattr(user_center, "slug", None),
            requested_center=getattr(center, "slug", None),
        )
        return None, None, _mobile_json_error(
            "Bu foydalanuvchi ushbu markazga tegishli emas",
            status=403,
            code="center_mismatch",
        )

    resolved_center = center or user_center
    if resolved_center is not None:
        _bind_request_center(request, resolved_center)

    _mobile_debug(
        "login_auth_success",
        login=identifier,
        user_id=authenticated_user.id,
        role=authenticated_user.role,
        center=getattr(resolved_center, "slug", None),
    )
    logger.info(
        "mobile_login outcome=success identifier=%s user_id=%s center_slug=%s role=%s",
        masked_identifier or "-",
        authenticated_user.id,
        getattr(resolved_center, "slug", None) or "-",
        getattr(authenticated_user, "role", None) or "-",
    )
    return authenticated_user, resolved_center, None


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


_HTML_BR_RE = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean_mobile_text(value) -> str:
    text = html.unescape(str(value or ""))
    text = _HTML_BR_RE.sub("\n", text)
    text = _HTML_TAG_RE.sub("", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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
        "phone": user.telefon1 or user.phone_number or "",
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


def _serialize_session(request, user: User, *, access_token: str | None = None, token_obj: MobileAccessToken | None = None) -> dict:
    payload = {
        "ok": True,
        "success": True,
        "authenticated": True,
        "csrf_token": get_token(request),
        "user": _serialize_user(request, user),
        "role": user.role,
        "center": _serialize_center(_request_center(request)),
    }
    if access_token:
        payload["access_token"] = access_token
        payload["token"] = access_token
        payload["token_type"] = "Bearer"
        payload["expires_at"] = token_obj.expires_at.isoformat() if token_obj else None
    return payload


_CHAQMOQ_ADDED_KEYWORDS = (
    "qo‘shildi",
    "qoshildi",
    "qo'shildi",
    "added",
    "bonus",
)
_CHAQMOQ_REMOVED_KEYWORDS = (
    "ayrildi",
    "ayirildi",
    "olib tashlandi",
    "removed",
    "jarima",
    "penalty",
    "minus",
)


def _classify_notification(notification: Notification) -> tuple[str, int | None, str]:
    """Return (kind, amount, reason) for a notification.

    `kind` is one of: ``chaqmoq_added``, ``chaqmoq_removed``, or the original
    ``notification.type``. `amount` is the chaqmoq integer if present.
    `reason` is the explicit "Sabab: ..." line from the message if any.
    """
    base = (notification.type or "").lower()
    raw = " ".join(
        [
            notification.title or "",
            notification.message or "",
            notification.type or "",
        ]
    )
    text = raw.replace("’", "'").replace("‘", "'").lower()

    is_coin = base == "coin" or "chaqmoq" in text or "lightning" in text
    kind = base or "info"
    amount: int | None = None
    if is_coin:
        if any(kw in text for kw in _CHAQMOQ_REMOVED_KEYWORDS):
            kind = "chaqmoq_removed"
        elif any(kw in text for kw in _CHAQMOQ_ADDED_KEYWORDS):
            kind = "chaqmoq_added"
        else:
            kind = "chaqmoq_added"

        match = re.search(r"(\d+)\s*chaqmoq", text)
        if match:
            try:
                amount = int(match.group(1))
            except (TypeError, ValueError):
                amount = None

    reason = ""
    for line in (notification.message or "").splitlines():
        stripped = line.strip()
        lower = stripped.lower().replace("’", "'").replace("‘", "'")
        if lower.startswith("sabab:") or lower.startswith("izoh:"):
            reason = stripped.split(":", 1)[1].strip()
            break

    return kind, amount, reason


def _serialize_notification(notification: Notification) -> dict:
    kind, amount, reason = _classify_notification(notification)
    payload = {
        "id": notification.id,
        "title": _clean_mobile_text(notification.title),
        "message": _clean_mobile_text(notification.message),
        "type": notification.type,
        "kind": kind,
        "is_read": notification.is_read,
        "created_at": timezone.localtime(notification.created_at).isoformat(),
        "sender_name": _full_name(notification.sender) if notification.sender_id and notification.sender else "",
        "recipient_name": _full_name(notification.recipient) if notification.recipient_id and notification.recipient else "",
        "reason": reason,
    }
    if amount is not None:
        payload["amount"] = amount
        payload["signed_amount"] = (
            amount if kind == "chaqmoq_added" else -amount if kind == "chaqmoq_removed" else amount
        )
    return payload


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
    """
    Joriy oydagi qarzni admin paneldagi ``qarzdorlar_home`` bilan bir xil
    formula orqali hisoblaydi: faqat ``calculate_enrollment_debt_snapshots``
    o'qiladi, hech qanday TuitionMonth qaytadan yozilmaydi (admin ham yozmaydi).
    """
    current_month = timezone.localdate().replace(day=1)
    enrollments = list(
        Enrollment.objects.filter(
            student=student,
            group__center=center,
            is_active=True,
            student__is_archived=False,
            group__is_archived=False,
            group__is_deleted=False,
        ).select_related("group")
    )
    snapshots = calculate_enrollment_debt_snapshots(enrollments, [current_month])
    total_due = sum(int(snap.get("total_fee", 0) or 0) for snap in snapshots.values())
    total_paid = sum(int(snap.get("total_paid", 0) or 0) for snap in snapshots.values())
    total_debt = sum(int(snap.get("debt", 0) or 0) for snap in snapshots.values())
    logger.info(
        "mobile_student_open_debt student_id=%s full_name=%s month=%s total_due=%s total_paid=%s debt_amount=%s",
        getattr(student, "id", None),
        student.get_full_name() if hasattr(student, "get_full_name") else "",
        current_month.isoformat(),
        total_due,
        total_paid,
        total_debt,
    )
    return int(total_debt)


def _student_attendance_summary(student: User, center, *, start_date=None, end_date=None) -> dict:
    qs = Attendance.objects.filter(student=student, group__center=center)
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lt=end_date)
    total = qs.count()
    present = qs.filter(Q(status="present") | Q(present=True) | Q(forced=True)).count()
    if start_date or end_date:
        recent_qs = qs
    else:
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


def _student_monthly_attendance_summary(
    student: User,
    center,
    month_start: date,
    *,
    group_id: int | None = None,
) -> dict:
    """
    Tanlangan oy uchun davomat statistikasi.

    `total_lessons` — shu oy ichida o'quvchi guruhlari uchun belgilangan
    rejalashtirilgan darslar soni (har bir guruhning ``oy_dars_soni``,
    bo'sh bo'lsa 12 — bu admin paneldagi ``qarzdorlar_home`` mantig'i bilan
    bir xil). `attended_lessons` — shu oy ichida ``present`` deb belgilangan
    real yozuvlar soni. `attended` ``total`` dan oshmaydi (test bazadagi
    takroriy yozuvlar uchun himoya).
    """
    month_end = _add_months(month_start, 1)

    enrollments = Enrollment.objects.filter(
        student=student,
        group__center=center,
        is_active=True,
        student__is_archived=False,
        group__is_archived=False,
        group__is_deleted=False,
    ).select_related("group")
    if group_id:
        enrollments = enrollments.filter(group_id=group_id)

    # Rejalashtirilgan darslar soni — qarzdorlar sahifasida ishlatiladigan
    # ``expected_lessons_in_period`` orqali (haqiqiy GroupSchedule asosida).
    # Shu bilan May = 13 ta dars (haqiqiy jadval), Yanvar = 12 ta — degan
    # aniq ko'rsatkich olamiz.
    from education.services.tuition import expected_lessons_in_period
    last_day = month_end - timezone.timedelta(days=1)
    planned = 0
    for enr in enrollments:
        try:
            planned += int(expected_lessons_in_period(enr, month_start, last_day) or 0)
        except Exception:  # pragma: no cover - fallback
            planned += int(getattr(enr.group, "oy_dars_soni", 0) or 0) or 12

    att_qs = Attendance.objects.filter(
        student=student,
        group__center=center,
        date__gte=month_start,
        date__lt=month_end,
    )
    if group_id:
        att_qs = att_qs.filter(group_id=group_id)

    attended = att_qs.filter(
        Q(status="present") | Q(present=True) | Q(forced=True)
    ).count()
    excused = att_qs.filter(status="absent_excused").count()
    unexcused = att_qs.filter(status="absent_unexcused").count()
    recorded = att_qs.count()

    # `total_lessons` har doim "oy uchun rejalashtirilgan darslar soni" (ya'ni
    # guruhning ``oy_dars_soni``). A'zolik ma'lumoti bo'lmasa, real yozilgan
    # darslar sonidan foydalanamiz, lekin har holatda `attended` ni `total`
    # dan oshmasligini ta'minlaymiz — bazadagi noto'g'ri/takroriy yozuvlar
    # ko'rinishni buzmasligi uchun.
    total = planned if planned > 0 else recorded
    if total > 0 and attended > total:
        attended = total
    missed = max(0, total - attended)
    percent = int(round((attended / total) * 100)) if total else 0

    return {
        "month": month_start.strftime("%Y-%m"),
        "total_lessons": total,
        "attended_lessons": attended,
        "missed_lessons": missed,
        "attendance_percent": percent,
        # backward-compatible aliases
        "present_lessons": attended,
        "absent_excused": excused,
        "absent_unexcused": unexcused,
        "recorded_lessons": recorded,
        "attendance_rate": percent,
        "recent_total_lessons": total,
        "recent_present_lessons": attended,
        "recent_attendance_rate": percent,
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
    groups = _student_groups(student, center)
    is_archived = bool(getattr(student, "is_archived", False))
    has_active_group = any(bool(g.get("is_active")) for g in groups)
    return {
        "id": student.id,
        "full_name": student.get_full_name(),
        "balance": _student_balance(student, center),
        "debt": _student_open_debt(student, center),
        "attendance": _student_attendance_summary(student, center),
        "groups": groups,
        "payments": _student_payments(student, center),
        "certificates": _student_certificates(student, center),
        "is_archived": is_archived,
        "is_active_student": (not is_archived) and has_active_group,
    }


def _role_required(request, allowed_roles: tuple[str, ...]) -> JsonResponse | None:
    if request.user.is_superuser:
        return None
    if getattr(request.user, "role", None) not in allowed_roles:
        return _json_error("Permission denied", status=403, code="permission_denied")
    return None


def _month_start(date_obj):
    return date_obj.replace(day=1)


def _add_months(date_obj, months: int):
    month_index = date_obj.month - 1 + months
    year = date_obj.year + month_index // 12
    month = month_index % 12 + 1
    day = min(date_obj.day, calendar.monthrange(year, month)[1])
    return date_obj.replace(year=year, month=month, day=day)


def _month_label_uz(date_obj) -> str:
    labels = {
        1: "Yan",
        2: "Fev",
        3: "Mar",
        4: "Apr",
        5: "May",
        6: "Iyun",
        7: "Iyul",
        8: "Avg",
        9: "Sen",
        10: "Okt",
        11: "Noy",
        12: "Dek",
    }
    return labels.get(date_obj.month, date_obj.strftime("%b"))


def _parse_month_start(value: str | None):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        year_text, month_text = raw[:7].split("-", 1)
        year = int(year_text)
        month = int(month_text)
        if 1 <= month <= 12:
            return date(year, month, 1)
    except (TypeError, ValueError):
        return None
    return None


def _parse_iso_date(value: str | None):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _parent_children_queryset(parent: User, center):
    qs = parent.children.filter(role="student", is_archived=False).select_related("center")
    if center:
        qs = qs.filter(center=center)
    return qs


def _resolve_parent_child(request, child_id=None):
    # Students viewing their own progress/payments/etc.
    if request.user.role == "student" and not request.user.is_superuser:
        if child_id and int(child_id) != request.user.id:
            return None, _mobile_json_error("Permission denied", status=403, code="permission_denied")
        return request.user, None

    if not request.user.is_superuser and request.user.role != "parent":
        return None, _mobile_json_error("Permission denied", status=403, code="permission_denied")

    center = _request_center(request)
    children = _parent_children_queryset(request.user, center)
    if child_id:
        child = children.filter(pk=child_id).first()
    else:
        child = children.first()

    if not child:
        return None, _mobile_json_error("Farzand topilmadi", status=404, code="child_not_found")
    return child, None


def _split_full_name(full_name: str) -> tuple[str, str, str]:
    parts = [part for part in re.split(r"\s+", full_name.strip()) if part]
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return parts[0], parts[1], " ".join(parts[2:])


def _normalize_child_code(raw_code: str) -> str:
    return re.sub(r"\s+", "", str(raw_code or "")).upper()


def _normalize_mobile_profile_phone(raw_phone: str) -> str | None:
    digits = re.sub(r"\D", "", str(raw_phone or ""))
    if not digits:
        return ""
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    return None


def _coerce_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "ha", "on"}


def _month_label_uz_full(date_obj) -> str:
    labels = {
        1: "Yanvar",
        2: "Fevral",
        3: "Mart",
        4: "Aprel",
        5: "May",
        6: "Iyun",
        7: "Iyul",
        8: "Avgust",
        9: "Sentabr",
        10: "Oktabr",
        11: "Noyabr",
        12: "Dekabr",
    }
    return labels.get(date_obj.month, date_obj.strftime("%B"))


def _period_month_bounds(period_key: str):
    today = timezone.localdate()
    current_month = today.replace(day=1)
    normalized = str(period_key or "").strip().lower()
    if normalized in {"joriy", "current", "current_term"}:
        start = current_month
        end = _add_months(current_month, 1)
        return "current", "Joriy davr", start, end
    if normalized in {"last_month", "previous_month", "o_tgan_oy", "otgan_oy"}:
        start = _add_months(current_month, -1)
        return "last_month", "O‘tgan oy", start, current_month
    if normalized in {"last_3_months", "three_months", "oxirgi_3_oy"}:
        start = _add_months(current_month, -2)
        end = _add_months(current_month, 1)
        return "last_3_months", "Oxirgi 3 oy", start, end
    return "all", "Barcha davr", None, None


def _find_student_by_child_code(child_code: str) -> User | None:
    normalized_code = _normalize_child_code(child_code)
    if not normalized_code:
        return None
    return (
        User.objects
        .filter(
            role="student",
            is_archived=False,
            child_code__iexact=normalized_code,
        )
        .select_related("center")
        .first()
    )


def _serialize_child_profile(request, child: User, center) -> dict:
    groups = _student_groups(child, center)
    primary_group = groups[0] if groups else {}
    return {
        "id": child.id,
        "full_name": child.get_full_name(),
        "first_name": child.ism,
        "last_name": child.familya,
        "avatar_url": _safe_media_url(request, child.avatar),
        "phone": child.phone_number or child.telefon1 or "",
        "email": child.email,
        "class_name": primary_group.get("category") or "",
        "group_name": primary_group.get("name") or "",
        "group_id": primary_group.get("id"),
        "child_code": child.child_code or "",
        "center": _serialize_center(center or child.center),
        "groups": groups,
    }


def _student_average_score(student: User, center, *, start_date=None, end_date=None) -> int:
    exam_results = ExamResult.objects.filter(student=student, center=center, percent__isnull=False)
    if start_date:
        exam_results = exam_results.filter(exam_date__gte=start_date)
    if end_date:
        exam_results = exam_results.filter(exam_date__lt=end_date)
    avg_result = (
        exam_results.aggregate(avg=Avg("percent"))["avg"]
    )
    if avg_result is not None:
        return int(round(float(avg_result)))

    summary_qs = StudentAcademicSummary.objects.filter(
        student=student,
        center=center,
        average_percent__isnull=False,
    )
    avg_summary = summary_qs.aggregate(avg=Avg("average_percent"))["avg"]
    if avg_summary is not None:
        return int(round(float(avg_summary)))
    return 0


def _next_payment_date(student: User, center):
    today = timezone.localdate()
    enrollments = Enrollment.objects.filter(student=student, group__center=center, is_active=True)
    unpaid_months = (
        TuitionMonth.objects
        .filter(enrollment__in=enrollments, is_deleted=False)
        .select_related("enrollment")
        .order_by("month")
    )
    for tuition in unpaid_months:
        paid = tuition.allocations.filter(is_deleted=False).aggregate(total=Sum("amount"))["total"] or 0
        if _money(paid) < _money(tuition.fee_amount):
            day = min(getattr(center, "payment_day", 5) or 5, calendar.monthrange(tuition.month.year, tuition.month.month)[1])
            return tuition.month.replace(day=day)

    target = today
    day = min(getattr(center, "payment_day", 5) or 5, calendar.monthrange(target.year, target.month)[1])
    due = target.replace(day=day)
    if due < today:
        target = _add_months(target, 1)
        day = min(getattr(center, "payment_day", 5) or 5, calendar.monthrange(target.year, target.month)[1])
        due = target.replace(day=day)
    return due


def _student_progress_chart(student: User, center, *, period_key: str = "current") -> list[dict]:
    today = timezone.localdate()
    resolved_period, _, start_date, end_date = _period_month_bounds(period_key)
    bucket_starts: list[date] = []
    bucket_labels: list[str] = []

    if resolved_period in {"current", "last_month"} and start_date and end_date:
        month_end = end_date
        for day in (1, 8, 15, 22):
            bucket_start = start_date.replace(day=day)
            if bucket_start >= month_end:
                continue
            bucket_starts.append(bucket_start)
            next_week = min(bucket_start + timezone.timedelta(days=7), month_end)
            bucket_labels.append(f"{bucket_start.day}-{max(bucket_start.day, next_week.day - 1)}")
    elif resolved_period == "last_3_months" and start_date:
        month_cursor = start_date
        while month_cursor < (end_date or month_cursor):
            bucket_starts.append(month_cursor)
            bucket_labels.append(_month_label_uz(month_cursor))
            month_cursor = _add_months(month_cursor, 1)
    else:
        earliest_result = (
            ExamResult.objects.filter(student=student, center=center)
            .order_by("exam_date")
            .values_list("exam_date", flat=True)
            .first()
        )
        if earliest_result:
            month_cursor = _month_start(earliest_result)
        else:
            month_cursor = _month_start(_add_months(today, -5))
        end_month = _month_start(today)
        while month_cursor <= end_month:
            bucket_starts.append(month_cursor)
            bucket_labels.append(_month_label_uz(month_cursor))
            month_cursor = _add_months(month_cursor, 1)
        if len(bucket_starts) > 8:
            bucket_starts = bucket_starts[-8:]
            bucket_labels = bucket_labels[-8:]

    if not bucket_starts:
        bucket_starts = [_month_start(_add_months(today, offset)) for offset in range(-2, 1)]
        bucket_labels = [_month_label_uz(item) for item in bucket_starts]

    enrollments = (
        Enrollment.objects
        .filter(student=student, group__center=center, is_active=True)
        .select_related("group")
        .order_by("group__nom")
    )
    items = []
    for enrollment in enrollments[:6]:
        group = enrollment.group
        points = []
        has_data = False
        for index, bucket_start in enumerate(bucket_starts):
            next_bucket = (
                bucket_starts[index + 1]
                if index + 1 < len(bucket_starts)
                else (
                    end_date
                    if end_date and resolved_period in {"current", "last_month", "last_3_months"}
                    else _add_months(bucket_start, 1)
                )
            )
            avg = (
                ExamResult.objects
                .filter(
                    student=student,
                    group=group,
                    center=center,
                    exam_date__gte=bucket_start,
                    exam_date__lt=next_bucket,
                    percent__isnull=False,
                )
                .aggregate(avg=Avg("percent"))["avg"]
            )
            if avg is not None:
                has_data = True
            points.append(round(float(avg or 0), 1))
        if not has_data:
            summary = StudentAcademicSummary.objects.filter(student=student, group=group, center=center).first()
            if summary and summary.average_percent is not None:
                has_data = True
                points = [round(float(summary.average_percent), 1)] * len(bucket_starts)
        if has_data:
            items.append({
                "subject": group.nom,
                "label": group.nom,
                "percent": int(round(points[-1])),
                "points": points,
                "months": bucket_labels,
            })
    return items


def _notification_queryset_for_user(user: User):
    if getattr(user, "role", None) == "parent":
        child_ids = list(user.children.values_list("id", flat=True))
        return Notification.objects.filter(Q(recipient=user) | Q(recipient_id__in=child_ids))
    return Notification.objects.filter(recipient=user)


def _latest_parent_notifications(user: User, *, limit: int = 3) -> list[dict]:
    return [_serialize_notification(item) for item in _notification_queryset_for_user(user).order_by("-created_at")[:limit]]


_CHAQMOQ_REMOVED_KEYWORDS_FALLBACK = (
    "ayrildi",
    "ayirildi",
    "olib tashlandi",
    "removed",
    "jarima",
    "penalty",
    "minus",
)


def _student_chaqmoq_stats(child: User, center, *, months: int = 6) -> dict:
    """Joriy balans + so'nggi N oy bo'yicha chaqmoq xulosasi.

    Asosiy manba: ``chaqmoq.Ledger``. Agar bu jadvalda o'quvchi uchun yozuv
    bo'lmasa (legacy ma'lumot — chaqmoq faqat ``Notification`` orqali yuborilgan
    bo'lsa), bildirishnomalardan miqdorni regex bilan ajratib hisoblaymiz.
    """
    from collections import OrderedDict
    from chaqmoq.models import Ledger

    today = timezone.localdate()

    start = today.replace(day=1)
    for _ in range(max(0, months - 1)):
        start = (start - timedelta(days=1)).replace(day=1)

    buckets: "OrderedDict[str, dict]" = OrderedDict()
    cursor = start
    for _ in range(months):
        key = f"{cursor.year:04d}-{cursor.month:02d}"
        buckets[key] = {
            "year": cursor.year,
            "month": cursor.month,
            "key": key,
            "earned": 0,
            "lost": 0,
            "net": 0,
        }
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)

    this_month_key = f"{today.year:04d}-{today.month:02d}"

    # ─── 1) Asosiy manba: Ledger ─────────────────────────────────────
    ledger_qs = Ledger.objects.filter(student_id=child.id)
    if center:
        ledger_qs = ledger_qs.filter(
            Q(group__center=center)
            | Q(rule__center=center)
            | Q(rule__center__isnull=True)
        )
    ledger_total_count = ledger_qs.count()

    if ledger_total_count > 0:
        balance = int(Ledger.student_balansi(child.id, center=center) or 0)
        period_qs = ledger_qs.filter(
            sana__date__gte=start, sana__date__lte=today,
        ).only("ball", "sana")
        for entry in period_qs:
            ball = int(entry.ball or 0)
            if ball == 0 or not entry.sana:
                continue
            d = entry.sana.date()
            key = f"{d.year:04d}-{d.month:02d}"
            bucket = buckets.get(key)
            if bucket is None:
                continue
            if ball >= 0:
                bucket["earned"] += ball
            else:
                bucket["lost"] += abs(ball)
            bucket["net"] += ball
        source = "ledger"
    else:
        # ─── 2) Fallback: bildirishnoma matnidan parse ───────────────
        # Bu loyihada chaqmoq xabarlari ko'pincha Notification.type="coin"
        # bilan yuboriladi. Agar Ledger yozuvi bo'lmasa, balansni xabarlardan
        # tiklab olamiz — shu tarzda parent ekrani 0 ko'rsatib qolmaydi.
        notif_qs = Notification.objects.filter(recipient=child).only(
            "title", "message", "type", "created_at",
        )
        balance_from_notifs = 0
        for notif in notif_qs:
            text = (
                f"{notif.title or ''} {notif.message or ''} {notif.type or ''}"
            )
            text = text.replace("’", "'").replace("‘", "'").lower()
            is_coin = (notif.type or "").lower() == "coin" or (
                "chaqmoq" in text or "lightning" in text
            )
            if not is_coin:
                continue
            match = re.search(r"(\d+)\s*chaqmoq", text)
            if not match:
                continue
            amount = int(match.group(1))
            is_removed = any(
                kw in text for kw in _CHAQMOQ_REMOVED_KEYWORDS_FALLBACK
            )
            signed = -amount if is_removed else amount
            balance_from_notifs += signed

            if not notif.created_at:
                continue
            d = timezone.localtime(notif.created_at).date()
            key = f"{d.year:04d}-{d.month:02d}"
            bucket = buckets.get(key)
            if bucket is None:
                continue
            if signed >= 0:
                bucket["earned"] += amount
            else:
                bucket["lost"] += amount
            bucket["net"] += signed
        balance = balance_from_notifs
        source = "notifications" if balance != 0 else "empty"

    this_month = buckets.get(
        this_month_key,
        {"earned": 0, "lost": 0, "net": 0},
    )
    return {
        "balance": int(balance),
        "chaqmoq_balance": int(balance),
        "this_month_earned": int(this_month["earned"]),
        "this_month_lost": int(this_month["lost"]),
        "this_month_net": int(this_month["net"]),
        "monthly_added": int(this_month["earned"]),
        "monthly_removed": int(this_month["lost"]),
        "monthly": list(buckets.values()),
        "source": source,
    }


def _parent_dashboard_payload(request, child: User) -> dict:
    center = _request_center(request) or child.center
    attendance = _student_attendance_summary(child, center)
    monthly_attendance = _student_monthly_attendance_summary(
        child,
        center,
        timezone.localdate().replace(day=1),
    )
    debt = _student_open_debt(child, center)
    average_score = _student_average_score(child, center)
    next_payment = _next_payment_date(child, center)
    children = [_serialize_child_profile(request, item, center) for item in _parent_children_queryset(request.user, center)]
    timeline = build_progress_timeline(
        child.id,
        center_id=getattr(center, "id", None),
        period_key="month",
    )
    progress_level = _progress_level_from_timeline(timeline, average_score)
    debt_status = "qarzdor" if debt > 0 else "to_liq_to_langan"
    logger.info(
        "mobile_parent_dashboard student_id=%s student_name=%s current_month=%s "
        "monthly_price=%s paid_this_month=%s calculated_debt=%s "
        "dashboard_response_debt=%s status=%s",
        getattr(child, "id", None),
        child.get_full_name(),
        timezone.localdate().replace(day=1).isoformat(),
        _student_monthly_price(child, center),
        _student_paid_this_month(child, center),
        debt,
        debt,
        debt_status,
    )
    chaqmoq_stats = _student_chaqmoq_stats(child, center, months=6)
    return {
        "ok": True,
        "student_id": child.id,
        "chaqmoq_balance": chaqmoq_stats["balance"],
        "monthly_added": chaqmoq_stats["this_month_earned"],
        "monthly_removed": chaqmoq_stats["this_month_lost"],
        "parent": _serialize_user(request, request.user),
        "center": _serialize_center(center),
        "selected_child": _serialize_child_profile(request, child, center),
        "children": children,
        "stats": {
            "attendance_percent": int(monthly_attendance.get("attendance_percent") or 0),
            "monthly_total_lessons": int(monthly_attendance.get("total_lessons") or 0),
            "monthly_attended_lessons": int(monthly_attendance.get("attended_lessons") or 0),
            "debt_amount": debt,
            "debt_status": debt_status,
            "average_score": average_score,
            "current_level": progress_level["current_level"],
            "max_level": progress_level["max_level"],
            "monthly_change": progress_level["monthly_change"],
            "next_payment_date": next_payment.isoformat() if next_payment else None,
        },
        "chaqmoq": chaqmoq_stats,
        "progress_chart": _student_progress_chart(child, center),
        "progress_timeline": timeline,
        "progress_level": progress_level,
        "latest_notifications": _latest_parent_notifications(request.user, limit=3),
        "unread_notifications": _notification_queryset_for_user(request.user).filter(is_read=False).count(),
    }


def _student_monthly_price(student: User, center) -> int:
    enrollments = Enrollment.objects.filter(
        student=student,
        group__center=center,
        is_active=True,
        student__is_archived=False,
        group__is_archived=False,
        group__is_deleted=False,
    )
    return int(sum(int(getattr(e, "resolved_monthly_price", 0) or 0) for e in enrollments))


def _student_paid_this_month(student: User, center) -> int:
    cm = timezone.localdate().replace(day=1)
    paid = (
        Payment.objects
        .filter(student=student, center=center, is_deleted=False, paid_date__gte=cm)
        .aggregate(total=Sum("summa"))["total"]
        or 0
    )
    return _money(paid)


def _progress_breakdown(
    timeline: dict,
    *,
    attendance_summary: dict | None = None,
    fallback_percent: int = 0,
) -> dict:
    """
    Real ma'lumotlar asosida "Bilim darajasi" izohini qaytaradi.

    Tarkibiy qismlar (jami 5 ball):
      • Davomat (0..2 ball)  — attendance_rate ga proporsional
      • Vazifalar (0..1 ball) — timeline'dagi "Vazifa bajardi" sodirlari
      • Faollik (0..2 ball)   — kunlik o'rtacha ball asosida

    Trend: oxirgi 30 kun ichida birinchi va ikkinchi yarmining o'rtacha
    ballarini taqqoslab "yaxshilandi" / "barqaror" / "pasaydi" qiymatini
    qaytaradi.

    Agar real ma'lumot bo'lmasa (timeline bo'sh va attendance ham yo'q):
    breakdown bo'sh, current_level=0, label="—", trend="kutilmoqda".
    """
    points = timeline.get("timeline") or []
    has_timeline = bool(points)

    attendance_pct = 0
    if attendance_summary:
        attendance_pct = int(
            round(
                attendance_summary.get("recent_attendance_rate")
                or attendance_summary.get("attendance_rate")
                or 0
            )
        )

    if attendance_pct == 0 and not has_timeline and fallback_percent:
        attendance_pct = max(0, min(100, int(fallback_percent or 0)))

    attendance_rate = round(attendance_pct / 100, 2)

    # ─── Vazifalar (0..1) ─────────────────────────────────────────────
    homework_done = sum(
        1
        for p in points
        if any("vazifa" in str(r).lower() for r in (p.get("reasons") or []))
    )
    active_days = sum(
        1
        for p in points
        if int(p.get("score") or 0) != 0 or (p.get("reasons") or [])
    )
    homework_rate = (homework_done / active_days) if active_days else 0.0
    homework_rate = round(homework_rate, 2)
    homework_pct = int(round(homework_rate * 100))

    # Tanlangan davrda biror ma'lumot bo'lsa — natijani ko'rsatamiz.
    # "Kamida 3 kun" sharti olib tashlandi: ota-ona o'tgan oy / 3 oy
    # tanlasa ham mos davrning natijasini darhol ko'radi.
    has_data = has_timeline or attendance_pct > 0
    has_min_data = has_data

    # ─── Davomat (0..2) ───────────────────────────────────────────────
    davomat_score = round(attendance_rate * 2, 2)

    # ─── Vazifalar (0..1) ─────────────────────────────────────────────
    vazifalar_score = round(homework_rate * 1, 2)

    # ─── Faollik (0..2) ───────────────────────────────────────────────
    if active_days > 0:
        avg_daily = sum(int(p.get("score") or 0) for p in points) / active_days
    else:
        avg_daily = 0.0
    # Avg daily score (typical 0..3 from attendance + homework + activity)
    # is normalized to a 0..5 activity_score and gated per spec.
    activity_score = round(min(5.0, max(0.0, avg_daily * 2.0)), 2)

    if activity_score >= 4:
        faollik_label = "Yuqori"
        faollik_score = 2.0
    elif activity_score >= 2:
        faollik_label = "O‘rtacha"
        faollik_score = 1.0
    elif active_days > 0:
        faollik_label = "Past"
        faollik_score = 0.0
    else:
        faollik_label = "—"
        faollik_score = 0.0

    breakdown = [
        {
            "title": "Davomat",
            "label": "Davomat",
            "value": f"{attendance_pct}%" if has_data else "—",
            "score": davomat_score,
            "max_score": 2,
        },
        {
            "title": "Vazifalar",
            "label": "Vazifalar",
            "value": f"{homework_pct}%" if has_timeline else "—",
            "score": vazifalar_score,
            "max_score": 1,
        },
        {
            "title": "Faollik",
            "label": "Faollik",
            "value": faollik_label if active_days > 0 else "—",
            "score": faollik_score,
            "max_score": 2,
        },
    ]

    raw_total = davomat_score + vazifalar_score + faollik_score
    current_level = round(min(5.0, max(0.0, raw_total)), 2) if has_min_data else 0.0

    if not has_min_data:
        level_label = "Kutilmoqda"
    elif current_level >= 4:
        level_label = "Yaxshi"
    elif current_level >= 2:
        level_label = "O‘rtacha"
    elif current_level > 0:
        level_label = "E’tibor kerak"
    else:
        level_label = "—"

    # ─── Trend (oxirgi 15 kun vs avvalgi 15 kun) ──────────────────────
    monthly_change = 0.0
    trend = "kutilmoqda"
    if has_min_data and has_timeline:
        midpoint = len(points) // 2
        first_half = points[:midpoint]
        second_half = points[midpoint:]
        if first_half and second_half:
            first_avg = sum(int(p.get("score") or 0) for p in first_half) / len(first_half)
            second_avg = sum(int(p.get("score") or 0) for p in second_half) / len(second_half)
            delta = second_avg - first_avg
            monthly_change = round(delta * 0.5, 1)
            if delta > 0.2:
                trend = "yaxshilandi"
            elif delta < -0.2:
                trend = "pasaydi"
            else:
                trend = "barqaror"

    return {
        "current_level": current_level,
        "max_level": 5,
        "label": level_label,
        "trend": trend,
        "monthly_change": monthly_change,
        "breakdown": breakdown,
        "has_data": has_data,
        "has_min_data": has_min_data,
        "attendance_rate": attendance_rate,
        "homework_rate": homework_rate,
        "activity_score": activity_score,
        "active_days": active_days,
    }


def _progress_level_from_timeline(timeline: dict, fallback_percent: int) -> dict:
    insight = _progress_breakdown(
        timeline,
        attendance_summary=None,
        fallback_percent=fallback_percent,
    )
    return {
        "current_level": insight["current_level"],
        "max_level": insight["max_level"],
        "monthly_change": insight["monthly_change"],
    }


def _tuition_due_date(tuition_month: TuitionMonth, center):
    day = min(
        getattr(center, "payment_day", 5) or 5,
        calendar.monthrange(tuition_month.month.year, tuition_month.month.month)[1],
    )
    return tuition_month.month.replace(day=day)


def _parent_notification_settings_payload(user: User) -> dict:
    preference, _ = NotificationPreference.objects.get_or_create(user=user)
    return {
        "attendance": bool(preference.receive_system),
        "payments": bool(preference.receive_purchase),
        "progress": bool(preference.receive_coin),
        "general": bool(preference.receive_broadcast),
    }


@require_GET
@csrf_exempt
def mobile_health(request):
    return JsonResponse({"ok": True, "status": "awake", "ts": timezone.now().isoformat()})


@require_GET
@ensure_csrf_cookie
def mobile_auth_csrf(request):
    return JsonResponse({"ok": True, "csrf_token": get_token(request)})


@csrf_exempt
@require_POST
def mobile_auth_login(request):
    data = _request_payload(request)
    try:
        user, center, error = _resolve_login_user(request, data)
        if error:
            return error

        if center is not None:
            _bind_request_center(request, center)
        if not getattr(user, "backend", ""):
            user.backend = settings.AUTHENTICATION_BACKENDS[0]
        login(request, user)
        raw_token, token = _create_mobile_access_token(request, user, center, data)
        try:
            record_activity(user, "Login successful (Mobile API)", request=request)
        except Exception:
            pass
        return JsonResponse(_serialize_session(request, user, access_token=raw_token, token_obj=token))
    finally:
        clear_current_tenant()


@csrf_exempt
@require_POST
def mobile_auth_logout(request):
    try:
        token = getattr(request, "mobile_access_token", None)
        if token is None:
            _authenticate_mobile_token(request)
            token = getattr(request, "mobile_access_token", None)
        if token is not None:
            token.is_revoked = True
            token.save(update_fields=["is_revoked"])
        if request.user.is_authenticated:
            try:
                record_activity(request.user, "Logout (Mobile API)", request=request)
            except Exception:
                pass
        logout(request)
        return JsonResponse({"ok": True, "authenticated": False})
    finally:
        clear_current_tenant()


@require_GET
def mobile_auth_status(request):
    try:
        if not request.user.is_authenticated:
            _authenticate_mobile_token(request)
        center = _request_center(request)
        if center is not None:
            _bind_request_center(request, center)
        if not request.user.is_authenticated:
            return JsonResponse({"ok": True, "authenticated": False, "csrf_token": get_token(request)})
        return JsonResponse(_serialize_session(request, request.user))
    finally:
        clear_current_tenant()


@require_GET
@mobile_login_required
def mobile_me(request):
    return JsonResponse({"ok": True, "user": _serialize_user(request, request.user), "csrf_token": get_token(request)})


@require_GET
@mobile_login_required
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
@mobile_login_required
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
@mobile_login_required
def mobile_student_home(request):
    if not request.user.is_superuser and request.user.role != "student":
        return _json_error("Permission denied", status=403, code="permission_denied")
    center = _request_center(request)
    return JsonResponse({"ok": True, "student": _serialize_student_summary(request.user, center)})


@require_GET
@mobile_login_required
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
@mobile_login_required
def mobile_parent_dashboard(request):
    child, error = _resolve_parent_child(request, request.GET.get("child_id") or request.GET.get("selected_child_id"))
    if error:
        return error
    return JsonResponse(_parent_dashboard_payload(request, child))


@require_GET
@mobile_login_required
def mobile_dashboard(request):
    child, error = _resolve_parent_child(request, request.GET.get("child_id") or request.GET.get("selected_child_id"))
    if error:
        return error
    return JsonResponse(_parent_dashboard_payload(request, child))


@require_GET
@mobile_login_required
def mobile_parent_children(request):
    if not request.user.is_superuser and request.user.role != "parent":
        return _mobile_json_error("Permission denied", status=403, code="permission_denied")
    center = _request_center(request)
    children = [_serialize_child_profile(request, item, center) for item in _parent_children_queryset(request.user, center)]
    return JsonResponse({"ok": True, "children": children})


@csrf_exempt
@require_POST
@mobile_login_required
def mobile_parent_select_child(request):
    data = _parse_json_body(request)
    child, error = _resolve_parent_child(request, data.get("child_id"))
    if error:
        return error
    return JsonResponse({"ok": True, "selected_child": _serialize_child_profile(request, child, _request_center(request) or child.center)})


@require_GET
@mobile_login_required
def mobile_parent_child_attendance(request, child_id: int):
    child, error = _resolve_parent_child(request, child_id)
    if error:
        return error
    center = _request_center(request) or child.center
    month_start = _parse_month_start(request.GET.get("month"))
    qs = (
        Attendance.objects
        .filter(student=child, group__center=center)
        .select_related("group", "teacher")
        .order_by("-date", "group__nom")
    )
    if month_start:
        qs = qs.filter(date__gte=month_start, date__lt=_add_months(month_start, 1))

    date_from = _parse_iso_date(request.GET.get("from"))
    date_to = _parse_iso_date(request.GET.get("to"))
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    raw_group_id = request.GET.get("group_id")
    selected_group_id = None
    if raw_group_id:
        try:
            selected_group_id = int(raw_group_id)
        except (TypeError, ValueError):
            selected_group_id = None
        if selected_group_id is not None:
            qs = qs.filter(group_id=selected_group_id)

    group_options = list(
        Enrollment.objects
        .filter(student=child, group__center=center)
        .values("group_id", "group__nom")
        .order_by("group__nom")
        .distinct()
    )

    summary_month = month_start or timezone.localdate().replace(day=1)
    summary = _student_monthly_attendance_summary(
        child,
        center,
        summary_month,
        group_id=selected_group_id,
    )

    def _status_label(item) -> str:
        if item.status == "present" or item.present or item.forced:
            return "Kelgan"
        if item.status == "absent_excused":
            return "Sababli"
        return "Kelmagan"

    items = [
        {
            "id": item.id,
            "date": item.date.isoformat(),
            "group_id": item.group_id,
            "group_name": item.group.nom,
            "teacher_name": item.teacher.get_full_name() if item.teacher else "",
            "status": item.status,
            "status_label": _status_label(item),
            "present": bool(item.status == "present" or item.present or item.forced),
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in qs[:200]
    ]
    attendance_block = {
        "month": summary.get("month"),
        "total_lessons": summary.get("total_lessons", 0),
        "attended_lessons": summary.get("attended_lessons", 0),
        "missed_lessons": summary.get("missed_lessons", 0),
        "attendance_percent": summary.get("attendance_percent", 0),
    }
    return JsonResponse({
        "ok": True,
        "child": _serialize_child_profile(request, child, center),
        "attendance": attendance_block,
        "summary": summary,
        "items": items,
        "groups": [
            {"id": opt["group_id"], "name": opt["group__nom"] or ""}
            for opt in group_options
            if opt["group_id"]
        ],
        "filters": {
            "from": date_from.isoformat() if date_from else None,
            "to": date_to.isoformat() if date_to else None,
            "group_id": selected_group_id,
            "month": month_start.isoformat() if month_start else None,
        },
    })


@require_GET
@mobile_login_required
def mobile_attendance(request):
    if request.user.role == "student" and not request.user.is_superuser:
        return mobile_parent_child_attendance(request, request.user.id)
    child, error = _resolve_parent_child(request, request.GET.get("child_id") or request.GET.get("selected_child_id"))
    if error:
        return error
    return mobile_parent_child_attendance(request, child.id)


def _mobile_payments_payload(request, child: User, center) -> dict:
    enrollments = list(
        Enrollment.objects.filter(
            student=child,
            group__center=center,
            is_active=True,
            student__is_archived=False,
            group__is_archived=False,
            group__is_deleted=False,
        )
        .select_related("group")
        .order_by("group__nom")
    )
    tuition_months = list(
        TuitionMonth.objects
        .filter(enrollment__student=child, enrollment__group__center=center, is_deleted=False)
        .select_related("enrollment", "enrollment__group")
        .prefetch_related("allocations")
        .order_by("month", "enrollment__group__nom")
    )
    paid_total = (
        Payment.objects.filter(student=child, center=center, is_deleted=False)
        .aggregate(total=Sum("summa"))["total"]
        or 0
    )
    payments = (
        Payment.objects
        .filter(student=child, center=center, is_deleted=False)
        .select_related("group")
        .order_by("-paid_date", "-id")
    )
    current_month = timezone.localdate().replace(day=1)
    paid_this_month = (
        payments.filter(paid_date__gte=current_month).aggregate(total=Sum("summa"))["total"]
        or 0
    )
    total_plan = 0
    debt_amount = 0
    pending_amount = 0
    next_payment = None
    plan_items = []
    today = timezone.localdate()
    current_month_start = timezone.localdate().replace(day=1)
    for tuition in tuition_months:
        group = tuition.enrollment.group
        planned_amount = _money(tuition.fee_amount)
        paid_amount = sum(
            _money(allocation.amount)
            for allocation in tuition.allocations.all()
            if not getattr(allocation, "is_deleted", False)
        )
        remaining_amount = max(0, planned_amount - paid_amount)
        due_date = _tuition_due_date(tuition, center)
        if remaining_amount <= 0:
            status = "paid"
            status_label = "To‘langan"
        elif tuition.month > current_month_start:
            # Kelajakdagi oy — hali boshlanmagan, qarz emas, kutilayotgan to'lov.
            status = "pending"
            status_label = "Kutilmoqda"
            pending_amount += remaining_amount
            if next_payment is None or due_date < next_payment:
                next_payment = due_date
        else:
            # Joriy yoki o'tgan oy va to'lanmagan — qarzdorlik (admin panel mantig'i).
            debt_amount += remaining_amount
            if due_date < today:
                status = "debt"
                status_label = "Qarzdorlik"
            else:
                status = "pending"
                status_label = "Kutilmoqda"
                if next_payment is None or due_date < next_payment:
                    next_payment = due_date

        total_plan += planned_amount
        plan_items.append(
            {
                "id": tuition.id,
                "group_name": group.nom,
                "title": f"{_month_label_uz_full(tuition.month)} oyi to‘lovi",
                "month_label": _month_label_uz_full(tuition.month),
                "month": tuition.month.isoformat(),
                "due_date": due_date.isoformat(),
                "planned_amount": planned_amount,
                "paid_amount": paid_amount,
                "remaining_amount": remaining_amount,
                "status": status,
                "status_label": status_label,
            }
        )

    # Joriy oy uchun TuitionMonth yozuvi bo'lmasa, admin paneldagi qarzdorlar
    # ko'rinishi virtual prorated_monthly_fee orqali qarz hisoblaydi. Mobil
    # to'lovlar sahifasida ham xuddi shu summa ko'rsatilishi uchun shu
    # ma'lumotni summary.debt_amountga qo'shamiz va plan_itemsga "virtual" oy
    # qatori sifatida kiritamiz.
    enrollments_with_real_current = {
        tm.enrollment_id for tm in tuition_months if tm.month == current_month_start
    }
    virtual_enrollments = [
        enrollment
        for enrollment in enrollments
        if enrollment.id not in enrollments_with_real_current
    ]
    if virtual_enrollments:
        virtual_snapshots = calculate_enrollment_debt_snapshots(
            virtual_enrollments,
            [current_month_start],
        )
        for enrollment in virtual_enrollments:
            virtual_snapshot = virtual_snapshots.get(enrollment.id, {})
            virtual_fee = int(virtual_snapshot.get("total_fee", 0) or 0)
            virtual_debt = int(virtual_snapshot.get("debt", 0) or 0)
            if virtual_fee <= 0 and virtual_debt <= 0:
                continue
            due_date = current_month_start.replace(
                day=min(getattr(center, "payment_day", 5) or 5, 28)
            )
            status = "debt" if due_date < today else "pending"
            status_label = "Qarzdorlik" if status == "debt" else "Kutilmoqda"
            debt_amount += virtual_debt
            total_plan += virtual_fee
            if status == "pending" and (next_payment is None or due_date < next_payment):
                next_payment = due_date
            plan_items.append(
                {
                    "id": None,
                    "group_name": enrollment.group.nom,
                    "title": f"{_month_label_uz_full(current_month_start)} oyi to‘lovi",
                    "month_label": _month_label_uz_full(current_month_start),
                    "month": current_month_start.isoformat(),
                    "due_date": due_date.isoformat(),
                    "planned_amount": virtual_fee,
                    "paid_amount": 0,
                    "remaining_amount": virtual_debt,
                    "status": status,
                    "status_label": status_label,
                }
            )

    if total_plan <= 0:
        total_plan = sum(enrollment.resolved_monthly_price for enrollment in enrollments)
    if next_payment is None:
        next_payment = _next_payment_date(child, center)
    logger.info(
        "mobile_payments_summary student_id=%s student_name=%s current_month=%s monthly_price=%s paid_this_month=%s calculated_debt=%s response_debt_amount=%s",
        getattr(child, "id", None),
        child.get_full_name(),
        current_month_start.isoformat(),
        total_plan,
        _money(paid_this_month),
        debt_amount,
        debt_amount,
    )
    history = [
        {
            "id": payment.id,
            "title": f"{payment.group.nom} uchun to‘lov",
            "group_name": payment.group.nom,
            "date": payment.paid_date.isoformat(),
            "amount": payment.summa,
            "status": "paid",
            "status_label": "To‘langan",
            "payment_type": payment.payment_type,
            "note": payment.note or "",
        }
        for payment in payments[:100]
    ]
    return {
        "ok": True,
        "child": _serialize_child_profile(request, child, center),
        "summary": {
            "total_plan": total_plan,
            "total_balance": total_plan if total_plan > 0 else _money(paid_total) + debt_amount + pending_amount,
            "paid_total": _money(paid_total),
            "debt_amount": debt_amount,
            "pending_amount": pending_amount,
            "paid_this_month": _money(paid_this_month),
            "next_payment_date": next_payment.isoformat() if next_payment else None,
        },
        "plan_items": plan_items,
        "payment_gateway_available": False,
        "center_contact": {
            "name": getattr(center, "name", ""),
            "phone": getattr(center, "phone", ""),
        },
        "history": history,
    }


@require_GET
@mobile_login_required
def mobile_parent_child_payments(request, child_id: int):
    child, error = _resolve_parent_child(request, child_id)
    if error:
        return error
    center = _request_center(request) or child.center
    return JsonResponse(_mobile_payments_payload(request, child, center))


@require_GET
@mobile_login_required
def mobile_payments(request):
    if request.user.role == "student" and not request.user.is_superuser:
        center = _request_center(request)
        return JsonResponse(_mobile_payments_payload(request, request.user, center))
    child, error = _resolve_parent_child(request, request.GET.get("child_id") or request.GET.get("selected_child_id"))
    if error:
        return error
    return mobile_parent_child_payments(request, child.id)


@require_GET
@mobile_login_required
def mobile_parent_child_progress(request, child_id: int):
    child, error = _resolve_parent_child(request, child_id)
    if error:
        return error
    center = _request_center(request) or child.center
    period_key, period_label, start_date, end_date = _period_month_bounds(
        request.GET.get("period"),
    )
    subjects = []
    for enrollment in (
        Enrollment.objects
        .filter(student=child, group__center=center, is_active=True)
        .select_related("group", "group__oqituvchi")
        .order_by("group__nom")
    ):
        group = enrollment.group
        exam_results = ExamResult.objects.filter(
            student=child,
            group=group,
            center=center,
            percent__isnull=False,
        )
        if start_date:
            exam_results = exam_results.filter(exam_date__gte=start_date)
        if end_date:
            exam_results = exam_results.filter(exam_date__lt=end_date)
        avg = exam_results.aggregate(avg=Avg("percent"))["avg"]
        summary = StudentAcademicSummary.objects.filter(student=child, group=group, center=center).first()
        attendance_qs = Attendance.objects.filter(student=child, group=group, group__center=center)
        if start_date:
            attendance_qs = attendance_qs.filter(date__gte=start_date)
        if end_date:
            attendance_qs = attendance_qs.filter(date__lt=end_date)
        attendance_total = attendance_qs.count()
        attendance_present = attendance_qs.filter(
            Q(status="present") | Q(present=True) | Q(forced=True),
        ).count()
        attendance_percent = round((attendance_present / attendance_total) * 100) if attendance_total else 0
        exam_percent = (
            float(avg)
            if avg is not None
            else float(summary.average_percent)
            if summary and summary.average_percent is not None
            else 0
        )
        effective_percent = int(round(exam_percent if exam_percent > 0 else attendance_percent))
        subjects.append({
            "id": group.id,
            "subject": group.nom,
            "teacher_name": group.oqituvchi.get_full_name() if group.oqituvchi else "",
            "percent": effective_percent,
            "exam_percent": int(round(exam_percent)),
            "attendance_percent": attendance_percent,
            "status": "A’lo" if effective_percent >= 90 else "Yaxshi" if effective_percent >= 65 else "O‘rta",
        })
    comment_qs = (
        ExamResult.objects
        .filter(student=child, center=center)
        .exclude(teacher_comment="")
        .select_related("teacher", "group")
    )
    if start_date:
        comment_qs = comment_qs.filter(exam_date__gte=start_date)
    if end_date:
        comment_qs = comment_qs.filter(exam_date__lt=end_date)
    comment_qs = comment_qs.order_by("-exam_date", "-id")
    teacher_comments = [
        {
            "teacher_name": item.teacher.get_full_name() if item.teacher else "",
            "teacher_role": f"{item.group.nom} o‘qituvchisi",
            "date": item.exam_date.isoformat(),
            "comment": item.teacher_comment,
        }
        for item in comment_qs[:10]
    ]
    average_subject_percent = round(
        sum(item["percent"] for item in subjects) / len(subjects),
    ) if subjects else 0
    attendance_summary = _student_attendance_summary(
        child,
        center,
        start_date=start_date,
        end_date=end_date,
    )
    # Davomat ballini har doim joriy oy uchun hisoblaymiz, parent panelida
    # ko'rsatilayotgan oy bilan bir xil bo'lishi shart.
    monthly_attendance = _student_monthly_attendance_summary(
        child,
        center,
        timezone.localdate().replace(day=1),
    )
    attendance_percent = int(
        round(
            attendance_summary["recent_attendance_rate"]
            if period_key == "current"
            else attendance_summary["attendance_rate"],
        ),
    )
    overall_percent = max(
        average_subject_percent,
        int(round((average_subject_percent * 0.75) + (attendance_percent * 0.25))),
    ) if subjects else _student_average_score(
        child,
        center,
        start_date=start_date,
        end_date=end_date,
    )
    # Timeline darhol UI period'ning aniq oraliqlarini ishlatadi:
    # "current" → joriy oy, "last_month" → o'tgan oy, "last_3_months" →
    # joriy oy + oldingi 2 oy, "all" → barcha mavjud davr (hozirgi sanagacha).
    if period_key == "all":
        timeline_start = None
        timeline_end = None
        timeline_period_key = "all"
    else:
        timeline_start = start_date
        timeline_end = end_date
        timeline_period_key = period_key
    timeline_payload = build_progress_timeline(
        child.id,
        center_id=getattr(center, "id", None),
        period_key=timeline_period_key,
        start_date=timeline_start,
        end_date=timeline_end,
    )
    # Davomat hisobini ham tanlangan davrga moslab beramiz (yuqorida `attendance_summary`
    # period-bound qilib hisoblangan); shu tarzda 3 oy / o'tgan oy tanlanganda 5-ballik
    # natija ham, breakdown ham haqiqiy davrni aks ettiradi.
    insight = _progress_breakdown(
        timeline_payload,
        attendance_summary=attendance_summary,
        fallback_percent=overall_percent,
    )
    progress_block = {
        "current_level": insight["current_level"],
        "max_level": insight["max_level"],
        "label": insight["label"],
        "trend": insight["trend"],
        "breakdown": insight["breakdown"],
    }
    attendance_block = {
        "month": monthly_attendance.get("month"),
        "total_lessons": monthly_attendance.get("total_lessons", 0),
        "attended_lessons": monthly_attendance.get("attended_lessons", 0),
        "missed_lessons": monthly_attendance.get("missed_lessons", 0),
        "attendance_percent": monthly_attendance.get("attendance_percent", 0),
    }
    attendance_summary_block = {
        "attended": monthly_attendance.get("attended_lessons", 0),
        "total": monthly_attendance.get("total_lessons", 0),
    }
    return JsonResponse({
        "ok": True,
        "child": _serialize_child_profile(request, child, center),
        "selected_period": period_key,
        "selected_period_label": period_label,
        "available_periods": [
            {"key": "current", "label": "Joriy davr"},
            {"key": "last_month", "label": "O‘tgan oy"},
            {"key": "last_3_months", "label": "Oxirgi 3 oy"},
            {"key": "all", "label": "Barcha davr"},
        ],
        "overall_percent": overall_percent,
        "attendance_percent": attendance_percent,
        "subject_average_percent": average_subject_percent,
        "attendance": attendance_block,
        "progress": progress_block,
        "current_level": insight["current_level"],
        "max_level": insight["max_level"],
        "label": insight["label"],
        "trend": insight["trend"],
        "monthly_change": insight["monthly_change"],
        "breakdown": insight["breakdown"],
        "has_breakdown_data": insight["has_data"],
        "has_min_data": insight["has_min_data"],
        "attendance_rate": insight["attendance_rate"],
        "homework_rate": insight["homework_rate"],
        "activity_score": insight["activity_score"],
        "active_days": insight["active_days"],
        "total_chaqmoq": int(timeline_payload.get("total_chaqmoq", 0) or 0),
        "attendance_summary": attendance_summary_block,
        "progress_chart": _student_progress_chart(child, center, period_key=period_key),
        "progress_timeline": timeline_payload,
        "subjects": subjects,
        "teacher_comments": teacher_comments,
        "latest_teacher_comment": teacher_comments[0] if teacher_comments else None,
    })


@require_GET
@mobile_login_required
def mobile_progress(request):
    if request.user.role == "student" and not request.user.is_superuser:
        return mobile_parent_child_progress(request, request.user.id)
    child, error = _resolve_parent_child(request, request.GET.get("child_id") or request.GET.get("selected_child_id"))
    if error:
        return error
    return mobile_parent_child_progress(request, child.id)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
@mobile_login_required
def mobile_parent_profile(request):
    if not request.user.is_superuser and request.user.role != "parent":
        return _mobile_json_error("Permission denied", status=403, code="permission_denied")
    if request.method == "PATCH":
        data = _parse_json_body(request)
        full_name = str(data.get("full_name") or "").strip()
        phone = str(data.get("phone") or data.get("telefon1") or "").strip()
        email = str(data.get("email") or "").strip()

        if not full_name:
            return _mobile_json_error("Ism-familiya majburiy", code="full_name_required")

        normalized_phone = _normalize_mobile_profile_phone(phone)
        if normalized_phone is None:
            return _mobile_json_error(
                "Telefon raqam noto‘g‘ri kiritildi",
                code="invalid_phone",
            )

        if not email:
            return _mobile_json_error("Emailni kiriting", code="email_required")
        try:
            validate_email(email)
        except ValidationError:
            return _mobile_json_error("Email noto‘g‘ri kiritildi", code="invalid_email")
        if User.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
            return _mobile_json_error("Bu email allaqachon ishlatilgan", code="email_taken")

        ism, familya, otchestvo = _split_full_name(full_name)
        if not ism:
            return _mobile_json_error("Ism-familiya majburiy", code="full_name_required")

        request.user.ism = ism
        request.user.familya = familya
        request.user.otchestvo = otchestvo
        request.user.telefon1 = normalized_phone or ""
        request.user.gmail = email
        request.user.email = email
        request.user.save(
            update_fields=[
                "ism",
                "familya",
                "otchestvo",
                "telefon1",
                "gmail",
                "email",
            ]
        )
    center = _request_center(request)
    return JsonResponse({
        "ok": True,
        "parent": _serialize_user(request, request.user),
        "children": [_serialize_child_profile(request, item, center) for item in _parent_children_queryset(request.user, center)],
    })


@csrf_exempt
@require_http_methods(["POST"])
@mobile_login_required
def mobile_parent_profile_avatar(request):
    if not request.user.is_superuser and request.user.role != "parent":
        return _mobile_json_error("Permission denied", status=403, code="permission_denied")

    should_clear = _coerce_bool(request.POST.get("clear"), default=False)
    uploaded_avatar = request.FILES.get("avatar")
    if uploaded_avatar is None and not should_clear:
        return _mobile_json_error("Profil rasmi yuborilmadi", code="avatar_required")

    if should_clear:
        if request.user.avatar:
            request.user.avatar.delete(save=False)
        request.user.avatar = None
    elif uploaded_avatar is not None:
        request.user.avatar = uploaded_avatar

    request.user.save(update_fields=["avatar"])
    center = _request_center(request)
    return JsonResponse(
        {
            "ok": True,
            "parent": _serialize_user(request, request.user),
            "children": [
                _serialize_child_profile(request, item, center)
                for item in _parent_children_queryset(request.user, center)
            ],
        }
    )


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
@mobile_login_required
def mobile_parent_notification_preferences(request):
    if not request.user.is_superuser and request.user.role != "parent":
        return _mobile_json_error("Permission denied", status=403, code="permission_denied")

    preference, _ = NotificationPreference.objects.get_or_create(user=request.user)
    if request.method == "PATCH":
        data = _parse_json_body(request)
        preference.receive_system = _coerce_bool(
            data.get("attendance"),
            default=preference.receive_system,
        )
        preference.receive_purchase = _coerce_bool(
            data.get("payments"),
            default=preference.receive_purchase,
        )
        preference.receive_coin = _coerce_bool(
            data.get("progress"),
            default=preference.receive_coin,
        )
        preference.receive_broadcast = _coerce_bool(
            data.get("general"),
            default=preference.receive_broadcast,
        )
        preference.save(
            update_fields=[
                "receive_system",
                "receive_purchase",
                "receive_coin",
                "receive_broadcast",
                "updated_at",
            ]
        )

    return JsonResponse(
        {
            "ok": True,
            "settings": _parent_notification_settings_payload(request.user),
        }
    )


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
@mobile_login_required
def mobile_profile(request):
    if request.user.role == "parent" or request.user.is_superuser:
        return mobile_parent_profile(request)
    user = request.user
    center = _request_center(request)
    if request.method == "PATCH":
        data = _parse_json_body(request)
        ism = str(data.get("ism") or "").strip()
        familya = str(data.get("familya") or "").strip()
        otchestvo = str(data.get("otchestvo") or "").strip()
        phone = str(data.get("phone") or "").strip()
        if ism:
            user.ism = ism
        if familya:
            user.familya = familya
        if otchestvo is not None:
            user.otchestvo = otchestvo
        if phone:
            user.telefon1 = phone
        user.save(update_fields=["ism", "familya", "otchestvo", "telefon1"])
        return JsonResponse({"ok": True, "user": _serialize_user(request, user)})
    return JsonResponse(
        {
            "ok": True,
            "user": _serialize_user(request, user),
            "center": _serialize_center(center),
        }
    )


@csrf_exempt
@require_POST
@mobile_login_required
def mobile_profile_avatar(request):
    """Avatar yuklash/o’chirish — barcha rollar uchun."""
    user = request.user
    if request.POST.get("clear") in ("true", "1", "yes"):
        if user.avatar:
            user.avatar.delete(save=False)
            user.avatar = None
            user.save(update_fields=["avatar"])
        return JsonResponse({"ok": True, "user": _serialize_user(request, user)})
    avatar_file = request.FILES.get("avatar")
    if not avatar_file:
        return _json_error("avatar fayl talab qilinadi", status=400)
    if avatar_file.size > 5 * 1024 * 1024:
        return _json_error("Fayl hajmi 5MB dan oshmasin", status=400)
    user.avatar = avatar_file
    user.save(update_fields=["avatar"])
    return JsonResponse({"ok": True, "user": _serialize_user(request, user)})


@csrf_exempt
@require_POST
@mobile_login_required
def mobile_auth_change_password(request):
    data = _parse_json_body(request)
    current_password = str(data.get("current_password") or "").strip()
    new_password = str(data.get("new_password") or "").strip()
    confirm_password = str(data.get("confirm_password") or "").strip()

    if not current_password or not new_password or not confirm_password:
        return _mobile_json_error("Barcha maydonlarni to‘ldiring", code="missing_fields")
    if not request.user.check_password(current_password):
        return _mobile_json_error("Joriy parol noto‘g‘ri", code="invalid_current_password")
    if len(new_password) < 8:
        return _mobile_json_error("Yangi parol kamida 8 ta belgidan iborat bo‘lishi kerak", code="password_too_short")
    if new_password != confirm_password:
        return _mobile_json_error("Parollar mos kelmadi", code="password_mismatch")

    request.user.set_password(new_password)
    request.user.save(update_fields=["password"])
    return JsonResponse({"ok": True, "message": "Parol muvaffaqiyatli yangilandi"})


@csrf_exempt
@require_POST
@mobile_login_required
def mobile_parent_children_add(request):
    if not request.user.is_superuser and request.user.role != "parent":
        return _mobile_json_error("Permission denied", status=403, code="permission_denied")

    data = _parse_json_body(request)
    child_code = _normalize_child_code(
        data.get("child_code") or data.get("code") or ""
    )
    if not child_code:
        return _mobile_json_error("Farzand kodini kiriting", code="child_code_required")

    center = _request_center(request)
    child = _find_student_by_child_code(child_code)
    if child is None:
        return _mobile_json_error(
            "Bu kod bo‘yicha o‘quvchi topilmadi",
            status=404,
            code="child_not_found",
        )
    if center is not None and child.center_id != center.id:
        return _mobile_json_error(
            "Bu o‘quvchi boshqa markazga tegishli",
            status=403,
            code="center_mismatch",
        )
    if request.user.children.filter(pk=child.pk).exists():
        return _mobile_json_error(
            "Bu farzand allaqachon qo‘shilgan",
            status=409,
            code="already_linked",
        )

    request.user.children.add(child)
    return JsonResponse(
        {
            "ok": True,
            "success": True,
            "message": "Farzand muvaffaqiyatli qo‘shildi",
            "child": _serialize_child_profile(request, child, center or child.center),
        },
        status=201,
    )


@csrf_exempt
@require_POST
@mobile_login_required
def mobile_notification_read(request, notification_id: int):
    qs = _notification_queryset_for_user(request.user)
    notification = get_object_or_404(qs, pk=notification_id)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return JsonResponse({"ok": True, "notification": _serialize_notification(notification)})


@require_GET
@mobile_login_required
def mobile_notifications(request):
    page = max(int(request.GET.get("page") or 1), 1)
    per_page = min(max(int(request.GET.get("per_page") or 20), 1), 100)
    qs = _notification_queryset_for_user(request.user).order_by("-created_at")
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


@csrf_exempt
@require_POST
@mobile_login_required
def mobile_notifications_read_all(request):
    updated_count = _notification_queryset_for_user(request.user).filter(is_read=False).update(is_read=True)
    return JsonResponse({"ok": True, "updated_count": updated_count})


@require_GET
@mobile_login_required
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
@mobile_login_required
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
@mobile_login_required
def mobile_store_products(request):
    center = _request_center(request)
    qs = Product.objects.filter(center=center, is_deleted=False).prefetch_related("rasmlar").order_by("-yaratilgan")
    return JsonResponse({"ok": True, "items": [_serialize_product(request, product) for product in qs[:100]]})


@require_GET
@mobile_login_required
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
@mobile_login_required
def mobile_chaqmoq_leaderboard(request):
    """Markazdagi barcha o'quvchilarning chaqmoq ball reytingi.

    Backend-dagi ``chaqmoq:reyting`` (chaqmoq/views.py: ``reyting``) sahifasi
    bilan bir xil ma'lumot manbasidan foydalanadi — shuning uchun mobil
    ilovadagi ro'yxat o'quv markaz panelidagi reyting ro'yxati bilan to'liq
    mos keladi (Ledger asosiy, LightningHistory fallback).
    """
    from chaqmoq.views import _get_balances_with_legacy_fallback

    if not request.user.is_superuser and request.user.role not in (
        "student",
        "parent",
        "teacher",
        "manager",
        "director",
    ):
        return _json_error("Permission denied", status=403, code="permission_denied")

    # Reyting kontekstidagi o'quvchini aniqlash (ota-ona uchun bola).
    me_user = request.user
    if request.user.role == "parent":
        student_id = request.GET.get("student_id")
        if student_id:
            child = request.user.children.filter(pk=student_id).first()
            if child is not None:
                me_user = child

    # Markazni aniqlash: sub-domen / X-Center-Slug yoki foydalanuvchi markazidan
    # foydalanamiz. Agar talabnoma kontekstida markaz yo'q-u, lekin "men"ning
    # markazi mavjud bo'lsa, undan foydalanamiz, shunda o'quvchi roziyajiy
    # ravishda o'z markazidagi reytingni ko'radi.
    center = _request_center(request) or getattr(me_user, "center", None)

    students_qs = User.objects.filter(role="student")
    if center is not None:
        students_qs = students_qs.filter(center=center)

    students = list(
        students_qs.values(
            "id",
            "ism",
            "familya",
            "otchestvo",
            "first_name",
            "last_name",
            "email",
        )
    )

    # Talabnoma egasi (me_user) ro'yxatda yo'q bo'lsa ham qo'shamiz —
    # masalan, role/markaz nomuvofiqligi tufayli filtrdan tushib qolgan
    # bo'lsa, foydalanuvchi reytingda hech bo'lmasa o'zini ko'radi.
    if me_user.role == "student" and me_user.id not in {row["id"] for row in students}:
        students.append(
            {
                "id": me_user.id,
                "ism": getattr(me_user, "ism", "") or "",
                "familya": getattr(me_user, "familya", "") or "",
                "otchestvo": getattr(me_user, "otchestvo", "") or "",
                "first_name": me_user.first_name or "",
                "last_name": me_user.last_name or "",
                "email": me_user.email or "",
            }
        )

    student_ids = [row["id"] for row in students]
    balance_map = _get_balances_with_legacy_fallback(student_ids, center=center)

    def _full_name(row: dict) -> str:
        # `User.full_name()` mantig'ini takrorlaymiz: ism/familya/otchestvo
        # birikmasi bo'sh bo'lsa, AbstractUser maydonlariga qaytamiz.
        parts = []
        seen = set()
        for raw in (row.get("ism"), row.get("familya"), row.get("otchestvo")):
            word = (raw or "").strip()
            if word and word.lower() not in ("none", "null") and word not in seen:
                parts.append(word)
                seen.add(word)
        composed = " ".join(parts).strip()
        if composed:
            return composed
        legacy = f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip()
        return legacy or (row.get("email") or "")

    rows = [
        {
            "id": row["id"],
            "full_name": _full_name(row),
            "balance": int(balance_map.get(row["id"], 0)),
        }
        for row in students
    ]
    rows.sort(key=lambda r: (-int(r["balance"]), (r["full_name"] or "").lower(), r["id"]))

    me_id = getattr(me_user, "id", None)
    me_rank = 0
    me_balance = 0
    full_items = []
    for index, row in enumerate(rows, start=1):
        is_me = row["id"] == me_id
        if is_me:
            me_rank = index
            me_balance = row["balance"]
        full_items.append(
            {
                "rank": index,
                "id": row["id"],
                "full_name": row["full_name"],
                "balance": row["balance"],
                "is_me": is_me,
            }
        )

    q = (request.GET.get("q") or "").strip().lower()
    if q:
        filtered_items = [it for it in full_items if q in (it["full_name"] or "").lower()]
    else:
        filtered_items = full_items

    try:
        page = max(int(request.GET.get("page") or 1), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.GET.get("per_page") or 20)
    except (TypeError, ValueError):
        per_page = 20
    per_page = max(5, min(per_page, 100))

    matched = len(filtered_items)
    total_pages = max(1, (matched + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    page_items = filtered_items[start : start + per_page]

    return JsonResponse(
        {
            "ok": True,
            "total": len(full_items),
            "matched": matched,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "me_rank": me_rank,
            "me_balance": me_balance,
            "items": page_items,
        }
    )


@require_GET
@mobile_login_required
def mobile_chaqmoq_student_detail(request, student_id: int):
    """Bitta o'quvchining barcha chaqmoq tarixi (admin paneldagi
    ``chaqmoq:student_detail`` sahifasi bilan bir xil ma'lumotlarni qaytaradi:
    yig'indilar (kelgan/ketgan/sof), beruvchilar bo'yicha statistika va
    sahifalangan ledger yozuvlari).
    """
    from django.db.models import Case, F, IntegerField, Value, When
    from django.db.models.functions import Abs, Coalesce

    center = _request_center(request)
    students_qs = User.objects.filter(role="student")
    if center is not None:
        students_qs = students_qs.filter(center=center)
    student = get_object_or_404(students_qs, pk=student_id)

    # Faqat shu markazga tegishli rolega ega bo'lganlar ko'ra oladi.
    if not request.user.is_superuser:
        viewer_role = getattr(request.user, "role", None)
        if viewer_role not in ("director", "manager", "teacher", "student", "parent"):
            return _json_error("Permission denied", status=403, code="permission_denied")
        viewer_center = getattr(request.user, "center", None)
        if center is None and viewer_center and viewer_center != student.center:
            return _json_error("Permission denied", status=403, code="permission_denied")

    led_qs = Ledger.objects.filter(student=student)
    if center is not None:
        led_qs = led_qs.filter(
            Q(group__center=center) | Q(rule__center=center) | Q(rule__center__isnull=True)
        )
    led_qs = led_qs.select_related("group", "rule", "beruvchi").order_by("-created_at", "-id")

    totals = led_qs.aggregate(
        total_plus=Coalesce(
            Sum(
                Case(
                    When(ball__gt=0, then=F("ball")),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            0,
        ),
        total_minus=Coalesce(
            Sum(
                Case(
                    When(ball__lt=0, then=Abs(F("ball"))),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            0,
        ),
        balance=Coalesce(Sum("ball"), 0),
    )

    teacher_stats_qs = (
        led_qs.values(
            "beruvchi__id",
            "beruvchi__ism",
            "beruvchi__familya",
            "beruvchi__role",
        )
        .annotate(
            coin_plus=Coalesce(
                Sum(
                    Case(
                        When(ball__gt=0, then=F("ball")),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                0,
            ),
            coin_minus=Coalesce(
                Sum(
                    Case(
                        When(ball__lt=0, then=Abs(F("ball"))),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                0,
            ),
        )
        .order_by("-coin_plus", "-coin_minus", "beruvchi__ism")
    )
    teacher_stats = []
    for row in teacher_stats_qs:
        ism = (row.get("beruvchi__ism") or "").strip()
        familya = (row.get("beruvchi__familya") or "").strip()
        full = " ".join(p for p in (ism, familya) if p) or "—"
        teacher_stats.append(
            {
                "id": row.get("beruvchi__id"),
                "full_name": full,
                "role": row.get("beruvchi__role") or "",
                "coin_plus": int(row.get("coin_plus") or 0),
                "coin_minus": int(row.get("coin_minus") or 0),
            }
        )

    try:
        page = max(int(request.GET.get("page") or 1), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.GET.get("per_page") or 20)
    except (TypeError, ValueError):
        per_page = 20
    per_page = max(5, min(per_page, 100))

    paginator = Paginator(led_qs, per_page)
    page_obj = paginator.get_page(page)

    items = []
    for entry in page_obj.object_list:
        rule_name = entry.rule_nom or (entry.rule.nom if entry.rule else "")
        items.append(
            {
                "id": entry.id,
                "points": entry.ball,
                "rule_name": rule_name,
                "group_name": entry.group.nom if entry.group else "",
                "giver_name": entry.beruvchi.get_full_name() if entry.beruvchi else "",
                "giver_role": getattr(entry.beruvchi, "role", "") if entry.beruvchi else "",
                "created_at": timezone.localtime(entry.created_at).isoformat()
                if entry.created_at
                else timezone.localtime(entry.sana).isoformat(),
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "student": {
                "id": student.id,
                "full_name": student.get_full_name(),
            },
            "totals": {
                "total_plus": int(totals.get("total_plus") or 0),
                "total_minus": int(totals.get("total_minus") or 0),
                "balance": int(totals.get("balance") or 0),
            },
            "teacher_stats": teacher_stats,
            "page": page_obj.number,
            "per_page": per_page,
            "total_pages": paginator.num_pages,
            "total_items": paginator.count,
            "items": items,
        }
    )


@require_GET
@mobile_login_required
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


@csrf_exempt
@require_POST
@mobile_login_required
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
@mobile_login_required
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
    # Admin paneldagi `qarzdorlar_home` ham `is_active=True` + arxivlanmagan
    # filterlarni qo'llaydi. `ensure_tuition_month`ni chaqirmaymiz: admin ham
    # uni chaqirmaydi va saqlangan TuitionMonth.fee_amountni ustiga yozish
    # qarz qiymatini buzib qo'yishi mumkin.
    enrollments = list(
        Enrollment.objects.filter(
            student=target_user,
            group__center=center,
            is_active=True,
            student__is_archived=False,
            group__is_archived=False,
            group__is_deleted=False,
        ).select_related("group")
    )

    snapshots = calculate_enrollment_debt_snapshots(enrollments, [current_month])

    items = []
    total_debt = 0
    total_due = 0
    total_paid = 0
    for enrollment in enrollments:
        snapshot = snapshots.get(enrollment.id, {})
        fee = int(snapshot.get("total_fee", 0) or 0)
        paid = int(snapshot.get("total_paid", 0) or 0)
        debt = int(snapshot.get("debt", 0) or 0)
        total_due += fee
        total_paid += paid
        total_debt += debt
        items.append(
            {
                "group_id": enrollment.group_id,
                "group_name": enrollment.group.nom,
                "month": current_month.isoformat(),
                "fee": fee,
                "paid": paid,
                "debt": debt,
            }
        )

    logger.info(
        "mobile_student_debt student_id=%s full_name=%s month=%s total_due=%s total_paid=%s debt_amount=%s response_total_debt=%s",
        target_user.id,
        target_user.get_full_name(),
        current_month.isoformat(),
        total_due,
        total_paid,
        total_debt,
        total_debt,
    )

    return JsonResponse(
        {
            "ok": True,
            "total_debt": total_debt,
            "total_due": total_due,
            "total_paid": total_paid,
            "items": items,
        }
    )


# ─────────────────────────────────────────────
# TEACHER PANEL — mobile API endpoints
# ─────────────────────────────────────────────

@require_GET
@mobile_login_required
def mobile_teacher_groups(request):
    """O'qituvchining barcha guruhlarini qaytaradi."""
    permission_error = _role_required(request, ("teacher", "director", "manager"))
    if permission_error:
        return permission_error
    center = _request_center(request)
    teacher = request.user
    if request.user.role in ("director", "manager") and request.GET.get("teacher_id"):
        teacher = get_object_or_404(User, pk=request.GET.get("teacher_id"), role="teacher", center=center)

    today = timezone.localdate()
    groups = (
        Group.objects.filter(center=center, oqituvchi=teacher, is_archived=False)
        .select_related("category_obj")
        .order_by("nom")
    )
    data = []
    for g in groups:
        total_students = Enrollment.objects.filter(group=g, is_active=True).count()
        attended_today = Attendance.objects.filter(
            group=g, date=today,
        ).filter(
            Q(present=True) | Q(forced=True) | Q(status="present")
        ).count()
        data.append({
            **_serialize_group(g),
            "student_count": total_students,
            "attended_today": attended_today,
        })
    return JsonResponse({"ok": True, "groups": data})


@require_GET
@mobile_login_required
def mobile_teacher_group_students(request, group_id: int):
    """Guruh o'quvchilari va bugungi davomatlari."""
    permission_error = _role_required(request, ("teacher", "director", "manager"))
    if permission_error:
        return permission_error
    center = _request_center(request)
    group = get_object_or_404(Group, pk=group_id, center=center)

    # Faqat o'z guruhi
    if request.user.role == "teacher" and group.oqituvchi_id != request.user.id:
        return _json_error("Permission denied", status=403, code="permission_denied")

    date_str = request.GET.get("date")
    att_date = _parse_iso_date(date_str) if date_str else timezone.localdate()

    enrollments = (
        Enrollment.objects.filter(group=group, is_active=True)
        .select_related("student")
        .order_by("student__ism", "student__familiya")
    )

    # O'sha kun davomat ma'lumotlari
    att_map = {}
    for att in Attendance.objects.filter(group=group, date=att_date):
        att_map[att.student_id] = att

    students = []
    for enr in enrollments:
        s = enr.student
        att = att_map.get(s.id)
        status = "none"
        if att:
            if att.present or att.forced or att.status == "present":
                status = "present"
            elif att.status == "absent_excused":
                status = "excused"
            else:
                status = "absent"
        students.append({
            "id": s.id,
            "full_name": s.get_full_name(),
            "phone": s.phone or "",
            "balance": _student_balance(s, center),
            "attendance_status": status,
        })

    return JsonResponse({
        "ok": True,
        "group": _serialize_group(group),
        "date": att_date.isoformat(),
        "students": students,
    })


@csrf_exempt
@require_POST
@mobile_login_required
def mobile_teacher_mark_attendance(request):
    """Davomat belgilash/o'chirish (toggle)."""
    permission_error = _role_required(request, ("teacher", "director", "manager"))
    if permission_error:
        return permission_error
    center = _request_center(request)
    data = _parse_json_body(request)
    group_id = data.get("group_id")
    student_id = data.get("student_id")
    date_str = data.get("date")
    mark_present = data.get("present")  # True/False yoki None (toggle)

    if not (group_id and student_id):
        return _json_error("group_id va student_id talab qilinadi", status=400)

    group = get_object_or_404(Group, pk=group_id, center=center)
    if request.user.role == "teacher" and group.oqituvchi_id != request.user.id:
        return _json_error("Permission denied", status=403, code="permission_denied")

    att_date = _parse_iso_date(date_str) if date_str else timezone.localdate()

    att, created = Attendance.objects.get_or_create(
        group_id=group_id,
        student_id=student_id,
        date=att_date,
        defaults={"teacher": request.user, "present": True},
    )
    if not created:
        if mark_present is None:
            att.present = not att.present
        else:
            att.present = bool(mark_present)
        att.teacher = request.user
        att.save()

    status = "present" if att.present else "absent"
    return JsonResponse({"ok": True, "present": att.present, "status": status, "date": att_date.isoformat()})


@require_GET
@mobile_login_required
def mobile_teacher_income(request):
    """O'qituvchi oylik daromadi."""
    permission_error = _role_required(request, ("teacher", "director", "manager"))
    if permission_error:
        return permission_error
    center = _request_center(request)
    teacher = request.user
    if request.user.role in ("director", "manager") and request.GET.get("teacher_id"):
        teacher = get_object_or_404(User, pk=request.GET.get("teacher_id"), role="teacher", center=center)

    today = timezone.localdate()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    from education.services.historical_finance_service import HistoricalFinanceService
    salary_data = HistoricalFinanceService.calculate_teacher_salary(teacher, year, month, center)
    expected = calculate_expected_income(teacher=teacher, year=year, month=month, center=center)

    # 12 oylik grafik
    yearly = HistoricalFinanceService.get_yearly_teacher_salary(teacher, year, center)

    current_max = expected.get("expected_income", 0)
    current_salary = int(salary_data.get("salary", 0))
    progress_pct = min(100, round(current_salary / current_max * 100)) if current_max > 0 else 0

    return JsonResponse({
        "ok": True,
        "year": year,
        "month": month,
        "salary": current_salary,
        "expected_income": current_max,
        "progress_pct": progress_pct,
        "is_locked": salary_data.get("is_locked", False),
        "details": salary_data.get("details", []),
        "yearly": yearly,
        "breakdown": expected.get("breakdown", []),
    })
