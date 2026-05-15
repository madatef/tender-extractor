from django.apps import AppConfig


class ObservabilityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.observability"

    def ready(self):
        from django.conf import settings

        from apps.observability.logging.setup import configure_logging

        configure_logging(log_level=getattr(settings, "LOG_LEVEL", "INFO"))
