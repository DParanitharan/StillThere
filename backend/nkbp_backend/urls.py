"""Root URL configuration for backend routes."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.api.urls")),
]

if settings.DEBUG:
    urlpatterns += [
        path("__debug__/", include("debug_toolbar.urls")),
    ]

if settings.DEBUG:
    # In production, MEDIA_URL must be served by a dedicated web server (e.g. nginx).
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
