"""
Reads a GeoDataFrame and bulk-inserts every feature into the
UploadedFeature table so they are queryable with PostGIS spatial functions.
"""

import json
import logging

import geopandas as gpd
from django.contrib.gis.geos import GEOSGeometry
from shapely.ops import transform as shapely_transform

from apps.geo.models import UploadedFeature

logger = logging.getLogger(__name__)


def _force_2d(geom):
    """Strip Z coordinate from a Shapely geometry."""
    return shapely_transform(lambda x, y, z=None: (x, y), geom)


def ingest_geodataframe_to_postgis(gdf: gpd.GeoDataFrame, upload_session) -> int:
    """
    Bulk-insert every row of a GeoDataFrame (already in EPSG:4326,
    null geometries already removed) into PostGIS.

    Returns the number of features inserted.
    """
    attr_cols = [c for c in gdf.columns if c != gdf.geometry.name]

    features = []
    for idx, row in gdf.iterrows():
        # Build a JSON-safe properties dict
        props = {}
        for col in attr_cols:
            val = row[col]
            try:
                val = val.item()          # numpy scalar → python scalar
            except (AttributeError, ValueError):
                pass
            if val != val:                # NaN → None
                val = None
            props[col] = val

        # Force 2D — shapefile may contain Z coordinates
        geom_2d = _force_2d(row.geometry)
        geojson_str = json.dumps(geom_2d.__geo_interface__)
        geos_geom = GEOSGeometry(geojson_str, srid=4326)

        features.append(
            UploadedFeature(
                upload_session=upload_session,
                feature_index=int(idx),
                properties=props,
                geom=geos_geom,
            )
        )

    UploadedFeature.objects.bulk_create(features, batch_size=500)
    logger.info(
        "Ingested %d features into PostGIS for session %s",
        len(features),
        upload_session.id,
    )
    return len(features)