# config/settings_prod.py
"""
Production settings for Render.com deployment
SECURITY WARNING: Keep secret keys secure in environment variables!
"""
import os
from django.core.exceptions import ImproperlyConfigured
from .settings import *

# ==================== CORE SETTINGS ====================

DEBUG = False
is_production_runtime = bool(os.getenv("RENDER") or os.getenv("MODE") == "production")

# Your production domain
ROOT_DOMAIN = os.getenv("ROOT_DOMAIN", "chaqmoqapp.uz")

# Render service URL (auto-provided by Render)
RENDER_SERVICE = os.getenv("RENDER_EXTERNAL_URL", "")
if RENDER_SERVICE:
    RENDER_SERVICE = RENDER_SERVICE.replace("https://", "").replace("http://", "")

# ==================== ALLOWED HOSTS ====================

ALLOWED_HOSTS = [
    "chaqmoqapp.uz",
    "www.chaqmoqapp.uz",
    "localhost",
    "127.0.0.1",
    ".onrender.com",  # Wildcard for all render subdomains
]

# Add specific Render service URL if provided
if RENDER_SERVICE:
    ALLOWED_HOSTS.append(RENDER_SERVICE)

# Allow adding hosts via environment variable (comma separated)
if os.getenv("ALLOWED_HOSTS"):
    ALLOWED_HOSTS.extend(os.getenv("ALLOWED_HOSTS").split(","))

# ==================== CSRF PROTECTION ====================

CSRF_TRUSTED_ORIGINS = [
    "https://chaqmoqapp.uz",
    "https://www.chaqmoqapp.uz",
    "https://*.onrender.com",
]

if RENDER_SERVICE:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_SERVICE}")

# ==================== SESSION & COOKIES ====================

# Multi-tenant: Isolated sessions per subdomain (RECOMMENDED)
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_DOMAIN = None
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# If you need SSO across subdomains (uncomment):
# SESSION_COOKIE_DOMAIN = f".{ROOT_DOMAIN}"
# CSRF_COOKIE_DOMAIN = f".{ROOT_DOMAIN}"

# ==================== SECURITY HEADERS ====================

# Render uses proxy - trust X-Forwarded-* headers
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Force HTTPS in production
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Browser security
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# HSTS (HTTP Strict Transport Security)
_enable_hsts = os.getenv("ENABLE_HSTS", "1") == "1"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000")) if _enable_hsts else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "1") == "1"
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "0") == "1"

if is_production_runtime:
    if not SECRET_KEY or SECRET_KEY == "unsafe-secret-key":
        raise ImproperlyConfigured("SECRET_KEY productionda environment orqali berilishi shart.")

    if not API_SECRET or len(API_SECRET) < 32:
        raise ImproperlyConfigured("API_SECRET productionda kamida 32 belgili bo'lishi shart.")

    if not CLICK_SECRET_KEY or CLICK_SECRET_KEY == "tFFjf4jX2kn9OJ69Ex":
        raise ImproperlyConfigured("CLICK_SECRET_KEY productionda environment orqali berilishi shart.")

CLICK_ALLOWED_IPS = [ip.strip() for ip in os.getenv("CLICK_ALLOWED_IPS", "").split(",") if ip.strip()]

# ==================== DATABASE ====================

# Render provides DATABASE_URL automatically
# psycopg2-binary must be in requirements.txt

if "DATABASE_URL" in os.environ:
    import dj_database_url
    DATABASES = {
        "default": dj_database_url.config(
            default=os.getenv("DATABASE_URL"),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Productionda DATABASE_URL bo'lmasa sqlitega tushib qolish ma'lumot yo'qolishiga olib keladi.
    if is_production_runtime:
        raise RuntimeError("DATABASE_URL topilmadi. Production uchun Postgres ulanmagan.")

    # Local fallback
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ==================== SESSION CONFIGURATION ====================

# Use database for sessions to persist across deployments
# This prevents ALL users from being logged out on every deploy!
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_SAVE_EVERY_REQUEST = False

# Template loader caching for production render speed.
if TEMPLATES and TEMPLATES[0].get("APP_DIRS", False):
    TEMPLATES[0]["APP_DIRS"] = False
    TEMPLATES[0]["OPTIONS"]["loaders"] = [
        ("django.template.loaders.cached.Loader", [
            "django.template.loaders.filesystem.Loader",
            "django.template.loaders.app_directories.Loader",
        ])
    ]

# ==================== STATIC FILES ====================

STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_URL = "/static/"

# WhiteNoise for serving static files
# Hash + compression for immutable static caching in production.
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Ignore missing source maps (they're not critical for production)
WHITENOISE_KEEP_ONLY_HASHED_FILES = False
WHITENOISE_ALLOW_ALL_ORIGINS = True
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_MAX_AGE = 31536000

# Ensure WhiteNoise middleware is active (should be in MIDDLEWARE)
# "whitenoise.middleware.WhiteNoiseMiddleware",

# ==================== MEDIA FILES ====================

# Production: Use cloud storage (S3, Cloudinary, etc.)
MEDIA_URL = "/media/"
MEDIA_ROOT = os.getenv("MEDIA_ROOT", "/opt/render/project/src/media")

# For S3 (uncomment and configure):
# DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
# AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
# AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
# AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
# AWS_S3_REGION_NAME = "us-east-1"

# ==================== EMAIL ====================

# Configure production email backend
# Example: SendGrid, AWS SES, Mailgun

# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = "smtp.sendgrid.net"
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = os.getenv("SENDGRID_USERNAME")
# EMAIL_HOST_PASSWORD = os.getenv("SENDGRID_PASSWORD")
# DEFAULT_FROM_EMAIL = f"noreply@{ROOT_DOMAIN}"

# ==================== LOGGING ====================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "core.middleware": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ==================== PERFORMANCE ====================

# Connection pooling
CONN_MAX_AGE = 600

# Cache (Redis if REDIS_URL exists, otherwise local-memory fallback)
if os.getenv("REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.getenv("REDIS_URL"),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "chaqmoq-prod-cache",
            "TIMEOUT": 300,
        }
    }

# ==================== ADMIN ====================

# Custom admin URL for security
# Update urls.py: path("secret-admin/", admin.site.urls)
ADMIN_URL = os.getenv("ADMIN_URL", "admin/")
