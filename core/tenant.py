# core/tenant.py
from django.http import Http404
from django.shortcuts import redirect

def get_request_center(request):
    """Active centerni requestdan yoki userdan oladi"""
    return getattr(request, "center", None) or getattr(getattr(request, "user", None), "center", None)

def require_center(request):
    """
    request.center bo'lmasa - superadmin bo'lsa pickerga, boshqalar bo'lsa 404.
    """
    center = get_request_center(request)
    if center is None:
        user = getattr(request, "user", None)
        if user and user.is_authenticated and user.is_superuser:
            return redirect("platform_global:superadmin_dashboard")
        raise Http404("Center not found")
    return center

def ensure_obj_center(request, obj_center_id):
    """
    obj.center_id bilan request.center.id mosligini tekshiradi.
    Global obyektlarga (center=None) ruxsat beriladi.
    """
    center = require_center(request)
    if obj_center_id and obj_center_id != center.id:
        raise Http404("Object not found")
    return True
