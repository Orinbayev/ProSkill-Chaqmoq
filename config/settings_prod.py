# config/settings_prod.py
"""
Production settings for Render.com deployment
SECURITY WARNING: Keep secret keys secure in environment variables!
"""
import os
from .settings import *

# ==================== CORE SETTINGS ====================

DEBUG = False

# Your production domain
ROOT_DOMAIN = os.getenv("ROOT_DOMAIN", "chaqmoq.uz")

# Render service URL (auto-provided by Render)
RENDER_SERVICE = os.getenv("RENDER_EXTERNAL_URL", "")
if RENDER_SERVICE:
    RENDER_SERVICE = RENDER_SERVICE.replace("https://", "").replace("http://", "")

# ==================== ALLOWED HOSTS ====================

ALLOWED_HOSTS = [
    ROOT_DOMAIN,                    # chaqmoq.uz
    f".{ROOT_DOMAIN}",              # *.chaqmoq.uz (wildcard subdomains)
    "localhost",                    # Local testing
    "127.0.0.1",
]

# Add Render service URL if provided
if RENDER_SERVICE:
    ALLOWED_HOSTS.append(RENDER_SERVICE)  # your-app.onrender.com

# ==================== CSRF PROTECTION ====================

CSRF_TRUSTED_ORIGINS = [
    f"https://{ROOT_DOMAIN}",
    f"https://*.{ROOT_DOMAIN}",     # Wildcard for subdomains
]

if RENDER_SERVICE:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_SERVICE}")

# ==================== SESSION & COOKIES ====================

# Multi-tenant: Isolated sessions per subdomain (RECOMMENDED)
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_DOMAIN = None
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

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
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# HSTS (HTTP Strict Transport Security)
# IMPORTANT: Only enable after confirming HTTPS works!
# SECURE_HSTS_SECONDS = 31536000  # 1 year
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True

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
    # Fallback to SQLite (not recommended for production)
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

# ==================== STATIC FILES ====================

STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_URL = "/static/"

# WhiteNoise for serving static files
# Use CompressedStaticFilesStorage to avoid .map file issues
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

# Ignore missing source maps (they're not critical for production)
WHITENOISE_KEEP_ONLY_HASHED_FILES = False
WHITENOISE_ALLOW_ALL_ORIGINS = True

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
            "level": "DEBUG",  # See tenant resolution logs
            "propagate": False,
        },
    },
}

# ==================== PERFORMANCE ====================

# Connection pooling
CONN_MAX_AGE = 600

# Cache (optional - Redis recommended)
# CACHES = {
#     "default": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": os.getenv("REDIS_URL"),
#         "OPTIONS": {
#             "CLIENT_CLASS": "django_redis.client.DefaultClient",
#         }
#     }
# }

# ==================== ADMIN ====================

# Custom admin URL for security
# Update urls.py: path("secret-admin/", admin.site.urls)
ADMIN_URL = os.getenv("ADMIN_URL", "admin/")
