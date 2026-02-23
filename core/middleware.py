from django.shortcuts import redirect, render
from django.http import HttpResponseForbidden, Http404
from django.conf import settings
from accounts.models import Center
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class TenantMiddleware:
    """
    Middleware to resolve the active center (tenant) from User Session ONLY.
    Subdomains are completely IGNORED.
    
    Logic:
    1. If user is logged in -> set request.center = user.center
    2. If superuser -> allow session based switching
    3. No redirects to subdomains.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        
        # Initialize defaults
        request.subdomain = None
        request.active_center = None
        request.center = None

        # 1. Skip Static/Media/Favicon
        if path.startswith('/static/') or path.startswith('/media/') or path == '/favicon.ico':
            return self.get_response(request)
            
        # 2. Authenticated User Logic
        if request.user.is_authenticated:
            
            # A) Superuser: Check session for override
            if request.user.is_superuser:
                active_center_id = request.session.get("active_center_id")
                if active_center_id:
                    center = Center.objects.filter(id=active_center_id, is_deleted=False).first()
                    if center:
                        request.active_center = center
                        request.center = center
                        
            # B) Standard User: Always use assigned center
            elif hasattr(request.user, 'center') and request.user.center:
                # ✅ Refresh center from DB to ensure is_deleted/status is fresh
                try:
                    fresh_center = Center.objects.get(pk=request.user.center.pk)
                except Center.DoesNotExist:
                     # Center hard deleted
                     from django.contrib.auth import logout
                     logout(request)
                     return redirect('/')

                # ✅ If center is deleted -> Force Logout
                if fresh_center.is_deleted:
                    from django.contrib.auth import logout
                    logout(request)
                    return redirect('/')
                
                # ✅ Check for Archive (optional but good practice)
                if fresh_center.status == 'ARCHIVED':
                    from django.contrib.auth import logout
                    logout(request)
                    return redirect('/')

                request.active_center = fresh_center
                request.center = fresh_center

                # ✅ Optimized Sub Check: Only check once per hour per session to save DB queries
                last_check = request.session.get('last_sub_check')
                now_ts = timezone.now().timestamp()
                
                if not last_check or (now_ts - last_check > 3600): # 1 hour cooldown
                    try:
                        from billing.services import check_subscription_expiry
                        check_subscription_expiry(fresh_center)
                        request.session['last_sub_check'] = now_ts
                    except Exception as e:
                        import logging
                        logging.error(f"Middleware Sub Check Error: {e}")
                
                # Check Blocked Status
                is_blocked = False
                if request.active_center.status == 'BLOCKED':
                    is_blocked = True
                elif hasattr(request.active_center, 'subscription') and request.active_center.subscription:
                     if request.active_center.subscription.is_blocked():
                         is_blocked = True
                
                if is_blocked:
                    # Allow logout, admin, and billing pages
                    if not path.startswith('/hisob/billing/') and \
                       not path.startswith('/hisob/tolov/') and \
                       not path.startswith('/logout/') and \
                       not path.startswith('/admin/logout/'):
                         
                        # ✅ Don't block students, parents, teachers -> they can't pay anyway
                        # Only redirect Managers/Directors/Admins to payment page
                        role = getattr(request.user, "role", None)
                        if role not in ("student", "parent", "teacher"):
                            return redirect('billing:plans')

            # C) Orphan User (No center assigned)
            # We allow them to proceed, but views might restrict access
            # or context processors will show empty state.
            
        # 3. Unauthenticated User
        # Let them browse unless the view requires login (handled by @login_required)
        
        return self.get_response(request)
