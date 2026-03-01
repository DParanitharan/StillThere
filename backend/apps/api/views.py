import logging
import os
import tempfile
import uuid

import geopandas as gpd
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


class UploadProcessingError(Exception): #when shapefile processing fails


def _create_upload_session_from_zip(uploaded_file) -> UploadSession:
    uploaded_file.seek(0)

    session = UploadSession.objects.create(
        source_zip=uploaded_file,
        dataset_name=os.path.splitext(uploaded_file.name)[0],
    )

    saved_path = session.source_zip.path
    tmp_path = None

    if not os.path.exists(saved_path):
        uploaded_file.seek(0)
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        read_path = tmp_path
    else:
        read_path = saved_path

    try:
        gdf = gpd.read_file(f"zip://{read_path}")
        gdf = gdf[gdf.geometry.notnull()].copy()
        session.crs = str(gdf.crs) if gdf.crs else ""
        session.building_count = int(len(gdf))
        session.footprints_geojson = gdf.__geo_interface__
        session.save(update_fields=["crs", "building_count", "footprints_geojson"])
        return session

    except Exception as exc:
        try:
            session.delete()
        except Exception:
            logger.exception(
                "Failed to clean up session %s after processing error.", session.id
            )
        raise UploadProcessingError(str(exc)) from exc

    finally:
        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except OSError:
                logger.warning("Could not remove temp file: %s", tmp_path)


class HealthView(APIView): #Return API liveness status

    def get(self, request):
        serializer = HealthResponseSerializer({"status": "ok"})
        return Response(serializer.data)


class UploadShapefileView(APIView):
    ''' Accept ZIP file containing shapefile parts, parse via GeoPandas, store minimal metadata&GeoJSON 

    POST /api/upload/
    multipart/form-data
    file=<zip containing shp/shx/dbf

    Returns 
    - 201 with session metadata and GeoJSON on success
    - 400 for invalid or unreadable shapefile content
    - 500 for unexpected server-side failures'''

    def post(self, request): #Validate and process uploaded shapefile zip into a stored GeoJSON session
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
            logger.warning("Upload rejected — shapefile could not be parsed: %s", exc)
            return Response(
                {"error": "Invalid shapefile zip", "details": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.exception("Unexpected error while processing upload.")
            return Response(
                {"error": "Failed to process upload. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        serializer = UploadResponseSerializer(
            {
                "session_id": session.id,
                "dataset_name": session.dataset_name,
                "crs": session.crs,
                "building_count": session.building_count,
                "geojson": session.footprints_geojson,
            }
        )

        response_data = dict(serializer.data)
        response_data["message"] = (
            f"'{session.dataset_name}' uploaded successfully. "
            f"{session.building_count} features loaded."
        )

        return Response(response_data, status=status.HTTP_201_CREATED)


class GetOverlayView(APIView):
    def get(self, request, session_id):
        session = get_object_or_404(UploadSession, id=session_id)
        serializer = OverlayResponseSerializer(
            {"session_id": session.id, "geojson": session.footprints_geojson}
        )
        return Response(serializer.data)


class AnalysisStartStubView(APIView):
    def post(self, request, upload_id):
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
    def get(self, request, analysis_id):
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
    def post(self, request, session_id):
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
    def get(self, request, session_id, export_type):
        session = get_object_or_404(UploadSession, id=session_id)
        serializer = ExportResponseSerializer(
            {
                "session_id": session.id,
                "export_type": export_type,
                "status": "not_implemented",
            }
        )
        return Response(serializer.data)