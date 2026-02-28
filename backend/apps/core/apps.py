"""App configuration for the core backend app."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Configuration metadata for the core app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
