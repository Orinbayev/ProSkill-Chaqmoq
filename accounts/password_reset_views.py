from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from accounts.models import User
from django.utils import timezone
from datetime import timedelta
import secrets
import string
from .utils_bot import send_telegram_message
from django.contrib.auth import login
from .utils import normalize_phone
from .api_auth import record_activity

GENERIC_RESET_MESSAGE = "Agar ma'lumotlar mos bo'lsa, tasdiqlash kodi yuboriladi."


def _is_strong_password(password: str) -> bool:
    if len(password or "") < 8:
        return False
    return any(ch.isalpha() for ch in password) and any(ch.isdigit() for ch in password)


def send_code_to_telegram(user):
    """
    Generates 6-digit code and sends to linked Telegram.
    Checks rate limits and connection status.
    """
    center = getattr(user, "center", None)
    if getattr(user, "is_demo_user", False) or (center and getattr(center, "is_demo", False)):
        return False, "Demo markaz uchun Telegram kod yuborish o'chirilgan."

    if not user.telegram_id or not user.is_telegram_linked:
        return False, "Bu hisob uchun Telegram hali ulanmagan."
        
    # Rate limit: Max 3 requests in 10 minutes per user
    now = timezone.now()
    if user.reset_last_attempt and (now - user.reset_last_attempt).total_seconds() < 600:
        if user.reset_attempts >= 3:
            return False, "Ko'p urinishlar qilindi. 10 daqiqadan so'ng qayta urinib ko'ring."
    else:
        user.reset_attempts = 0 # reset attempts if > 10 mins
        
    # Generate random 6-digit code
    code = ''.join(secrets.choice(string.digits) for _ in range(6))
    user.reset_code = code
    user.reset_code_expire_at = timezone.now() + timedelta(minutes=5)
    user.reset_code_used = False
    user.reset_attempts += 1
    user.reset_last_attempt = now
    # update_fields: o'qituvchi post_save signalidagi N+1 (barcha davomat) oldini oladi
    user.save(update_fields=["reset_code", "reset_code_expire_at", "reset_code_used",
                             "reset_attempts", "reset_last_attempt"])
    
    msg = f"<code>Code: {code}</code>\n\nUshbu kod 5 daqiqa davomida amal qiladi."
    
    # Inline keyboard with copy button (supported in API 7.3+)
    reply_markup = {
        "inline_keyboard": [[
            {"text": "📋 Copy", "copy_text": {"text": code}}
        ]]
    }
    
    if send_telegram_message(user.telegram_id, msg, reply_markup=reply_markup):
        return True, "Tasdiqlash kodi Telegram botingizga yuborildi."
    return False, "Kodni yuborishda xatolik yuz berdi. Bot ishlayotganiga ishonch hosil qiling."

def forgot_password_init(request):
    """Choice: Email or Phone to reset."""
    if request.method == "POST":
        method = request.POST.get("method")
        identifier = request.POST.get("identifier", "").strip()
        
        if method == "phone":
            phone = normalize_phone(identifier)
            users = User.objects.filter(phone_number=phone)
            
            if users.exists():
                # Store potential users in session
                request.session['auth_potential_user_ids'] = list(users.values_list('id', flat=True))
                request.session['auth_flow_type'] = 'reset'
                request.session['auth_identifier'] = phone
                return redirect("forgot_password_verify_choice")
            messages.success(request, GENERIC_RESET_MESSAGE)
        
        elif method == "email":
            user = User.objects.filter(email__iexact=identifier).first()
            if user:
                # Direct reset for unique email
                success, msg = send_code_to_telegram(user)
                if success:
                    request.session['auth_user_id'] = user.id
                    request.session['auth_flow_type'] = 'reset'
                    record_activity(user, "Password reset code requested (via Email)", request=request)
                    messages.success(request, msg)
                    return redirect("forgot_password_verify")
            messages.success(request, GENERIC_RESET_MESSAGE)
            
    return render(request, "accounts/forgot_password_init.html")

def phone_login_init(request):
    """New flow: Login directly via Telegram code."""
    if request.method == "POST":
        phone_raw = request.POST.get("phone", "").strip()
        phone = normalize_phone(phone_raw)
        
        users = User.objects.filter(phone_number=phone)
        if users.exists():
            request.session['auth_potential_user_ids'] = list(users.values_list('id', flat=True))
            request.session['auth_flow_type'] = 'login'
            request.session['auth_identifier'] = phone
            return redirect("forgot_password_verify_choice")
        messages.success(request, GENERIC_RESET_MESSAGE)
            
    return render(request, "accounts/phone_login_init.html")

def forgot_password_verify_choice(request):
    """Page to select WHICH user profile is logging in/resetting."""
    user_ids = request.session.get('auth_potential_user_ids')
    if not user_ids:
        return redirect("login")
        
    users = User.objects.filter(id__in=user_ids)
    return render(request, "accounts/forgot_password_verify_choice.html", {"users": users})

def forgot_password_confirm_choice(request):
    """User selected a profile, now send code."""
    if request.method == "POST":
        user_id = request.POST.get("user_id")
        user_ids = request.session.get('auth_potential_user_ids', [])

        try:
            user_id_int = int(user_id)
        except (TypeError, ValueError):
            messages.error(request, "Xavfsizlik yuzasidan xatolik yuz berdi.")
            return redirect("forgot_password_verify_choice")

        if user_id_int in user_ids:
            user = get_object_or_404(User, id=user_id)
            success, msg = send_code_to_telegram(user)
            if success:
                request.session['auth_user_id'] = user.id
                # Keep auth_flow_type from session
                record_activity(user, f"{request.session.get('auth_flow_type')} code requested after profile selection", request=request)
                request.session['auth_verify_attempts'] = 0
                messages.success(request, msg)
                return redirect("forgot_password_verify")
            else:
                messages.error(request, msg)
        else:
            messages.error(request, "Xavfsizlik yuzasidan xatolik yuz berdi.")
            
    return redirect("forgot_password_verify_choice")

def forgot_password_verify(request):
    """Shared code verification page."""
    user_id = request.session.get('auth_user_id')
    flow_type = request.session.get('auth_flow_type')
    
    if not user_id:
        return redirect("login")
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        attempts = int(request.session.get("auth_verify_attempts", 0))
        if attempts >= 5:
            messages.error(request, "Juda ko'p noto'g'ri urinish. Qayta kod olib urinib ko'ring.")
            return render(request, "accounts/forgot_password_verify.html", {"phone": user.phone_number or "..."})

        if user.reset_code == code and user.reset_code_expire_at and user.reset_code_expire_at > timezone.now() and not user.reset_code_used:
            user.reset_code_used = True
            user.save(update_fields=["reset_code_used"])
            request.session['auth_verify_attempts'] = 0
            
            if flow_type == 'login':
                # Direct login
                user.backend = 'accounts.backends.EmailOrPhoneBackend'
                login(request, user)
                record_activity(user, "Login successful (via Telegram Code)", request=request)
                del request.session['auth_user_id']
                del request.session['auth_flow_type']
                return redirect("/") # Redirect to home
            else:
                # Reset password flow
                request.session['auth_verified'] = True
                return redirect("forgot_password_set")
        else:
            request.session['auth_verify_attempts'] = attempts + 1
            messages.error(request, "Kod noto'g'ri yoki eskirgan.")
            
    # Try to mask phone for display
    display_phone = user.phone_number or "..."
    return render(request, "accounts/forgot_password_verify.html", {"phone": display_phone})

def forgot_password_set(request):
    """Password change after verification."""
    user_id = request.session.get('auth_user_id')
    verified = request.session.get('auth_verified')
    
    if not user_id or not verified:
        return redirect("forgot_password_init")
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == "POST":
        password = request.POST.get("password")
        confirm = request.POST.get("confirm_password")
        
        if password == confirm and _is_strong_password(password):
            user.set_password(password)
            user.save(update_fields=["password"])
        try:
            from accounts.login_throttle import unlock_login_identifier
            unlock_login_identifier(user.email)
            if getattr(user, "phone_number", None):
                unlock_login_identifier(user.phone_number)
        except Exception:
            pass

            record_activity(user, "Password changed successfully", request=request)
            
            # Cleanup session
            del request.session['auth_user_id']
            del request.session['auth_verified']
            if 'auth_flow_type' in request.session:
                del request.session['auth_flow_type']
                
            messages.success(request, "Parolingiz muvaffaqiyatli o'zgartirildi.")
            return redirect("login")
        else:
            messages.error(request, "Parol kamida 8 belgidan iborat bo'lib, harf va raqamni o'z ichiga olishi kerak.")
            
    return render(request, "accounts/forgot_password_set.html")
