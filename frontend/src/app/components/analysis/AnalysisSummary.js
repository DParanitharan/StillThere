import styles from './AnalysisSummary.module.css';

export default function AnalysisSummary({ results }) {
  const { added, removed, modified, unchanged, review } = results;
  const total = added + removed + modified + unchanged + review;

  const items = [
    { label: 'Added', value: added, color: '#16a34a', icon: '+' },
    { label: 'Removed', value: removed, color: '#dc2626', icon: '−' },
    { label: 'Modified', value: modified, color: '#eab308', icon: '~' },
    { label: 'Review', value: review, color: '#0891b2', icon: '?' },
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