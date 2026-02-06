"""
Role-based permission decorators for views.

Bu decoratorlar har bir view'da ishlatiladi va middleware o'rniga
ancha sodda va tushunarli yechim beradi.
"""

from functools import wraps
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from django.contrib import messages


def role_required(*allowed_roles):
    """
    View faqat belgilangan rollarga ruxsat beradi.
    
    Usage:
        @role_required('admin', 'manager')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Login tekshir
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            
            # Superuser har doim ruxsat
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Foydalanuvchi rolini ol
            user_role = getattr(request.user, 'role', None)
            
            # Rol tekshir
            if user_role not in allowed_roles:
                # Ruxsat yo'q - dashboardga yo'naltir
                messages.warning(
                    request, 
                    "Sizda bu sahifaga kirish huquqi yo'q."
                )
                return redirect(_get_dashboard_for_role(user_role))
            
            # Ruxsat bor - davom ettir
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def staff_only(view_func):
    """
    Faqat admin va manager'lar uchun.
    
    Usage:
        @staff_only
        def admin_view(request):
            ...
    """
    return role_required('admin', 'manager')(view_func)


def teacher_and_staff(view_func):
    """
    Teacher, manager va admin'lar uchun.
    
    Usage:
        @teacher_and_staff
        def group_view(request):
            ...
    """
    return role_required('teacher', 'manager', 'admin')(view_func)


def _get_dashboard_for_role(role):
    """Rol uchun dashboard URL'ni qaytaradi"""
    
    dashboard_map = {
        'student': 'core:home',
        'parent': 'core:dashboard_parent',
        'teacher': 'core:home',
        'manager': 'core:home',
        'admin': 'core:home',
    }
    
    return dashboard_map.get(role, 'core:home')
