'use client';

import { useState } from 'react';
import Navbar from '@/app/components/layout/Navbar';
import Sidebar from '@/app/components/layout/Sidebar';
import MapView from '@/app/components/map/MapView';
import FileUpload from '@/app/components/upload/FileUpload';
import AnalysisSummary from '@/app/components/analysis/AnalysisSummary';
import styles from './page.module.css';

export default function Home() {
  // Shared state - components will use these
  const [geoData, setGeoData] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [address, setAddress] = useState("");
  const [searchPoint, setSearchPoint] = useState(null); // { lat, lng, label }
  const [geoLoading, setGeoLoading] = useState(false);
  const backend = process.env.NEXT_PUBLIC_BACKEND_URL;

  const handleFileUpload = (file, data) => {
    setGeoData(data);
    setAnalysisResult(null);
  };

  const handleRunAnalysis = async () => {
    if (!geoData) return;
    setIsAnalyzing(true);
    // TODO: Connect to backend API
    setTimeout(() => {
      setAnalysisResult({ added: 0, removed: 0, modified: 0, unchanged: 0, review: 0 });
      setIsAnalyzing(false);
    }, 1000);
  };
  
  const testBackendHealth = async () => {
    try {
      const res = await fetch("/api/health"); // <-- uses next.config.js rewrite
      const text = await res.text();

      console.log("HTTP status:", res.status);
      console.log("Raw response:", text);

      alert(`status=${res.status}\n${text.slice(0, 200)}`);
    } catch (e) {
      console.error("Fetch failed:", e);
      alert("Request failed — see console");
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

      const loc = data.results[0].geometry.location; // { lat, lng }
      setSearchPoint({
        lat: loc.lat,
        lng: loc.lng,
        label: data.results[0].formatted_address || address,
      });
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

      <pre style={{ padding: 12, margin: 12, background: "#f5f5f5", borderRadius: 8 }}>
      BACKEND: {process.env.NEXT_PUBLIC_BACKEND_URL}
      {"\n"}
      GMAPS KEY loaded: {process.env.NEXT_PUBLIC_GOOGLE_MAPS_KEY ? "YES" : "NO"}
      </pre>


      <div className={styles.mainContent}>
        <Sidebar>
          <FileUpload onUpload={handleFileUpload} />
          {geoData && (
            <button
              className={styles.analyzeButton}
              onClick={handleRunAnalysis}
              disabled={isAnalyzing}
            >
              {isAnalyzing ? 'Analyzing...' : 'Run Change Analysis'}
            </button>
          )}
          {analysisResult && <AnalysisSummary results={analysisResult} />}

          <button className={styles.analyzeButton} onClick={testBackendHealth}>
            Test Backend Health
          </button>

          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
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
          <MapView geoData={geoData} analysisResult={analysisResult} searchPoint={searchPoint} />
        </div>
      </div>
    </div>
  );
}