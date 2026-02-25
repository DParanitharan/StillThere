"""App configuration for API endpoints."""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Configuration metadata for the API app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.api"
