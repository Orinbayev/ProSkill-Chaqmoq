import os
from pathlib import Path
from dotenv import load_dotenv

# ===== Load environment variables =====
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ===== Core =====
SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-secret-key")
DEBUG = True # ✅ Force Debug for Local Dev to prevent redirect issues

# ✅ HOSTS FIX: Allow all necessary local domains
# ✅ HOSTS FIX: Allow all necessary local domains
ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".localhost", "*"]

# ✅ COOKIE FIX: Localhost requires strict handling to avoid loops
# We use None so cookies are host-only. This prevents subdomain conflict on local.
SESSION_COOKIE_DOMAIN = None 
CSRF_COOKIE_DOMAIN = None

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://*.localhost:8000",
    "http://*.localhost",
    "https://*.onrender.com",
    "https://*.chaqmoq.uz"
]
    
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
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.TenantMiddleware", # ✅ Custom Tenant Middleware
]

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

# ===== Authentication =====
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailOrPhoneBackend",
    "django.contrib.auth.backends.ModelBackend"
]
# ✅ FIX: Point directly to the URL path to avoid resolution ambiguity
LOGIN_URL = "/hisob/login/" 
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "login"

LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "uz")
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Tashkent")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

# Bot Configuration
BOT_INTERNAL_API_URL = os.getenv("BOT_INTERNAL_API_URL", "http://127.0.0.1:8080")
API_SECRET = os.getenv("API_SECRET", "7d8a9c1e2f3b4a5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2u3v4w5x6y7z8a9b")


MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
if MODE == "render":
    MEDIA_ROOT = "/opt/render/project/src/media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# ==================== CLICK PAYMENT ====================
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "")
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "")
# Local default: return to platform dashboard after payment.
CLICK_RETURN_URL = os.getenv("CLICK_RETURN_URL", "http://127.0.0.1:8000/platform/")
CLICK_SUCCESS_REDIRECT_URL = os.getenv("CLICK_SUCCESS_REDIRECT_URL", "http://127.0.0.1:8000/platform/")
CLICK_WEBHOOK_URL = os.getenv("CLICK_WEBHOOK_URL", "https://chaqmoqapp.uz/api/click/webhook/")
CLICK_PREPARE_URL = os.getenv("CLICK_PREPARE_URL", "https://chaqmoqapp.uz/api/click/webhook/")
CLICK_COMPLETE_URL = os.getenv("CLICK_COMPLETE_URL", "https://chaqmoqapp.uz/api/click/webhook/")


# Telegram bot for payment notifications (official Telegram API via aiogram)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", os.getenv("BOT_TOKEN", ""))

# ==================== PRODUCTION OVERRIDE ====================
# Auto-load production settings when deployed to Render
if os.getenv("MODE") == "production" or os.getenv("RENDER"):
    try:
        from .settings_prod import *
        print("✅ Production settings loaded successfully")
    except ImportError as e:
        print(f"⚠️ Failed to load production settings: {e}")
