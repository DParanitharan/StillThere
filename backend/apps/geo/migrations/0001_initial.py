# Generated manually for scaffold bootstrap.
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="UploadSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("source_zip", models.FileField(upload_to="uploads/")),
                ("dataset_name", models.CharField(blank=True, max_length=255)),
                ("crs", models.CharField(blank=True, max_length=64)),
                ("building_count", models.IntegerField(default=0)),
                ("footprints_geojson", models.JSONField(blank=True, null=True)),
            ],
        ),
    ]
