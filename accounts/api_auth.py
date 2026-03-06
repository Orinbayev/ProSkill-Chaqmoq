from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from accounts.models import User
import json
from django.conf import settings
from django.utils import timezone

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





