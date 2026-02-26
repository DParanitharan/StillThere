"""API view implementations for upload, overlay, analysis, and export routes."""

import logging
import os
import tempfile
import uuid
import requests
import zipfile

import geopandas as gpd
from pathlib import Path
from django.shortcuts import get_object_or_404
from rest_framework import status
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


class UploadProcessingError(Exception):
    """Raised when shapefile processing fails for expected upload-related reasons."""


def _create_upload_session_from_zip(uploaded_file) -> UploadSession:
    """Create and persist an upload session from a zipped shapefile upload."""
    session = UploadSession.objects.create(
        source_zip=uploaded_file,
        dataset_name=os.path.splitext(uploaded_file.name)[0],
    )

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        # Find the .shp file inside the zip 
        with zipfile.ZipFile(tmp_path) as z:
            shp_files = [f for f in z.namelist() if f.endswith('.shp')]
            if not shp_files:
                raise UploadProcessingError("No .shp file found in zip")
            shp_path = shp_files[0]

        tmp_path_str = Path(tmp_path).as_posix()
        gdf = gpd.read_file(f"zip://{tmp_path_str}!{shp_path}")
        gdf = gdf[gdf.geometry.notnull()].copy()

        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
            
        session.crs = str(gdf.crs) if gdf.crs else ""
    
        session.building_count = int(len(gdf))
        session.footprints_geojson = gdf.__geo_interface__
        session.save(update_fields=["crs", "building_count", "footprints_geojson"])
        return session
    except (OSError, RuntimeError, ValueError) as exc:
        session.delete()
        raise UploadProcessingError(str(exc)) from exc
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


class HealthView(APIView):
    """Simple health endpoint."""

    def get(self, request):
        """Return API liveness status."""
        serializer = HealthResponseSerializer({"status": "ok"})
        return Response(serializer.data)


class UploadShapefileView(APIView):
    """
    Accept a ZIP file with shapefile parts, parse via GeoPandas,
    store minimal metadata + GeoJSON for frontend map rendering.
    """

    def post(self, request):
        """Validate and process uploaded shapefile zip into stored GeoJSON."""
        request_serializer = UploadRequestSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(
                {"error": "Invalid upload", "details": request_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_file = request_serializer.validated_data["file"]
        try:
            session = _create_upload_session_from_zip(uploaded_file)
        except UploadProcessingError as exc:
            logger.warning("Upload rejected: %s", str(exc))
            return Response(
                {"error": "Invalid shapefile zip", "details": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except OSError:
            logger.exception("Unexpected filesystem error while processing upload.")
            return Response(
                {"error": "Failed to process upload"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = UploadResponseSerializer(
            {
                "session_id": session.id,
                "dataset_name": session.dataset_name,
                "crs": session.crs,
                "building_count": session.building_count,
                # Frontend expects response.data.geojson
                "geojson": session.footprints_geojson,
            }
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class GetOverlayView(APIView):
    """Return saved overlay GeoJSON for a session."""

    def get(self, request, session_id):
        """Fetch overlay payload by upload session id."""
        session = get_object_or_404(UploadSession, id=session_id)
        serializer = OverlayResponseSerializer(
            {"session_id": session.id, "geojson": session.footprints_geojson}
        )
        return Response(serializer.data)


class AnalysisStartStubView(APIView):
    """
    Matches current frontend API call: POST /api/analysis/<upload_id>/
    """

    def post(self, request, upload_id):
        """Return stub analysis start response."""
        get_object_or_404(UploadSession, id=upload_id)
        analysis_id = uuid.uuid4()
        serializer = AnalysisStubSerializer(
            {
                "analysis_id": analysis_id,
                "upload_id": upload_id,
                "status": "not_implemented",
                "message": "Change detection not implemented yet.",
            }
        )
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class AnalysisResultsStubView(APIView):
    """
    Matches current frontend API call: GET /api/analysis/<analysis_id>/results/
    """

    def get(self, request, analysis_id):
        """Return stub analysis results."""
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
    """
    Additional explicit route requested: POST /api/analyze/<session_id>/
    """

    def post(self, request, session_id):
        """Return stub response for explicit analyze endpoint."""
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
    """Return stub response for export endpoint."""

    def get(self, request, session_id, export_type):
        """Return requested export type in a stub payload."""
        session = get_object_or_404(UploadSession, id=session_id)
        serializer = ExportResponseSerializer(
            {
                "session_id": session.id,
                "export_type": export_type,
                "status": "not_implemented",
            }
        )
        return Response(serializer.data)

class GeocodeView(APIView):
    """
    Backend-only Google API call. Frontend calls this endpoint; backend uses secret key.
    GET /api/geocode/?address=...
    """

    def get(self, request):
        address = request.query_params.get("address")
        if not address:
            return Response({"error": "Missing address"}, status=status.HTTP_400_BAD_REQUEST)

        key = os.getenv("GOOGLE_EARTH_API_KEY")
        if not key:
            return Response({"error": "GOOGLE_EARTH_API_KEY not set"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        r = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": key},
            timeout=10,
        )

        # Pass through Google's response (you can filter fields later)
        return Response(r.json(), status=r.status_code)