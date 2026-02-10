"""
Django settings for Chaqmoq Academy project (Render Disk version).
This configuration works 100% correctly on Render.com with persistent media storage.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ===== Load environment variables =====
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ===== Core =====
SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-secret-key")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
# ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
ALLOWED_HOSTS = ['a1b2c3d4.ngrok-free.app', '127.0.0.1', 'proskill-chaqmoq.onrender.com']

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
    "site_header": "⚡ Chaqmoq Academy",
    "site_brand": "Chaqmoq Admin",
    "welcome_sign": "Chaqmoq Academy boshqaruv paneliga xush kelibsiz",
    "copyright": "Chaqmoq Academy © 2025",
    
    # Apple-style Light Theme
    "theme": "flatly",

    # Logos (agar bo'lsa)
    # "site_logo": "images/chaqmoq_logo.png",
    # "login_logo": "images/chaqmoq_logo.png",

    # Top navigation settings
    "topmenu_links": [
        {"name": "Bosh sahifa", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"model": "accounts.user"},
        {"model": "education.category"},
        {"app": "store"},
    ],

    # User menu items
    "usermenu_links": [
        {"name": "Profil", "url": "admin:password_change"},
        {"name": "Chiqish", "url": "admin:logout"},
    ],

    # Sidebar settings
    "show_sidebar": True,
    "navigation_expanded": True,

    # Custom icons for each model (fontawesome)
    "icons": {
        "accounts.User": "fas fa-user",
        "accounts.Center": "fas fa-school",

        "chaqmoq.ChaqmoqQoidalari": "fas fa-bolt",
        "chaqmoq.ChaqmoqYozuvlari": "fas fa-keyboard",

        "education.Category": "fas fa-layer-group",
        "education.Davomatlar": "fas fa-calendar-check",
        "education.Guruh": "fas fa-users",
        "education.GuruxgaQoshilishlar": "fas fa-user-plus",
        "education.KunlikchaqmoqLimitlari": "fas fa-clock",
        "education.Tolovlar": "fas fa-wallet",

        "store.Products": "fas fa-box",
        "store.ProductImages": "fas fa-images",
        "store.Leads": "fas fa-address-book",
        "store.LeadStatus": "fas fa-flag",
        "store.Sotuvlar": "fas fa-shopping-cart",
        "store.XaridSorovlari": "fas fa-file-invoice",
        "store.Yonalish": "fas fa-route",
        "store.Izohlar": "fas fa-comments",
    },

    # UI Tweaks
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {"auth.user": "collapsible"},
    
    # Footer settings
    "show_ui_builder": False,
}


# ===== Middleware =====
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Static optimization
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.TenantMiddleware",
    # "billing.middleware.SubscriptionMiddleware",  # ❌ Vaqtinchalik o'chirildi - redirect loop
    # "core.middleware_rbac.RoleBasedAccessMiddleware",  # ❌ Vaqtinchalik o'chirildi
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

# ===== Database Switcher =====
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
else:  # Local development mode
    DATABASES = {
        "default": {
            "ENGINE": os.getenv("LOCAL_DB_ENGINE", "django.db.backends.sqlite3"),
            "NAME": BASE_DIR / os.getenv("LOCAL_DB_NAME", "db.sqlite3"),
            "OPTIONS": {
                "timeout": 60,
            }
        }
    }

# ===== Authentication =====
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailOrUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 6}},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "login"

# ===== Locale =====
LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "uz")
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Tashkent")
USE_I18N = True
USE_TZ = True

# ===== Static Files =====
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

# ===== Media Files (Local & Render Disk) =====
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if MODE == "render":
    MEDIA_ROOT = "/opt/render/project/src/media"

# ===== Misc =====
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ===== Logging (Render Debugging) =====
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
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
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}
