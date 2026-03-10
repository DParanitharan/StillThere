'use client';

import { useState, useMemo, useCallback } from 'react';
import Navbar from '@/app/components/layout/Navbar';
import MapView from '@/app/components/map/MapView';
import FileUpload from '@/app/components/upload/FileUpload';
import ProgressPanel from '@/app/components/progress/ProgressPanel';
import ChatWidget from '@/app/components/chat/ChatWidget';
import { extractBuildings } from '@/services/api';
import styles from './dashboard.module.css';

export default function DashboardPage() {
  const [geoData, setGeoData] = useState(null);
  const [buildingsGeoJSON, setBuildingsGeoJSON] = useState(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [address, setAddress] = useState('');
  const [searchPoint, setSearchPoint] = useState(null);
  const [geoLoading, setGeoLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState('all');
  const [sessionTitle, setSessionTitle] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

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
    setSaveSuccess(false);
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

  const handleSaveToHistory = async () => {
    if (!sessionId) {
      alert('No analysis session to save. Upload a file first.');
      return;
    }
    if (!sessionTitle.trim()) {
      alert('Please enter a title for this session.');
      return;
    }
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      const res = await fetch('/api/sessions/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          title: sessionTitle.trim(),
          summary: summary || null,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSaveSuccess(true);
    } catch (err) {
      console.error('Failed to save session:', err);
      alert('Failed to save session. See console for details.');
    } finally {
      setIsSaving(false);
    }
  };

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
    <div className={styles.page}>
      <Navbar />
      <div className={styles.body}>
        {/* Sidebar */}
        <aside className={styles.sidebar}>
          <h2 className={styles.sideTitle}>Analyze Changes</h2>
          <p className={styles.sideDesc}>Upload geospatial data to detect building footprint changes.</p>

          <div className={styles.field}>
            <label className={styles.label}>Upload File</label>
            <FileUpload onUpload={handleFileUpload} />
          </div>

          {isExtracting && sessionId && (
            <ProgressPanel 
              sessionId={sessionId} 
              onComplete={handleProgressComplete} />
          )}

          {summary && !isExtracting && (
            <div className={styles.results}>
              <h4 className={styles.resultsHead}>Classification Results</h4>
              <div className={styles.filters}>
                {['all', 'unchanged', 'modified', 'removed'].map((s) => (
                  <button
                    key={s}
                    onClick={() => setStatusFilter(s)}
                    className={`${styles.filterBtn} ${statusFilter === s ? styles.filterActive : ''}`}
                  >
                    {s === 'all'
                      ? `All (${buildingsGeoJSON?.features?.length || 0})`
                      : `${s.charAt(0).toUpperCase() + s.slice(1)} (${summary[s] || 0})`}
                  </button>
                ))}
              </div>
              <div className={styles.stats}>
                {[
                  { label: 'Unchanged', color: '#16a34a', val: summary.unchanged },
                  { label: 'Modified', color: '#f59e0b', val: summary.modified },
                  { label: 'Removed', color: '#ef4444', val: summary.removed },
                ].map((r) => (
                  <div key={r.label} className={styles.statRow}>
                    <span className={styles.dot} style={{ background: r.color }} />
                    {r.label}: <strong>{r.val}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Save to History */}
          <div className={styles.saveSection}>
            <label className={styles.label}>Session Title</label>
            <input
              type="text"
              value={sessionTitle}
              onChange={(e) => {
                setSessionTitle(e.target.value);
                setSaveSuccess(false);
              }}
              placeholder="e.g. Singapore East — March 2026"
              className={styles.titleInput}
            />
            <button
              onClick={handleSaveToHistory}
              disabled={isSaving || !sessionId}
              className={styles.saveBtn}
            >
              {isSaving ? 'Saving…' : saveSuccess ? '✓ Saved' : 'Save to History'}
            </button>
            {!sessionId && (
              <p className={styles.saveHint}>Upload and analyze a file first.</p>
            )}
            {saveSuccess && (
              <p className={styles.saveOk}>Session saved! View it on the History page.</p>
            )}
          </div>

          <div className={styles.searchRow}>
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleGeocode()}
              placeholder="Search address…"
              className={styles.searchInput}
            />
            <button onClick={handleGeocode} disabled={geoLoading} className={styles.goBtn}>
              {geoLoading ? '…' : 'Go'}
            </button>
          </div>
        </aside>

        {/* Map */}
        <div className={styles.map}>
          <MapView geoData={geoData} buildingsGeoData={filteredGeoJSON} searchPoint={searchPoint} />
        </div>
      </div>
      <ChatWidget />
    </div>
  );
}
