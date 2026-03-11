"""Serializer classes for API request/response payloads."""

import os
import zipfile

from rest_framework import serializers
from .models import AnalysisSession


class HealthResponseSerializer(serializers.Serializer):
    """Health-check response schema."""

    status = serializers.CharField()


class UploadRequestSerializer(serializers.Serializer):
    """Upload request schema with basic archive validation."""

    file = serializers.FileField()

    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
    REQUIRED_SHAPEFILE_EXTENSIONS = {".shp", ".shx", ".dbf"}

    def validate_file(self, value):
        """Validate uploaded file type, size, and required shapefile members."""
        filename = (value.name or "").lower()
        if not filename.endswith(".zip"):
            raise serializers.ValidationError("Upload must be a .zip file.")

        if value.size > self.MAX_FILE_SIZE_BYTES:
            raise serializers.ValidationError("Upload exceeds 50MB limit.")

        # Sanity check archive structure before expensive processing.
        try:
            with zipfile.ZipFile(value) as archive:
                members = {
                    os.path.splitext(os.path.basename(name))[1].lower()
                    for name in archive.namelist()
                    if not name.endswith("/")
                }
        except (zipfile.BadZipFile, OSError):
            raise serializers.ValidationError("File is not a valid ZIP archive.")
        finally:
            value.seek(0)

        if not self.REQUIRED_SHAPEFILE_EXTENSIONS.issubset(members):
            raise serializers.ValidationError(
                "ZIP must include .shp, .shx and .dbf shapefile components."
            )

        return value


class UploadResponseSerializer(serializers.Serializer):
    """Upload response schema used by frontend map flow."""

    session_id = serializers.UUIDField()
    dataset_name = serializers.CharField()
    crs = serializers.CharField(allow_blank=True)
    building_count = serializers.IntegerField()
    geojson = serializers.JSONField(allow_null=True)


class OverlayResponseSerializer(serializers.Serializer):
    """Overlay response schema for retrieving stored GeoJSON."""

    session_id = serializers.UUIDField()
    geojson = serializers.JSONField(allow_null=True)


class AnalysisStubSerializer(serializers.Serializer):
    """Stub schema for analysis start endpoint."""

    analysis_id = serializers.UUIDField()
    upload_id = serializers.UUIDField()
    status = serializers.CharField()
    message = serializers.CharField()


class AnalysisResultsStubSerializer(serializers.Serializer):
    """Stub schema for analysis result endpoint."""

    analysis_id = serializers.UUIDField()
    status = serializers.CharField()
    summary = serializers.JSONField()
    features = serializers.ListField()


class AnalyzeResponseSerializer(serializers.Serializer):
    """Stub schema for generic analyze endpoint."""

    session_id = serializers.UUIDField()
    status = serializers.CharField()
    message = serializers.CharField()


class ExportResponseSerializer(serializers.Serializer):
    """Stub schema for export endpoint."""

    session_id = serializers.UUIDField()
    export_type = serializers.CharField()
    status = serializers.CharField()


class AnalysisSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisSession
        fields = ['id', 'session_id', 'title', 'filename', 'summary', 'created_at']
