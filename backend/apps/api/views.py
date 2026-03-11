"""API view implementations for upload, overlay, analysis, and export routes."""

import json
import logging
import os
import tempfile
import threading
import requests
import uuid
import zipfile


import geopandas as gpd
from pathlib import Path
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import (
    AllowAny,
)  # from rest_framework.permissions import IsAuthenticated - change back to this when doing auth implementation for production
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
from apps.geo.utils import (
    classify_buildings,
    get_progress,
    to_2d_geom,
)

logger = logging.getLogger(__name__)

VALID_EXPORT_TYPES = {"csv", "pdf"}


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

        original_crs = str(gdf.crs) if gdf.crs else ""

        if gdf.crs:
            gdf = gdf.to_crs(epsg=4326)

        session = UploadSession.objects.create(
            source_zip=uploaded_file,
            dataset_name=os.path.splitext(uploaded_file.name)[0],
            crs=original_crs,
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
                    "removed": 0,
                    "modified": 0,
                    "unchanged": 0,
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
                "message": "Change detection not implemented yet. Classifies removed, modified, and unchanged only.",
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


class ClassificationResultView(APIView):
    """Return the classified buildings GeoJSON for a completed session."""

    def get(self, request, session_id):
        result_path = os.path.join(
            "media", "outputs", str(session_id), "buildings_classified.geojson"
        )
        if not os.path.exists(result_path):
            return Response(
                {"error": "Results not ready or session not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            with open(result_path, "r", encoding="utf-8") as f:
                return Response(json.load(f))
        except (OSError, ValueError) as exc:
            logger.error("Failed to read result for session %s: %s", session_id, exc)
            return Response(
                {"error": "Failed to read result file"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ClassificationProgressView(APIView):
    """Poll classification progress for a session."""

    def get(self, request, session_id):
        progress = get_progress(session_id)
        if progress is None:
            # Thread hasn't written to cache yet — return an initializing state
            # so the frontend doesn't treat this as a hard error.
            return Response(
                {
                    "phase": "initializing",
                    "progress": 0,
                    "processed": 0,
                    "total": 0,
                    "elapsed": 0,
                    "eta_seconds": None,
                    "counts": {"unchanged": 0, "modified": 0, "removed": 0, "error": 0},
                    "logs": [],
                }
            )
        return Response(progress)


class GeocodeView(APIView):
    """
    Backend-only Google API call. Frontend calls this endpoint; backend uses secret key.
    GET /api/geocode/?address=...
    """

    def get(self, request):
        address = request.query_params.get("address")
        if not address:
            return Response(
                {"error": "Missing address"}, status=status.HTTP_400_BAD_REQUEST
            )

        key = os.getenv("GOOGLE_EARTH_API_KEY")
        if not key:
            return Response(
                {"error": "GOOGLE_EARTH_API_KEY not set"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        r = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": key},
            timeout=10,
        )

        # Pass through Google's response (you can filter fields later)
        return Response(r.json(), status=r.status_code)


class BuildingExtractionView(APIView):
    """Extract buildings from a shapefile."""

    def post(self, request):

        session_id = request.data.get("session_id")
        if not session_id:
            return Response(
                {"error": "Missing session_id"}, status=status.HTTP_400_BAD_REQUEST
            )

        output_dir = os.path.join("media", "outputs", str(session_id))
        os.makedirs(output_dir, exist_ok=True)

        logger.info("BuildingExtractionView POST called. Session: %s", session_id)

        session = get_object_or_404(UploadSession, id=session_id)

        if not session.footprints_geojson:
            return Response(
                {"error": "Session has no stored footprints; re-upload the shapefile."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        gdf = gpd.GeoDataFrame.from_features(
            session.footprints_geojson["features"], crs="EPSG:4326"
        )
        gdf = gdf[gdf.geometry.notnull() & gdf.geometry.is_valid].copy()

        logger.info("Input shapefile has %d polygons", len(gdf))

        def _run_classification():
            try:
                result_gdf = classify_buildings(
                    input_gdf=gdf,
                    output_dir=output_dir,
                    zoom=19,
                    session_id=session_id,
                )
                result_gdf["geometry"] = result_gdf["geometry"].apply(to_2d_geom)
                logger.info(
                    "Classification complete for session %s (%d buildings)",
                    session_id,
                    len(result_gdf),
                )
            except Exception:
                logger.exception("Classification failed for session %s", session_id)

        thread = threading.Thread(target=_run_classification, daemon=True)
        thread.start()

        return Response(
            {"session_id": session_id, "status": "processing"},
            status=status.HTTP_202_ACCEPTED,
        )
