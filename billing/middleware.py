# billing/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone

from .services import ensure_center_subscription


class SubscriptionMiddleware(MiddlewareMixin):
    """
    TenantMiddleware request.center ni topgandan keyin ishlaydi.
    Center BLOCKED bo‘lsa: faqat billing sahifalari ochiq.
    """

    def process_request(self, request):
        user = getattr(request, "user", None)
        center = getattr(request, "center", None)

        if not user or not user.is_authenticated:
            return None

        # superadmin bloklanmaydi (u platforma egasi)
        if user.is_superuser:
            return None

        if not center:
            return None

        sub = ensure_center_subscription(center)

        # allowed URL prefixlar:
        allowed_prefixes = [
            "/hisob/billing/",
            "/hisob/login/",
            "/logout/",
            "/admin/",
        ]

        if any(request.path.startswith(p) for p in allowed_prefixes):
            return None

        # blocked bo‘lsa redirect
        if sub.is_blocked():
            return redirect("billing:blocked")

        return None
