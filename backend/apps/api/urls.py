"""URL routes for API endpoints."""

from django.urls import path

from .views import (
    AnalysisResultsStubView,
    AnalysisStartStubView,
    AnalyzeChangesStubView,
    ExportStubView,
    GetOverlayView,
    HealthView,
    UploadShapefileView,
    GeocodeView
)

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("upload/", UploadShapefileView.as_view(), name="upload"),
    path("overlay/<uuid:session_id>/", GetOverlayView.as_view(), name="overlay"),
    path("analysis/<uuid:upload_id>/", AnalysisStartStubView.as_view(), name="analysis-start"),
    path(
        "analysis/<uuid:analysis_id>/results/",
        AnalysisResultsStubView.as_view(),
        name="analysis-results",
    ),
    path("analyze/<uuid:session_id>/", AnalyzeChangesStubView.as_view(), name="analyze"),
    path("export/<uuid:session_id>/<str:export_type>/", ExportStubView.as_view(), name="export"),
    path("geocode/", GeocodeView.as_view(), name="geocode")
]
