"""API app models.

This app currently exposes endpoints and serializers only.
"""

from django.db import models


class AnalysisSession(models.Model):
    session_id = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    filename = models.CharField(max_length=255, blank=True, default='')
    summary = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.session_id})"
