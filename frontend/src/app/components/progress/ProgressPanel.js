"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./ProgressPanel.module.css";

const PHASE_CONFIG = {
  initializing: { label: "Initializing", icon: "⚙️", step: 0 },
  setup: { label: "Validating Input", icon: "📋", step: 1 },
  tiling: { label: "Grouping Tiles", icon: "🗺️", step: 2 },
  phase1_satellite: {
    label: "Phase 1: Satellite & Pixel Analysis",
    icon: "🛰️",
    step: 3,
  },
  phase2_sam_loading: { label: "Loading SAM Model", icon: "🧠", step: 4 },
  phase2_sam: { label: "Phase 2: SAM Segmentation", icon: "🔍", step: 5 },
  saving: { label: "Saving Results", icon: "💾", step: 6 },
  complete: { label: "Complete", icon: "✅", step: 7 },
};

const TOTAL_STEPS = 7;

function formatTime(seconds) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

export default function ProgressPanel({ sessionId, onComplete }) {
  const [progress, setProgress] = useState(null);
  const [showLogs, setShowLogs] = useState(false);
  const logsEndRef = useRef(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    if (!sessionId) return;

    const poll = async () => {
      try {
        const res = await fetch(`/api/progress/${sessionId}/`);
        if (!res.ok) return;
        const data = await res.json();
        setProgress(data);

        if (data.phase === "complete") {
          clearInterval(intervalRef.current);
          if (onComplete) onComplete(data);
        }
      } catch (e) {
        // Silently retry
      }
    };

    poll(); // Immediate first poll
    intervalRef.current = setInterval(poll, 1500);

    return () => clearInterval(intervalRef.current);
  }, [sessionId, onComplete]);

  useEffect(() => {
    if (showLogs && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [progress?.logs?.length, showLogs]);

  if (!progress) {
    return (
      <div className={styles.panel}>
        <div className={styles.header}>
          <div className={styles.spinnerSmall}></div>
          <span>Connecting to server…</span>
        </div>
      </div>
    );
  }

  const phaseInfo = PHASE_CONFIG[progress.phase] || PHASE_CONFIG.initializing;
  const isComplete = progress.phase === "complete";
  const overallProgress = Math.round((phaseInfo.step / TOTAL_STEPS) * 100);

  return (
    <div
      className={`${styles.panel} ${isComplete ? styles.panelComplete : ""}`}
    >
      {/* Phase indicator */}
      <div className={styles.header}>
        <span className={styles.phaseIcon}>{phaseInfo.icon}</span>
        <div className={styles.headerText}>
          <div className={styles.phaseLabel}>{phaseInfo.label}</div>
          <div className={styles.phaseMeta}>
            Step {phaseInfo.step}/{TOTAL_STEPS}
            {progress.elapsed != null &&
              ` • ${formatTime(progress.elapsed)} elapsed`}
            {progress.eta_seconds != null &&
              !isComplete &&
              ` • ~${formatTime(progress.eta_seconds)} remaining`}
          </div>
        </div>
      </div>

      {/* Overall progress bar */}
      <div className={styles.progressSection}>
        <div className={styles.progressTrack}>
          <div
            className={`${styles.progressFill} ${isComplete ? styles.progressComplete : ""}`}
            style={{
              width: `${isComplete ? 100 : Math.max(overallProgress, progress.progress * 0.9)}%`,
            }}
          ></div>
        </div>
        <div className={styles.progressPercent}>
          {isComplete
            ? "100"
            : Math.round(Math.max(overallProgress, progress.progress))}
          %
        </div>
      </div>

      {/* Building counts */}
      {progress.processed > 0 && (
        <div className={styles.stats}>
          <div className={styles.statItem}>
            <span className={styles.statValue}>{progress.processed}</span>
            <span className={styles.statLabel}>
              / {progress.total} processed
            </span>
          </div>
          <div className={styles.statDivider}></div>
          <div className={styles.countRow}>
            <span
              className={styles.countDot}
              style={{ background: "#16a34a" }}
            ></span>
            <span className={styles.countNum}>
              {progress.counts?.unchanged || 0}
            </span>
            <span
              className={styles.countDot}
              style={{ background: "#f59e0b" }}
            ></span>
            <span className={styles.countNum}>
              {progress.counts?.modified || 0}
            </span>
            <span
              className={styles.countDot}
              style={{ background: "#ef4444" }}
            ></span>
            <span className={styles.countNum}>
              {progress.counts?.removed || 0}
            </span>
          </div>
        </div>
      )}

      {/* Step timeline */}
      <div className={styles.timeline}>
        {Object.entries(PHASE_CONFIG)
          .filter(([k]) => k !== "initializing")
          .map(([key, cfg]) => {
            const isDone = cfg.step < phaseInfo.step;
            const isCurrent = cfg.step === phaseInfo.step;
            return (
              <div
                key={key}
                className={`${styles.timelineStep} ${isDone ? styles.stepDone : ""} ${isCurrent ? styles.stepCurrent : ""}`}
              >
                <div className={styles.stepDot}>
                  {isDone ? (
                    "✓"
                  ) : isCurrent ? (
                    <span className={styles.stepPulse}></span>
                  ) : (
                    ""
                  )}
                </div>
                <span className={styles.stepLabel}>{cfg.label}</span>
              </div>
            );
          })}
      </div>

      {/* Expandable logs */}
      <button
        className={styles.logsToggle}
        onClick={() => setShowLogs(!showLogs)}
      >
        {showLogs ? "▾ Hide logs" : "▸ Show logs"} ({progress.logs?.length || 0}
        )
      </button>

      {showLogs && (
        <div className={styles.logsContainer}>
          {(progress.logs || []).map((log, i) => (
            <div
              key={i}
              className={`${styles.logLine} ${log.level === "error" ? styles.logError : ""}`}
            >
              <span className={styles.logTime}>{formatTime(log.time)}</span>
              <span className={styles.logMsg}>{log.message}</span>
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
      )}
    </div>
  );
}
