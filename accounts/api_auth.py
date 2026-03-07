from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from accounts.models import User
import json
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from accounts.utils import normalize_phone
from accounts.models import User, UserActivity

from accounts.utils_bot import send_telegram_message

def get_device_info(ua_string):
    if not ua_string: return "Noma'lum"
    ua = ua_string.lower()
    if 'iphone' in ua: return 'iPhone'
    if 'android' in ua: return 'Android'
    if 'windows' in ua: return 'Windows'
    if 'macintosh' in ua: return 'MacBook'
    return 'Brauzer'

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
    
    # Check API Secret
    secret = request.headers.get("X-API-SECRET")
    if secret != settings.API_SECRET:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
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
        
        return JsonResponse({"status": "ok", "user": user.email, "updated_phone": user.phone_number})
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def unlink_telegram_api(request):
    """Disconnect telegram_id from a specific user or all linked users."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    secret = request.headers.get("X-API-SECRET")
    if secret != settings.API_SECRET:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
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
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def get_bot_user_status(request):
    """Check if telegram_id is linked to any user(s)."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    secret = request.headers.get("X-API-SECRET")
    if secret != settings.API_SECRET:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
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
    
    secret = request.headers.get("X-API-SECRET")
    if secret != settings.API_SECRET:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
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
    secret = request.headers.get("X-API-SECRET")
    if secret != settings.API_SECRET:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
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
def get_bot_linked_users(request):
    """List of linked users with filters."""
    secret = request.headers.get("X-API-SECRET")
    if secret != settings.API_SECRET:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
    admin_tg_id = request.GET.get("admin_tg_id")
    if not is_bot_admin(admin_tg_id):
        return JsonResponse({"error": "Forbidden"}, status=403)

    role_filter = request.GET.get("role")
    users = User.objects.filter(is_telegram_linked=True).order_by("-date_joined")
    
    if role_filter and role_filter != "all":
        users = users.filter(role=role_filter)

    # Simplified pagination or limit
    limit = int(request.GET.get("limit", 20))
    offset = int(request.GET.get("offset", 0))
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
    secret = request.headers.get("X-API-SECRET")
    if secret != settings.API_SECRET:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
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
    secret = request.headers.get("X-API-SECRET")
    if secret != settings.API_SECRET:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
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
            u.ism, u.familya, u.get_role_display(), u.phone_number, 
            u.telegram_id, u.telegram_username or "", 
            u.date_joined.strftime("%Y-%m-%d"), u.date_joined.strftime("%H:%M")
        ])

    # Role specific sheets
    for role_key, role_name in Roles.choices:
        ws = wb.create_sheet(title=role_name[:30]) # Excel sheet title limit
        ws.append(headers)
        role_users = all_users.filter(role=role_key)
        for u in role_users:
            ws.append([
                u.ism, u.familya, u.get_role_display(), u.phone_number, 
                u.telegram_id, u.telegram_username or "", 
                u.date_joined.strftime("%Y-%m-%d"), u.date_joined.strftime("%H:%M")
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
    secret = request.headers.get("X-API-SECRET")
    if secret != settings.API_SECRET:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
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
    secret = request.headers.get("X-API-SECRET")
    if secret != settings.API_SECRET:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
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
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def get_parent_reports_data(request):
    """Fetch daily report data for parents."""
    secret = request.headers.get("X-API-SECRET")
    if secret != settings.API_SECRET:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
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





