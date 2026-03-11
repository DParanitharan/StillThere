'use client';

import { useState, useRef, useEffect } from 'react';
import { chatQuery } from '@/services/api';
import styles from './ChatWidget.module.css';

const EXAMPLE_QUERIES = [
  "Show me all removed buildings",
  "Find buildings larger than 500 sqm",
  "How many buildings changed?",
  "Show wooden buildings",
  "Buildings taller than 10 meters",
  "Show buildings in the flood zone",
];

export default function ChatWidget({ sessionId, onMapFilter, onGeoJsonOverlay }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hello! I can query your building data using natural language. Try asking something like:",
      examples: true,
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    if (open && endRef.current) endRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [messages, open]);

  const send = async (text = null) => {
    const message = (text || input).trim();
    if (!message || loading) return;

    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: message }]);
    setLoading(true);

    try {
      const result = await chatQuery(message, sessionId);

      const assistantMsg = {
        role: 'assistant',
        content: result.explanation || 'Query executed.',
        sql: result.sql,
        mapFilter: result.map_filter,
        rowCount: result.row_count,
        isAggregate: result.is_aggregate,
        geojson: result.geojson,
        aggregateResults: result.results,
        error: result.error,
      };

      setMessages((prev) => [...prev, assistantMsg]);

      // Apply map filter if the query is about a classification category
      if (result.map_filter && onMapFilter) {
        onMapFilter(result.map_filter);
      }

      // Overlay GeoJSON results on the map (for ALL non-aggregate queries with geometry)
      if (!result.is_aggregate && result.geojson && result.geojson.features?.length > 0 && onGeoJsonOverlay) {
        onGeoJsonOverlay(result.geojson);
      }

      // For aggregate queries, clear any previous overlay
      if (result.is_aggregate && onGeoJsonOverlay) {
        onGeoJsonOverlay(null);
      }
    } catch (err) {
      const errorMsg = err.response?.data?.error || err.message || 'Failed to process query';
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `⚠️ Error: ${errorMsg}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <>
      {open && (
        <div className={styles.panel}>
          <div className={styles.header}>
            <span>🔍 Building Query Assistant</span>
            <div>
              {/* Clear overlay button */}
              <button
                className={styles.clearBtn}
                onClick={() => onGeoJsonOverlay && onGeoJsonOverlay(null)}
                title="Clear map overlay"
              >
                🗺️✕
              </button>
              <button className={styles.close} onClick={() => setOpen(false)}>✕</button>
            </div>
          </div>

          <div className={styles.msgs}>
            {messages.map((m, i) => (
              <div key={i} className={m.role === 'user' ? styles.user : styles.bot}>
                {/* Message text */}
                <p className={styles.msgText}>{m.content}</p>

                {/* Example query buttons (first message only) */}
                {m.examples && (
                  <div className={styles.examples}>
                    {EXAMPLE_QUERIES.map((q, j) => (
                      <button
                        key={j}
                        className={styles.exampleBtn}
                        onClick={() => send(q)}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                )}

                {/* Row count */}
                {m.rowCount !== undefined && m.rowCount !== null && (
                  <span className={styles.meta}>
                    📊 {m.rowCount} result{m.rowCount !== 1 ? 's' : ''}
                    {m.geojson && m.geojson.features?.length > 0 && ' — shown on map'}
                  </span>
                )}

                {/* Map filter badge */}
                {m.mapFilter && (
                  <span className={`${styles.badge} ${styles[m.mapFilter]}`}>
                    🗺️ Filtered: {m.mapFilter}
                  </span>
                )}

                {/* Aggregate table */}
                {m.isAggregate && m.aggregateResults && m.aggregateResults.length > 0 && (
                  <div className={styles.tableWrap}>
                    <table className={styles.table}>
                      <thead>
                        <tr>
                          {Object.keys(m.aggregateResults[0]).map((key) => (
                            <th key={key}>{key}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {m.aggregateResults.map((row, j) => (
                          <tr key={j}>
                            {Object.values(row).map((val, k) => (
                              <td key={k}>
                                {typeof val === 'number'
                                  ? Number(val).toLocaleString(undefined, { maximumFractionDigits: 2 })
                                  : String(val ?? '')}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Collapsible SQL */}
                {m.sql && (
                  <details className={styles.sqlDetails}>
                    <summary>View SQL</summary>
                    <pre className={styles.sqlCode}>{m.sql}</pre>
                  </details>
                )}
              </div>
            ))}

            {/* Typing indicator */}
            {loading && (
              <div className={styles.bot}>
                <div className={styles.typing}>
                  <span /><span /><span />
                </div>
              </div>
            )}

            <div ref={endRef} />
          </div>

          <div className={styles.inputRow}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about buildings..."
              className={styles.chatInput}
              disabled={loading}
            />
            <button
              className={styles.sendBtn}
              onClick={() => send()}
              disabled={loading || !input.trim()}
            >
              {loading ? '⏳' : '➤'}
            </button>
          </div>
        </div>
      )}

      {!open && <div className={styles.tooltip}>Ask about buildings</div>}
      <button className={styles.fab} onClick={() => setOpen(!open)}>
        {open ? '✕' : '💬'}
      </button>
    </>
  );
}
