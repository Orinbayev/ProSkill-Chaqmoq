# core/middleware_prod.py
"""
Production-ready TenantMiddleware with robust subdomain parsing
Handles localhost, Render.com, and custom domain scenarios
"""
from django.shortcuts import redirect, render
from django.http import HttpResponseForbidden, Http404
from django.conf import settings
from accounts.models import Center
import logging

logger = logging.getLogger(__name__)


class TenantMiddleware:
    """
    Multi-tenant middleware with production-ready subdomain parsing.
    
    Supports:
    - localhost: tenant.localhost:8000
    - Render: tenant.app.onrender.com (optional)
    - Production: tenant.chaqmoq.uz
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.root_domain = getattr(settings, 'ROOT_DOMAIN', 'localhost')

    def __call__(self, request):
        # ==================== HOST PARSING ====================
        host_port = request.get_host()
        host = host_port.split(':')[0].lower()
        
        # Parse port
        port = None
        if ':' in host_port:
            try:
                port = host_port.split(':')[1]
            except IndexError:
                pass

        subdomain = None
        parsed_root = self.root_domain
        
        # Determine subdomain based on environment
        subdomain, parsed_root = self._parse_subdomain(host)
        
        logger.debug(f"Host: {host}, Subdomain: {subdomain}, Root: {parsed_root}")
        
        # ==================== TENANT RESOLUTION ====================
        request.active_center = None
        request.center = None
        
        if subdomain:
            center = self._resolve_tenant(subdomain)
            
            if not center:
                # Tenant not found → 404 (NOT connection refused)
                return self._handle_tenant_not_found(
                    request, subdomain, parsed_root, host_port, port
                )
            
            # Tenant found
            request.active_center = center
            request.center = center
        
        # Fallback: Session-based center (for Render.com direct URL access)
        if not request.center:
            request.center = self._get_session_center(request)
            request.active_center = request.center
        
        # ==================== ACCESS CONTROL ====================
        return self._handle_access_control(request) or self.get_response(request)
    
    def _parse_subdomain(self, host):
        """
        Parse subdomain from host.
        
        Returns: (subdomain, root_domain)
        """
        # 1. Localhost (Development)
        if "localhost" in host or host in ["127.0.0.1", "0.0.0.0"]:
            parts = host.split('.')
            if len(parts) > 1 and parts[0] != "www":
                return parts[0], "localhost"
            return None, "localhost"
        
        # 2. Render.com direct URL
        if "onrender.com" in host:
            # Options:
            # A) tenant-app.onrender.com (if using this pattern)
            # B) app.onrender.com (no tenant - use session fallback)
            
            parts = host.split('-')
            if len(parts) > 1:
                # Assume first part is tenant if hyphen exists
                return parts[0], host
            
            # No subdomain on Render URL
            return None, host
        
        # 3. Production custom domain
        root_parts = self.root_domain.split('.')
        host_parts = host.split('.')
        
        if len(host_parts) > len(root_parts):
            # tenant.chaqmoq.uz → subdomain = "tenant"
            subdomain = host_parts[0]
            root = ".".join(host_parts[1:])
            return subdomain, root
        
        # No subdomain (apex domain)
        return None, host
    
    def _resolve_tenant(self, slug):
        """Find center by slug"""
        return Center.objects.filter(
            slug=slug,
            is_deleted=False
        ).first()
    
    def _get_session_center(self, request):
        """Get center from session (fallback for non-subdomain access)"""
        center_id = request.session.get("active_center_id")
        if center_id:
            return Center.objects.filter(
                id=center_id,
                is_deleted=False
            ).first()
        return None
    
    def _handle_tenant_not_found(self, request, subdomain, root_domain, host, port):
        """Handle case when subdomain exists but tenant not found"""
        
        # Exempt static/media
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return self.get_response(request)
        
        # Superadmin → redirect to platform
        if request.user.is_authenticated and request.user.is_superuser:
            scheme = request.scheme
            port_str = f":{port}" if port and port not in ['80', '443', None] else ""
            platform_url = f"{scheme}://{root_domain}{port_str}/platform/centers/"
            logger.info(f"Tenant '{subdomain}' not found, redirecting superadmin to {platform_url}")
            return redirect(platform_url)
        
        # Regular user/guest → Custom 404
        logger.warning(f"Tenant '{subdomain}' not found for host {host}")
        return render(request, 'core/center_404.html', {
            'subdomain': subdomain,
            'root_domain': root_domain,
            'host': host
        }, status=404)
    
    def _handle_access_control(self, request):
        """
        Handle authentication and authorization.
        Returns redirect/error response or None to continue.
        """
        path = request.path
        
        # Exempt paths that don't require tenant/auth
        EXEMPT_PREFIXES = (
            '/hisob/login/',
            '/login/',
            '/logout/',
            '/static/',
            '/media/',
            '/admin/',
            '/platform/',      # Superadmin platform
            '/favicon.ico',
            '/robots.txt',
            '/sitemap.xml',
        )
        
        if any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
            return None
        
        # User not authenticated
        if not request.user.is_authenticated:
            login_url = settings.LOGIN_URL
            return redirect(f"{login_url}?next={path}")
        
        # Superadmin can access anything
        if request.user.is_superuser:
            return None
        
        # Regular user access control
        user_center = getattr(request.user, 'center', None)
        
        if not user_center:
            # Orphan user (no center assigned)
            logger.error(f"User {request.user.email} has no center assigned")
            return HttpResponseForbidden(
                "Siz hech qanday markazga biriktirilmagansiz. "
                "Administrator bilan bog'laning."
            )
        
        # Check tenant isolation
        if request.active_center and request.active_center != user_center:
            logger.warning(
                f"User {request.user.email} (center: {user_center.slug}) "
                f"tried accessing {request.active_center.slug}"
            )
            return HttpResponseForbidden(
                f"Sizga '{request.active_center.name}' markaziga kirish ruxsat etilmagan."
            )
        
        # Check if center is blocked
        if request.active_center:
            is_blocked = False
            
            # Check status
            if request.active_center.status == 'BLOCKED':
                is_blocked = True
            
            # Check subscription
            if hasattr(request.active_center, 'subscription'):
                sub = request.active_center.subscription
                if sub and sub.is_blocked():
                    is_blocked = True
            
            # Redirect blocked users (except billing/payment paths)
            if is_blocked:
                if not path.startswith('/hisob/billing/') and not path.startswith('/hisob/tolov/'):
                    logger.info(f"Center {request.active_center.slug} is blocked, redirecting to billing")
                    return redirect('billing:plans')
        
        return None
