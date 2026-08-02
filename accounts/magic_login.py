"""
Bir-bosishli "Kirish havolasi" (magic login).

Maqsad: ota-ona/o'quvchi parol yoki botsiz, bitta havola orqali saytga kirsin,
so'ng o'ziga qulay parol o'rnatsin. Keyingi safar — telefon + parol.

Xavfsizlik:
- Token `django.core.signing` bilan imzolanadi (soxtalashtirib bo'lmaydi).
- `MAGIC_MAX_AGE` muddati bor (default 30 kun).
- Token foydalanuvchi parol-hashiga bog'langan: foydalanuvchi parol o'rnatishi
  bilan eski havola avtomatik kuchsizlanadi (bir martalik xarakter).
"""
from __future__ import annotations

from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.core import signing
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.views.decorators.http import require_http_methods

User = get_user_model()

MAGIC_SALT = "chaqmoq-magic-login-v1"
MAGIC_MAX_AGE = 60 * 60 * 24 * 30  # 30 kun
_BACKEND = "accounts.backends.EmailOrPhoneBackend"


def _password_stamp(user) -> str:
    """Parol o'zgarsa, eski havola kuchsizlansin uchun hashning bir qismi."""
    return (getattr(user, "password", "") or "")[-12:]


def make_magic_token(user) -> str:
    """Foydalanuvchi uchun imzolangan bir-bosishli kirish tokenini yaratadi."""
    return signing.dumps(
        {"uid": user.id, "s": _password_stamp(user)},
        salt=MAGIC_SALT,
    )


def make_magic_login_url(user, *, base_url: str = "") -> str:
    """To'liq magic login URL (bot/panel uchun)."""
    path = reverse("magic_login", kwargs={"token": make_magic_token(user)})
    base = (base_url or "").rstrip("/")
    return f"{base}{path}" if base else path


def read_magic_token(token: str, *, max_age: int = MAGIC_MAX_AGE):
    """Tokenni tekshirib, foydalanuvchini qaytaradi. Xato bo'lsa None."""
    try:
        data = signing.loads(token, salt=MAGIC_SALT, max_age=max_age)
    except signing.SignatureExpired:
        return None
    except signing.BadSignature:
        return None
    except Exception:
        return None

    if not isinstance(data, dict) or "uid" not in data:
        return None
    user = User.objects.filter(id=data["uid"], is_active=True, is_archived=False).first()
    if not user:
        return None
    # Parol o'zgargan bo'lsa — eski havola ishlamaydi.
    if data.get("s") != _password_stamp(user):
        return None
    return user


def _home_url_for(user) -> str:
    """Login'dan keyin rolga qarab bosh sahifa (SecureLoginView bilan bir xil)."""
    if getattr(user, "is_superuser", False):
        try:
            return reverse("platform_global:superadmin_dashboard")
        except NoReverseMatch:
            return "/platform/"
    center = getattr(user, "center", None)
    if center and getattr(center, "slug", None):
        return f"/{center.slug}/"
    try:
        return reverse("core:home")
    except NoReverseMatch:
        return "/"


def _is_ok_password(password: str) -> bool:
    if len(password or "") < 6:
        return False
    return any(ch.isalpha() for ch in password) and any(ch.isdigit() for ch in password)


def magic_login(request, token: str):
    """Havolani ochib avtomat kirish → parol o'rnatish sahifasiga o'tkazadi."""
    user = read_magic_token(token)
    if not user:
        return render(request, "accounts/magic_expired.html", status=400)

    login(request, user, backend=_BACKEND)
    try:
        from accounts.api_auth import record_activity
        record_activity(user, "Login via magic link", request=request)
    except Exception:
        pass

    request.session["magic_prompt_password"] = True
    return redirect("magic_set_password")


@require_http_methods(["GET", "POST"])
def magic_set_password(request):
    """Kirgan foydalanuvchi o'ziga qulay parol o'rnatadi (yoki 'Keyinroq')."""
    if not request.user.is_authenticated:
        return redirect("login")

    home_url = _home_url_for(request.user)

    if request.method == "POST":
        password = request.POST.get("password") or ""
        confirm = request.POST.get("confirm_password") or ""
        if password != confirm:
            return render(request, "accounts/magic_set_password.html",
                          {"error": "Parollar mos kelmadi.", "home_url": home_url})
        if not _is_ok_password(password):
            return render(request, "accounts/magic_set_password.html",
                          {"error": "Parol kamida 6 belgi, harf va raqamdan iborat bo'lsin.",
                           "home_url": home_url})
        user = request.user
        user.set_password(password)
        user.save(update_fields=["password"])
        try:
            from accounts.login_throttle import unlock_login_identifier
            unlock_login_identifier(user.email)
            if getattr(user, "phone_number", None):
                unlock_login_identifier(user.phone_number)
        except Exception:
            pass

        # Parol o'zgargach sessiya buzilmasligi uchun — foydalanuvchi tizimda qoladi.
        update_session_auth_hash(request, user)
        request.session.pop("magic_prompt_password", None)
        try:
            from accounts.api_auth import record_activity
            record_activity(user, "Password set via magic link", request=request)
        except Exception:
            pass
        return redirect(home_url)

    return render(request, "accounts/magic_set_password.html", {"home_url": home_url})
