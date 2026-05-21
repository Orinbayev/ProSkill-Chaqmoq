import os
import socket
from pathlib import Path
from dotenv import load_dotenv
from django.utils.translation import gettext_lazy as _
from config.shared_secret import resolve_api_secret

# ===== Load environment variables =====
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ===== Core =====
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if os.getenv("MODE") in ("production", "render"):
        raise RuntimeError("SECRET_KEY environment variable must be set in production!")
    SECRET_KEY = "local-dev-unsafe-secret-key-change-in-production"
DEBUG = True # ✅ Force Debug for Local Dev to prevent redirect issues

def _detect_lan_ip():
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.2)
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return ""
    finally:
        if sock is not None:
            sock.close()

_ALLOWED = os.getenv("ALLOWED_HOSTS", "")
if _ALLOWED:
    ALLOWED_HOSTS = [host.strip() for host in _ALLOWED.split(",") if host.strip()]
else:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".localhost"]

LOCAL_DEV_HOST = os.getenv("LOCAL_DEV_HOST") or _detect_lan_ip()
LOCAL_EMULATOR_HOST = "10.0.2.2"
if DEBUG:
    for host in ("0.0.0.0", LOCAL_DEV_HOST, LOCAL_EMULATOR_HOST):
        if host and host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)

# ✅ COOKIE FIX: Localhost requires strict handling to avoid loops
# We use None so cookies are host-only. This prevents subdomain conflict on local.
SESSION_COOKIE_DOMAIN = None 
CSRF_COOKIE_DOMAIN = None

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://*.localhost:8000",
    "http://*.localhost",
    "https://*.onrender.com",
    "https://*.chaqmoq.uz",
    "https://chaqmoqapp.uz",
    "https://www.chaqmoqapp.uz",
]

# Cloudflare proxy orqali kelgan real IP'ni ko'rish uchun
# Render ham X-Forwarded-For header'ni ishlatadi
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if DEBUG and LOCAL_DEV_HOST:
    CSRF_TRUSTED_ORIGINS.append(f"http://{LOCAL_DEV_HOST}:8000")
if DEBUG:
    CSRF_TRUSTED_ORIGINS.append(f"http://{LOCAL_EMULATOR_HOST}:8000")
    
# Security settings for local dev (Disable SSL/Secure cookies to prevent loops)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# ===== Installed Apps =====
INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_extensions",
    "django.contrib.humanize",
    "accounts",
    "education",
    "chaqmoq",
    "store",
    "core",
    "billing",
    "marketing",
    "rest_framework",
    "drf_spectacular",
]

JAZZMIN_SETTINGS = {
    "site_title": "⚡ Chaqmoq Admin",
    "site_header": "⚡ ChaqmoqApp",
    "site_brand": "Chaqmoq Admin",
    "welcome_sign": "ChaqmoqApp boshqaruv paneliga xush kelibsiz",
    "copyright": "ChaqmoqApp © 2025",
    "theme": "flatly",
    "topmenu_links": [
        {"name": "Bosh sahifa", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"model": "accounts.user"},
        {"model": "education.category"},
        {"app": "store"},
    ],
    "usermenu_links": [
        {"name": "Profil", "url": "admin:password_change"},
        {"name": "Chiqish", "url": "admin:logout"},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "accounts.User": "fas fa-user",
        "accounts.Center": "fas fa-school",
        "chaqmoq.ChaqmoqQoidalari": "fas fa-bolt",
        "education.Category": "fas fa-layer-group",
        "education.Davomatlar": "fas fa-calendar-check",
        "education.Guruh": "fas fa-users",
        "education.Tolovlar": "fas fa-wallet",
        "store.Products": "fas fa-box",
        "store.Leads": "fas fa-address-book",
    },
    "show_ui_builder": False,
    "changeform_format": "single",
}

# ===== Middleware =====
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # PERF: performance logging — SecurityMiddleware dan keyin
    "core.middleware_perf.SlowRequestLoggingMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "core.middleware.MobileApiCorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.TenantMiddleware",          # ✅ Custom Tenant Middleware
    "core.middleware_rbac.RoleBasedAccessMiddleware",  # ✅ RBAC kirish nazorati
]

# PERF: Performance logging settings — override via Render environment variables.
# SLOW_REQUEST_MS  — bu'dan sekin so'rovlar [SLOW]/[CRITICAL] tegi oladi (default: 800ms)
# PERF_LOG_ALL     — True: har request loglanadi | False: faqat sekin/high-query
SLOW_REQUEST_MS = int(os.environ.get("SLOW_REQUEST_MS", "800"))
SLOW_REQUEST_LOG_QUERIES = os.environ.get("SLOW_REQUEST_LOG_QUERIES", "1") == "1"
PERF_LOG_ALL = os.environ.get("PERF_LOG_ALL", "1") == "1"
# PERF_MIDDLEWARE_DEBUG=1 → per-section timing logs in TenantMiddleware
PERF_MIDDLEWARE_DEBUG = os.environ.get("PERF_MIDDLEWARE_DEBUG", "0") == "1"

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# ===== Templates =====
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.tenant_context",
            ],
        },
    },
]

# ===== Database =====
MODE = os.getenv("MODE", "local")
if MODE == "render":
    DATABASES = {
        "default": {
            "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.postgresql"),
            "NAME": os.getenv("DB_NAME"),
            "USER": os.getenv("DB_USER"),
            "PASSWORD": os.getenv("DB_PASSWORD"),
            "HOST": os.getenv("DB_HOST"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "require")},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": os.getenv("LOCAL_DB_ENGINE", "django.db.backends.sqlite3"),
            "NAME": BASE_DIR / os.getenv("LOCAL_DB_NAME", "db.sqlite3"),
            "OPTIONS": {"timeout": 60}
        }
    }

# ===== Database Routers (multi-tenant foundation) =====
DATABASE_ROUTERS = [
    'core.db_router.TenantDatabaseRouter',
]

# ===== Authentication =====
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailOrPhoneBackend",
    "django.contrib.auth.backends.ModelBackend"
]
# ✅ FIX: Point directly to the URL path to avoid resolution ambiguity
LOGIN_URL = "/hisob/login/" 
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "login"

LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "uz")
LANGUAGES = [
    ("uz", _("O'zbekcha")),
    ("ru", _("Русский")),
    ("en", _("English")),
]
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Tashkent")
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

# Bot Configuration
BOT_INTERNAL_API_URL = os.getenv("BOT_INTERNAL_API_URL", "http://127.0.0.1:8080")
API_SECRET = resolve_api_secret(secret_key=SECRET_KEY)


MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
if MODE == "render":
    MEDIA_ROOT = "/opt/render/project/src/media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==================== REST FRAMEWORK ====================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# ==================== DRF SPECTACULAR (Swagger/OpenAPI) ====================
SPECTACULAR_SETTINGS = {
    "TITLE": "ChaqmoqApp API",
    "DESCRIPTION": (
        "ChaqmoqApp — o'quv markazlari boshqaruv platformasi uchun REST API. "
        "Mobile (Flutter) va tashqi integratsiyalar uchun."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "CONTACT": {"name": "ChaqmoqApp Team", "url": "https://chaqmoqapp.uz"},
    "SERVERS": [
        {"url": "https://chaqmoqapp.uz", "description": "Production"},
        {"url": "http://localhost:8000", "description": "Local Dev"},
    ],
    "TAGS": [
        {"name": "auth", "description": "Autentifikatsiya va sessiya"},
        {"name": "mobile", "description": "Flutter mobile ilovasi uchun endpointlar"},
        {"name": "director", "description": "Direktor dashboard va statistika"},
        {"name": "ai", "description": "AI insights va tahlil"},
        {"name": "billing", "description": "To'lov va obuna tizimi"},
    ],
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "perf": {
            "format": "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
        "perf_console": {
            "class": "logging.StreamHandler",
            "formatter": "perf",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        # Slow request middleware logger — chiqishi WARNING+
        "perf.slow_request": {
            "handlers": ["perf_console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# ==================== CLICK PAYMENT ====================
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "")
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "")

# Return URLs for browser redirect
_CLICK_DEFAULT_RETURN_URL = (
    "https://chaqmoqapp.uz/platform/"
    if (os.getenv("RENDER") or os.getenv("MODE") in {"production", "render"})
    else "http://localhost:8000/platform/"
)
CLICK_RETURN_URL = os.getenv("CLICK_RETURN_URL", _CLICK_DEFAULT_RETURN_URL)
CLICK_SUCCESS_REDIRECT_URL = CLICK_RETURN_URL
CLICK_WEBHOOK_URL = "/click/webhook/"
CLICK_PREPARE_URL = "/click/prepare/"
CLICK_COMPLETE_URL = "/click/complete/"

# Click Merchant Panel should point to these exact URLs:
# Prepare: https://chaqmoqapp.uz/click/prepare/
# Complete: https://chaqmoqapp.uz/click/complete/


# Telegram bot for payment notifications (official Telegram API via aiogram)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", os.getenv("BOT_TOKEN", ""))
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "YOUR_BOT").lstrip("@")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID", os.getenv("BACKUP_GROUP_ID", ""))
TELEGRAM_BACKUP_CHAT_ID = os.getenv(
    "TELEGRAM_BACKUP_CHAT_ID",
    os.getenv("BACKUP_GROUP_ID", TELEGRAM_GROUP_ID),
)
BACKUP_BOT_TOKEN = os.getenv("BACKUP_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
BACKUP_GROUP_ID = os.getenv("BACKUP_GROUP_ID", TELEGRAM_BACKUP_CHAT_ID)
BACKUP_TIMEZONE = os.getenv("BACKUP_TIMEZONE", TIME_ZONE)
BACKUP_SEND_TIME = os.getenv("BACKUP_SEND_TIME", "18:00")
BACKUP_KEEP_DAYS = int(os.getenv("BACKUP_KEEP_DAYS", "7"))
ADMIN_TELEGRAM_IDS = os.getenv("ADMIN_TELEGRAM_IDS", "")

# ==================== BILLING SOZLAMALARI ====================
# Obuna tugaganidan keyin necha soat muhlat (grace period)
BILLING_GRACE_PERIOD_HOURS = int(os.getenv("BILLING_GRACE_PERIOD_HOURS", "72"))
# Obuna tugashiga necha kun qolganda ogohlantirish ko'rsatiladi
BILLING_EXPIRY_WARN_DAYS = int(os.getenv("BILLING_EXPIRY_WARN_DAYS", "7"))

# ==================== PRODUCTION OVERRIDE ====================
# Auto-load production settings when deployed to Render
if os.getenv("MODE") == "production" or os.getenv("RENDER"):
    try:
        from .settings_prod import *
        print("✅ Production settings loaded successfully")
    except (ImportError, RuntimeError) as e:
        print(f"⚠️ Failed to load production settings: {e}")
