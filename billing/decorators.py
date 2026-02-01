# billing/decorators.py
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

from .services import get_feature_flags, ensure_center_subscription


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
                messages.error(request, "Center topilmadi.")
                return redirect("core:home")

            flags = get_feature_flags(center)
            if feature_name not in flags:
                messages.warning(request, "Bu bo‘lim faqat PRO tarifda mavjud. Tarifni yangilang.")
                return redirect("billing:plans")

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
