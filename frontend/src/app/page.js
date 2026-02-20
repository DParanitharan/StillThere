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
      </div>
    </div>
  );
}