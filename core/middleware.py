from django.shortcuts import redirect, render
from django.http import HttpResponseForbidden, Http404
from django.conf import settings
from accounts.models import Center
import logging

logger = logging.getLogger(__name__)

class TenantMiddleware:
    """
    Middleware to resolve the active center (tenant) from subdomain or session.
    Enforces strict isolation and prevents redirect loops.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        host_port = request.get_host() # e.g. "laylo.localhost:8000"
        host = host_port.split(':')[0].lower() # "laylo.localhost"
        
        # Parse Port
        port = None
        if ':' in host_port:
            try:
                port = host_port.split(':')[1]
            except IndexError:
                pass

        subdomain = None
        root_domain = "localhost" # Default fallback
        
        # 1. Robust Subdomain Parsing
        # Localhost / IP handling
        if "localhost" in host:
            # e.g. laylo.localhost -> parts=["laylo", "localhost"]
            parts = host.split('.')
            if len(parts) > 1 and parts[0] != "www":
                subdomain = parts[0]
                # Reconstruct root domain (e.g. localhost)
                root_domain = ".".join(parts[1:]) 
            else:
                root_domain = host
        elif host.replace('.', '').isdigit(): # IP Address
            root_domain = host
        else: # Production domains e.g. tenant.chaqmoq.uz
            parts = host.split('.')
            if len(parts) > 2: # tenant.domain.com
                subdomain = parts[0]
                root_domain = ".".join(parts[1:])
            else:
                root_domain = host

        # Initialize
        request.active_center = None
        request.center = None

        # 2. Resolve Tenant (Center)
        if subdomain:
            # Try finding center by slug (subdomain)
            center = Center.objects.filter(slug=subdomain, is_deleted=False).first()
            
            # ✅ FIX: If subdomain exists but Center NOT found
            if not center:
                # Avoid redirect loop if already on global picker or static
                if path.startswith('/static/') or path.startswith('/media/'):
                    return self.get_response(request)

                # A) If Superadmin -> Redirect to Global Picker
                if request.user.is_authenticated and request.user.is_superuser:
                    scheme = request.scheme
                    port_str = f":{port}" if port else ""
                    global_url = f"{scheme}://{root_domain}{port_str}/hisob/centers/?error=not_found&tenant={subdomain}"
                    return redirect(global_url)
                
                # B) Ordinary User or Guest -> Show Nice 404 Page (SaaS Style)
                return render(request, 'core/center_404.html', {
                    'subdomain': subdomain,
                    'root_domain': root_domain,
                    'host': host_port
                }, status=404)
            
            else:
                request.active_center = center
                request.center = center
        
        # 3. Handle Exempt Paths (Login, Static, Admin)
        # Allows access without Center check, BUT still populates request.center if found above
        EXEMPT_PREFIXES = (
            '/hisob/login/', 
            '/login/',       
            '/logout/', 
            '/static/', 
            '/media/', 
            '/admin/',       
            '/platform/',    # Superadmin Global Dashboard
            '/favicon.ico',
        )

        if any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
            return self.get_response(request)

        # 4. Access Enforcement & Flow Control
        if request.user.is_authenticated:
            # A) Superadmin Logic
            if request.user.is_superuser:
                # If on ROOT domain and active_center_id in session -> Redirect to Subdomain
                if not subdomain:
                    active_center_id = request.session.get("active_center_id")
                    if active_center_id:
                        center = Center.objects.filter(id=active_center_id, is_deleted=False).first()
                        if center:
                            scheme = request.scheme
                            port_str = f":{port}" if port else ""
                            return redirect(f"{scheme}://{center.slug}.{root_domain}{port_str}/")
                # Superadmin can access anything
                pass 
            
            # B) Normal User (Director/Teacher/Student)
            elif request.user.center:
                # 1. On Root Domain -> Redirect to User's Subdomain
                if not subdomain:
                    scheme = request.scheme
                    port_str = f":{port}" if port else ""
                    tenant_url = f"{scheme}://{request.user.center.slug}.{root_domain}{port_str}/"
                    return redirect(tenant_url)
                
                # 2. On WRONG Subdomain -> 403 Forbidden
                if request.active_center and request.active_center != request.user.center:
                    return HttpResponseForbidden(f"Sizga '{request.active_center.name}' markaziga kirish ruxsat etilmagan.")
                
                # 3. Blocked Status Check (Center Status OR Hard Expiry)
                is_blocked = False
                if request.active_center.status == 'BLOCKED':
                    is_blocked = True
                elif hasattr(request.active_center, 'subscription') and request.active_center.subscription:
                     if request.active_center.subscription.is_blocked():
                         is_blocked = True

                if is_blocked:
                    if not path.startswith('/hisob/billing/') and not path.startswith('/hisob/tolov/'):
                        return redirect('billing:plans')

            # C) User has no center (Orphan) -> 403
            else:
                 return HttpResponseForbidden("Siz hech qanday markazga biriktirilmagansiz.")
                 
        # 5. Unauthenticated User
        else:
            # Not logged in.
            # If on Tenant Subdomain -> Redirect to Login (on tenant domain)
            # If on Root Domain -> Redirect to Login (on root domain)
            # We already passed EXEMPT checks, so this is a protected page.
            
            login_url = settings.LOGIN_URL
            if not login_url.startswith('http'):
                 login_url = f"{settings.LOGIN_URL}"
            
            return redirect(f"{login_url}?next={request.path}")

        return self.get_response(request)
