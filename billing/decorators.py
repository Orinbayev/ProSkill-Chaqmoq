# billing/decorators.py
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse

from .services import get_feature_flags, ensure_center_subscription, check_subscription


def require_active_subscription(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and user.is_superuser:
            return view_func(request, *args, **kwargs)

        center = getattr(request, "center", None)
        if not center:
            messages.error(request, "Center topilmadi.")
            return redirect("core:home")

        sub = ensure_center_subscription(center)
        if sub.is_blocked():
            return redirect("billing:blocked")

        return view_func(request, *args, **kwargs)
    return _wrapped


def require_feature(feature_name: str):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if user and user.is_authenticated and user.is_superuser:
                return view_func(request, *args, **kwargs)

            center = getattr(request, "center", None)
            if not center:
                if _is_api(request):
                    return JsonResponse({"ok": False, "error": "Center topilmadi."}, status=403)
                messages.error(request, "Center topilmadi.")
                return redirect("core:home")

            flags = get_feature_flags(center)
            if feature_name not in flags:
                if _is_api(request):
                    return JsonResponse(
                        {"ok": False, "error": "Bu xususiyat sizning tarifingizda mavjud emas.",
                         "feature": feature_name, "upgrade_url": "/billing/plans/"},
                        status=403,
                    )
                messages.warning(
                    request,
                    "Bu bo’lim sizning tarifingizda mavjud emas. Tarifni yangilang."
                )
                return redirect("billing:plans")

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def _is_api(request) -> bool:
    """AJAX yoki JSON API so’rovmi?"""
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.headers.get("Accept", "").startswith("application/json")
        or request.path.startswith("/api/")
        or "/api/" in request.path
    )


def require_pro(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and user.is_superuser:
            return view_func(request, *args, **kwargs)

        sub = check_subscription(user)
        plan_code = (sub.plan.code or "").upper() if sub and sub.plan else "FREE"
        has_pro_access = bool(sub and plan_code != "FREE")
        if has_pro_access:
            return view_func(request, *args, **kwargs)

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"error": "PRO subscription required."}, status=403)

        messages.warning(request, "Bu bo'lim PRO obuna uchun mavjud.")
        return redirect("billing:plans")

    return _wrapped
