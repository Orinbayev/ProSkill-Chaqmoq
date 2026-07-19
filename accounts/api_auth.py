from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.db import transaction
from django.core.cache import cache
from accounts.models import User
import json
import logging
import secrets
import string
from hmac import compare_digest
from django.conf import settings
from django.utils import timezone
from datetime import timedelta, datetime, date as date_cls

from accounts.utils import normalize_phone
from accounts.models import User, UserActivity

from accounts.utils_bot import send_telegram_message

logger = logging.getLogger(__name__)

_WEAK_API_SECRETS = {
    "",
    "unsafe-secret-key",
    "changeme",
    "7d8a9c1e2f3b4a5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2u3v4w5x6y7z8a9b",
}


def _require_api_secret(request):
    configured = str(getattr(settings, "API_SECRET", "") or "").strip()
    provided = str(request.headers.get("X-API-SECRET", "") or "")

    if configured in _WEAK_API_SECRETS or len(configured) < 32:
        logger.error("API_SECRET is missing/weak. Internal bot API request denied.")
        return JsonResponse({"error": "Server configuration error"}, status=503)

    if not compare_digest(provided, configured):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    return None


def _safe_excel_cell(value):
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


def get_device_info(ua_string):
    if not ua_string: return "Noma'lum"
    ua = ua_string.lower()
    if 'iphone' in ua: return 'iPhone'
    if 'android' in ua: return 'Android'
    if 'windows' in ua: return 'Windows'
    if 'macintosh' in ua: return 'MacBook'
    return 'Brauzer'


def _is_demo_user_context(user) -> bool:
    center = getattr(user, "center", None)
    return bool(
        getattr(user, "is_demo_user", False)
        or (center and getattr(center, "is_demo", False))
    )


def record_activity(user, action, request=None, device_info=None):
    ip = None
    ua = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        ua = request.META.get('HTTP_USER_AGENT')
    
    # Auto-generate device_info if it's empty but we have request
    if not device_info and ua:
        device_info = get_device_info(ua)

    now = timezone.now()
    
    UserActivity.objects.create(
        user=user,
        action=action,
        ip_address=ip,
        user_agent=ua,
        device_info=device_info,
        created_at=now
    )

    # Part 8: Security alerts
    # Demo users/centers must never trigger real Telegram messages.
    if _is_demo_user_context(user):
        return

    if user.telegram_id and user.is_telegram_linked:
        # Avoid redundant alerts: Don't send alert for "code requested" if you want to be "Ideal"
        # Just send for key events: Success login, Password change, Link
        critical_actions = ["Login successful", "Password changed", "Telegram account linked", "Failed login attempt detected"]
        
        if any(ca in action for ca in critical_actions):
            from django.utils.timezone import localtime
            local_time = localtime(now).strftime('%d.%m.%Y %H:%M')
            
            icon = "⚠️" if "Failed" in action else "✅"
            if "Login successful" in action: icon = "🔓"
            
            # Translate action to Uzbek for better UX
            action_uz = action
            if "Login successful" in action: action_uz = "Muvaffaqiyatli kirish"
            if "Failed login attempt" in action: action_uz = "Muvaffaqiyatsiz kirish urinishi"
            if "Password changed" in action: action_uz = "Parol o'zgartirildi"
            if "linked" in action: action_uz = "Telegram hisobga bog'landi"

            msg = (
                f"{icon} <b>{action_uz}</b>\n\n"
                f"IP: <code>{ip or 'Nomalum'}</code>\n"
                f"Vaqt: <code>{local_time}</code>\n"
            )
            if device_info:
                msg += f"Ma'lumot: <i>{device_info}</i>\n"
            
            msg += "\nAgar bu siz bo'lmasangiz, darhol parolingizni o'zgartiring."
            send_telegram_message(user.telegram_id, msg)

@csrf_exempt
def link_telegram_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error
    
    try:
        data = json.loads(request.body)
        code = data.get("code")
        tg_id = data.get("telegram_id")
        tg_username = data.get("telegram_username")
        phone_from_tg = normalize_phone(data.get("phone"))
        
        if not code or not tg_id or not phone_from_tg:
            return JsonResponse({"error": "Missing parameters"}, status=400)
        
        # Find user by code and check if not expired and not used
        user = User.objects.filter(
            reset_code=code, 
            reset_code_expire_at__gt=timezone.now(),
            reset_code_used=False
        ).first()
        
        if not user:
            return JsonResponse({"error": "Ulash kodi noto'g'ri yoki vaqti o'tib ketgan. Iltimos, saytdan yangi kod oling."}, status=404)

        # Current phone logic:

        # If the Telegram verified phone or ID already belongs to another user,
        # we will DISCONNECT it from the old user and MOVING it to the current one.
        # This is because the user has proven ownership via 6-digit code + TG Contact.
        
        # Handle multiple profiles logic: 
        # We NO LONGER disconnect others. We allow many users to share one TG ID.
        # This allows a parent and student to share a Telegram account.
            
        # 3. Finalize current user linking
        user.phone_number = phone_from_tg
        user.telegram_id = tg_id
        user.telegram_username = tg_username
        user.is_telegram_linked = True
        user.reset_code_used = True
        user.save()
        
        record_activity(user, "Telegram account linked", device_info=f"TG ID: {tg_id}")
        
        return JsonResponse(
            {
                "status": "ok",
                "user": user.email,
                "updated_phone": user.phone_number,
                "role": user.role,
                "role_display": user.get_role_display(),
                "full_name": user.get_full_name(),
            }
        )
        
    except Exception:
        logger.exception("link_telegram_api failed")
        return JsonResponse({"error": "Internal server error"}, status=500)


@csrf_exempt
def connect_parent_by_token_api(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error

    try:
        data = json.loads(request.body or "{}")
        token = data.get("token")
        tg_id = data.get("telegram_id")
        tg_username = data.get("telegram_username") or ""
        first_name = data.get("first_name") or ""
        last_name = data.get("last_name") or ""

        from accounts.services.parent_telegram_link import ParentLinkError, consume_parent_telegram_invite

        try:
            result = consume_parent_telegram_invite(
                raw_token=token,
                telegram_id=tg_id,
                telegram_username=tg_username,
                first_name=first_name,
                last_name=last_name,
            )
        except ParentLinkError as exc:
            return JsonResponse({"ok": False, "error": exc.message}, status=exc.status_code)

        linked_at = result.get("linked_at")
        return JsonResponse(
            {
                "ok": True,
                "student": result["student"],
                "parent": result["parent"],
                "linked_at": linked_at.isoformat() if linked_at else "",
                "linked_at_display": timezone.localtime(linked_at).strftime("%d.%m.%Y %H:%M") if linked_at else "",
            }
        )
    except Exception:
        logger.exception("connect_parent_by_token_api failed")
        return JsonResponse({"ok": False, "error": "Internal server error"}, status=500)

@csrf_exempt
def unlink_telegram_api(request):
    """Disconnect telegram_id from a specific user or all linked users."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error
    
    try:
        data = json.loads(request.body)
        tg_id = data.get("telegram_id")
        user_email = data.get("email") # To unlink a specific profile
        
        if not tg_id:
            return JsonResponse({"error": "Missing telegram_id"}, status=400)
        
        # Build queryset
        users_qs = User.objects.filter(telegram_id=tg_id, is_telegram_linked=True)
        if user_email:
            users_qs = users_qs.filter(email=user_email)
            
        count = users_qs.count()
        
        for user in users_qs:
            record_activity(user, "Telegram account unlinked (via Bot)", device_info=f"TG ID: {tg_id}")
            user.telegram_id = None
            user.is_telegram_linked = False
            user.save()
            
        return JsonResponse({"status": "ok", "unlinked_count": count})
    except Exception:
        logger.exception("unlink_telegram_api failed")
        return JsonResponse({"error": "Internal server error"}, status=500)

@csrf_exempt
def get_bot_user_status(request):
    """Check if telegram_id is linked to any user(s)."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error
    
    tg_id = request.GET.get("telegram_id")
    if not tg_id:
        return JsonResponse({"error": "Missing telegram_id"}, status=400)
    
    users = User.objects.filter(telegram_id=tg_id, is_telegram_linked=True)
    if users.exists():
        user_list = []
        for u in users:
            user_list.append({
                "id": u.id,
                "ism": u.ism,
                "familya": u.familya,
                "phone": u.phone_number,
                "role": u.role,
                "role_display": u.get_role_display(),
                "email": u.email
            })
        
        return JsonResponse({
            "status": "linked",
            "users": user_list,
            "count": len(user_list)
        })
    else:
        return JsonResponse({"status": "unlinked"})

@csrf_exempt
def get_bot_user_details(request):
    """Retrieve profile, activity and security history for a specific user via bot."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error
    
    tg_id = request.GET.get("telegram_id")
    user_email = request.GET.get("email") # To select specifically which profile
    
    if not tg_id:
        return JsonResponse({"error": "Missing telegram_id"}, status=400)
    
    users_qs = User.objects.filter(telegram_id=tg_id, is_telegram_linked=True)
    
    if user_email:
        user = users_qs.filter(email=user_email).first()
    else:
        user = users_qs.first() # Default to first if not specified
        
    if not user:
        return JsonResponse({"error": "User not found or not linked"}, status=404)
    
    # Profile
    profile = {
        "id": user.id,
        "ism": user.ism,
        "familya": user.familya,
        "full_name": user.get_full_name(),
        "phone": user.phone_number,
        "role": user.get_role_display(),
        "role_key": user.role,
        "email": user.email,
        "linked_at": user.date_joined.strftime("%d.%m.%Y")
    }
    
    # Activity & Security
    from django.utils.timezone import localtime
    activities_qs = user.activities.all()[:15]
    activities = []
    
    for act in activities_qs:
        # Translate action for bot display
        action_uz = act.action
        if "Login successful" in act.action: action_uz = "Muvaffaqiyatli kirish"
        if "Failed login attempt" in act.action: action_uz = "Muvaffaqiyatsiz kirish"
        if "Password reset code requested" in act.action: action_uz = "Parolni tiklash kodi"
        if "Login code requested" in act.action: action_uz = "Kirish kodi so'raldi"
        if "Telegram account linked" in act.action: action_uz = "Telegram bog'landi"
        if "Password changed" in act.action: action_uz = "Parol o'zgartirildi"

        activities.append({
            "action": action_uz,
            "raw_action": act.action,
            "created_at": localtime(act.created_at).strftime("%d.%m.%Y %H:%M"),
            "device": act.device_info or "Brauzer",
            "ip": act.ip_address or ".."
        })

    return JsonResponse({
        "profile": profile,
        "activities": activities
    })

# ==================================================
# ADMIN PANEL APIS
# ==================================================

from django.db.models import Count
from accounts.models import BotAdmin, BotSettings, AdminAuditLog, Roles
import openpyxl
from io import BytesIO
from django.http import HttpResponse

def is_bot_admin(tg_id):
    return BotAdmin.objects.filter(telegram_id=tg_id).exists()

@csrf_exempt
def get_bot_admin_dashboard(request):
    """Stats and Admin check."""
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error
    
    admin_tg_id = request.GET.get("admin_tg_id")
    if not is_bot_admin(admin_tg_id):
        return JsonResponse({"is_admin": False})

    # Stats
    total_linked = User.objects.filter(is_telegram_linked=True).count()
    
    role_stats = User.objects.filter(is_telegram_linked=True).values('role').annotate(count=Count('id'))
    roles_data = {r[0]: 0 for r in Roles.choices}
    for item in role_stats:
        roles_data[item['role']] = item['count']

    now = timezone.now()
    today_count = User.objects.filter(is_telegram_linked=True, date_joined__date=now.date()).count()
    week_start = now - timedelta(days=now.weekday())
    week_count = User.objects.filter(is_telegram_linked=True, date_joined__gte=week_start).count()
    month_count = User.objects.filter(is_telegram_linked=True, date_joined__month=now.month, date_joined__year=now.year).count()

    return JsonResponse({
        "is_admin": True,
        "stats": {
            "total": total_linked,
            "roles": roles_data,
            "today": today_count,
            "week": week_count,
            "month": month_count
        }
    })

@csrf_exempt
def get_bot_app_adoption(request):
    """Mobil ilova (ChaqmoqApp) qamrovi — har markazda nechta o'quvchi ilovadan foydalanyapti."""
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error

    admin_tg_id = request.GET.get("admin_tg_id")
    if not is_bot_admin(admin_tg_id):
        return JsonResponse({"is_admin": False})

    from core.services.app_adoption import center_app_adoption, app_adoption_totals
    rows = center_app_adoption()
    return JsonResponse({
        "is_admin": True,
        "summary": app_adoption_totals(rows),
        "centers": rows,
    })


@csrf_exempt
def get_bot_linked_users(request):
    """List of linked users with filters."""
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error
    
    admin_tg_id = request.GET.get("admin_tg_id")
    if not is_bot_admin(admin_tg_id):
        return JsonResponse({"error": "Forbidden"}, status=403)

    role_filter = request.GET.get("role")
    users = User.objects.filter(is_telegram_linked=True).order_by("-date_joined")
    
    if role_filter and role_filter != "all":
        users = users.filter(role=role_filter)

    # Simplified pagination or limit
    try:
        limit = int(request.GET.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20
    try:
        offset = int(request.GET.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    count = users.count()
    users = users[offset:offset+limit]

    data = []
    for u in users:
        data.append({
            "full_name": u.full_name(),
            "role": u.get_role_display(),
            "phone": u.phone_number,
            "tg_username": u.telegram_username or "Yo'q",
            "tg_id": u.telegram_id,
            "linked_at": u.date_joined.strftime("%Y-%m-%d %H:%M")
        })

    return JsonResponse({"users": data, "total": count})

@csrf_exempt
def get_bot_broadcast_list(request):
    """Get list of TG IDs for broadcasting."""
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error
    
    admin_tg_id = request.GET.get("admin_tg_id")
    if not is_bot_admin(admin_tg_id):
        return JsonResponse({"error": "Forbidden"}, status=403)

    role_filter = request.GET.get("role")
    users = User.objects.filter(is_telegram_linked=True, telegram_id__isnull=False)
    
    if role_filter and role_filter != "all":
        users = users.filter(role=role_filter)

    # Return unique telegram IDs
    tg_ids = list(users.values_list('telegram_id', flat=True).distinct())

    # Log action
    admin_user = BotAdmin.objects.get(telegram_id=admin_tg_id).user
    AdminAuditLog.objects.create(
        admin=admin_user,
        action_type="Broadcast Started",
        target_audience=role_filter or "all",
        details=f"Target count: {len(tg_ids)}"
    )

    return JsonResponse({"tg_ids": tg_ids})

@csrf_exempt
def get_bot_excel_export(request):
    """Generate Excel with role sheets."""
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error
    
    admin_tg_id = request.GET.get("admin_tg_id")
    if not is_bot_admin(admin_tg_id):
        return JsonResponse({"error": "Forbidden"}, status=403)

    wb = openpyxl.Workbook()
    
    # Sheet 1: All Users
    ws_all = wb.active
    ws_all.title = "Barcha Foydalanuvchilar"
    headers = ["Ism", "Familiya", "Rol", "Telefon", "Telegram ID", "Username", "Sana", "Vaqt"]
    ws_all.append(headers)
    
    all_users = User.objects.filter(is_telegram_linked=True).order_by("-date_joined")
    for u in all_users:
        ws_all.append([
            _safe_excel_cell(u.ism),
            _safe_excel_cell(u.familya),
            _safe_excel_cell(u.get_role_display()),
            _safe_excel_cell(u.phone_number),
            _safe_excel_cell(u.telegram_id),
            _safe_excel_cell(u.telegram_username or ""),
            _safe_excel_cell(u.date_joined.strftime("%Y-%m-%d")),
            _safe_excel_cell(u.date_joined.strftime("%H:%M")),
        ])

    # Role specific sheets
    for role_key, role_name in Roles.choices:
        ws = wb.create_sheet(title=role_name[:30]) # Excel sheet title limit
        ws.append(headers)
        role_users = all_users.filter(role=role_key)
        for u in role_users:
            ws.append([
                _safe_excel_cell(u.ism),
                _safe_excel_cell(u.familya),
                _safe_excel_cell(u.get_role_display()),
                _safe_excel_cell(u.phone_number),
                _safe_excel_cell(u.telegram_id),
                _safe_excel_cell(u.telegram_username or ""),
                _safe_excel_cell(u.date_joined.strftime("%Y-%m-%d")),
                _safe_excel_cell(u.date_joined.strftime("%H:%M")),
            ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Log action
    admin_user = BotAdmin.objects.get(telegram_id=admin_tg_id).user
    AdminAuditLog.objects.create(
        admin=admin_user,
        action_type="Excel Export",
        details="All users and role sheets generated"
    )

    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = 'attachment; filename=linked_users.xlsx'
    return response

@csrf_exempt
def manage_bot_admins_api(request):
    """List, Add, Remove bot admins."""
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error
    
    admin_tg_id = request.GET.get("admin_tg_id")
    if not is_bot_admin(admin_tg_id):
        return JsonResponse({"error": "Forbidden"}, status=403)

    action = request.GET.get("action", "list")
    
    if action == "list":
        admins = BotAdmin.objects.all().order_by("-created_at").select_related('user', 'added_by')
        data = []
        for a in admins:
            # Use User's telegram_username if available
            uname = a.username or a.user.telegram_username or "Yo'q"
            data.append({
                "full_name": a.user.full_name(),
                "tg_id": a.telegram_id,
                "username": uname,
                "added_by": a.added_by.full_name() if a.added_by else "Tizim",
                "created_at": a.created_at.strftime("%Y-%m-%d")
            })
        return JsonResponse({"admins": data})
    
    elif action == "add":
        target_tg_id = request.GET.get("target_tg_id")
        target_username = request.GET.get("target_username")
        
        # Find user by TG ID - they must be linked first
        user = User.objects.filter(telegram_id=target_tg_id, is_telegram_linked=True).first()
        if not user:
            return JsonResponse({"error": "Foydalanuvchi avval botdan ro'yxatdan o'tgan bo'lishi shart"}, status=400)
        
        if BotAdmin.objects.filter(telegram_id=target_tg_id).exists():
            return JsonResponse({"error": "Bu foydalanuvchi allaqachon admin"}, status=400)

        added_by = BotAdmin.objects.get(telegram_id=admin_tg_id).user
        
        # If no username passed, use user's telegram_username
        if not target_username or target_username in ["Noma'lum", "None"]:
            target_username = user.telegram_username

        BotAdmin.objects.create(
            user=user,
            telegram_id=target_tg_id,
            username=target_username,
            added_by=added_by
        )
        AdminAuditLog.objects.create(
            admin=added_by,
            action_type="Admin Added",
            details=f"Target: {user.full_name()} ({target_tg_id})"
        )
        return JsonResponse({"status": "ok"})

    elif action == "remove":
        target_tg_id = request.GET.get("target_tg_id")
        if target_tg_id == admin_tg_id:
             return JsonResponse({"error": "O'zingizni o'chira olmaysiz"}, status=400)
        
        BotAdmin.objects.filter(telegram_id=target_tg_id).delete()
        admin_user = BotAdmin.objects.get(telegram_id=admin_tg_id).user
        AdminAuditLog.objects.create(
            admin=admin_user,
            action_type="Admin Removed",
            details=f"Target TG ID: {target_tg_id}"
        )
        return JsonResponse({"status": "ok"})

    return JsonResponse({"error": "Invalid action"}, status=400)

@csrf_exempt
def bot_settings_api(request):
    """Get/Set bot settings (e.g. report time)."""
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error
    
    admin_tg_id = request.GET.get("admin_tg_id")
    if not is_bot_admin(admin_tg_id):
        return JsonResponse({"error": "Forbidden"}, status=403)

    if request.method == "GET":
        report_time = BotSettings.get_val("parent_report_time", "20:00")
        return JsonResponse({"parent_report_time": report_time})

    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            new_time = data.get("parent_report_time")
            if not new_time:
                return JsonResponse({"error": "Missing time"}, status=400)
            
            # Simple validation HH:MM
            import re
            if not re.match(r"^\d{2}:\d{2}$", new_time):
                return JsonResponse({"error": "Format xato (HH:MM)"}, status=400)

            setting, _ = BotSettings.objects.get_or_create(key="parent_report_time")
            old_val = setting.value
            setting.value = new_time
            setting.save()

            admin_user = BotAdmin.objects.get(telegram_id=admin_tg_id).user
            AdminAuditLog.objects.create(
                admin=admin_user,
                action_type="Settings Changed",
                details=f"Parent report time: {old_val} -> {new_time}"
            )
            return JsonResponse({"status": "ok"})
        except Exception:
            logger.exception("bot_settings_api update failed")
            return JsonResponse({"error": "Invalid request"}, status=400)

    return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def get_parent_reports_data(request):
    """Fetch daily report data for parents."""
    auth_error = _require_api_secret(request)
    if auth_error:
        return auth_error
    
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    from chaqmoq.models import Ledger
    # Get all ledger entries for today
    today_ledgers = Ledger.objects.filter(created_at__gte=today_start).select_related('student', 'beruvchi', 'rule')
    
    if not today_ledgers.exists():
        return JsonResponse({"reports": {}})

    # Group ledgers by student
    student_reports = {}
    for entry in today_ledgers:
        sid = entry.student.id
        if sid not in student_reports:
            student_reports[sid] = {
                "name": entry.student.full_name(),
                "added": [],
                "removed": [],
                "total_today_plus": 0,
                "total_today_minus": 0,
                "current_total": entry.student.chaqmoq
            }
        
        detail = {
            "ball": abs(entry.ball),
            "reason": entry.rule_nom or (entry.rule.nom if entry.rule else "Sabab ko'rsatilmadi"),
            "by": entry.beruvchi.full_name() if entry.beruvchi else "Tizim"
        }
        
        if entry.ball > 0:
            student_reports[sid]["added"].append(detail)
            student_reports[sid]["total_today_plus"] += entry.ball
        else:
            student_reports[sid]["removed"].append(detail)
            student_reports[sid]["total_today_minus"] += abs(entry.ball)

    # Now find parents for these students who are linked to TG
    parent_messages = {}
    
    for sid, report in student_reports.items():
        try:
            student = User.objects.get(id=sid)
            for parent in student.parents.filter(is_telegram_linked=True, telegram_id__isnull=False):
                if parent.telegram_id not in parent_messages:
                    parent_messages[parent.telegram_id] = []
                parent_messages[parent.telegram_id].append(report)
        except User.DoesNotExist:
            continue

    # Return data for bot
    return JsonResponse({"reports": parent_messages})


# ─── Family bot — telefon orqali avtorizatsiya ─────────────────────────────
# Rate limit faqat dastlabki qidirishga (find-by-phone) qo'llaniladi —
# tasdiqlash/qo'shish/login bosqichlari trusted hisoblanadi.
_FAMILY_RATE_LIMIT_WINDOW = 120  # 2 daqiqa
_FAMILY_RATE_LIMIT_MAX = 30  # 2 daqiqada 30 marta — keng chegaralangan
_FAMILY_PASSWORD_LENGTH = 10
_FAMILY_PASSWORD_ALPHABET = string.ascii_letters + string.digits


def _family_rate_limit_check(phone: str, telegram_id: str) -> bool:
    """Faqat find-by-phone uchun. Boshqa endpointlar trusted."""
    key_parts = []
    if phone:
        key_parts.append(f"family_rl:phone:{phone}")
    if telegram_id:
        key_parts.append(f"family_rl:tg:{telegram_id}")
    if not key_parts:
        return True
    try:
        for key in key_parts:
            count = cache.get(key, 0) + 1
            cache.set(key, count, timeout=_FAMILY_RATE_LIMIT_WINDOW)
            if count > _FAMILY_RATE_LIMIT_MAX:
                return False
    except Exception:
        logger.exception("family rate limit cache error")
        # Cache muammo bo'lsa — bloklamaymiz
        return True
    return True


def _gen_family_password() -> str:
    return "".join(secrets.choice(_FAMILY_PASSWORD_ALPHABET) for _ in range(_FAMILY_PASSWORD_LENGTH))


def _build_login_url(user) -> str:
    """User markazi asosida login URL qaytarish."""
    base = str(getattr(settings, "PUBLIC_BASE_URL", "") or "").rstrip("/")
    if not base:
        base = "https://chaqmoqapp.uz"
    center = getattr(user, "center", None)
    if center and getattr(center, "slug", None):
        return f"{base}/{center.slug}/"
    return f"{base}/"


def _serialize_match_user(user) -> dict:
    center = getattr(user, "center", None)
    return {
        "id": user.id,
        "full_name": (f"{user.familya} {user.ism}").strip() or user.email,
        "role": user.role,
        "role_label": user.get_role_display() if hasattr(user, "get_role_display") else user.role,
        "center": getattr(center, "name", "") if center else "",
        "center_slug": getattr(center, "slug", "") if center else "",
    }


_BOT_DISABLED_MSG = "Bu o'quv markazi uchun Telegram bot yoqilmagan. Iltimos, markazingizga murojaat qiling."


def _center_bot_allowed(center) -> bool:
    """Markaz uchun Telegram (Oila) bot yoqilganmi?"""
    return bool(center and getattr(center, "telegram_bot_enabled", False))


def _find_parent_user_by_phone(phone: str):
    """Telefon orqali parent rolidagi User'ni topish."""
    if not phone:
        return None
    return (
        User.objects.filter(role="parent", is_active=True, is_archived=False)
        .filter(Q(phone_number=phone) | Q(telefon1=phone) | Q(telefon2=phone))
        .select_related("center")
        .first()
    )


@csrf_exempt
@require_POST
def family_find_by_phone_api(request):
    """
    Telefon raqami orqali ota-ona/o'quvchi yozuvini topish.

    POST: {phone, role, telegram_id, telegram_username}
    Response (ok=true): {
        ok: true,
        matches: [
            {id, full_name, role, role_label, center, center_slug},
            ...
        ]
    }
    """
    secret_err = _require_api_secret(request)
    if secret_err:
        return secret_err

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Noto'g'ri JSON."}, status=400)

    phone_raw = (payload.get("phone") or "").strip()
    role = (payload.get("role") or "").strip().lower()
    telegram_id = str(payload.get("telegram_id") or "").strip()
    telegram_username = (payload.get("telegram_username") or "") or None

    if role not in ("parent", "student"):
        return JsonResponse({"ok": False, "error": "Noto'g'ri rol."}, status=400)
    if not phone_raw:
        return JsonResponse({"ok": False, "error": "Telefon raqami bo'sh."}, status=400)

    phone = normalize_phone(phone_raw)
    if not phone:
        return JsonResponse({"ok": False, "error": "Telefon raqami noto'g'ri."}, status=400)

    if not _family_rate_limit_check(phone, telegram_id):
        return JsonResponse(
            {"ok": False, "error": "Juda ko'p urinish. Biroz kuting va qayta urinib ko'ring."},
            status=429,
        )

    phone_q = Q(phone_number=phone) | Q(telefon1=phone) | Q(telefon2=phone)

    if role == "student":
        # Bevosita o'quvchi yozuvi
        students = list(
            User.objects.filter(role="student", is_active=True, is_archived=False)
            .filter(phone_q)
            .select_related("center")[:10]
        )
        if not students:
            return JsonResponse(
                {"ok": False, "error": "Sizning raqamingiz bilan o'quvchi topilmadi."},
                status=404,
            )
        allowed = [s for s in students if _center_bot_allowed(s.center)]
        if not allowed:
            return JsonResponse({"ok": False, "error": _BOT_DISABLED_MSG}, status=403)
        return JsonResponse({"ok": True, "matches": [_serialize_match_user(s) for s in allowed]})

    # role == "parent": ikki yo'l — User.role=parent + children M2M, yoki student.parents
    matches = []

    # 1) Mavjud Parent useri bo'lsa, uning bola ro'yxatini olamiz
    parent_users = list(
        User.objects.filter(role="parent", is_active=True, is_archived=False)
        .filter(phone_q)
        .prefetch_related("children", "children__center")
    )
    seen_child_ids = set()
    disabled_hit = False  # bot o'chirilgan markazда farzand topildimi?
    for parent in parent_users:
        for child in parent.children.filter(is_active=True, is_archived=False):
            if child.id in seen_child_ids:
                continue
            seen_child_ids.add(child.id)
            if not _center_bot_allowed(child.center):
                disabled_hit = True
                continue
            matches.append(_serialize_match_user(child))

    # 2) Student modelida `parents` reverse M2M — "Ota-ona telefoni" sifatida saqlangan students
    #    (telefon1/telefon2 maydonlariga ota-ona telefoni yozilgan bo'lishi mumkin)
    if not matches:
        candidate_students = list(
            User.objects.filter(role="student", is_active=True, is_archived=False)
            .filter(phone_q)
            .select_related("center")[:20]
        )
        for child in candidate_students:
            if child.id in seen_child_ids:
                continue
            seen_child_ids.add(child.id)
            if not _center_bot_allowed(child.center):
                disabled_hit = True
                continue
            matches.append(_serialize_match_user(child))

    if not matches:
        if disabled_hit:
            return JsonResponse({"ok": False, "error": _BOT_DISABLED_MSG}, status=403)
        return JsonResponse(
            {
                "ok": False,
                "error": "Sizning raqamingiz tizimda topilmadi yoki farzand biriktirilmagan.",
            },
            status=404,
        )

    # Audit (eng birinchi parent ga yozamiz, agar bor bo'lsa; yo'q bo'lsa skip)
    if parent_users and telegram_id:
        try:
            UserActivity.objects.create(
                user=parent_users[0],
                action=f"Family bot: telefon orqali qidirish (matches={len(matches)}, tg={telegram_id})",
            )
        except Exception:
            logger.exception("family_find_by_phone audit log failed")

    parent_user_id = parent_users[0].id if parent_users else None
    parent_center_slug = ""
    if parent_users and parent_users[0].center:
        parent_center_slug = parent_users[0].center.slug or ""

    return JsonResponse(
        {
            "ok": True,
            "matches": matches,
            "parent_user_id": parent_user_id,
            "parent_center_slug": parent_center_slug,
            "can_add_children": bool(parent_user_id),
        }
    )


@csrf_exempt
@require_POST
def family_issue_credentials_api(request):
    """
    Tanlangan o'quvchi yoki ota-ona uchun yangi parol yaratib qaytarish.

    POST: {user_id, role, telegram_id}
    Response (ok=true): {
        ok: true,
        user: {full_name, role, role_label, center},
        credentials: {email, password},
        login_url: "https://chaqmoqapp.uz/<slug>/"
    }
    """
    secret_err = _require_api_secret(request)
    if secret_err:
        return secret_err

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Noto'g'ri JSON."}, status=400)

    try:
        user_id = int(payload.get("user_id") or 0)
    except (TypeError, ValueError):
        user_id = 0

    role = (payload.get("role") or "").strip().lower()
    telegram_id = str(payload.get("telegram_id") or "").strip()

    if user_id <= 0:
        return JsonResponse({"ok": False, "error": "Noto'g'ri user_id."}, status=400)
    if role not in ("parent", "student"):
        return JsonResponse({"ok": False, "error": "Noto'g'ri rol."}, status=400)

    try:
        user = User.objects.select_related("center").get(
            id=user_id, is_active=True, is_archived=False
        )
    except User.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Foydalanuvchi topilmadi."}, status=404)

    if user.role not in ("student", "parent"):
        return JsonResponse(
            {"ok": False, "error": "Bu foydalanuvchi uchun login berilmaydi."},
            status=403,
        )

    new_password = _gen_family_password()

    try:
        with transaction.atomic():
            user.set_password(new_password)
            # Eski reset kodini ham bekor qilamiz (xavfsizlik)
            user.reset_code = None
            user.reset_code_expire_at = None
            user.reset_code_used = False
            user.reset_attempts = 0
            user.save(
                update_fields=[
                    "password",
                    "reset_code",
                    "reset_code_expire_at",
                    "reset_code_used",
                    "reset_attempts",
                ]
            )
            try:
                UserActivity.objects.create(
                    user=user,
                    action=f"Family bot: yangi parol berildi (tg={telegram_id})",
                )
            except Exception:
                logger.exception("family_issue_credentials audit log failed")
    except Exception:
        logger.exception("family_issue_credentials failed for user_id=%s", user_id)
        return JsonResponse(
            {"ok": False, "error": "Server xatosi. Keyinroq qayta urinib ko'ring."},
            status=500,
        )

    # Bir-bosishli "Kirish havolasi" — parolsiz, botsiz. Token yangi parol
    # hashiga bog'lanadi, foydalanuvchi o'z parolini o'rnatishi bilan kuchsizlanadi.
    from accounts.magic_login import make_magic_login_url
    base = str(getattr(settings, "PUBLIC_BASE_URL", "") or "").rstrip("/") or "https://chaqmoqapp.uz"
    magic_url = make_magic_login_url(user, base_url=base)

    return JsonResponse(
        {
            "ok": True,
            "user": _serialize_match_user(user),
            "credentials": {
                "email": user.email,
                "password": new_password,
            },
            "login_url": _build_login_url(user),
            "magic_url": magic_url,
        }
    )


@csrf_exempt
@require_POST
def family_confirm_link_api(request):
    """
    Telefon orqali tasdiqlangan foydalanuvchini Telegram bilan bog'lash.

    POST: {user_id, role, telegram_id, telegram_username}
    Response: {ok: true, profile: {id, email, role, full_name}}
    """
    secret_err = _require_api_secret(request)
    if secret_err:
        return secret_err

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Noto'g'ri JSON."}, status=400)

    try:
        user_id = int(payload.get("user_id") or 0)
    except (TypeError, ValueError):
        user_id = 0
    role = (payload.get("role") or "").strip().lower()
    telegram_id = str(payload.get("telegram_id") or "").strip()
    telegram_username = (payload.get("telegram_username") or "") or None

    if user_id <= 0:
        return JsonResponse({"ok": False, "error": "Noto'g'ri user_id."}, status=400)
    if role not in ("parent", "student"):
        return JsonResponse({"ok": False, "error": "Noto'g'ri rol."}, status=400)
    if not telegram_id:
        return JsonResponse({"ok": False, "error": "Telegram ID bo'sh."}, status=400)

    try:
        user = User.objects.select_related("center").get(
            id=user_id, is_active=True, is_archived=False
        )
    except User.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Foydalanuvchi topilmadi."}, status=404)

    if user.role != role:
        return JsonResponse(
            {"ok": False, "error": "Foydalanuvchi roli mos kelmadi."},
            status=403,
        )

    try:
        with transaction.atomic():
            update_fields = []
            if user.telegram_id != telegram_id:
                user.telegram_id = telegram_id
                update_fields.append("telegram_id")
            if user.telegram_username != telegram_username:
                user.telegram_username = telegram_username
                update_fields.append("telegram_username")
            if not user.is_telegram_linked:
                user.is_telegram_linked = True
                update_fields.append("is_telegram_linked")
            if update_fields:
                user.save(update_fields=update_fields)

            try:
                UserActivity.objects.create(
                    user=user,
                    action=f"Family bot: profil tasdiqlandi (tg={telegram_id})",
                )
            except Exception:
                logger.exception("family_confirm_link audit log failed")
    except Exception:
        logger.exception("family_confirm_link failed user_id=%s", user_id)
        return JsonResponse({"ok": False, "error": "Server xatosi."}, status=500)

    return JsonResponse(
        {
            "ok": True,
            "profile": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "role_label": user.get_role_display() if hasattr(user, "get_role_display") else user.role,
                "full_name": (f"{user.familya} {user.ism}").strip() or user.email,
            },
        }
    )


def _parse_user_birth_date(raw: str):
    """Foydalanuvchi yozgan sanani DD.MM.YYYY yoki YYYY-MM-DD formatda qabul qilish."""
    if not raw:
        return None
    raw = raw.strip().replace("/", ".").replace("-", ".")
    parts = raw.split(".")
    if len(parts) != 3:
        return None
    try:
        a, b, c = (int(p) for p in parts)
    except ValueError:
        return None
    # Format aniqlanadi: agar birinchi qism 4 xonali bo'lsa YYYY.MM.DD
    if a > 1900:
        year, month, day = a, b, c
    else:
        day, month, year = a, b, c
    try:
        return date_cls(year, month, day)
    except ValueError:
        return None


@csrf_exempt
@require_POST
def family_student_by_name_api(request):
    """
    O'quvchi uchun ism + tug'ilgan sana orqali yozuvni topish.
    Telefon raqami yo'q yoki noto'g'ri bo'lganda alternativ yo'l.

    POST: {name_query, birth_date, telegram_id}
    Response: {ok: true, matches: [{id, full_name, role, role_label, center, center_slug}]}
    """
    secret_err = _require_api_secret(request)
    if secret_err:
        return secret_err

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Noto'g'ri JSON."}, status=400)

    name_query = " ".join(str(payload.get("name_query") or "").split()).strip()
    birth_date_raw = str(payload.get("birth_date") or "").strip()
    telegram_id = str(payload.get("telegram_id") or "").strip()

    if len(name_query) < 3:
        return JsonResponse({"ok": False, "error": "Ismingizni kamida 3 harfdan iborat yozing."}, status=400)

    parsed_date = _parse_user_birth_date(birth_date_raw)
    if not parsed_date:
        return JsonResponse(
            {"ok": False, "error": "Tug'ilgan sana noto'g'ri formatda. Masalan: 15.03.2010"},
            status=400,
        )

    # Rate limit faqat dastlabki qidirishga
    if not _family_rate_limit_check("", telegram_id):
        return JsonResponse({"ok": False, "error": "Juda ko'p urinish. Biroz kuting."}, status=429)

    qs = (
        User.objects.filter(
            role="student",
            is_active=True,
            is_archived=False,
            birth_date=parsed_date,
        )
        .select_related("center")
    )

    # Ism familiya bo'yicha qidirish
    tokens = [t for t in name_query.split() if t]
    name_filter = Q()
    for tok in tokens:
        name_filter &= Q(ism__icontains=tok) | Q(familya__icontains=tok) | Q(otchestvo__icontains=tok)
    qs = qs.filter(name_filter)

    found = list(qs[:10])
    allowed = [s for s in found if _center_bot_allowed(s.center)]
    if not allowed:
        if found:  # topildi, lekin markaz uchun bot o'chirilgan
            return JsonResponse({"ok": False, "error": _BOT_DISABLED_MSG}, status=403)
        return JsonResponse(
            {
                "ok": False,
                "error": "Sizning ismingiz va tug'ilgan sanangiz bilan o'quvchi topilmadi. "
                "Markazga murojaat qiling.",
            },
            status=404,
        )

    return JsonResponse({"ok": True, "matches": [_serialize_match_user(s) for s in allowed]})


@csrf_exempt
@require_POST
def family_search_child_api(request):
    """
    Ota-ona uchun farzand qidirish (ism orqali, parent markazi ichida).

    POST: {parent_user_id, name_query, telegram_id}
    Response: {ok: true, results: [{id, full_name, center, has_birth_date}]}
    """
    secret_err = _require_api_secret(request)
    if secret_err:
        return secret_err

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Noto'g'ri JSON."}, status=400)

    try:
        parent_user_id = int(payload.get("parent_user_id") or 0)
    except (TypeError, ValueError):
        parent_user_id = 0
    name_query = " ".join(str(payload.get("name_query") or "").split()).strip()
    telegram_id = str(payload.get("telegram_id") or "").strip()

    if parent_user_id <= 0:
        return JsonResponse({"ok": False, "error": "Ota-ona profili topilmadi."}, status=400)
    if len(name_query) < 3:
        return JsonResponse({"ok": False, "error": "Kamida 3 harf yozing."}, status=400)

    try:
        parent = User.objects.select_related("center").get(
            id=parent_user_id, role="parent", is_active=True, is_archived=False
        )
    except User.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Ota-ona topilmadi."}, status=404)

    qs = (
        User.objects.filter(role="student", is_active=True, is_archived=False)
        .select_related("center")
    )
    # Faqat ota-ona o'z markazi ichida qidiradi (xavfsizlik)
    if parent.center_id:
        qs = qs.filter(center_id=parent.center_id)

    # Ism familiya bo'yicha qidirish (har ikkala maydonda)
    tokens = [t for t in name_query.split() if t]
    name_filter = Q()
    for tok in tokens:
        name_filter &= Q(ism__icontains=tok) | Q(familya__icontains=tok) | Q(otchestvo__icontains=tok)
    qs = qs.filter(name_filter)

    # Allaqachon biriktirilgan bolalarni chiqarib tashlash
    existing_ids = list(parent.children.values_list("id", flat=True))
    if existing_ids:
        qs = qs.exclude(id__in=existing_ids)

    results = []
    for s in qs[:15]:
        results.append(
            {
                "id": s.id,
                "full_name": (f"{s.familya} {s.ism}").strip() or s.email,
                "center": s.center.name if s.center else "",
                "has_birth_date": bool(s.birth_date),
            }
        )

    if not results:
        return JsonResponse(
            {"ok": False, "error": "Hech qanday farzand topilmadi. Ismni to'g'ri yozganingizni tekshiring."},
            status=404,
        )

    return JsonResponse({"ok": True, "results": results})


@csrf_exempt
@require_POST
def family_add_child_api(request):
    """
    Ota-ona o'ziga farzandni biriktirish (tug'ilgan sana orqali tasdiqlash).

    POST: {parent_user_id, child_id, birth_date, telegram_id}
    Response: {ok: true, child: {id, full_name, center}}
    """
    secret_err = _require_api_secret(request)
    if secret_err:
        return secret_err

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Noto'g'ri JSON."}, status=400)

    try:
        parent_user_id = int(payload.get("parent_user_id") or 0)
        child_id = int(payload.get("child_id") or 0)
    except (TypeError, ValueError):
        parent_user_id = child_id = 0
    birth_date_raw = str(payload.get("birth_date") or "").strip()
    telegram_id = str(payload.get("telegram_id") or "").strip()

    if parent_user_id <= 0 or child_id <= 0:
        return JsonResponse({"ok": False, "error": "Ma'lumot to'liq emas."}, status=400)

    parsed_date = _parse_user_birth_date(birth_date_raw)
    if not parsed_date:
        return JsonResponse(
            {"ok": False, "error": "Tug'ilgan sana noto'g'ri formatda. Masalan: 15.03.2010"},
            status=400,
        )

    try:
        parent = User.objects.select_related("center").get(
            id=parent_user_id, role="parent", is_active=True, is_archived=False
        )
        child = User.objects.select_related("center").get(
            id=child_id, role="student", is_active=True, is_archived=False
        )
    except User.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Foydalanuvchi topilmadi."}, status=404)

    # Markaz tekshiruvi (xavfsizlik)
    if parent.center_id and child.center_id and parent.center_id != child.center_id:
        return JsonResponse(
            {"ok": False, "error": "Bu farzand boshqa markazda. Qo'shib bo'lmadi."},
            status=403,
        )

    # Allaqachon biriktirilgan bo'lsa
    if parent.children.filter(id=child.id).exists():
        return JsonResponse(
            {"ok": False, "error": "Bu farzand allaqachon ro'yxatingizda."},
            status=409,
        )

    # Tug'ilgan sana tasdiqlash (xavfsizlik)
    if not child.birth_date:
        return JsonResponse(
            {
                "ok": False,
                "error": "Bu farzandning tug'ilgan sanasi tizimda yo'q. Markazga murojaat qiling.",
            },
            status=409,
        )
    if child.birth_date != parsed_date:
        return JsonResponse(
            {"ok": False, "error": "Tug'ilgan sana mos kelmadi. Iltimos, qaytadan tekshiring."},
            status=403,
        )

    try:
        with transaction.atomic():
            parent.children.add(child)
            try:
                UserActivity.objects.create(
                    user=parent,
                    action=f"Family bot: yangi farzand biriktirildi (child_id={child.id}, tg={telegram_id})",
                )
            except Exception:
                logger.exception("family_add_child audit log failed")
    except Exception:
        logger.exception("family_add_child failed parent=%s child=%s", parent_user_id, child_id)
        return JsonResponse({"ok": False, "error": "Server xatosi."}, status=500)

    return JsonResponse(
        {
            "ok": True,
            "child": {
                "id": child.id,
                "full_name": (f"{child.familya} {child.ism}").strip() or child.email,
                "center": child.center.name if child.center else "",
            },
        }
    )
