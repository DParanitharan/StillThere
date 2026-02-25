import os
import tempfile
import uuid

import geopandas as gpd
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.geo.models import UploadSession


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})


class UploadShapefileView(APIView):
    """
    Accept a ZIP file with shapefile parts, parse via GeoPandas,
    store minimal metadata + GeoJSON for frontend map rendering.
    """

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"error": "Missing file"}, status=status.HTTP_400_BAD_REQUEST)

        session = UploadSession.objects.create(
            source_zip=uploaded_file,
            dataset_name=os.path.splitext(uploaded_file.name)[0],
        )

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            gdf = gpd.read_file(f"zip://{tmp_path}")
            gdf = gdf[gdf.geometry.notnull()].copy()

            session.crs = str(gdf.crs) if gdf.crs else ""
            session.building_count = int(len(gdf))

            # Keep as JSON object for direct frontend consumption.
            session.footprints_geojson = gdf.__geo_interface__
            session.save(update_fields=["crs", "building_count", "footprints_geojson"])
        except Exception as exc:
            session.delete()
            return Response(
                {"error": "Invalid shapefile zip", "details": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        return Response(
            {
                "session_id": str(session.id),
                "dataset_name": session.dataset_name,
                "crs": session.crs,
                "building_count": session.building_count,
                # Frontend expects response.data.geojson
                "geojson": session.footprints_geojson,
            },
            status=status.HTTP_201_CREATED,
        )


class GetOverlayView(APIView):
    def get(self, request, session_id):
        session = get_object_or_404(UploadSession, id=session_id)
        return Response({"session_id": str(session.id), "geojson": session.footprints_geojson})


class AnalysisStartStubView(APIView):
    """
    Matches current frontend API call: POST /api/analysis/<upload_id>/
    """

    def post(self, request, upload_id):
        get_object_or_404(UploadSession, id=upload_id)
        analysis_id = uuid.uuid4()

        return Response(
            {
                "analysis_id": str(analysis_id),
                "upload_id": str(upload_id),
                "status": "not_implemented",
                "message": "Change detection not implemented yet.",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class AnalysisResultsStubView(APIView):
    """
    Matches current frontend API call: GET /api/analysis/<analysis_id>/results/
    """

    def get(self, request, analysis_id):
        return Response(
            {
                "analysis_id": str(analysis_id),
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


class AnalyzeChangesStubView(APIView):
    """
    Additional explicit route requested: POST /api/analyze/<session_id>/
    """

    def post(self, request, session_id):
        session = get_object_or_404(UploadSession, id=session_id)
        return Response(
            {
                "session_id": str(session.id),
                "status": "not_implemented",
                "message": "Change detection not implemented yet.",
            }
        )


class ExportStubView(APIView):
    def get(self, request, session_id, export_type):
        session = get_object_or_404(UploadSession, id=session_id)
        return Response(
            {
                "session_id": str(session.id),
                "export_type": export_type,
                "status": "not_implemented",
            }
        )
