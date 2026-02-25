"""Data models for uploaded geospatial datasets."""

import uuid

from django.db import models


class UploadSession(models.Model):
    """Stores a single uploaded shapefile archive and derived metadata."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    source_zip = models.FileField(upload_to="uploads/")
    dataset_name = models.CharField(max_length=255, blank=True)
    crs = models.CharField(max_length=64, blank=True)
    building_count = models.IntegerField(default=0)

    # MVP storage; move to normalized/PostGIS geometry tables later.
    footprints_geojson = models.JSONField(null=True, blank=True)

    def __str__(self) -> str:
        """Return compact identifier for admin/debug views."""
        return f"UploadSession({self.id})"
