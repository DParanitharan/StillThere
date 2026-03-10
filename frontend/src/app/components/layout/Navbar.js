'use client';

import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import styles from './Navbar.module.css';

export default function Navbar() {
  const pathname = usePathname();

  const links = [
    { href: '/dashboard', label: 'Footprint Checker' },
    { href: '/history', label: 'Past Workflows' },
    { href: '/faq', label: 'FAQs' },
  ];

  return (
    <nav className={styles.navbar}>
      <Link href="/" className={styles.brand}>
        <div className={styles.logo}>
          <Image src="/logo.png" alt="Logo" width={274} height={50} />
        </div>
      </Link>
      <ul className={styles.links}>
        {links.map((l) => (
          <li key={l.href}>
            <Link href={l.href} className={`${styles.link} ${pathname === l.href ? styles.active : ''}`}>
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}