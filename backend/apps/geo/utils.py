import geopandas as gpd
import os
import requests
import math
import numpy as np
import io
import logging
import json
import time
from django.core.cache import cache
from PIL import Image, ImageDraw
from shapely.geometry import shape
from shapely.ops import transform
from rasterio.transform import from_bounds
from rasterio.features import shapes as rasterio_shapes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _env_float(key, default):
    """Read a float from an environment variable, falling back to *default*."""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        logger.warning(f"Invalid float for {key}={val!r}, using default {default}")
        return default


def _env_int(key, default):
    """Read an int from an environment variable, falling back to *default*."""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        logger.warning(f"Invalid int for {key}={val!r}, using default {default}")
        return default


CLASSIFY_THRESHOLDS = {
    "iou_unchanged": _env_float("CLASSIFY_IOU_UNCHANGED", 0.35),
    "iou_modified_low": _env_float("CLASSIFY_IOU_MODIFIED_LOW", 0.10),
    "sam_confidence_min": _env_float("CLASSIFY_SAM_CONFIDENCE_MIN", 0.50),
    "box_pad_px": _env_int("CLASSIFY_BOX_PAD_PX", 10),
    "overlap_ratio_min": _env_float("CLASSIFY_OVERLAP_RATIO_MIN", 0.30),
    "pixel_fallback_min": _env_float("CLASSIFY_PIXEL_FALLBACK_MIN", 0.50),
    "threshold_removed": _env_float("CLASSIFY_THRESHOLD_REMOVED", 0.25),
    # Pixel analysis scoring thresholds
    "brightness_min": _env_float("CLASSIFY_BRIGHTNESS_MIN", 60.0),
    "brightness_max": _env_float("CLASSIFY_BRIGHTNESS_MAX", 220.0),
    "color_std_low": _env_float("CLASSIFY_COLOR_STD_LOW", 40.0),
    "color_std_high": _env_float("CLASSIFY_COLOR_STD_HIGH", 60.0),
    "texture_std_min": _env_float("CLASSIFY_TEXTURE_STD_MIN", 15.0),
    "texture_std_max": _env_float("CLASSIFY_TEXTURE_STD_MAX", 60.0),
    "green_ratio_low": _env_float("CLASSIFY_GREEN_RATIO_LOW", 0.38),
    "green_ratio_high": _env_float("CLASSIFY_GREEN_RATIO_HIGH", 0.42),
    "saturation_low": _env_float("CLASSIFY_SATURATION_LOW", 0.30),
    "saturation_high": _env_float("CLASSIFY_SATURATION_HIGH", 0.50),
    # Max buildings sent through SAM; remainder use pixel-only fallback.
    # Lower values = faster; raise for higher shape-accuracy on large datasets.
    "sam_max_buildings": _env_int("CLASSIFY_SAM_MAX_BUILDINGS", 200),
}

logger.info("Classification thresholds: %s", CLASSIFY_THRESHOLDS)

_TILE_DOWNLOAD_MAX_RETRIES = _env_int("CLASSIFY_TILE_DOWNLOAD_MAX_RETRIES", 3)
_TILE_DOWNLOAD_TIMEOUT = _env_int("CLASSIFY_TILE_DOWNLOAD_TIMEOUT", 15)

# Cached SAM predictor — loaded once per worker process.
_sam_predictor = None


# ── Progress tracker ─────────────────────────────────────────────────────────

# Progress state is stored in Django's cache so all workers can read it.
# Use a Redis cache backend in production for true multi-worker support.
_PROGRESS_CACHE_TIMEOUT = 3600  # seconds — long enough to survive the full job


class ProgressTracker:
    """Collects progress events and flushes state to Django cache after every mutation."""

    def __init__(self, cache_key=None):
        self._cache_key = cache_key
        self.logs = []
        self.phase = "initializing"
        self.phase_progress = 0.0  # 0–1
        self.total_buildings = 0
        self.processed_buildings = 0
        self.start_time = time.time()
        self.phase_start_time = time.time()
        self.counts = {"unchanged": 0, "modified": 0, "removed": 0, "error": 0}

    def _flush(self):
        """Write current state to the shared cache."""
        if self._cache_key:
            cache.set(self._cache_key, self.to_dict(), _PROGRESS_CACHE_TIMEOUT)

    def log(self, message, level="info"):
        elapsed = round(time.time() - self.start_time, 1)
        entry = {
            "time": elapsed,
            "phase": self.phase,
            "message": message,
            "level": level,
            "progress": round(self.phase_progress * 100, 1),
            "processed": self.processed_buildings,
            "total": self.total_buildings,
            "counts": dict(self.counts),
        }
        self.logs.append(entry)
        logger.info("[%.1fs] [%s] %s", elapsed, self.phase, message)
        self._flush()

    def set_phase(self, phase, message=None, level="info"):
        self.phase = phase
        self.phase_progress = 0.0
        self.phase_start_time = time.time()
        self.log(message or f"Starting {phase}", level=level)

    def set_progress(self, current, total, message=None):
        self.phase_progress = current / total if total > 0 else 0
        self.processed_buildings = current
        self.phase_total = total
        if message:
            self.log(message)
        else:
            self._flush()

    def to_dict(self):
        elapsed = round(time.time() - self.start_time, 1)
        phase_elapsed = round(time.time() - self.phase_start_time, 1)

        # ETA is derived from current-phase timing only, so Phase 2
        # (capped at sam_max_buildings, not total_buildings) gives an
        # accurate estimate rather than projecting from the full count.
        eta = None
        phase_total = getattr(self, "phase_total", self.total_buildings)
        if self.phase_progress > 0.01:
            eta = round(
                phase_elapsed / self.phase_progress * (1.0 - self.phase_progress), 1
            )

        return {
            "phase": self.phase,
            "progress": round(self.phase_progress * 100, 1),
            "processed": self.processed_buildings,
            "total": phase_total,
            "elapsed": elapsed,
            "eta_seconds": eta,
            "counts": dict(self.counts),
            "logs": self.logs[-50:],
        }


def get_progress(session_id):
    """Retrieve progress for a session from the shared cache (called by the API view)."""
    return cache.get(f"progress:{session_id}")


# ── helpers ──────────────────────────────────────────────────────────────────


def _meters_per_pixel(lat, zoom):
    return 156543.03392 * math.cos(lat * math.pi / 180) / (2**zoom)


def _download_google_tile(center_lat, center_lng, zoom, size, api_key):
    url = (
        f"https://maps.googleapis.com/maps/api/staticmap?"
        f"center={center_lat},{center_lng}"
        f"&zoom={zoom}"
        f"&size={size}x{size}"
        f"&maptype=satellite"
        f"&key={api_key}"
    )
    last_exc = None
    for attempt in range(1, _TILE_DOWNLOAD_MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=_TILE_DOWNLOAD_TIMEOUT)
            if resp.status_code != 200:
                raise RuntimeError(f"Google Maps API error: {resp.status_code}")
            return np.array(Image.open(io.BytesIO(resp.content)).convert("RGB"))
        except Exception as exc:
            last_exc = exc
            if attempt < _TILE_DOWNLOAD_MAX_RETRIES:
                wait = 2 ** (attempt - 1)
                logger.warning(
                    "Tile download attempt %d/%d failed: %s. Retrying in %ds",
                    attempt,
                    _TILE_DOWNLOAD_MAX_RETRIES,
                    exc,
                    wait,
                )
                time.sleep(wait)
    raise last_exc


def _tile_bounds(center_lat, center_lng, size_px, mpp):
    half_lat = (size_px / 2 * mpp) / 111000
    half_lng = (size_px / 2 * mpp) / (111000 * math.cos(center_lat * math.pi / 180))
    return {
        "min_lng": center_lng - half_lng,
        "max_lng": center_lng + half_lng,
        "min_lat": center_lat - half_lat,
        "max_lat": center_lat + half_lat,
    }


def _polygon_to_pixel_coords(polygon, inv_transform):
    """Convert a shapely polygon's exterior coords to pixel coordinates."""
    pixel_coords = []
    for coord in polygon.exterior.coords:
        lng, lat = coord[0], coord[1]
        col, row = inv_transform * (lng, lat)
        pixel_coords.append((int(col), int(row)))
    return pixel_coords


def _create_polygon_mask(pixel_coords, img_shape):
    mask_img = Image.new("L", (img_shape[1], img_shape[0]), 0)
    if len(pixel_coords) >= 3:
        ImageDraw.Draw(mask_img).polygon(pixel_coords, fill=255)
    return np.array(mask_img) > 0


def _group_buildings_into_tiles(gdf, tile_size_m=180):
    gdf_3857 = gdf.to_crs(epsg=3857)
    centroids = gdf_3857.geometry.centroid
    min_x, min_y = centroids.x.min(), centroids.y.min()
    groups = {}
    for idx, row in gdf.iterrows():
        c = gdf_3857.loc[idx].geometry.centroid
        key = (int((c.x - min_x) // tile_size_m), int((c.y - min_y) // tile_size_m))
        groups.setdefault(key, []).append((idx, row))
    tiles = []
    for key, buildings in groups.items():
        lats = [b[1].geometry.centroid.y for b in buildings]
        lngs = [b[1].geometry.centroid.x for b in buildings]
        tiles.append((sum(lats) / len(lats), sum(lngs) / len(lngs), buildings))
    return tiles


# Phase 1: Fast pixel-based comparison to find "removed" buildings


def _analyze_building_pixels(img_array, polygon_mask):
    masked_pixels = img_array[polygon_mask]
    if len(masked_pixels) < 10:
        return 0.0, {"reason": "too_few_pixels"}

    pixels = masked_pixels.astype(np.float32)
    mean_brightness = np.mean(pixels)
    color_std = np.mean(np.std(pixels, axis=0))

    gray = np.mean(img_array, axis=2)
    texture_std = np.std(gray[polygon_mask])

    r, g, b = pixels[:, 0], pixels[:, 1], pixels[:, 2]
    total = r + g + b + 1e-10
    green_ratio = float(np.mean(g / total))

    max_c = np.max(pixels, axis=1)
    min_c = np.min(pixels, axis=1)
    saturation = float(np.mean((max_c - min_c) / (max_c + 1e-10)))

    t = CLASSIFY_THRESHOLDS
    score = 0.0
    if t["brightness_min"] < mean_brightness < t["brightness_max"]:
        score += 0.2
    if color_std < t["color_std_low"]:
        score += 0.2
    elif color_std < t["color_std_high"]:
        score += 0.1
    if t["texture_std_min"] < texture_std < t["texture_std_max"]:
        score += 0.2
    if green_ratio < t["green_ratio_low"]:
        score += 0.2
    elif green_ratio < t["green_ratio_high"]:
        score += 0.1
    if saturation < t["saturation_low"]:
        score += 0.2
    elif saturation < t["saturation_high"]:
        score += 0.1

    return score, {
        "mean_brightness": float(mean_brightness),
        "color_std": float(color_std),
        "texture_std": float(texture_std),
        "green_ratio": green_ratio,
        "saturation": saturation,
    }


#  Phase 2: SAM shape comparison


def _load_sam_predictor():
    global _sam_predictor
    if _sam_predictor is not None:
        return _sam_predictor

    import torch
    from segment_anything import sam_model_registry, SamPredictor

    # Use all available CPU cores for PyTorch operations (default on Linux
    # Docker is often 1, which severely underutilises multi-core machines).
    torch.set_num_threads(os.cpu_count() or 4)
    logger.info("SAM using %d CPU threads", torch.get_num_threads())

    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    for model_type, filename in [
        ("vit_b", "sam_vit_b_01ec64.pth"),
        ("vit_h", "sam_vit_h_4b8939.pth"),
    ]:
        path = os.path.join(base, filename)
        if os.path.exists(path):
            device = (
                "mps"
                if torch.backends.mps.is_available()
                else ("cuda" if torch.cuda.is_available() else "cpu")
            )
            logger.info(f"Loading SAM {model_type} on {device}")
            sam = sam_model_registry[model_type](checkpoint=path)
            sam.to(device)
            _sam_predictor = SamPredictor(sam)
            return _sam_predictor

    raise FileNotFoundError("No SAM checkpoint found")


def _compute_iou(poly_a, poly_b):
    if poly_a.is_empty or poly_b.is_empty:
        return 0.0
    try:
        intersection = poly_a.intersection(poly_b).area
        union = poly_a.union(poly_b).area
        return intersection / union if union > 0 else 0.0
    except Exception:
        return 0.0


def _sam_extract_building(
    predictor, img_array, center_px, center_py, bbox_px, img_transform
):
    """
    Run SAM with BOTH a point prompt and a box prompt for better accuracy.
    """
    size_px = img_array.shape[0]
    pad = CLASSIFY_THRESHOLDS["box_pad_px"]
    sam_confidence_min = CLASSIFY_THRESHOLDS["sam_confidence_min"]

    x_min = max(0, bbox_px[0] - pad)
    y_min = max(0, bbox_px[1] - pad)
    x_max = min(size_px - 1, bbox_px[2] + pad)
    y_max = min(size_px - 1, bbox_px[3] + pad)

    masks, scores, _ = predictor.predict(
        point_coords=np.array([[center_px, center_py]]),
        point_labels=np.array([1]),
        box=np.array([x_min, y_min, x_max, y_max]),
        multimask_output=True,
    )

    if masks is None or len(masks) == 0:
        return None, 0.0

    best_idx = np.argmax(scores)
    best_mask = masks[best_idx].astype(np.uint8)
    best_score = float(scores[best_idx])

    if best_score < sam_confidence_min:
        return None, best_score

    results = list(rasterio_shapes(best_mask, mask=best_mask, transform=img_transform))
    polygons = [shape(geom) for geom, val in results if val == 1]
    if not polygons:
        return None, best_score

    return max(polygons, key=lambda p: p.area), best_score


# ── Main classification pipeline ────────────────────────────────────────────


def classify_buildings(input_gdf, output_dir, zoom=19, session_id=None):
    """
    Two-phase classification with progress tracking.
    Pass session_id to enable progress polling from the API.
    Progress state is written to Django's cache so any worker can serve poll requests.
    """
    cache_key = f"progress:{session_id}" if session_id else None
    progress = ProgressTracker(cache_key=cache_key)

    try:
        result = _classify_buildings_inner(input_gdf, output_dir, zoom, progress)
        progress.set_phase("complete", "Classification finished")
        return result
    except Exception as exc:
        progress.set_phase("error", f"Classification failed: {exc}", level="error")
        raise


def _classify_buildings_inner(input_gdf, output_dir, zoom, progress):
    # ── Read thresholds ─────────────────────────────────────────────────
    threshold_removed = CLASSIFY_THRESHOLDS["threshold_removed"]
    iou_unchanged = CLASSIFY_THRESHOLDS["iou_unchanged"]
    iou_modified_low = CLASSIFY_THRESHOLDS["iou_modified_low"]
    overlap_ratio_min = CLASSIFY_THRESHOLDS["overlap_ratio_min"]
    pixel_fallback_min = CLASSIFY_THRESHOLDS["pixel_fallback_min"]

    progress.set_phase("setup", "Reading thresholds and validating input")
    progress.log(f"Thresholds: {CLASSIFY_THRESHOLDS}")

    api_key = os.getenv("GOOGLE_EARTH_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_EARTH_API_KEY not set")

    gdf = input_gdf.to_crs(epsg=4326).copy()
    gdf = gdf[gdf.geometry.notnull() & gdf.geometry.is_valid].copy()
    progress.total_buildings = len(gdf)
    progress.log(f"Loaded {len(gdf)} valid building polygons")

    # ── Tile grouping ───────────────────────────────────────────────────
    progress.set_phase("tiling", "Grouping buildings into spatial tiles")
    tile_groups = _group_buildings_into_tiles(gdf, tile_size_m=180)
    progress.log(f"Created {len(tile_groups)} tiles (180m grid)")

    size_px = 640
    phase1_results = {}
    sam_candidates = []
    total_processed = 0

    # ── PHASE 1: Pixel triage ───────────────────────────────────────────
    progress.set_phase(
        "phase1_satellite", "Downloading satellite imagery & pixel analysis"
    )
    tile_cache = {}
    total_tiles = len(tile_groups)

    for tile_idx, (tile_lat, tile_lng, buildings) in enumerate(tile_groups):
        try:
            progress.log(
                f"Tile {tile_idx+1}/{total_tiles}: downloading satellite image "
                f"({len(buildings)} buildings)"
            )

            mpp = _meters_per_pixel(tile_lat, zoom)
            img_array = _download_google_tile(
                tile_lat, tile_lng, zoom, size_px, api_key
            )
            bounds = _tile_bounds(tile_lat, tile_lng, size_px, mpp)
            img_transform = from_bounds(
                bounds["min_lng"],
                bounds["min_lat"],
                bounds["max_lng"],
                bounds["max_lat"],
                img_array.shape[1],
                img_array.shape[0],
            )
            inv_transform = ~img_transform
            tile_cache[tile_idx] = (img_array, img_transform, inv_transform)

            for bld_idx, row in buildings:
                polygon = row.geometry
                pixel_coords = _polygon_to_pixel_coords(polygon, inv_transform)
                pixel_coords = [
                    (max(0, min(px, size_px - 1)), max(0, min(py, size_px - 1)))
                    for px, py in pixel_coords
                ]
                poly_mask = _create_polygon_mask(pixel_coords, img_array.shape[:2])
                score, metrics = _analyze_building_pixels(img_array, poly_mask)

                if score < threshold_removed:
                    phase1_results[bld_idx] = {
                        "geometry": polygon,
                        "status": "removed",
                        "confidence": score,
                        "sam_polygon": None,
                        "iou": 0.0,
                        "metrics": json.dumps(metrics),
                    }
                    progress.counts["removed"] += 1
                else:
                    sam_candidates.append((bld_idx, row, tile_idx, score))

            total_processed += len(buildings)
            progress.set_progress(
                total_processed,
                len(gdf),
                f"Phase 1: {total_processed}/{len(gdf)} buildings analyzed",
            )

        except Exception as e:
            logger.error(f"Phase 1 error on tile {tile_idx}: {e}")
            progress.log(f"Error on tile {tile_idx}: {e}", level="error")
            for bld_idx, row in buildings:
                phase1_results[bld_idx] = {
                    "geometry": row.geometry,
                    "status": "error",
                    "confidence": 0.0,
                    "sam_polygon": None,
                    "iou": 0.0,
                    "metrics": json.dumps({"error": str(e)}),
                }
                progress.counts["error"] += 1
            total_processed += len(buildings)

    removed_count = sum(1 for r in phase1_results.values() if r["status"] == "removed")
    progress.log(
        f"Phase 1 complete: {removed_count} removed, "
        f"{len(sam_candidates)} need SAM verification"
    )

    # Sort by pixel score ascending: lowest (most ambiguous, closest to removal
    # threshold) go through SAM first — they benefit most from shape verification.
    sam_max = CLASSIFY_THRESHOLDS["sam_max_buildings"]
    sam_candidates.sort(key=lambda x: x[3])
    pixel_only_candidates = sam_candidates[sam_max:]
    sam_candidates = sam_candidates[:sam_max]

    for bld_idx, row, tile_idx, px_score in pixel_only_candidates:
        status = "modified" if px_score >= pixel_fallback_min else "removed"
        phase1_results[bld_idx] = {
            "geometry": row.geometry,
            "status": status,
            "confidence": px_score,
            "sam_polygon": None,
            "iou": 0.0,
            "metrics": json.dumps(
                {"pixel_score": px_score, "note": "pixel-only, SAM cap reached"}
            ),
        }
        progress.counts[status] += 1

    if pixel_only_candidates:
        progress.log(
            f"SAM cap ({sam_max}): {len(pixel_only_candidates)} buildings classified "
            f"by pixel-only fallback (raise CLASSIFY_SAM_MAX_BUILDINGS to include them)"
        )

    # ── PHASE 2: SAM ────────────────────────────────────────────────────
    if sam_candidates:
        progress.set_phase("phase2_sam_loading", "Loading SAM model into memory")
        progress.log(f"Loading SAM model for {len(sam_candidates)} buildings…")
        predictor = _load_sam_predictor()
        progress.log("SAM model loaded successfully")

        progress.set_phase(
            "phase2_sam", f"Running SAM segmentation on {len(sam_candidates)} buildings"
        )

        candidates_by_tile = {}
        for bld_idx, row, tile_idx, _score in sam_candidates:
            candidates_by_tile.setdefault(tile_idx, []).append((bld_idx, row))

        sam_processed = 0
        last_tile_idx = None

        for tile_idx, bld_list in candidates_by_tile.items():
            if tile_idx not in tile_cache:
                continue

            img_array, img_transform, inv_transform = tile_cache[tile_idx]

            if tile_idx != last_tile_idx:
                predictor.set_image(img_array)
                last_tile_idx = tile_idx

            for bld_idx, row in bld_list:
                polygon = row.geometry
                centroid = polygon.centroid
                cx, cy = inv_transform * (centroid.x, centroid.y)
                cx, cy = int(max(0, min(cx, size_px - 1))), int(
                    max(0, min(cy, size_px - 1))
                )

                pixel_coords = _polygon_to_pixel_coords(polygon, inv_transform)
                xs = [p[0] for p in pixel_coords]
                ys = [p[1] for p in pixel_coords]
                bbox_px = (min(xs), min(ys), max(xs), max(ys))

                sam_poly, sam_score = _sam_extract_building(
                    predictor, img_array, cx, cy, bbox_px, img_transform
                )

                if sam_poly is None:
                    phase1_results[bld_idx] = {
                        "geometry": polygon,
                        "status": "removed",
                        "confidence": sam_score,
                        "sam_polygon": None,
                        "iou": 0.0,
                        "metrics": json.dumps(
                            {"sam_score": sam_score, "note": "SAM found no building"}
                        ),
                    }
                    progress.counts["removed"] += 1
                else:
                    iou = _compute_iou(polygon, sam_poly)

                    if iou >= iou_unchanged:
                        status = "unchanged"
                    elif iou >= iou_modified_low:
                        status = "modified"
                    else:
                        try:
                            overlap_ratio = (
                                polygon.intersection(sam_poly).area / polygon.area
                            )
                        except Exception:
                            overlap_ratio = 0.0

                        # Pixel fallback — computed once and shared across sub-branches.
                        pixel_coords_clamped = [
                            (
                                max(0, min(px, size_px - 1)),
                                max(0, min(py, size_px - 1)),
                            )
                            for px, py in _polygon_to_pixel_coords(
                                polygon, inv_transform
                            )
                        ]
                        poly_mask = _create_polygon_mask(
                            pixel_coords_clamped, img_array.shape[:2]
                        )
                        px_score, _ = _analyze_building_pixels(img_array, poly_mask)

                        if overlap_ratio > overlap_ratio_min:
                            status = "modified"
                        elif iou == 0.0 and overlap_ratio == 0.0:
                            # SAM found a mask but with zero spatial overlap with the
                            # original footprint.  Use OR so either strong pixel evidence
                            # or high SAM confidence is sufficient to avoid a false
                            # "removed" label.
                            if px_score >= 0.8 or sam_score >= 0.9:
                                status = "modified"
                                iou = 0.0
                            else:
                                status = "removed"
                        else:
                            if px_score >= pixel_fallback_min:
                                status = "modified"
                                iou = overlap_ratio
                            else:
                                status = "removed"

                    progress.counts[status] += 1

                    phase1_results[bld_idx] = {
                        "geometry": polygon,
                        "status": status,
                        "confidence": sam_score,
                        "sam_polygon": sam_poly.wkt,
                        "iou": round(iou, 3),
                        "metrics": json.dumps(
                            {
                                "sam_score": sam_score,
                                "iou": round(iou, 3),
                            }
                        ),
                    }

                sam_processed += 1
                if sam_processed % 20 == 0 or sam_processed == len(sam_candidates):
                    progress.set_progress(
                        sam_processed,
                        len(sam_candidates),
                        f"SAM: {sam_processed}/{len(sam_candidates)} — "
                        f"U:{progress.counts['unchanged']} "
                        f"M:{progress.counts['modified']} "
                        f"R:{progress.counts['removed']}",
                    )

        progress.log(f"Phase 2 done: {sam_processed} buildings verified by SAM")

    # ── Build result ────────────────────────────────────────────────────
    progress.set_phase("saving", "Building result GeoJSON")

    rows = []
    for bld_idx, data in phase1_results.items():
        rows.append(
            {
                "input_idx": bld_idx,
                "geometry": data["geometry"],
                "status": data["status"],
                "confidence": data["confidence"],
                "iou": data["iou"],
                "sam_polygon": data["sam_polygon"],
                "metrics": data["metrics"],
            }
        )

    result_gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")

    counts = result_gdf["status"].value_counts()
    progress.log(f"Final: {counts.to_dict()}")

    out_path = os.path.join(output_dir, "buildings_classified.geojson")
    result_gdf.to_file(out_path, driver="GeoJSON")
    progress.log(f"Saved to {out_path}")

    return result_gdf


def to_2d_geom(g):
    if g is None:
        return None
    return transform(lambda x, y, z=None: (x, y), g)
