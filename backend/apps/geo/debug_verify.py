"""
Debug script to visually verify classification results.
Run: python -m apps.geo.debug_verify
"""
import geopandas as gpd
import numpy as np
import os
import json
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUTPUT_DIR = Path('media/outputs/debug_tiles')


def generate_verification_report(classified_path='media/outputs/buildings_classified.geojson',
                                  max_samples=50):
    """
    Generate PNG images showing each classified building with its status.
    Focuses on 'modified' buildings so you can verify if they're truly modified.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    gdf = gpd.read_file(classified_path)
    print(f"Loaded {len(gdf)} buildings")
    print(f"Status counts:\n{gdf['status'].value_counts()}")

    # Print IoU distribution for modified buildings
    modified = gdf[gdf['status'] == 'modified'].copy()
    if 'iou' in modified.columns:
        print(f"\nModified buildings IoU distribution:")
        print(f"  Mean: {modified['iou'].mean():.3f}")
        print(f"  Median: {modified['iou'].median():.3f}")
        print(f"  Min: {modified['iou'].min():.3f}")
        print(f"  Max: {modified['iou'].max():.3f}")
        print(f"\n  IoU histogram:")
        for low in np.arange(0, 0.55, 0.05):
            high = low + 0.05
            count = ((modified['iou'] >= low) & (modified['iou'] < high)).sum()
            bar = '█' * count
            print(f"  {low:.2f}-{high:.2f}: {count:4d} {bar}")

    # Show a sample of modified buildings with their metrics
    print(f"\n{'='*80}")
    print(f"Sample modified buildings (first {min(max_samples, len(modified))}):")
    print(f"{'='*80}")

    for i, (idx, row) in enumerate(modified.head(max_samples).iterrows()):
        metrics = json.loads(row['metrics']) if isinstance(row['metrics'], str) else row['metrics']
        print(f"\n  Building {row.get('input_idx', idx)}:")
        print(f"    Status: {row['status']}")
        print(f"    IoU: {row.get('iou', 'N/A')}")
        print(f"    Confidence: {row.get('confidence', 'N/A')}")
        print(f"    SAM score: {metrics.get('sam_score', 'N/A')}")
        print(f"    Geometry area (deg²): {row.geometry.area:.10f}")

    # Summary recommendation
    print(f"\n{'='*80}")
    print("RECOMMENDATION:")
    if modified['iou'].median() > 0.35:
        print(f"  Median IoU of modified buildings is {modified['iou'].median():.3f}")
        print(f"  Many 'modified' buildings likely have IoU close to 0.5 threshold.")
        print(f"  Consider LOWERING iou_modified threshold (e.g., 0.3) to reduce false positives.")
        print(f"  Or these buildings genuinely have shape differences vs SAM detection.")
    else:
        print(f"  Median IoU is low ({modified['iou'].median():.3f}), suggesting real differences.")


if __name__ == '__main__':
    generate_verification_report()