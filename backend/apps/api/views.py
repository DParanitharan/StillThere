"""API view implementations for upload, overlay, analysis, and export routes."""

import logging
import os
import tempfile
import threading
import uuid
import requests
import zipfile
import json

import geopandas as gpd
from pathlib import Path
from django.shortcuts import get_object_or_404,render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

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
from apps.geo.models import UploadSession, ClassifiedBuilding
from apps.geo.utils import (
    classify_buildings,
    get_progress,
)
from apps.geo.ingest import ingest_geodataframe_to_postgis
from .models import AnalysisSession
from .serializers import AnalysisSessionSerializer

from apps.api.chat import chat_query

logger = logging.getLogger(__name__)

class WhoAmIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"username": request.user.username})

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


def _create_upload_session_from_zip(uploaded_file) -> "UploadSession":
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
            shp_files = [f for f in z.namelist() if f.endswith(".shp")]
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
        # ── persist individual features to PostGIS ──────────
        try:
            count = ingest_geodataframe_to_postgis(gdf, session)
            logger.info("Saved %d features to PostGIS for session %s", count, session.id)
        except Exception as exc:
            logger.error("PostGIS ingest failed for session %s: %s", session.id, exc)
            # Non-fatal: the session still has the GeoJSON blob,
            # but spatial queries won't work for this upload.
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
            return Response({"status": "not_found"}, status=404)
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

        key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not key:
            return Response(
                {"error": "GOOGLE_MAPS_API_KEY not set"},
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
    """Start building extraction in a background thread; poll /api/progress/<session_id>/ for updates."""

    def post(self, request):
        session_id = request.data.get("session_id")
        if not session_id:
            return Response(
                {"error": "session_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        session = get_object_or_404(UploadSession, id=session_id)
        zip_path = session.source_zip.path

        with zipfile.ZipFile(zip_path) as zf:
            shp_files = [f for f in zf.namelist() if f.endswith(".shp")]
            if not shp_files:
                return Response(
                    {"error": "No .shp found in zip"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            shp_path = shp_files[0]

        gdf = gpd.read_file(f"zip://{zip_path}!{shp_path}")
        gdf = gdf[gdf.geometry.notnull()].copy()
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        gdf = gdf[gdf.geometry.is_valid].copy()

        logger.info(
            "BuildingExtractionView: starting background thread for session %s (%d polygons)",
            session_id,
            len(gdf),
        )

        output_dir = "media/outputs/"
        os.makedirs(output_dir, exist_ok=True)

        def _run():
            classify_buildings(
                input_gdf=gdf,
                output_dir=output_dir,
                zoom=19,
                session_id=session_id,
            )

        threading.Thread(target=_run, daemon=True).start()

        return Response(
            {"status": "started", "session_id": str(session_id)},
            status=status.HTTP_202_ACCEPTED,
        )


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


class ClassificationResultsView(APIView):
    """
    GET /api/classification/<session_id>/
    Returns persisted classification results from PostGIS.

    Query params:
        ?classification=removed      — filter by type
        ?bbox=140.85,36.90,140.95,36.97  — spatial filter
    """

    def get(self, request, session_id):
        qs = ClassifiedBuilding.objects.filter(upload_session_id=session_id)

        # Filter by classification type
        classification = request.query_params.get("classification")
        if classification:
            qs = qs.filter(classification=classification)

        # Spatial bounding box filter
        bbox = request.query_params.get("bbox")
        if bbox:
            try:
                from django.contrib.gis.geos import Polygon as GeosPolygon
                coords = [float(c) for c in bbox.split(",")]
                box = GeosPolygon.from_bbox(coords)
                box.srid = 4326
                qs = qs.filter(input_geom__intersects=box)
            except (ValueError, IndexError):
                return Response(
                    {"error": "bbox must be xmin,ymin,xmax,ymax"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Build GeoJSON FeatureCollection
        features = []
        for b in qs:
            feature = {
                "type": "Feature",
                "geometry": json.loads(b.input_geom.geojson),
                "properties": {
                    "id": b.id,
                    "feature_index": b.feature_index,
                    "classification": b.classification,
                    "confidence": b.confidence,
                    "iou_score": b.iou_score,
                    "pixel_score": b.pixel_score,
                    **b.properties,
                },
            }
            if b.detected_geom:
                feature["properties"]["detected_geometry"] = json.loads(b.detected_geom.geojson)
            features.append(feature)

        # Summary stats
        from django.db.models import Count
        summary = dict(
            qs.values("classification")
              .annotate(count=Count("id"))
              .values_list("classification", "count")
        )

        return Response({
            "type": "FeatureCollection",
            "count": qs.count(),
            "summary": summary,
            "features": features,
        })

class ChatQueryView(APIView):

    def post(self, request):
        message = request.data.get("message", "").strip()
        session_id = request.data.get("session_id")

        if not message:
            return Response(
                {"error": "message is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not os.getenv("GEMINI_API_KEY"):
            return Response(
                {"error": "GEMINI_API_KEY not configured. Get one at https://aistudio.google.com/apikey"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        result = chat_query(message, session_id)
        return Response(result)
