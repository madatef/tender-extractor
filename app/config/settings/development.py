"""
Development settings — local run without Docker.
"""
from .base import *  # noqa: F401, F403

DEBUG = True

CORS_ALLOW_ALL_ORIGINS = True

# Swagger accessible without auth in development
SPECTACULAR_SETTINGS["SERVE_AUTHENTICATION_CLASSES"] = []  # noqa: F405
SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.AllowAny"]  # noqa: F405
