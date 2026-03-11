"""URL routes for API endpoints."""

from django.urls import path

from .views import (
    HealthView,
    UploadShapefileView,
    GetOverlayView,
    AnalysisStartStubView,
    AnalysisResultsStubView,
    AnalyzeChangesStubView,
    ExportStubView,
    BuildingExtractionView,
    ClassificationProgressView,
    AnalysisSessionListView,
    LoginView
)

urlpatterns = [
    path("health/", HealthView.as_view(), name="api-health"),
    path("upload/", UploadShapefileView.as_view(), name="upload-shapefile"),
    path("overlay/<uuid:session_id>/", GetOverlayView.as_view(), name="get-overlay"),
    path("analysis/<uuid:upload_id>/", AnalysisStartStubView.as_view(), name="analysis-start"),
    path("analysis/<uuid:analysis_id>/results/", AnalysisResultsStubView.as_view(), name="analysis-results"),
    path("analyze/<uuid:session_id>/", AnalyzeChangesStubView.as_view(), name="analyze-changes"),
    path("export/<uuid:session_id>/<str:export_type>/", ExportStubView.as_view(), name="export-stub"),
    path("extract-buildings/", BuildingExtractionView.as_view(), name="extract-buildings"),
    path('progress/<str:session_id>/', ClassificationProgressView.as_view(), name='classification-progress'),
    path('sessions/', AnalysisSessionListView.as_view(), name='analysis-session-list'),
    path('login/', LoginView.as_view(), name='login')
]