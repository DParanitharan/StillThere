'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Navbar from '@/app/components/layout/Navbar';
import styles from '../dashboard/dashboard.module.css'; // adjust if your dashboard path differs
import MapView from '@/app/components/map/MapView';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMsg('');

    try {
      const res = await fetch('/api/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
        credentials: 'include',
      });
      const data = await res.json();

      if (res.ok) {
        router.push('/'); // change to "/" if your main page is home
      } else {
        setMsg(data.error || 'Login failed');
      }
    } catch (err) {
      console.error(err);
      setMsg('Network error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      <Navbar />
      <div className={styles.body}>
        <aside className={styles.sidebar}>
          <h2 className={styles.sideTitle}>Login</h2>
          <p className={styles.sideDesc}>Sign in to continue.</p>

          <div className={styles.field}>
            <label className={styles.label}>Username</label>
            <input
              className={styles.searchInput}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
            />
          </div>

          <div className={styles.field}>
            <label className={styles.label}>Password</label>
            <input
              className={styles.searchInput}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          <button
            onClick={handleLogin}
            disabled={loading}
            className={styles.goBtn}
            style={{ marginTop: 12 }}
          >
            {loading ? 'Signing in…' : 'Login'}
          </button>

          {msg && <p style={{ marginTop: 12, color: '#fca5a5', fontSize: 13 }}>{msg}</p>}
        </aside>

        {/* Right side kept the same layout (empty map area) */}
        <div className={styles.map} />
            <MapView 
                geoData={null} 
                analysisResult={null} 
                searchPoint={{ lat: 1.3521, lng: 103.8198, label: "Singapore" }} 
            />
      </div>
    </div>
  );
}   