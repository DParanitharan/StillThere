'use client';

import { useState, useMemo, useCallback } from 'react';
import Navbar from '@/app/components/layout/Navbar';
import Sidebar from '@/app/components/layout/Sidebar';
import MapView from '@/app/components/map/MapView';
import FileUpload from '@/app/components/upload/FileUpload';
import ProgressPanel from '@/app/components/progress/ProgressPanel';
import { extractBuildings } from '@/services/api';
import styles from './page.module.css';

export default function Home() {
  const [geoData, setGeoData] = useState(null);
  const [buildingsGeoJSON, setBuildingsGeoJSON] = useState(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [address, setAddress] = useState("");
  const [searchPoint, setSearchPoint] = useState(null);
  const [geoLoading, setGeoLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState('all');

  const summary = useMemo(() => {
    if (!buildingsGeoJSON?.features) return null;
    const counts = { unchanged: 0, modified: 0, removed: 0, error: 0 };
    buildingsGeoJSON.features.forEach((f) => {
      const s = f.properties?.status || 'error';
      counts[s] = (counts[s] || 0) + 1;
    });
    return counts;
  }, [buildingsGeoJSON]);

  const filteredGeoJSON = useMemo(() => {
    if (!buildingsGeoJSON || statusFilter === 'all') return buildingsGeoJSON;
    return {
      ...buildingsGeoJSON,
      features: buildingsGeoJSON.features.filter(
        (f) => f.properties?.status === statusFilter
      ),
    };
  }, [buildingsGeoJSON, statusFilter]);

  const handleFileUpload = async (data) => {
    console.log('handleFileUpload called:', Object.keys(data || {}));
    if (data?.geojson) {
      setGeoData(data.geojson);
    }
    const sid = data?.session_id;
    if (!sid) {
      console.error("No session_id returned from upload");
      return;
    }
    setSessionId(sid);
    try {
      setIsExtracting(true);
      console.log('Classifying buildings for:', sid);
      const result = await extractBuildings(sid);
      console.log('Result features:', result?.features?.length);
      setBuildingsGeoJSON(result);
    } catch (err) {
      console.error("Classification failed:", err);
    } finally {
      setIsExtracting(false);
    }
  };

  const handleProgressComplete = useCallback(() => {
    // Progress panel shows complete — the extractBuildings promise
    // will resolve shortly after and set buildingsGeoJSON
  }, []);

  const handleGeocode = async () => {
    if (!address.trim()) return;
    setGeoLoading(true);
    try {
      const res = await fetch(`/api/geocode/?address=${encodeURIComponent(address)}`);
      const data = await res.json();
      if (data.status !== "OK" || !data.results?.length) {
        alert(`Geocode failed: ${data.status}`);
        return;
      }
      const loc = data.results[0].geometry.location;
      setSearchPoint({ lat: loc.lat, lng: loc.lng, label: data.results[0].formatted_address || address });
    } catch (e) {
      console.error(e);
      alert("Geocode request failed. See console.");
    } finally {
      setGeoLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <Navbar />
      <div className={styles.mainContent}>
        <Sidebar>
          <FileUpload onUpload={handleFileUpload} />

          {/* Progress Panel - replaces the old ⏳ text */}
          {isExtracting && sessionId && (
            <ProgressPanel
              sessionId={sessionId}
              onComplete={handleProgressComplete}
            />
          )}

          {summary && !isExtracting && (
            <div style={{ marginTop: '12px', fontSize: '14px', lineHeight: '1.8' }}>
              <h4 style={{ marginBottom: '8px' }}>Classification Results</h4>

              <div style={{ display: 'flex', gap: '4px', marginBottom: '8px', flexWrap: 'wrap' }}>
                {['all', 'unchanged', 'modified', 'removed'].map((s) => (
                  <button
                    key={s}
                    onClick={() => setStatusFilter(s)}
                    style={{
                      padding: '4px 10px',
                      fontSize: '12px',
                      border: statusFilter === s ? '2px solid #333' : '1px solid #ccc',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      backgroundColor: statusFilter === s ? '#e2e8f0' : '#fff',
                      fontWeight: statusFilter === s ? 'bold' : 'normal',
                    }}
                  >
                    {s === 'all' ? `All (${buildingsGeoJSON?.features?.length || 0})` :
                     `${s.charAt(0).toUpperCase() + s.slice(1)} (${summary[s] || 0})`}
                  </button>
                ))}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: 14, height: 14, backgroundColor: '#16a34a', display: 'inline-block', borderRadius: 2 }}></span>
                Unchanged: <strong>{summary.unchanged}</strong>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: 14, height: 14, backgroundColor: '#f59e0b', display: 'inline-block', borderRadius: 2 }}></span>
                Modified: <strong>{summary.modified}</strong>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: 14, height: 14, backgroundColor: '#ef4444', display: 'inline-block', borderRadius: 2 }}></span>
                Removed: <strong>{summary.removed}</strong>
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="Search address (e.g. Jurong East)"
              style={{ flex: 1, padding: 8, borderRadius: 6, border: "1px solid #ccc" }}
            />
            <button
              className={styles.analyzeButton}
              onClick={handleGeocode}
              disabled={geoLoading}
              style={{ whiteSpace: "nowrap" }}
            >
              {geoLoading ? "Searching..." : "Go"}
            </button>
          </div>
        </Sidebar>
        <div className={styles.mapContainer}>
          <MapView
            geoData={geoData}
            buildingsGeoData={filteredGeoJSON}
            searchPoint={searchPoint}
          />
        </div>
      </div>
    </div>
  );
}