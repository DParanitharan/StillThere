"use client";

import AnalysisSummary from "@/app/components/analysis/AnalysisSummary";
import ChatInterface from "@/app/components/chat/ChatInterface";
import Navbar from "@/app/components/layout/Navbar";
import Sidebar from "@/app/components/layout/Sidebar";
import MapView from "@/app/components/map/MapView";
import FileUpload from "@/app/components/upload/FileUpload";
import { useState } from "react";
import styles from "./page.module.css";

export default function Home() {
  // Shared state - components will use these
  const [geoData, setGeoData] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analysisError, setAnalysisError] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);

  const handleFileUpload = (file, data, id) => {
    setGeoData(data);
    setSessionId(id);
    setAnalysisResult(null);
    setAnalysisError(null);
  };

  const handleRunAnalysis = async () => {
    if (!geoData || !sessionId) return;

    setIsAnalyzing(true);
    setAnalysisError(null);

    try {
      const res = await fetch(`/api/analyze/${sessionId}/`, {
        method: "POST",
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Analysis failed (${res.status}): ${text}`);
      }

      const data = await res.json();
      setAnalysisResult(data);
    } catch (err) {
      console.error(err);
      setAnalysisError(err.message || "Analysis failed. Please try again.");
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
              {isAnalyzing ? "Analyzing..." : "Run Change Analysis"}
            </button>
          )}
          {analysisError && <p className={styles.error}>{analysisError}</p>}
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
