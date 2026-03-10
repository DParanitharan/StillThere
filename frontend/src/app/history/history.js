'use client';

import { useState, useEffect } from 'react';
import Navbar from '@/app/components/layout/Navbar';
import styles from './history.module.css';

const DUMMY_SESSION = {
  id: 'demo-001',
  session_id: 'demo-001',
  title: 'Singapore East — March 2026',
  created_at: '2026-03-08T14:32:00Z',
  filename: 'singapore_east_2026.tif',
  summary: { unchanged: 124, modified: 18, removed: 5 },
  steps: [
    { label: 'File uploaded', status: 'done', time: '14:32:01' },
    { label: 'Tiling image', status: 'done', time: '14:32:08' },
    { label: 'SAM segmentation', status: 'done', time: '14:33:45' },
    { label: 'Footprint filtering', status: 'done', time: '14:34:02' },
    { label: 'Change classification', status: 'done', time: '14:34:19' },
    { label: 'Results saved', status: 'done', time: '14:34:20' },
  ],
};

export default function HistoryPage() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    async function fetchHistory() {
      try {
        const res = await fetch('/api/sessions/');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setSessions(data);
      } catch (err) {
        console.error('Failed to fetch history:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchHistory();
  }, []);

  const allSessions = [DUMMY_SESSION, ...sessions];

  const toggleExpand = (id) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleString();
  };

  return (
    <div className={styles.page}>
      <Navbar />
      <div className={styles.container}>
        <h1 className={styles.title}>Analysis History</h1>
        <p className={styles.subtitle}>
          View past building footprint analysis sessions and their results.
        </p>

        {loading ? (
          <div className={styles.loading}>
            <div className={styles.spinner} />
            <p>Loading history…</p>
          </div>
        ) : (
          <div className={styles.list}>
            {allSessions.map((s) => (
              <div key={s.id} className={styles.card}>
                <button className={styles.cardHeader} onClick={() => toggleExpand(s.id)}>
                  <div className={styles.cardMeta}>
                    <span className={styles.sessionTitle}>
                      {s.title || `Untitled Session`}
                      {s.id === DUMMY_SESSION.id && (
                        <span className={styles.demoBadge}>Demo</span>
                      )}
                    </span>
                    <span className={styles.sessionMeta}>
                      {s.session_id && <span className={styles.sessionId}>ID: {s.session_id}</span>}
                      <span className={styles.date}>{formatDate(s.created_at)}</span>
                    </span>
                  </div>
                  <span className={styles.chevron}>
                    {expandedId === s.id ? '▲' : '▼'}
                  </span>
                </button>

                {expandedId === s.id && (
                  <div className={styles.cardBody}>
                    <div className={styles.detail}>
                      <strong>File:</strong> {s.filename || 'N/A'}
                    </div>

                    {s.steps && (
                      <div className={styles.workflow}>
                        <h4 className={styles.workflowTitle}>Workflow</h4>
                        <ol className={styles.timeline}>
                          {s.steps.map((step, idx) => (
                            <li key={idx} className={styles.timelineItem}>
                              <span
                                className={`${styles.timelineDot} ${
                                  step.status === 'done'
                                    ? styles.dotDone
                                    : step.status === 'running'
                                    ? styles.dotRunning
                                    : styles.dotPending
                                }`}
                              />
                              {idx < s.steps.length - 1 && (
                                <span className={styles.timelineLine} />
                              )}
                              <div className={styles.stepContent}>
                                <span className={styles.stepLabel}>{step.label}</span>
                                <span className={styles.stepTime}>{step.time}</span>
                              </div>
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}

                    {s.summary && (
                      <div className={styles.statsGrid}>
                        {[
                          { label: 'Unchanged', value: s.summary.unchanged, color: '#16a34a' },
                          { label: 'Modified', value: s.summary.modified, color: '#f59e0b' },
                          { label: 'Removed', value: s.summary.removed, color: '#ef4444' },
                        ].map((stat) => (
                          <div key={stat.label} className={styles.statCard}>
                            <span className={styles.dot} style={{ background: stat.color }} />
                            <span className={styles.statLabel}>{stat.label}</span>
                            <strong className={styles.statVal}>{stat.value ?? 0}</strong>
                          </div>
                        ))}
                      </div>
                    )}
                    {!s.summary && (
                      <p className={styles.noResults}>No classification results available.</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}