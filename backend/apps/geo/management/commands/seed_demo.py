"""
Seed the database with one real, pre-computed analysis so the public demo is
fully explorable without running the live SAM pipeline.

Populates, joined by shapefile row index (input_idx):
  - geo.UploadSession            (parent, stable UUID)
  - api.AnalysisSession          (session listing + summary counts)
  - geo.UploadedFeature          (raw shapefile attributes + geometry — chatbot)
  - geo.ClassifiedBuilding       (classification results + geometries — map)

Run locally (where GeoPandas is installed), pointed at the target database:
    python manage.py seed_demo
    python manage.py seed_demo --shapefile path/to.shp --geojson path/to.geojson

The heavy GeoPandas import is deferred to run time so this command module stays
importable in slim demo deployments that never invoke it.
"""

from __future__ import annotations

import glob
import json
import uuid
from pathlib import Path

from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.api.models import AnalysisSession
from apps.geo.models import ClassifiedBuilding, UploadedFeature, UploadSession

# Stable identifiers so the seed is reproducible and the frontend can deep-link.
DEMO_SESSION_UUID = uuid.UUID("00000000-0000-0000-0000-00000000d310")
DEMO_TITLE = "Onahama Coastal - Building Change Detection (Demo)"

# Repo-relative defaults. This file lives at backend/apps/geo/management/commands/,
# so parents[4] is backend/ and parents[5] is the repository root.
BACKEND_DIR = Path(__file__).resolve().parents[4]
REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_SHAPEFILE_GLOB = str(REPO_ROOT / "5540_onahama*" / "*.shp")
DEFAULT_GEOJSON_GLOB = str(BACKEND_DIR / "media" / "outputs" / "*" / "buildings_classified.geojson")


def _json_safe(value):
    """Convert numpy scalars to native types and NaN to None for JSONField."""
    try:
        value = value.item()
    except (AttributeError, ValueError):
        pass
    if isinstance(value, float) and value != value:  # NaN
        return None
    return value


def _resolve(pattern: str, explicit: str | None, kind: str) -> str:
    if explicit:
        if not Path(explicit).exists():
            raise CommandError(f"{kind} not found: {explicit}")
        return explicit
    matches = sorted(glob.glob(pattern), key=lambda p: Path(p).stat().st_size, reverse=True)
    if not matches:
        raise CommandError(f"No {kind} found matching {pattern}; pass an explicit path.")
    return matches[0]


class Command(BaseCommand):
    help = "Seed the database with one pre-computed analysis for the public demo."

    def add_arguments(self, parser):
        parser.add_argument("--shapefile", help="Path to the source .shp (original attributes).")
        parser.add_argument("--geojson", help="Path to buildings_classified.geojson (results).")

    def handle(self, *args, **options):
        # Deferred so the module imports without the geo stack in slim deploys.
        try:
            import geopandas as gpd
            from shapely import wkt as shp_wkt
            from shapely.geometry import shape as shp_shape
            from shapely.ops import transform as shp_transform
        except ImportError as exc:
            raise CommandError(
                "seed_demo needs GeoPandas/Shapely. Run it from the full local "
                f"environment, not a slim deploy. ({exc})"
            )

        # PostGIS columns here are 2D; drop any Z before inserting.
        def to_2d_geos(shapely_geom):
            flat = shp_transform(lambda *c: c[:2], shapely_geom)
            return GEOSGeometry(flat.wkt, srid=4326)

        shp_path = _resolve(DEFAULT_SHAPEFILE_GLOB, options.get("shapefile"), "shapefile")
        gj_path = _resolve(DEFAULT_GEOJSON_GLOB, options.get("geojson"), "classified geojson")
        self.stdout.write(f"Shapefile: {shp_path}")
        self.stdout.write(f"Classified GeoJSON: {gj_path}")

        gdf = gpd.read_file(shp_path)
        gdf = gdf[gdf.geometry.notnull()].to_crs(epsg=4326)
        geom_col = gdf.geometry.name

        # Per-row: JSON-safe attribute dict and a 4326 GEOS geometry, keyed by index.
        attrs_by_idx: dict[int, dict] = {}
        geom_by_idx: dict[int, GEOSGeometry] = {}
        for idx, row in gdf.iterrows():
            attrs_by_idx[int(idx)] = {
                col: _json_safe(row[col]) for col in gdf.columns if col != geom_col
            }
            geom_by_idx[int(idx)] = to_2d_geos(row.geometry)

        with open(gj_path, encoding="utf-8") as fh:
            features = json.load(fh)["features"]

        with transaction.atomic():
            UploadSession.objects.filter(id=DEMO_SESSION_UUID).delete()  # cascades children
            AnalysisSession.objects.filter(session_id=str(DEMO_SESSION_UUID)).delete()

            upload = UploadSession.objects.create(
                id=DEMO_SESSION_UUID,
                dataset_name=Path(shp_path).stem,
                crs="EPSG:4326",
                building_count=len(gdf),
            )

            UploadedFeature.objects.bulk_create(
                [
                    UploadedFeature(
                        upload_session=upload,
                        feature_index=idx,
                        properties=attrs_by_idx[idx],
                        geom=geom_by_idx[idx],
                    )
                    for idx in geom_by_idx
                ],
                batch_size=500,
            )

            classified, counts = [], {}
            for feat in features:
                props = feat["properties"]
                idx = int(props["input_idx"])
                status = props.get("status") or "unknown"
                counts[status] = counts.get(status, 0) + 1

                detected = None
                sam_wkt = props.get("sam_polygon")
                if sam_wkt:
                    try:
                        detected = to_2d_geos(shp_wkt.loads(sam_wkt))
                    except Exception as exc:  # noqa: BLE001 - skip a bad polygon, keep seeding
                        self.stderr.write(f"  skipped sam_polygon for idx {idx}: {exc}")

                classified.append(
                    ClassifiedBuilding(
                        upload_session=upload,
                        feature_index=idx,
                        classification=status,
                        confidence=props.get("confidence"),
                        iou_score=props.get("iou"),
                        pixel_score=None,
                        properties=attrs_by_idx.get(idx, {}),
                        input_geom=to_2d_geos(shp_shape(feat["geometry"])),
                        detected_geom=detected,
                    )
                )

            ClassifiedBuilding.objects.bulk_create(classified, batch_size=500)

            AnalysisSession.objects.create(
                session_id=str(DEMO_SESSION_UUID),
                title=DEMO_TITLE,
                filename=Path(shp_path).name,
                summary={"total": len(classified), **counts},
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(gdf)} features and {len(classified)} classified buildings "
                f"({counts}) under session {DEMO_SESSION_UUID}."
            )
        )
