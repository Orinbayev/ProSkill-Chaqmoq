# core/db_router.py
"""
Database router for multi-tenant architecture (foundation).
- Shared apps (accounts, core, tenancy, sessions, auth, admin, contenttypes) → default DB
- Tenant apps (education, billing) → future: center-specific DB
- For now: all apps use default unless tenant context is set (future step)
- Safe, non-breaking, with clear comments for future extension
"""

from core.tenant_context import get_current_tenant
from core.db_config import build_tenant_db_config
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

SHARED_APPS = [
    'accounts', 'core', 'tenancy',
    'sessions', 'auth', 'admin', 'contenttypes'
]
TENANT_APPS = [
    'education', 'billing'
]

from django.db import connections

def ensure_connection(alias, config):
    if alias not in settings.DATABASES:
        settings.DATABASES[alias] = config
        connections.databases[alias] = config
        logger.info(f"[MultiTenant] DB ulandi: {alias}")


class TenantDatabaseRouter:
    def db_for_read(self, model, **hints):
        app_label = model._meta.app_label
        if app_label in SHARED_APPS:
            return 'default'
        if app_label in TENANT_APPS:
            tenant = get_current_tenant()
            if tenant and getattr(tenant, 'db_name', None):
                alias = f"tenant_{tenant.id}"
                config = build_tenant_db_config(tenant)
                ensure_connection(alias, config)
                return alias
            return 'default'
        return 'default'

    def db_for_write(self, model, **hints):
        return self.db_for_read(model, **hints)

    def allow_relation(self, obj1, obj2, **hints):
        db_obj1 = self.db_for_read(obj1.__class__)
        db_obj2 = self.db_for_read(obj2.__class__)
        if db_obj1 and db_obj2:
            return db_obj1 == db_obj2
        return True  # безопасно разрешить по умолчанию

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == 'default':
            return True
        return None
