"""Django settings for Flowdow project."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    """Parses a boolean environment variable safely."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1", "yes", "on")


INSECURE_SECRET_KEYS: frozenset[str] = frozenset(
    {
        "",
        "flowdow-dev-secret-key-insecure-replace-in-production-min-50-chars-here",
        "django-insecure-change-me",
        "change-me",
        "changeme",
        "secret",
    }
)
INSECURE_DB_PASSWORDS: frozenset[str] = frozenset(
    {
        "",
        "flowdow_secure_password",
        "flowdow",
        "postgres",
        "password",
        "changeme",
        "admin",
    }
)


def validate_production_settings(
    *,
    debug: bool,
    secret_key: str,
    allowed_hosts: list[str],
    db_engine: str,
    db_password: str,
) -> None:
    """Rejects unsafe secrets, hosts, or default DB credentials when DEBUG=False."""
    if debug:
        return

    cleaned_secret = (secret_key or "").strip()
    if (
        cleaned_secret in INSECURE_SECRET_KEYS
        or cleaned_secret.startswith("django-insecure-")
        or len(cleaned_secret) < 50
        or len(set(cleaned_secret)) < 5
    ):
        raise ImproperlyConfigured(
            "Production mode (DEBUG=False) requires a strong SECRET_KEY (>= 50 random chars)."
        )

    if not allowed_hosts or "*" in allowed_hosts or "0.0.0.0" in allowed_hosts:
        raise ImproperlyConfigured(
            "Production mode (DEBUG=False) requires explicit ALLOWED_HOSTS without '*' or '0.0.0.0'."
        )

    if "postgresql" in db_engine and (db_password or "").strip() in INSECURE_DB_PASSWORDS:
        raise ImproperlyConfigured(
            "Production mode (DEBUG=False) requires a non-default DB_PASSWORD for PostgreSQL."
        )


# Security settings: default DEBUG to False; enable explicitly in local .env/dev environments.
DEBUG = _env_bool("DEBUG", default=False)

_raw_secret_key = os.getenv("SECRET_KEY", "").strip()
if _raw_secret_key:
    SECRET_KEY = _raw_secret_key
elif DEBUG:
    # Ephemeral development secret avoids shipping any static fallback credential in code.
    SECRET_KEY = get_random_secret_key()
else:
    SECRET_KEY = ""

_default_allowed_hosts = "localhost,127.0.0.1" if DEBUG else ""
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", _default_allowed_hosts).split(",")
    if host.strip()
]
if DEBUG and "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()
]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    # Flowdow Domain Apps
    "apps.core",
    "apps.accounts",
    "apps.organizations",
    "apps.documents",
    "apps.templates_manager",
    "apps.data_sources",
    "apps.mapping",
    "apps.generation",
    "apps.audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.global_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database configuration
# Defaults to PostgreSQL with environment-driven variables.
# When DB_ENGINE is explicitly sqlite3 or DB_NAME points to sqlite, use SQLite.
DB_ENGINE = os.getenv("DB_ENGINE", "django.db.backends.postgresql")
DB_NAME = os.getenv("DB_NAME", "flowdow")
DB_USER = os.getenv("DB_USER", "flowdow")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

validate_production_settings(
    debug=DEBUG,
    secret_key=SECRET_KEY,
    allowed_hosts=ALLOWED_HOSTS,
    db_engine=DB_ENGINE,
    db_password=DB_PASSWORD,
)

if "sqlite3" in DB_ENGINE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / (DB_NAME if DB_NAME.endswith(".sqlite3") else f"{DB_NAME}.sqlite3"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": DB_NAME,
            "USER": DB_USER,
            "PASSWORD": DB_PASSWORD,
            "HOST": DB_HOST,
            "PORT": DB_PORT,
            "CONN_MAX_AGE": 60,
        }
    }

# Custom User Model (Must be defined before first migration)
AUTH_USER_MODEL = "accounts.User"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Authentication URLs
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

# Internationalization
LANGUAGE_CODE = "ru"
LANGUAGES = [
    ("ru", "Русский"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files (Uploaded templates, data sources, generated documents)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Upload memory thresholds (bounded above app-level file validators to prevent body DoS)
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", str(30 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", str(10 * 1024 * 1024)))

# Browser, Cookie, and Transport Security Headers
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

if not DEBUG:
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", default=True)
    CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", default=True)
    SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
    SECURE_HSTS_PRELOAD = _env_bool("SECURE_HSTS_PRELOAD", default=False)
    if _env_bool("USE_X_FORWARDED_PROTO", default=False):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Flowdow Application Settings
FLOWDOW_ORGANIZATION_NAME = os.getenv("FLOWDOW_ORGANIZATION_NAME", "Flowdow Workspace")
FLOWDOW_DEFAULT_PAGE_SIZE = int(os.getenv("FLOWDOW_DEFAULT_PAGE_SIZE", "25"))
