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
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# ===== Installed Apps =====
INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "django_extensions",
    "django.contrib.humanize",

    # Local apps
    "accounts",
    "education",
    "chaqmoq",
    "store",
    "core",
]

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
            ],
        },
    },
]

# ===== Database =====
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
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ===== Media Files (Render Disk) =====
MEDIA_URL = "/media/"
MEDIA_ROOT = "/opt/render/project/src/media"  # The mount path of Render Disk

# ===== Misc =====
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

"""
# Django settings for Chaqmoq Academy project.
# Auto-detects: local (SQLite) or Render (PostgreSQL)
# """
# import os
# from pathlib import Path
# from dotenv import load_dotenv

# load_dotenv()
# BASE_DIR = Path(__file__).resolve().parent.parent

# # ===== Core =====
# SECRET_KEY = os.getenv("SECRET_KEY")
# DEBUG = os.getenv("DEBUG", "False").lower() == "true"
# ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# # ===== Installed Apps =====
# INSTALLED_APPS = [
#     "django.contrib.admin",
#     "django.contrib.auth",
#     "django.contrib.contenttypes",
#     "django.contrib.sessions",
#     "django.contrib.messages",
#     "django.contrib.staticfiles",
#     "django_extensions",
#     "django.contrib.humanize",
#     "accounts",
#     "education",
#     "chaqmoq",
#     "store",
#     "core",
# ]

# # ===== Middleware =====
# MIDDLEWARE = [
#     "django.middleware.security.SecurityMiddleware",
#     "whitenoise.middleware.WhiteNoiseMiddleware",
#     "django.contrib.sessions.middleware.SessionMiddleware",
#     "django.middleware.common.CommonMiddleware",
#     "django.middleware.csrf.CsrfViewMiddleware",
#     "django.contrib.auth.middleware.AuthenticationMiddleware",
#     "django.contrib.messages.middleware.MessageMiddleware",
#     "django.middleware.clickjacking.XFrameOptionsMiddleware",
# ]

# ROOT_URLCONF = "config.urls"
# WSGI_APPLICATION = "config.wsgi.application"

# # ===== Templates =====
# TEMPLATES = [
#     {
#         "BACKEND": "django.template.backends.django.DjangoTemplates",
#         "DIRS": [BASE_DIR / "templates"],
#         "APP_DIRS": True,
#         "OPTIONS": {
#             "context_processors": [
#                 "django.template.context_processors.debug",
#                 "django.template.context_processors.request",
#                 "django.contrib.auth.context_processors.auth",
#                 "django.contrib.messages.context_processors.messages",
#             ],
#         },
#     },
# ]

# # ===== Database Switcher =====
# MODE = os.getenv("MODE", "local")

# if MODE == "render":
#     DATABASES = {
#         "default": {
#             "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.postgresql"),
#             "NAME": os.getenv("DB_NAME"),
#             "USER": os.getenv("DB_USER"),
#             "PASSWORD": os.getenv("DB_PASSWORD"),
#             "HOST": os.getenv("DB_HOST"),
#             "PORT": os.getenv("DB_PORT", "5432"),
#             "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "require")},
#         }
#     }
# else:  # Local development mode
#     DATABASES = {
#         "default": {
#             "ENGINE": os.getenv("LOCAL_DB_ENGINE", "django.db.backends.sqlite3"),
#             "NAME": BASE_DIR / os.getenv("LOCAL_DB_NAME", "db.sqlite3"),
#         }
#     }

# # ===== Authentication =====
# AUTH_USER_MODEL = "accounts.User"
# AUTHENTICATION_BACKENDS = [
#     "accounts.backends.EmailOrUsernameBackend",
#     "django.contrib.auth.backends.ModelBackend",
# ]

# LOGIN_URL = "login"
# LOGIN_REDIRECT_URL = "core:home"
# LOGOUT_REDIRECT_URL = "login"

# # ===== Locale =====
# LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "uz")
# TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Tashkent")
# USE_I18N = True
# USE_TZ = True

# # ===== Static & Media =====
# STATIC_URL = "/static/"
# STATIC_ROOT = BASE_DIR / "staticfiles"
# STATICFILES_DIRS = [BASE_DIR / "static"]
# STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# MEDIA_URL = "/media/"
# MEDIA_ROOT = BASE_DIR / "media"  # localda ishlaydi

# # Agar Renderda bo‘lsa
# if MODE == "render":
#     MEDIA_ROOT = "/opt/render/project/src/media"

# DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
