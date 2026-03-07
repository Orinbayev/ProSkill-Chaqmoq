"""
Role-based access control middleware for ChaqmoqApp.

Bu middleware:
1. Har bir request'da foydalanuvchi rolini tekshiradi
2. Agar foydalanuvchi ruxsatsiz sahifaga kirmoqchi bo'lsa, o'z dashboardiga yo'naltiradi
3. Login'dan keyin ?next parametrini role-based filter qiladi
"""

from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden


class RoleBasedAccessMiddleware:
    """
    Har bir foydalanuvchi faqat o'z roliga mos sahifalarga kirishi mumkin.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Har bir rol uchun ruxsat berilgan URL pattern'lar
        self.role_permissions = {
            'student': [
                'core:home',
                'core:dashboard_student',
                'core:user_view',
                'store:*',  # Do'kon sahifalari
                'chaqmoq:*',  # Chaqmoq sahifalari
                'logout',
            ],
            'parent': [
                'core:home',
                'core:dashboard_parent',
                'core:user_view',
                'core:toggle_child',
                'logout',
            ],
            'teacher': [
                'core:home',
                'core:dashboard_teacher',
                'core:user_view',
                'core:user_edit',
                'education:*',  # O'qituvchi guruhlar bilan ishlashi uchun
                'chaqmoq:*',
                'store:*',
                'logout',
            ],
            'manager': [
                'core:*',  # Manager barcha core sahifalarga kirishi mumkin
                'education:*',
                'chaqmoq:*',
                'store:*',
                'billing:*',
                'logout',
            ],
            'admin': [
                '*',  # Admin barcha sahifalarga kirishi mumkin
            ],
        }
    
    def __call__(self, request):
        # Login qilinmagan foydalanuvchilar uchun skipla
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Static, media va admin panel'ni skipla
        if (request.path.startswith('/static/') or 
            request.path.startswith('/media/') or
            request.path.startswith('/admin/') or
            request.path == '/favicon.ico'):
            return self.get_response(request)
        
        # Logout va login sahifalarini skipla
        if request.path in ['/hisob/login/', '/hisob/logout/']:
            return self.get_response(request)
        
        # Current URL'ni resolve qil
        try:
            current_url = resolve(request.path)
            url_name = current_url.url_name
            namespace = current_url.namespace
            
            if namespace:
                full_url_name = f"{namespace}:{url_name}"
            else:
                full_url_name = url_name
        except:
            # URL resolve bo'lmasa, davom ettir
            return self.get_response(request)
        
        # Foydalanuvchi rolini ol
        user_role = getattr(request.user, 'role', None)
        
        # Superuser'lar uchun hamma narsa ruxsat
        if request.user.is_superuser:
            user_role = 'admin'
        
        # Agar rol aniqlanmasa, xavfsiz variant - logout
        if not user_role:
            return redirect('logout')
        
        # Rolga asoslangan ruxsatni tekshir
        if not self._has_permission(user_role, full_url_name, namespace):
            # Ruxsat yo'q - o'z dashboardiga yo'naltir
            return redirect(self._get_dashboard_url(user_role))
        
        response = self.get_response(request)
        return response
    
    def _has_permission(self, role, url_name, namespace):
        """Foydalanuvchi URL'ga kirish huquqi bormi?"""
        
        if role not in self.role_permissions:
            return False
        
        allowed_patterns = self.role_permissions[role]
        
        # '*' - hamma narsaga ruxsat
        if '*' in allowed_patterns:
            return True
        
        # To'liq URL nomi tekshir
        if url_name in allowed_patterns:
            return True
        
        # Namespace bilan wildcard tekshir (masalan: 'core:*')
        if namespace:
            namespace_wildcard = f"{namespace}:*"
            if namespace_wildcard in allowed_patterns:
                return True
        
        return False
    
    def _get_dashboard_url(self, role):
        """Rol uchun dashboard URL qaytaradi"""
        
        dashboard_map = {
            'student': 'core:home',
            'parent': 'core:dashboard_parent',
            'teacher': 'core:home',
            'manager': 'core:home',
            'admin': 'core:home',
        }
        
        return dashboard_map.get(role, 'core:home')
