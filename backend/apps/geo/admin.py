"""Admin configuration for geospatial domain models."""

from django.contrib import admin

from .models import UploadSession


@admin.register(UploadSession)
class UploadSessionAdmin(admin.ModelAdmin):
    """Admin list/search configuration for upload sessions."""

    list_display = ("id", "dataset_name", "building_count", "created_at")
    search_fields = ("id", "dataset_name")
    readonly_fields = ("id", "created_at")
