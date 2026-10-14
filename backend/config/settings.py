import os
from pathlib import Path

from dotenv import load_dotenv

# The backend/ folder. Used to find .env and the built React app.
BASE_DIR = Path(__file__).resolve().parent.parent

# Reads backend/.env into environment variables (the file is git-ignored).
load_dotenv(BASE_DIR / ".env")

# Local runs use this dev-only key. On Cloud Run the real key comes from Secret Manager.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key")

# On locally, off in production (the Dockerfile sets DJANGO_DEBUG=0).
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

# Host names Django will answer to, from a comma separated list.
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

# Only what we use: DRF for the API and our own trips app.
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "rest_framework",
    "trips",
]

# Code that runs on every request. WhiteNoise serves the built React files.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# The file that maps web addresses to views.
ROOT_URLCONF = "config.urls"

# What gunicorn runs in production.
WSGI_APPLICATION = "config.wsgi.application"

# The app stores nothing, so there is no database.
DATABASES = {}

# Weather answers are kept in memory for a while (see weather.py).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "weather-truck-routing",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True

STATIC_URL = "static/"

# The built React app. WhiteNoise serves it at "/" (index.html) next to the API.
WHITENOISE_ROOT = BASE_DIR.parent / "frontend" / "dist"
WHITENOISE_INDEX_FILE = True

# API responses are always JSON, with no login or user accounts.
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
}

# Read from backend/.env locally and from Secret Manager on Cloud Run.
HERE_API_KEY = os.environ.get("HERE_API_KEY", "")
