'use client';

import { useEffect, useState } from 'react';
import styles from './MapView.module.css';
// TODO: SCRUM-29 - Setup Map Library

export default function MapView({ geoData, analysisResult }) {
  const [MapComponents, setMapComponents] = useState(null);

  useEffect(() => {
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
      
      setMapComponents({ MapContainer, TileLayer, GeoJSON });
    };
    loadMap();
  }, []);

  const getFeatureStyle = (feature) => {
    const colors = {
      added: '#16a34a', removed: '#dc2626', modified: '#eab308',
      review: '#0891b2', unchanged: '#6b7280',
    };
    return {
      fillColor: colors[feature?.properties?.status] || '#2563eb',
      weight: 2, opacity: 1, color: '#1e293b', fillOpacity: 0.6,
    };
  };

  if (!MapComponents) {
    return <div className={styles.placeholder}><p>Loading map...</p></div>;
  }

  const { MapContainer, TileLayer, GeoJSON } = MapComponents;

  return (
    <div className={styles.mapWrapper}>
      <MapContainer center={[37.0902, 140.8877]} zoom={13} className={styles.map}>
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {geoData && <GeoJSON data={geoData} style={getFeatureStyle} />}
      </MapContainer>
      
      <div className={styles.legend}>
        <h4>Legend</h4>
        {[
          { label: 'Added', color: '#16a34a' },
          { label: 'Removed', color: '#dc2626' },
          { label: 'Modified', color: '#eab308' },
          { label: 'Review', color: '#0891b2' },
          { label: 'Unchanged', color: '#6b7280' },
        ].map(({ label, color }) => (
          <div key={label} className={styles.legendItem}>
            <span className={styles.legendColor} style={{ backgroundColor: color }}></span>
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}