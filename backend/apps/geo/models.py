"""Data models for uploaded geospatial datasets."""

import uuid

from django.contrib.gis.db import models as gis_models
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


class UploadedFeature(gis_models.Model):
    """
    Individual geometry feature from an uploaded shapefile.
    Stored in PostGIS so you can query with ST_Within, ST_Intersects,
    ST_Buffer, etc.
    """
    upload_session = gis_models.ForeignKey(
        "geo.UploadSession",
        on_delete=gis_models.CASCADE,
        related_name="features",
        help_text="The upload session this feature belongs to.",
    )
    feature_index = gis_models.IntegerField(
        help_text="Original row index inside the shapefile.",
    )
    properties = gis_models.JSONField(
        default=dict,
        blank=True,
        help_text="All non-geometry attributes from the shapefile row.",
    )
    geom = gis_models.GeometryField(
        srid=4326,
        help_text="Geometry in WGS-84. Queryable with ST_Within, ST_Intersects, ST_Buffer, etc.",
    )
    uploaded_at = gis_models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["upload_session", "feature_index"]
        indexes = [
            gis_models.Index(fields=["upload_session", "feature_index"]),
        ]

    def __str__(self):
        return f"Feature #{self.feature_index} (session {self.upload_session_id})"


class ClassifiedBuilding(gis_models.Model):
    """
    Stores the classification result for each building after analysis.
    Persists in PostGIS so results survive restarts and are spatially queryable.
    """

    CLASSIFICATION_CHOICES = [
        ("unchanged", "Unchanged"),
        ("modified", "Modified"),
        ("removed", "Removed"),
        ("new", "New"),
        ("unknown", "Unknown"),
    ]

    upload_session = gis_models.ForeignKey(
        "geo.UploadSession",
        on_delete=gis_models.CASCADE,
        related_name="classified_buildings",
    )
    analysis_session = gis_models.ForeignKey(
        "api.AnalysisSession",
        on_delete=gis_models.CASCADE,
        related_name="classified_buildings",
        null=True,
        blank=True,
    )
    feature_index = gis_models.IntegerField(
        help_text="Original row index from the uploaded shapefile.",
    )
    classification = models.CharField(
        max_length=20,
        choices=CLASSIFICATION_CHOICES,
        db_index=True,
    )
    confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Classification confidence score (0-1).",
    )
    iou_score = models.FloatField(
        null=True,
        blank=True,
        help_text="IoU between input polygon and SAM-detected polygon.",
    )
    pixel_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Pixel-based building presence score.",
    )
    properties = models.JSONField(
        default=dict,
        blank=True,
        help_text="Original shapefile attributes + classification metadata.",
    )
    input_geom = gis_models.GeometryField(
        srid=4326,
        help_text="Original building footprint from shapefile.",
    )
    detected_geom = gis_models.GeometryField(
        srid=4326,
        null=True,
        blank=True,
        help_text="SAM-detected building footprint (may differ from input).",
    )
    classified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["upload_session", "feature_index"]
        indexes = [
            models.Index(fields=["upload_session", "classification"]),
            models.Index(fields=["analysis_session", "classification"]),
        ]

    def __str__(self):
        return f"Building #{self.feature_index} → {self.classification} ({self.upload_session_id})"
