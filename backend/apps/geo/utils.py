import geopandas as gpd
import os
import requests
import math
import numpy as np
import torch
import io
import logging
import json
import time
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
    'iou_unchanged':        _env_float('CLASSIFY_IOU_UNCHANGED', 0.35),
    'iou_modified_low':     _env_float('CLASSIFY_IOU_MODIFIED_LOW', 0.10),
    'sam_confidence_min':   _env_float('CLASSIFY_SAM_CONFIDENCE_MIN', 0.50),
    'box_pad_px':           _env_int('CLASSIFY_BOX_PAD_PX', 10),
    'overlap_ratio_min':    _env_float('CLASSIFY_OVERLAP_RATIO_MIN', 0.30),
    'pixel_fallback_min':   _env_float('CLASSIFY_PIXEL_FALLBACK_MIN', 0.50),
    'threshold_removed':    _env_float('CLASSIFY_THRESHOLD_REMOVED', 0.25),
}

logger.info(f"Classification thresholds: {CLASSIFY_THRESHOLDS}")


# ── Progress tracker ─────────────────────────────────────────────────────────

class ProgressTracker:
    """Collects progress events that can be polled by the API."""

    def __init__(self):
        self.logs = []
        self.phase = 'initializing'
        self.phase_progress = 0.0        # 0–1
        self.total_buildings = 0
        self.processed_buildings = 0
        self.start_time = time.time()
        self.phase_start_time = time.time()
        self.counts = {'unchanged': 0, 'modified': 0, 'removed': 0, 'error': 0}

    def log(self, message, level='info'):
        elapsed = round(time.time() - self.start_time, 1)
        entry = {
            'time': elapsed,
            'phase': self.phase,
            'message': message,
            'level': level,
            'progress': round(self.phase_progress * 100, 1),
            'processed': self.processed_buildings,
            'total': self.total_buildings,
            'counts': dict(self.counts),
        }
        self.logs.append(entry)
        logger.info(f"[{elapsed}s] [{self.phase}] {message}")

    def set_phase(self, phase, message=None):
        self.phase = phase
        self.phase_progress = 0.0
        self.phase_start_time = time.time()
        self.log(message or f"Starting {phase}")

    def set_progress(self, current, total, message=None):
        self.phase_progress = current / total if total > 0 else 0
        self.processed_buildings = current
        if message:
            self.log(message)

    def to_dict(self):
        elapsed = round(time.time() - self.start_time, 1)
        # Estimate remaining time
        eta = None
        if self.processed_buildings > 0 and self.total_buildings > 0:
            rate = elapsed / self.processed_buildings
            remaining = self.total_buildings - self.processed_buildings
            eta = round(rate * remaining, 1)

        return {
            'phase': self.phase,
            'progress': round(self.phase_progress * 100, 1),
            'processed': self.processed_buildings,
            'total': self.total_buildings,
            'elapsed': elapsed,
            'eta_seconds': eta,
            'counts': dict(self.counts),
            'logs': self.logs[-50:],  # Last 50 entries
        }


# In-memory store for active progress trackers (keyed by session_id)
_active_progress = {}


def get_progress(session_id):
    """Retrieve progress for a session (called by the API view)."""
    tracker = _active_progress.get(session_id)
    if tracker is None:
        return None
    return tracker.to_dict()


# ── helpers ──────────────────────────────────────────────────────────────────

def _meters_per_pixel(lat, zoom):
    return 156543.03392 * math.cos(lat * math.pi / 180) / (2 ** zoom)


def _download_google_tile(center_lat, center_lng, zoom, size, api_key):
    url = (
        f"https://maps.googleapis.com/maps/api/staticmap?"
        f"center={center_lat},{center_lng}"
        f"&zoom={zoom}"
        f"&size={size}x{size}"
        f"&maptype=satellite"
        f"&key={api_key}"
    )
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Google Maps API error: {resp.status_code}")
    return np.array(Image.open(io.BytesIO(resp.content)).convert('RGB'))


def _tile_bounds(center_lat, center_lng, size_px, mpp):
    half_lat = (size_px / 2 * mpp) / 111000
    half_lng = (size_px / 2 * mpp) / (111000 * math.cos(center_lat * math.pi / 180))
    return {
        'min_lng': center_lng - half_lng, 'max_lng': center_lng + half_lng,
        'min_lat': center_lat - half_lat, 'max_lat': center_lat + half_lat,
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
    mask_img = Image.new('L', (img_shape[1], img_shape[0]), 0)
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
        tiles.append((sum(lats)/len(lats), sum(lngs)/len(lngs), buildings))
    return tiles


# Phase 1: Fast pixel-based comparison to find "removed" buildings

def _analyze_building_pixels(img_array, polygon_mask):
    masked_pixels = img_array[polygon_mask]
    if len(masked_pixels) < 10:
        return 0.0, {'reason': 'too_few_pixels'}

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

    score = 0.0
    if 60 < mean_brightness < 220:
        score += 0.2
    if color_std < 40:
        score += 0.2
    elif color_std < 60:
        score += 0.1
    if 15 < texture_std < 60:
        score += 0.2
    if green_ratio < 0.38:
        score += 0.2
    elif green_ratio < 0.42:
        score += 0.1
    if saturation < 0.3:
        score += 0.2
    elif saturation < 0.5:
        score += 0.1

    return score, {
        'mean_brightness': float(mean_brightness),
        'color_std': float(color_std),
        'texture_std': float(texture_std),
        'green_ratio': green_ratio,
        'saturation': saturation,
    }


#  Phase 2: SAM shape comparison

def _load_sam_predictor():
    from segment_anything import sam_model_registry, SamPredictor

    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    for model_type, filename in [('vit_b', 'sam_vit_b_01ec64.pth'),
                                  ('vit_h', 'sam_vit_h_4b8939.pth')]:
        path = os.path.join(base, filename)
        if os.path.exists(path):
            device = 'mps' if torch.backends.mps.is_available() else \
                     ('cuda' if torch.cuda.is_available() else 'cpu')
            logger.info(f"Loading SAM {model_type} on {device}")
            sam = sam_model_registry[model_type](checkpoint=path)
            sam.to(device)
            return SamPredictor(sam)

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


def _sam_extract_building(predictor, img_array, center_px, center_py,
                          bbox_px, img_transform):
    """
    Run SAM with BOTH a point prompt and a box prompt for better accuracy.
    """
    size_px = img_array.shape[0]
    pad = CLASSIFY_THRESHOLDS['box_pad_px']
    sam_confidence_min = CLASSIFY_THRESHOLDS['sam_confidence_min']

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
    """
    # ── Set up progress tracker ─────────────────────────────────────────
    progress = ProgressTracker()
    if session_id:
        _active_progress[session_id] = progress

    try:
        return _classify_buildings_inner(input_gdf, output_dir, zoom, progress)
    finally:
        # Mark complete
        progress.set_phase('complete', 'Classification finished')
        # Clean up after a delay (keep around for final poll)
        if session_id:
            import threading
            def _cleanup():
                time.sleep(30)
                _active_progress.pop(session_id, None)
            threading.Thread(target=_cleanup, daemon=True).start()


def _classify_buildings_inner(input_gdf, output_dir, zoom, progress):
    # ── Read thresholds ─────────────────────────────────────────────────
    threshold_removed   = CLASSIFY_THRESHOLDS['threshold_removed']
    iou_unchanged       = CLASSIFY_THRESHOLDS['iou_unchanged']
    iou_modified_low    = CLASSIFY_THRESHOLDS['iou_modified_low']
    overlap_ratio_min   = CLASSIFY_THRESHOLDS['overlap_ratio_min']
    pixel_fallback_min  = CLASSIFY_THRESHOLDS['pixel_fallback_min']

    progress.set_phase('setup', 'Reading thresholds and validating input')
    progress.log(f"Thresholds: {CLASSIFY_THRESHOLDS}")

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY not set")

    gdf = input_gdf.to_crs(epsg=4326).copy()
    gdf = gdf[gdf.geometry.notnull() & gdf.geometry.is_valid].copy()
    progress.total_buildings = len(gdf)
    progress.log(f"Loaded {len(gdf)} valid building polygons")

    # ── Tile grouping ───────────────────────────────────────────────────
    progress.set_phase('tiling', 'Grouping buildings into spatial tiles')
    tile_groups = _group_buildings_into_tiles(gdf, tile_size_m=180)
    progress.log(f"Created {len(tile_groups)} tiles (180m grid)")

    size_px = 640
    phase1_results = {}
    sam_candidates = []
    total_processed = 0

    # ── PHASE 1: Pixel triage ───────────────────────────────────────────
    progress.set_phase('phase1_satellite', 'Downloading satellite imagery & pixel analysis')
    tile_cache = {}
    total_tiles = len(tile_groups)

    for tile_idx, (tile_lat, tile_lng, buildings) in enumerate(tile_groups):
        try:
            progress.log(
                f"Tile {tile_idx+1}/{total_tiles}: downloading satellite image "
                f"({len(buildings)} buildings)"
            )

            mpp = _meters_per_pixel(tile_lat, zoom)
            img_array = _download_google_tile(tile_lat, tile_lng, zoom, size_px, api_key)
            bounds = _tile_bounds(tile_lat, tile_lng, size_px, mpp)
            img_transform = from_bounds(
                bounds['min_lng'], bounds['min_lat'],
                bounds['max_lng'], bounds['max_lat'],
                img_array.shape[1], img_array.shape[0]
            )
            inv_transform = ~img_transform
            tile_cache[tile_idx] = (img_array, img_transform, inv_transform)

            for bld_idx, row in buildings:
                polygon = row.geometry
                pixel_coords = _polygon_to_pixel_coords(polygon, inv_transform)
                pixel_coords = [(max(0, min(px, size_px-1)), max(0, min(py, size_px-1)))
                                for px, py in pixel_coords]
                poly_mask = _create_polygon_mask(pixel_coords, img_array.shape[:2])
                score, metrics = _analyze_building_pixels(img_array, poly_mask)

                if score < threshold_removed:
                    phase1_results[bld_idx] = {
                        'geometry': polygon,
                        'status': 'removed',
                        'confidence': score,
                        'sam_polygon': None,
                        'iou': 0.0,
                        'metrics': json.dumps(metrics),
                    }
                    progress.counts['removed'] += 1
                else:
                    sam_candidates.append((bld_idx, row, tile_idx))

            total_processed += len(buildings)
            progress.set_progress(
                total_processed, len(gdf),
                f"Phase 1: {total_processed}/{len(gdf)} buildings analyzed"
            )

        except Exception as e:
            logger.error(f"Phase 1 error on tile {tile_idx}: {e}")
            progress.log(f"Error on tile {tile_idx}: {e}", level='error')
            for bld_idx, row in buildings:
                phase1_results[bld_idx] = {
                    'geometry': row.geometry,
                    'status': 'error',
                    'confidence': 0.0,
                    'sam_polygon': None,
                    'iou': 0.0,
                    'metrics': json.dumps({'error': str(e)}),
                }
                progress.counts['error'] += 1
            total_processed += len(buildings)

    removed_count = sum(1 for r in phase1_results.values() if r['status'] == 'removed')
    progress.log(
        f"Phase 1 complete: {removed_count} removed, "
        f"{len(sam_candidates)} need SAM verification"
    )

    # ── PHASE 2: SAM ────────────────────────────────────────────────────
    if sam_candidates:
        progress.set_phase('phase2_sam_loading', 'Loading SAM model into memory')
        progress.log(f"Loading SAM model for {len(sam_candidates)} buildings…")
        predictor = _load_sam_predictor()
        progress.log("SAM model loaded successfully")

        progress.set_phase('phase2_sam', f'Running SAM segmentation on {len(sam_candidates)} buildings')

        candidates_by_tile = {}
        for bld_idx, row, tile_idx in sam_candidates:
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
                cx, cy = int(max(0, min(cx, size_px-1))), int(max(0, min(cy, size_px-1)))

                pixel_coords = _polygon_to_pixel_coords(polygon, inv_transform)
                xs = [p[0] for p in pixel_coords]
                ys = [p[1] for p in pixel_coords]
                bbox_px = (min(xs), min(ys), max(xs), max(ys))

                sam_poly, sam_score = _sam_extract_building(
                    predictor, img_array, cx, cy, bbox_px, img_transform
                )

                if sam_poly is None:
                    phase1_results[bld_idx] = {
                        'geometry': polygon,
                        'status': 'removed',
                        'confidence': sam_score,
                        'sam_polygon': None,
                        'iou': 0.0,
                        'metrics': json.dumps({'sam_score': sam_score,
                                               'note': 'SAM found no building'}),
                    }
                    progress.counts['removed'] += 1
                else:
                    iou = _compute_iou(polygon, sam_poly)

                    if iou >= iou_unchanged: #iou >= 0.35:
                        status = 'unchanged'
                    elif iou < iou_unchanged and iou >= iou_modified_low: # 0.10 <= iou < 0.35 
                        status = 'modified'
                    else: #iou < 0.10
                        try:
                            overlap_ratio = polygon.intersection(sam_poly).area / polygon.area
                        except (ZeroDivisionError, Exception) as e:
                            logger.warning(f"Overlap ratio computation failed for building {bld_idx}: {e}")
                            overlap_ratio = 0.0

                        if overlap_ratio > overlap_ratio_min:
                            status = 'modified'
                        elif iou == 0.0 and overlap_ratio == 0.0:
                            pixel_coords_clamped = [
                                (max(0, min(px, size_px-1)), max(0, min(py, size_px-1)))
                                for px, py in _polygon_to_pixel_coords(polygon, inv_transform)
                            ]
                            poly_mask = _create_polygon_mask(
                                pixel_coords_clamped, img_array.shape[:2]
                            )
                            px_score, _ = _analyze_building_pixels(img_array, poly_mask)
                            if px_score >= 0.8 and sam_score >= 0.9:
                                status = 'modified'
                                iou = 0.0
                            else:
                                status = 'removed'
                        else:
                            pixel_coords_clamped = [
                                (max(0, min(px, size_px-1)), max(0, min(py, size_px-1)))
                                for px, py in _polygon_to_pixel_coords(polygon, inv_transform)
                            ]
                            poly_mask = _create_polygon_mask(
                                pixel_coords_clamped, img_array.shape[:2]
                            )
                            px_score, _ = _analyze_building_pixels(img_array, poly_mask)
                            if px_score >= pixel_fallback_min:
                                status = 'modified'
                                iou = overlap_ratio
                            else:
                                status = 'removed'

                    progress.counts[status] += 1

                    phase1_results[bld_idx] = {
                        'geometry': polygon,
                        'status': status,
                        'confidence': sam_score,
                        'sam_polygon': sam_poly.wkt,
                        'iou': round(iou, 3),
                        'metrics': json.dumps({
                            'sam_score': sam_score,
                            'iou': round(iou, 3),
                        }),
                    }

                sam_processed += 1
                if sam_processed % 20 == 0 or sam_processed == len(sam_candidates):
                    progress.set_progress(
                        sam_processed, len(sam_candidates),
                        f"SAM: {sam_processed}/{len(sam_candidates)} — "
                        f"U:{progress.counts['unchanged']} "
                        f"M:{progress.counts['modified']} "
                        f"R:{progress.counts['removed']}"
                    )

        progress.log(f"Phase 2 done: {sam_processed} buildings verified by SAM")

    # ── Build result ────────────────────────────────────────────────────
    progress.set_phase('saving', 'Building result GeoJSON')

    rows = []
    for bld_idx, data in phase1_results.items():
        rows.append({
            'input_idx': bld_idx,
            'geometry': data['geometry'],
            'status': data['status'],
            'confidence': data['confidence'],
            'iou': data['iou'],
            'metrics': data['metrics'],
        })

    result_gdf = gpd.GeoDataFrame(rows, crs='EPSG:4326')

    counts = result_gdf['status'].value_counts()
    progress.log(f"Final: {counts.to_dict()}")

    out_path = os.path.join(output_dir, 'buildings_classified.geojson')
    result_gdf.to_file(out_path, driver='GeoJSON')
    progress.log(f"Saved to {out_path}")

    return result_gdf


def to_2d_geom(g):
    if g is None:
        return None
    return transform(lambda x, y, z=None: (x, y), g)