'use client';

import { useEffect, useState } from 'react';
import styles from './MapView.module.css';

export default function MapView({ geoData, analysisResult }) {
  const [MapComponents, setMapComponents] = useState(null);

  useEffect(() => {
    if (!geoData) return; // Don't load map if no data

    const loadMap = async () => {
      const L = await import('leaflet');
      const { MapContainer, TileLayer, GeoJSON } = await import('react-leaflet');
      await import('leaflet/dist/leaflet.css');
      
      delete L.Icon.Default.prototype._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
        iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
      });
      
      setMapComponents({ MapContainer, TileLayer, GeoJSON, L });
    };
    loadMap();
  }, [geoData]);

  const getFeatureStyle = (feature) => {
    const colors = {
      added: '#16a34a',
      removed: '#dc2626',
      modified: '#eab308',
      review: '#0000f6',
      unchanged: '#7997d4',
    };
    return {
      fillColor: colors[feature?.properties?.status] || '#7997d4',
      weight: 0.8,
      opacity: 1,
      color: '#374761',
      fillOpacity: 0.3,
    };
  };

  const getCenter = (data) => {
    if (!data || !data.features || data.features.length === 0) {
      return [1.3521, 103.8198]; // Default: Singapore
    }

    let minLat = Infinity, maxLat = -Infinity;
    let minLng = Infinity, maxLng = -Infinity;

    data.features.forEach((feature) => {
      const coords = feature.geometry.coordinates;
      
      const processCoords = (coordArray) => {
        if (typeof coordArray[0] === 'number') {
          // [lng, lat]
          minLng = Math.min(minLng, coordArray[0]);
          maxLng = Math.max(maxLng, coordArray[0]);
          minLat = Math.min(minLat, coordArray[1]);
          maxLat = Math.max(maxLat, coordArray[1]);
        } else {
          coordArray.forEach(processCoords);
        }
      };

      processCoords(coords);
    });

    return [(minLat + maxLat) / 2, (minLng + maxLng) / 2];
  };

  // No data uploaded - show placeholder
  if (!geoData) {
    return (
      <div className={styles.placeholder}>
        <div className={styles.placeholderContent}>
          <span className={styles.placeholderIcon}>🗺️</span>
          <h2>No Map Data</h2>
          <p>Upload a shapefile to visualise building footprints</p>
          <div className={styles.instructions}>
            <div className={styles.step}>
              <span className={styles.stepNumber}>1</span>
              <span>Upload a ZIP file containing your shapefile</span>
            </div>
            <div className={styles.step}>
              <span className={styles.stepNumber}>2</span>
              <span>View polygons rendered on the map</span>
            </div>
            <div className={styles.step}>
              <span className={styles.stepNumber}>3</span>
              <span>Run analysis to detect changes</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Data exists but map is still loading
  if (!MapComponents) {
    return (
      <div className={styles.placeholder}>
        <div className={styles.loadingContent}>
          <div className={styles.spinner}></div>
          <p>Loading map...</p>
        </div>
      </div>
    );
  }

  const { MapContainer, TileLayer, GeoJSON } = MapComponents;
  const center = getCenter(geoData);

  return (
    <div className={styles.mapWrapper}>
      <MapContainer center={center} zoom={14} className={styles.map}>
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <GeoJSON data={geoData} style={getFeatureStyle} />
      </MapContainer>
      
      <div className={styles.legend}>
        <h4>Legend</h4>
        {[
          { label: 'Added', color: '#16a34a' },
          { label: 'Removed', color: '#dc2626' },
          { label: 'Modified', color: '#eab308' },
          { label: 'Review', color: '#0000f6' },
          { label: 'Unchanged', color: '#7997d4' },
        ].map(({ label, color }) => (
          <div key={label} className={styles.legendItem}>
            <span className={styles.legendColor} style={{ backgroundColor: color }}></span>
            {label}
          </div>
        ))}
      </div>

      <div className={styles.featureCount}>
        {geoData.features?.length || 0} features loaded
      </div>
    </div>
  );
}
