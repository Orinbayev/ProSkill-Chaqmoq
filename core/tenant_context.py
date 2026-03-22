"""
Tenant context utilities (foundation).
- Uses thread-local storage for safe per-request tenant context
- Safe for sync Django (for async, consider contextvars in the future)
"""
import threading

_thread_locals = threading.local()

def set_current_tenant(tenant):
    """Set current tenant (center) for this thread/request."""
    _thread_locals.tenant = tenant

def get_current_tenant():
    """Get current tenant (center) for this thread/request."""
    return getattr(_thread_locals, 'tenant', None)

def clear_current_tenant():
    """Clear tenant context after request."""
    if hasattr(_thread_locals, 'tenant'):
        del _thread_locals.tenant

