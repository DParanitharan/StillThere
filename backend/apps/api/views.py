"""API view implementations for upload, overlay, analysis, and export routes."""

import logging
import os
import tempfile
import uuid
import requests
import zipfile

import geopandas as gpd
from pathlib import Path
from django.shortcuts import get_object_or_404,render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from rest_framework import status
from rest_framework.decorators import api_view
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
from .models import AnalysisSession
from .serializers import AnalysisSessionSerializer

logger = logging.getLogger(__name__)

class LoginView(APIView):
    authentication_classes = []  # allow unauthenticated
    permission_classes = []

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({"error": "Missing username/password"}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        login(request, user)  # sets session cookie
        return Response({"ok": True, "username": user.username})


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
    """Return results for a previously started analysis job."""


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

class ClassificationProgressView(APIView):
    """Poll classification progress for a session."""

    def get(self, request, session_id):
        progress = get_progress(session_id)
        if progress is None:
            return Response({'status': 'not_found'}, status=404)
        return Response(progress)

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
    
class BuildingExtractionView(APIView):
    """Extract buildings from a shapefile."""

    def post(self, request):
        import json
        import zipfile

        session_id = request.data.get('session_id')
        output_dir = 'media/outputs/'
        os.makedirs(output_dir, exist_ok=True)

        logger.info(f"BuildingExtractionView POST called. Session: {session_id}")

        session = get_object_or_404(UploadSession, id=session_id)
        zip_path = session.source_zip.path

        with zipfile.ZipFile(zip_path) as zf:
            shp_files = [f for f in zf.namelist() if f.endswith('.shp')]
            if not shp_files:
                return Response({'error': 'No .shp found in zip'}, status=400)
            shp_path = shp_files[0]

        gdf = gpd.read_file(f"zip://{zip_path}!{shp_path}")
        gdf = gdf[gdf.geometry.notnull()].copy()
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        gdf = gdf[gdf.geometry.is_valid].copy()

        logger.info(f"Input shapefile has {len(gdf)} polygons")

        # Classify buildings against current imagery
        result_gdf = classify_buildings(
            input_gdf=gdf,
            output_dir=output_dir,
            zoom=19,
            session_id=session_id,
        )

        # Clean up geometries
        result_gdf['geometry'] = result_gdf['geometry'].apply(to_2d_geom)

        feature_collection = json.loads(result_gdf.to_json())
        logger.info(f"Returning {len(result_gdf)} classified buildings")
        return Response(feature_collection, status=200)

class AnalysisSessionListView(APIView):
    """List all analysis sessions or create a new one."""

    def get(self, request):
        sessions = AnalysisSession.objects.all()
        serializer = AnalysisSessionSerializer(sessions, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AnalysisSessionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  

