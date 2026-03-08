"""App configuration for geospatial models."""

from django.apps import AppConfig


class GeoConfig(AppConfig):
    """Configuration metadata for the geo app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.geo"
