import styles from './AnalysisSummary.module.css';

export default function AnalysisSummary({ results }) {
  const { removed = 0, modified = 0, unchanged = 0 } = results;
  const total = removed + modified + unchanged;

  const items = [
    { label: 'Removed', value: removed, color: '#dc2626', icon: '−' },
    { label: 'Modified', value: modified, color: '#eab308', icon: '~' },
    { label: 'Unchanged', value: unchanged, color: '#6b7280', icon: '=' },
  ];

  return (
    <div className={styles.container}>
      <h3 className={styles.title}>Analysis Results</h3>
      <div className={styles.total}>
        <span>Total Buildings</span>
        <span className={styles.totalValue}>{total}</span>
      </div>
      <div className={styles.breakdown}>
        {items.map((item) => (
          <div key={item.label} className={styles.item}>
            <div className={styles.itemLabel}>
              <span className={styles.icon} style={{ backgroundColor: item.color }}>{item.icon}</span>
              <span>{item.label}</span>
            </div>
            <span className={styles.itemValue}>{item.value}</span>
          </div>
        ))}
      </div>
      <button className={styles.downloadButton}>Download Report</button>
    </div>
  );
}