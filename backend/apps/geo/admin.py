from django.contrib import admin

from .models import UploadSession


@admin.register(UploadSession)
class UploadSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "dataset_name", "building_count", "created_at")
    search_fields = ("id", "dataset_name")
    readonly_fields = ("id", "created_at")
