"""
Helper for building tenant (center) DB config (foundation).
- Returns Django DATABASES-compatible dict for PostgreSQL
- Does NOT mutate global settings
- Safe for future use
"""
def build_tenant_db_config(center):
    """
    Build a DATABASES-compatible dict for a given center (PostgreSQL).
    Does NOT mutate global settings.
    """
    if not center or not center.db_name:
        raise ValueError("Center or db_name not set")
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': center.db_name,
        'USER': center.db_user or '',
        'PASSWORD': center.db_password or '',  # TODO: безопасное хранение
        'HOST': center.db_host or 'localhost',
        'PORT': center.db_port or '5432',
    }

