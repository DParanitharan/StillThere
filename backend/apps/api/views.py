"""API view implementations for upload, overlay, analysis, and export routes."""

import json
import logging
import os
import tempfile
import uuid
import zipfile
from pathlib import Path

import geopandas as gpd
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.serializers import (
    AnalysisResultsStubSerializer,
    AnalysisStubSerializer,
    AnalyzeResponseSerializer,
    ExportResponseSerializer,
    HealthResponseSerializer,
    OverlayResponseSerializer,
    UploadRequestSerializer,
    UploadResponseSerializer,
)
from apps.geo.models import UploadSession

logger = logging.getLogger(__name__)

VALID_EXPORT_TYPES = {"csv", "pdf"}


@csrf_exempt
def analyze(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    payload = json.loads(request.body.decode("utf-8"))
    geo_data = payload.get("geoData")

    # TODO: do real analysis
    return JsonResponse({
        "added": 1,
        "removed": 2,
        "modified": 3,
        "unchanged": 4,
        "review": 5
    })


class UploadProcessingError(Exception):
    """Raised when shapefile processing fails for expected upload-related reasons."""


def _read_shapefile_from_zip(tmp_path):
    """Extract a zipped shapefile and return a clean GeoDataFrame."""
    with tempfile.TemporaryDirectory() as extract_dir:
        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(extract_dir)

        shp_files = list(Path(extract_dir).rglob("*.shp"))

        if not shp_files:
            raise UploadProcessingError("No .shp file found inside the ZIP archive.")

        if len(shp_files) > 1:
            raise UploadProcessingError(
                "Multiple .shp files found inside the ZIP archive. Please upload only one shapefile."
            )

        shp_path = shp_files[0]

        gdf = gpd.read_file(shp_path)
        gdf = gdf[gdf.geometry.notnull()].copy()
        return gdf


def _create_upload_session_from_zip(uploaded_file) -> UploadSession:
    """Create and persist an upload session from a zipped shapefile upload."""
    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        gdf = _read_shapefile_from_zip(tmp_path)

        session = UploadSession.objects.create(
            source_zip=uploaded_file,
            dataset_name=os.path.splitext(uploaded_file.name)[0],
            crs=str(gdf.crs) if gdf.crs else "",
            building_count=int(len(gdf)),
            footprints_geojson=gdf.__geo_interface__,
        )
        return session

    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        raise UploadProcessingError(str(exc)) from exc

    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


class HealthView(APIView):
    """Simple liveness endpoint."""

    permission_classes = [AllowAny]

    def get(self, request):
        """Return API health status."""
        serializer = HealthResponseSerializer({"status": "ok"})
        return Response(serializer.data)


class UploadShapefileView(APIView):
    """Accept a zipped shapefile, parse via GeoPandas, and store GeoJSON for map rendering."""

    permission_classes = [AllowAny]

    def post(self, request):
        """Validate and process uploaded shapefile ZIP into a stored session."""
        request_serializer = UploadRequestSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(
                {"error": "Invalid upload", "details": request_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_file = request_serializer.validated_data["file"]
        warnings = request_serializer.validated_data.get("warnings", [])

        try:
            session = _create_upload_session_from_zip(uploaded_file)
        except UploadProcessingError as exc:
            logger.warning("Upload rejected: %s", str(exc))
            return Response(
                {"error": "Invalid shapefile zip", "details": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception("Unexpected error while processing upload: %s", str(exc))
            return Response(
                {"error": "Failed to process upload", "details": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = UploadResponseSerializer(
            {
                "session_id": session.id,
                "dataset_name": session.dataset_name,
                "crs": session.crs,
                "building_count": session.building_count,
                "geojson": session.footprints_geojson,
                "warnings": warnings,
            }
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class GetOverlayView(APIView):
    """Return saved overlay GeoJSON for a session."""

    permission_classes = [AllowAny]

    def get(self, request, session_id):
        """Fetch overlay GeoJSON by session ID."""
        session = get_object_or_404(UploadSession, id=session_id)
        serializer = OverlayResponseSerializer(
            {"session_id": session.id, "geojson": session.footprints_geojson}
        )
        return Response(serializer.data)


class AnalysisStartStubView(APIView):
    """Trigger change detection analysis for an uploaded session."""

    permission_classes = [AllowAny]

    def post(self, request, upload_id):
        """Start analysis job and return a tracking ID."""
        session = get_object_or_404(UploadSession, id=upload_id)
        analysis_id = uuid.uuid4()

        serializer = AnalysisStubSerializer(
            {
                "analysis_id": analysis_id,
                "upload_id": session.id,
                "status": "not_implemented",
                "message": "Change detection not implemented yet.",
            }
        )
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class AnalysisResultsStubView(APIView):
    """Return results for a previously started analysis job."""

    permission_classes = [AllowAny]

    def get(self, request, analysis_id):
        """Fetch analysis results by analysis ID."""
        serializer = AnalysisResultsStubSerializer(
            {
                "analysis_id": analysis_id,
                "status": "not_implemented",
                "summary": {
                    "added": 0,
                    "removed": 0,
                    "modified": 0,
                    "unchanged": 0,
                    "review": 0,
                },
                "features": [],
            }
        )
        return Response(serializer.data)


class AnalyzeChangesStubView(APIView):
    """Trigger and return change detection results directly against a session."""

    permission_classes = [AllowAny]

    def post(self, request, session_id):
        """Run analysis directly on a session and return stub response."""
        session = get_object_or_404(UploadSession, id=session_id)
        serializer = AnalyzeResponseSerializer(
            {
                "session_id": session.id,
                "status": "not_implemented",
                "message": "Change detection not implemented yet.",
            }
        )
        return Response(serializer.data)


class ExportStubView(APIView):
    """Generate and return an export of analysis results."""

    permission_classes = [AllowAny]

    def get(self, request, session_id, export_type):
        """Return export stub response for a given session and export format."""
        if export_type not in VALID_EXPORT_TYPES:
            return Response(
                {
                    "error": f"Invalid export type. Must be one of: {sorted(VALID_EXPORT_TYPES)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = get_object_or_404(UploadSession, id=session_id)
        serializer = ExportResponseSerializer(
            {
                "session_id": session.id,
                "export_type": export_type,
                "status": "not_implemented",
            }
        )
        return Response(serializer.data)