# core/db_router.py
"""
Database router for multi-tenant architecture (phase 10 foundation).

Default behaviour (production-safe):
  TENANT_DB_ROUTING_ENABLED=False → barcha app'lar `default` DB.

When enabled and a center has dedicated db_name (+ resolved password/host):
  - SHARED_APPS  → always `default` (users, centers, sessions, …)
  - TENANT_APPS  → `tenant_<root_id>` connection

Filiallar root center DB metadata sidan foydalanadi.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.db import connections
from django.db.utils import DEFAULT_DB_ALIAS

from core.db_config import (
    build_tenant_db_config,
    center_has_dedicated_db,
    resolve_routing_center,
    tenant_db_routing_enabled,
)
from core.tenant_context import get_current_tenant, tenant_db_alias

logger = logging.getLogger(__name__)

SHARED_APPS = frozenset(
    {
        "accounts",
        "core",
        "tenancy",
        "sessions",
        "auth",
        "admin",
        "contenttypes",
        "messages",
        # Platform / marketing stay shared
        "marketing",
        "game",
    }
)
TENANT_APPS = frozenset(
    {
        "education",
        "billing",
        "chaqmoq",
        "store",
    }
)


def _database_identity(config: dict) -> tuple:
    return (
        str(config.get("NAME", "") or "").strip(),
        str(config.get("USER", "") or "").strip(),
        str(config.get("HOST", "") or "localhost").strip() or "localhost",
        str(config.get("PORT", "") or "5432").strip() or "5432",
    )


def uses_default_database(config: dict) -> bool:
    """True if config points at the same logical DB as default (avoid duplicate alias)."""
    default_config = settings.DATABASES.get(DEFAULT_DB_ALIAS, {})
    engine = str(default_config.get("ENGINE", "") or "").lower()
    # SQLite local: never treat as dedicated multi-db
    if "postgresql" not in engine and "postgres" not in engine:
        return True
    return _database_identity(config) == _database_identity(default_config)


def _normalize_connection_config(alias: str, config: dict) -> dict:
    databases = {
        DEFAULT_DB_ALIAS: dict(settings.DATABASES.get(DEFAULT_DB_ALIAS, {})),
        alias: dict(config),
    }
    return connections.configure_settings(databases)[alias]


def ensure_connection(alias: str, config: dict) -> dict:
    config = _normalize_connection_config(alias, config)
    if alias not in settings.DATABASES:
        settings.DATABASES[alias] = config
        connections.databases[alias] = config
        logger.info("[MultiTenant] DB ulandi: %s name=%s", alias, config.get("NAME"))
    else:
        settings.DATABASES[alias].update(config)
        connections.databases[alias] = settings.DATABASES[alias]
    return config


def resolve_tenant_db_alias(tenant=None) -> str:
    """
    Return DB alias for current (or given) tenant.

    Always returns 'default' when routing disabled, no tenant, or config equals default.
    """
    if not tenant_db_routing_enabled():
        return DEFAULT_DB_ALIAS

    tenant = resolve_routing_center(tenant if tenant is not None else get_current_tenant())
    if not center_has_dedicated_db(tenant):
        return DEFAULT_DB_ALIAS

    try:
        config = build_tenant_db_config(tenant)
    except ValueError:
        return DEFAULT_DB_ALIAS

    if uses_default_database(config):
        return DEFAULT_DB_ALIAS

    alias = tenant_db_alias(tenant) or f"tenant_{tenant.pk}"
    ensure_connection(alias, config)
    return alias


class TenantDatabaseRouter:
    def db_for_read(self, model, **hints):
        app_label = model._meta.app_label
        if app_label in SHARED_APPS:
            return DEFAULT_DB_ALIAS
        if app_label in TENANT_APPS:
            return resolve_tenant_db_alias()
        # Unknown apps stay on default
        return DEFAULT_DB_ALIAS

    def db_for_write(self, model, **hints):
        return self.db_for_read(model, **hints)

    def allow_relation(self, obj1, obj2, **hints):
        # Cross-DB relations are not supported; allow when both resolve same alias
        # or when either side has no routing (None → treat as default).
        try:
            db1 = self.db_for_read(obj1.__class__)
            db2 = self.db_for_read(obj2.__class__)
        except Exception:
            return None
        if db1 is None or db2 is None:
            return None
        return db1 == db2

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        - default: all apps migrate (shared deployment path)
        - tenant_*: only TENANT_APPS (when dedicated DBs are provisioned)
        """
        if db == DEFAULT_DB_ALIAS or db == "default":
            # When routing is off, everything lives here.
            # When routing is on, shared apps must still migrate on default;
            # tenant apps also migrate on default for shared-tenancy installs.
            return True
        if str(db).startswith("tenant_"):
            return app_label in TENANT_APPS
        return None
