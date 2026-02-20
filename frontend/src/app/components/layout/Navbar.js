import Link from 'next/link';
import styles from './Navbar.module.css';

export default function Navbar() {
  return (
    <nav className={styles.navbar}>
      <div className={styles.brand}>
        <span className={styles.icon}>🗺️</span>
        <span className={styles.title}>NKBP Footprint Change Checker</span>
      </div>
      <ul className={styles.navLinks}>
        <li><Link href="/history" className={styles.navLink}>Past Workflows</Link></li>
        <li><Link href="/help" className={styles.navLink}>Help</Link></li>
      </ul>
    </nav>
  );
}