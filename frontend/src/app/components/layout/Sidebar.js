import styles from './Sidebar.module.css';

export default function Sidebar({ children }) {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.content}>{children}</div>
    </aside>
  );
}