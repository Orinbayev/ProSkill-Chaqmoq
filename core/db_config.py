"""
Tenant (center) database configuration helpers.

Security notes (phase 10):
- Prefer password from environment: TENANT_DB_PASSWORD_<CENTER_ID> or TENANT_DB_PASSWORD_<SLUG>
- Do not log raw passwords; use mask_db_config() for diagnostics
- Routing is opt-in via TENANT_DB_ROUTING_ENABLED (default False → shared default DB)
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


def tenant_db_routing_enabled() -> bool:
    return bool(getattr(settings, "TENANT_DB_ROUTING_ENABLED", False))


def _slug_env_key(slug: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(slug or "").strip().upper()).strip("_")
    return cleaned or "UNKNOWN"


def resolve_tenant_db_password(center) -> str:
    """
    Resolve DB password without requiring plaintext in the Center row.

    Order:
    1. TENANT_DB_PASSWORD_<CENTER_ID>
    2. TENANT_DB_PASSWORD_<SLUG>
    3. TENANT_DB_PASSWORD (global fallback for all dedicated DBs)
    4. center.db_password (legacy plaintext — discouraged)
    """
    if center is None:
        return ""
    cid = getattr(center, "pk", None) or getattr(center, "id", None)
    slug = getattr(center, "slug", "") or ""
    candidates = []
    if cid:
        candidates.append(f"TENANT_DB_PASSWORD_{cid}")
    if slug:
        candidates.append(f"TENANT_DB_PASSWORD_{_slug_env_key(slug)}")
    candidates.append("TENANT_DB_PASSWORD")
    for key in candidates:
        value = os.environ.get(key)
        if value:
            return value
    return str(getattr(center, "db_password", None) or "")


def resolve_routing_center(center):
    """Filial → root (DB metadata yashaydi)."""
    if center is None:
        return None
    try:
        if getattr(center, "parent_center_id", None) and hasattr(center, "get_root_center"):
            return center.get_root_center()
    except Exception:
        pass
    return center


def center_has_dedicated_db(center) -> bool:
    """True when center (root) declares a db_name distinct enough to consider routing."""
    root = resolve_routing_center(center)
    if not root or not getattr(root, "db_name", None):
        return False
    name = str(root.db_name).strip()
    return bool(name)


def build_tenant_db_config(center, *, include_password: bool = True) -> dict[str, Any]:
    """
    Build a DATABASES-compatible dict for a given center (PostgreSQL).
    Does NOT mutate global settings.
    """
    root = resolve_routing_center(center)
    if not root or not getattr(root, "db_name", None):
        raise ValueError("Center or db_name not set")

    password = resolve_tenant_db_password(root) if include_password else ""
    if include_password and not password and getattr(root, "db_password", None):
        # legacy field already covered by resolve; keep branch for clarity
        password = str(root.db_password or "")

    if include_password and not password:
        logger.warning(
            "Tenant DB password empty for center_id=%s slug=%s — set TENANT_DB_PASSWORD_* env",
            getattr(root, "pk", None),
            getattr(root, "slug", None),
        )

    conn_max_age = int(getattr(settings, "TENANT_DB_CONN_MAX_AGE", 60) or 60)
    config: dict[str, Any] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": str(root.db_name).strip(),
        "USER": str(getattr(root, "db_user", None) or "").strip(),
        "PASSWORD": password,
        "HOST": str(getattr(root, "db_host", None) or "localhost").strip() or "localhost",
        "PORT": str(getattr(root, "db_port", None) or "5432").strip() or "5432",
        "CONN_MAX_AGE": conn_max_age,
        "ATOMIC_REQUESTS": False,
        "AUTOCOMMIT": True,
        "OPTIONS": {},
        "TIME_ZONE": getattr(settings, "TIME_ZONE", "UTC"),
    }
    return config


def mask_db_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a copy safe for logs/CLI (password redacted)."""
    out = dict(config or {})
    if out.get("PASSWORD"):
        out["PASSWORD"] = "***"
    return out
