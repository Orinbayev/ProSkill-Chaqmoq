"""
Custom authentication views for role-based redirects.
"""

from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.urls import reverse


class SecureLoginView(auth_views.LoginView):
    """
    Xavfsiz Login view - ?next parametrini role-based filter qiladi.
    
    Login qilgandan keyin foydalanuvchi HAR DOIM o'z dashboardiga yo'naltiriladi,
    qaysi URL orqali kelganidan qat'iy nazar.
    """
    
    template_name = 'accounts/login.html'
    
    def get_success_url(self):
        """
        Login qilgandan keyin foydalanuvchini o'z dashboardiga yo'naltiradi.
        ?next parametrini IGNORE qiladi - bu xavfsizlik uchun muhim!
        """
        
        user = self.request.user
        role = getattr(user, 'role', None)
        
        # Superuser admin panelga
        if user.is_superuser:
            # Agar center tanlangan bo'lsa - core:home, aks holda superadmin dashboard
            center = getattr(self.request, 'center', None)
            if center:
                return reverse('core:home')
            return reverse('accounts:superadmin_dashboard')
        
        # Role-based dashboard mapping
        dashboard_map = {
            'student': 'core:home',  # home view role-based redirect qiladi
            'parent': 'core:dashboard_parent',
            'teacher': 'core:home',
            'manager': 'core:home',
            'admin': 'core:home',
        }
        
        redirect_url = dashboard_map.get(role, 'core:home')
        
        return reverse(redirect_url)
    
    def get_redirect_url(self):
        """
        Django's default LoginView uses this method.
        We override to ALWAYS use get_success_url() and ignore 'next'.
        """
        return self.get_success_url()
