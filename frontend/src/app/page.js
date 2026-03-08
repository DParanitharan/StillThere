'use client';

import { useState } from 'react';
import Navbar from '@/app/components/layout/Navbar';
import Sidebar from '@/app/components/layout/Sidebar';
import MapView from '@/app/components/map/MapView';
import FileUpload from '@/app/components/upload/FileUpload';
import AnalysisSummary from '@/app/components/analysis/AnalysisSummary';
import styles from './page.module.css';
import ChatInterface from '@/app/components/chat/ChatInterface';

export default function Home() {
  // Shared state - components will use these
  const [geoData, setGeoData] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);

  const handleFileUpload = (file, data) => {
    setGeoData(data);
    setAnalysisResult(null);
  };

  const handleRunAnalysis = async () => {
    if (!geoData) return;

    setIsAnalyzing(true);

    try {
      const res = await fetch(`/api/analyze/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ geoData }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Backend error ${res.status}: ${text}`);
      }

      const data = await res.json();
      setAnalysisResult(data);

    } catch (err) {
      console.error(err);
      alert(err.message || "Failed to run analysis");
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className={styles.container}>
      <Navbar />
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
        </Sidebar>
        <div className={styles.mapContainer}>
          <MapView geoData={geoData} analysisResult={analysisResult} />
        </div>
        <ChatInterface 
          isOpen={isChatOpen} 
          onToggle={() => setIsChatOpen(!isChatOpen)}
          position="right"
          geoData={geoData}
          analysisResult={analysisResult}
        />
      </div>
    </div>
  );
}