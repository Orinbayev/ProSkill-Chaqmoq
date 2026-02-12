"""
Custom authentication views for role-based redirects.
"""

from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch
from accounts.models import Center


class SecureLoginView(auth_views.LoginView):
    """
    Xavfsiz Login view - role-based redirects with subdomain support.
    """
    
    template_name = 'accounts/login.html'
    
    def get_success_url(self):
        user = self.request.user
        role = getattr(user, 'role', None)
        
        # 1. SuperAdmin (SaaS Owner)
        if user.is_superuser:
            # Check if visiting via subdomain
            host = self.request.get_host().split(':')[0].lower()
            if '.localhost' in host and not host.startswith('chaqmoqapp'):
                # Already on a subdomain, go to center home
                return reverse('core:home')
            
            # On root domain, try platform_global first, then fallback to accounts
            try:
                return reverse('platform_global:superadmin_dashboard')
            except NoReverseMatch:
                return reverse('accounts:superadmin_dashboard')
        
        # 2. Normal roles (Director, Teacher, Student, Parent)
        center = getattr(user, 'center', None)
        if center and center.slug:
            host_parts = self.request.get_host().split(':')
            port = f":{host_parts[1]}" if len(host_parts) > 1 else ""
            
            # Construct subdomain URL
            return f"http://{center.slug}.localhost{port}/"
        
        # Fallback
        return reverse('core:home')
    
    def get_redirect_url(self):
        return self.get_success_url()
