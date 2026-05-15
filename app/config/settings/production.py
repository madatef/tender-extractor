"""
Production settings.
"""
from .base import *  # noqa: F401, F403

DEBUG = False

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])  # noqa: F405

# Swagger requires auth in production
SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = [  # noqa: F405
    "rest_framework.permissions.IsAuthenticated"
]
