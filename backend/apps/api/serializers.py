from rest_framework import serializers


class UploadResponseSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    dataset_name = serializers.CharField()
    crs = serializers.CharField(allow_blank=True)
    building_count = serializers.IntegerField()
    geojson = serializers.JSONField(allow_null=True)


class OverlayResponseSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    geojson = serializers.JSONField(allow_null=True)


class AnalysisStubSerializer(serializers.Serializer):
    analysis_id = serializers.UUIDField()
    upload_id = serializers.UUIDField()
    status = serializers.CharField()
    message = serializers.CharField()
