import hashlib
import os

_WEAK_API_SECRETS = {
    "",
    "unsafe-secret-key",
    "changeme",
    "7d8a9c1e2f3b4a5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2u3v4w5x6y7z8a9b",
}


def resolve_api_secret(env=None, *, secret_key=None):
    source = os.environ if env is None else env
    configured = str((source.get("API_SECRET") if hasattr(source, "get") else "") or "").strip()
    if configured not in _WEAK_API_SECRETS and len(configured) >= 32:
        return configured

    base_secret = str(secret_key or (source.get("SECRET_KEY") if hasattr(source, "get") else "") or "").strip()
    if not base_secret:
        return configured

    payload = f"internal-bot-api::{base_secret}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
