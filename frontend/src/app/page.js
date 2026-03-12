'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Navbar from '@/app/components/layout/Navbar';
import ChatWidget from '@/app/components/chat/ChatWidget';
import styles from './page.module.css';

export default function LandingPage() {
  const router = useRouter();

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/whoami/', { credentials: 'include' });
        if (!res.ok) router.replace('/login');
      } catch {
        router.replace('/login');
      }
    })();
  }, [router]);
  return (
    <div className={styles.page}>
      <Navbar />

      <main className={styles.hero}>
        <img src="/logo.png" width={310} height={100} style={{ marginBottom: 32 }} />

        <h1 className={styles.title}>
          Detect changes in footprint with
          <br />
          <span className={styles.highlight}>StillThere?</span>
        </h1>

        <p className={styles.subtitle}>
          Upload geospatial data and instantly visualize building footprint
          changes on an interactive map.
        </p>

        <Link href="/dashboard" className={styles.cta}>
          Start Analysis <span className={styles.arrow}>→</span>
        </Link>
      </main>

      <section className={styles.cards}>
        <div className={styles.card}>
          <div className={styles.cardIcon}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
          </div>
          <h3 className={styles.cardTitle}>Interactive Map</h3>
          <p className={styles.cardDesc}>Explore and analyze building footprint changes on an interactive map.</p>
        </div>
        <div className={styles.card}>
          <div className={styles.cardIcon}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
          </div>
          <h3 className={styles.cardTitle}>Filter Results</h3>
          <p className={styles.cardDesc}>Filter through results to obtain relevant insights quickly and efficiently.</p>
        </div>
        <div className={styles.card}>
          <div className={styles.cardIcon}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          </div>
          <h3 className={styles.cardTitle}>AI Chatbot</h3>
          <p className={styles.cardDesc}>Get immediate answers to your questions through our AI assistant.</p>
        </div>
      </section>

      <footer className={styles.footer}>
        <div className={styles.footerLeft}>
          <span className={styles.lang}>🌐 Change language</span>
        </div>
        <div className={styles.footerRight}>
          <a href="#">Terms of Use</a>
        </div>
      </footer>

      <ChatWidget />
    </div>
  );
}