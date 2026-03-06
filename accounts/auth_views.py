"""
Custom authentication views for role-based redirects.
"""

from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch
from django.conf import settings
from accounts.models import Center
from accounts.api_auth import record_activity


class SecureLoginView(auth_views.LoginView):
    """
    Xavfsiz Login view - role-based redirects with subdomain support.
    """
    
    template_name = 'accounts/login.html'
    
    def form_invalid(self, form):
        response = super().form_invalid(form)
        email = form.data.get('username') # Login form uses 'username' field for email/phone
        from accounts.models import User
        user = User.objects.filter(email__iexact=email).first()
        if not user:
             # Try phone
             user = User.objects.filter(phone_number=email).first()
             
        if user:
            record_activity(user, "Failed login attempt detected", request=self.request)
        return response
    
    def form_valid(self, form):
        response = super().form_valid(form)
        record_activity(self.request.user, "Login successful (Website)", request=self.request)
        return response
    
    def dispatch(self, request, *args, **kwargs):
        """
        ✅ FIX: Prevent login redirect loop
        If user is already authenticated, redirect to home
        """
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return super().dispatch(request, *args, **kwargs)
    
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
            
            # On root domain, go to platform
            try:
                return reverse('platform_global:superadmin_dashboard')
            except NoReverseMatch:
                return reverse('core:home')
        
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
