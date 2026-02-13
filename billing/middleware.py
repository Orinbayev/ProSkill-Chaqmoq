# billing/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone

from .services import ensure_center_subscription


class SubscriptionMiddleware(MiddlewareMixin):
    """
    TenantMiddleware request.center ni topgandan keyin ishlaydi.
    Center BLOCKED bo'lsa: faqat admin va manager uchun billing sahifalari majburiy.
    Student, parent, teacher bloklangan markazda ham o'z dashboardlarini ko'rishi mumkin.
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

        # ✅ Check both expiration AND student limit
        user_role = getattr(user, "role", None)
        
        is_blocked = sub and sub.is_blocked()
        is_over_limit = sub and sub.is_over_student_limit()
        
        if is_blocked or is_over_limit:
            # Faqat admin va manager'larni blocking sahifasiga yo'naltirish
            if user_role not in ("student", "parent", "teacher"):
                return redirect("billing:blocked")

        return None
