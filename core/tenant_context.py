"""
Tenant context utilities (multi-tenant foundation).

Uses contextvars (async-safe) with a thread-local fallback for older call paths.
Always prefer the *root* center for DB routing: filiallar root subscription/DB
metadata dan foydalanadi.
"""
from __future__ import annotations

import contextvars
import threading
from typing import Any

_tenant_var: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "chaqmoq_current_tenant", default=None
)
_thread_locals = threading.local()


def _resolve_root(tenant):
    if tenant is None:
        return None
    try:
        if getattr(tenant, "parent_center_id", None) and hasattr(tenant, "get_root_center"):
            return tenant.get_root_center()
    except Exception:
        pass
    return tenant


def set_current_tenant(tenant) -> None:
    """Set current tenant (center) for this request/task. Stores root center."""
    root = _resolve_root(tenant)
    _tenant_var.set(root)
    _thread_locals.tenant = root


def get_current_tenant():
    """Get current tenant (center) for this request/task."""
    try:
        value = _tenant_var.get()
    except LookupError:
        value = None
    if value is not None:
        return value
    return getattr(_thread_locals, "tenant", None)


def clear_current_tenant() -> None:
    """Clear tenant context after request."""
    _tenant_var.set(None)
    if hasattr(_thread_locals, "tenant"):
        del _thread_locals.tenant


def tenant_db_alias(tenant) -> str | None:
    """Canonical alias for a tenant's dedicated DB connection, or None."""
    root = _resolve_root(tenant)
    if root is None or not getattr(root, "pk", None):
        return None
    if not getattr(root, "db_name", None):
        return None
    return f"tenant_{root.pk}"
