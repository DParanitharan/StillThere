"""
Persist classification results from classify_buildings() into PostGIS.
"""

import json
import logging

import geopandas as gpd
from django.contrib.gis.geos import GEOSGeometry
from shapely.ops import transform as shapely_transform
from shapely import wkt as shapely_wkt

from apps.geo.models import ClassifiedBuilding, UploadSession

logger = logging.getLogger(__name__)


def _force_2d(geom):
    """Strip Z coordinate from a Shapely geometry."""
    return shapely_transform(lambda x, y, z=None: (x, y), geom)


def _safe_float(val):
    """Convert to float or return None."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if f != f else f  # NaN → None
    except (TypeError, ValueError):
        return None


def persist_classification_results(
    classified_gdf: gpd.GeoDataFrame,
    upload_session,
    analysis_session=None,
) -> int:
    """
    Save a classified GeoDataFrame to the ClassifiedBuilding table.

    Handles the column names from utils.py:
    - status (not "classification")
    - confidence
    - iou
    - metrics (JSON string)
    """
    # If a string/UUID was passed, resolve to model instance
    if isinstance(upload_session, (str,)):
        upload_session = UploadSession.objects.get(id=upload_session)

    # Clear previous results for this session (re-runnable)
    ClassifiedBuilding.objects.filter(upload_session=upload_session).delete()

    # Auto-detect classification column name
    classification_col = None
    for candidate in ["classification", "status", "label", "class", "result"]:
        if candidate in classified_gdf.columns:
            classification_col = candidate
            break

    if classification_col is None:
        raise ValueError(
            f"No classification column found. Available columns: {list(classified_gdf.columns)}"
        )

    logger.info(
        "Persisting %d rows. Classification column: '%s'. All columns: %s",
        len(classified_gdf), classification_col, list(classified_gdf.columns),
    )

    # Auto-detect IoU column
    iou_col = None
    for candidate in ["iou_score", "iou"]:
        if candidate in classified_gdf.columns:
            iou_col = candidate
            break

    rows = []
    for idx, row in classified_gdf.iterrows():
        # Input geometry (force 2D)
        input_geom_2d = _force_2d(row.geometry)
        input_geos = GEOSGeometry(json.dumps(input_geom_2d.__geo_interface__), srid=4326)

        # Detected geometry from SAM (stored as WKT string in 'sam_polygon' column)
        detected_geos = None
        if "sam_polygon" in classified_gdf.columns and row.get("sam_polygon") is not None:
            try:
                sam_geom = shapely_wkt.loads(row["sam_polygon"])
                sam_geom_2d = _force_2d(sam_geom)
                detected_geos = GEOSGeometry(
                    json.dumps(sam_geom_2d.__geo_interface__), srid=4326
                )
            except Exception as e:
                logger.warning("Could not parse sam_polygon for row %s: %s", idx, e)

        # Build properties from remaining columns
        reserved = {classification_col, "geometry", "confidence", "sam_polygon",
                    "metrics", "pixel_score", iou_col}
        props = {}
        for col in classified_gdf.columns:
            if col in reserved or col == classified_gdf.geometry.name:
                continue
            val = row[col]
            try:
                val = val.item()
            except (AttributeError, ValueError):
                pass
            if val != val:  # NaN
                val = None
            props[col] = val

        rows.append(ClassifiedBuilding(
            upload_session=upload_session,
            analysis_session=analysis_session,
            feature_index=int(idx),
            classification=row.get(classification_col, "unknown"),
            confidence=_safe_float(row.get("confidence")),
            iou_score=_safe_float(row.get(iou_col)) if iou_col else None,
            pixel_score=_safe_float(row.get("pixel_score")),
            properties=props,
            input_geom=input_geos,
            detected_geom=detected_geos,
        ))

    ClassifiedBuilding.objects.bulk_create(rows, batch_size=500)
    logger.info(
        "Persisted %d classified buildings for session %s",
        len(rows), upload_session.id if hasattr(upload_session, 'id') else upload_session,
    )
    return len(rows)