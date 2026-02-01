# core/middleware.py
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse, NoReverseMatch
from accounts.models import Center


def _safe_reverse(*names: str, default: str = "/") -> str:
    """
    Bir nechta url name'larni ketma-ket reverse qilib ko‘radi.
    Birortasi ishlasa -> o‘sha url
    Hech biri ishlamasa -> default
    """
    for name in names:
        try:
            return reverse(name)
        except NoReverseMatch:
            continue
        except Exception:
            continue
    return default


class TenantMiddleware:
    """
    - request.center ni session.active_center_id bo‘yicha o‘rnatadi
    - superadmin active center tanlamagan bo‘lsa -> center pickerga yuboradi
    - redirect loop bo‘lmasin (allowed paths)
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # ✅ URL'larni xavfsiz topamiz (bir nechta name sinab ko‘ramiz)
        p_center_picker = _safe_reverse("accounts:center_picker", default="/hisob/center-picker/")
        p_center_switch = _safe_reverse("accounts:center_switch", default="/hisob/center-switch/")

        # logout ba'zan "logout", ba'zan "accounts:logout" bo'lishi mumkin
        p_logout = _safe_reverse("logout", "accounts:logout", default="/logout/")

        # login ba'zan "login", ba'zan "accounts:login"
        p_login = _safe_reverse("login", "accounts:login", default="/accounts/login/")

        p_home = "/"
        p_superadmin = _safe_reverse("accounts:superadmin_dashboard", default="/hisob/superadmin/")

        allowed_prefixes = (
            p_center_picker,
            p_center_switch,
            p_logout,
            p_login,
            p_home,
            p_superadmin,
            "/hisob/api/",
            "/hisob/centers/",
            "/admin/",
            "/static/",
            "/media/",
        )

        path = request.path or "/"

        # default
        request.center = None

        if request.user.is_authenticated:
            # ✅ oddiy userlar: center userdan olinadi
            if not request.user.is_superuser:
                request.center = getattr(request.user, "center", None)

            else:
                # ✅ superadmin: center sessiondan olinadi
                active_center_id = request.session.get("active_center_id")
                if active_center_id:
                    request.center = Center.objects.filter(id=active_center_id, status="ACTIVE").first()
                else:
                    # ✅ active center yo‘q -> faqat allow-list bo‘lmasa pickerga yuboramiz
                    if not path.startswith(allowed_prefixes):
                        messages.info(request, "Davom etish uchun avval Active Center tanlang.")
                        return redirect(p_center_picker)

        return self.get_response(request)
