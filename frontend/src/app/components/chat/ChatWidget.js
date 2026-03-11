'use client';

import { useState, useRef, useEffect } from 'react';
import styles from './ChatWidget.module.css';

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    { role: 'assistant', content: "Hello! I'm your AI assistant. How can I help you with footprint analysis?" },
  ]);
  const [input, setInput] = useState('');
  const endRef = useRef(null);

  useEffect(() => {
    if (open && endRef.current) endRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [messages, open]);

  const send = () => {
    if (!input.trim()) return;
    setMessages((p) => [...p, { role: 'user', content: input }]);
    const q = input;
    setInput('');
    setTimeout(() => {
      setMessages((p) => [...p, { role: 'assistant', content: `Looking for buildings with IoU threshold between 0.25 and 0.35...` }]);
    }, 800);
  };

  return (
    <>
      {open && (
        <div className={styles.panel}>
          <div className={styles.header}>
            <span> AI Assistant</span>
            <button className={styles.close} onClick={() => setOpen(false)}>✕</button>
          </div>
          <div className={styles.msgs}>
            {messages.map((m, i) => (
              <div key={i} className={m.role === 'user' ? styles.user : styles.bot}>{m.content}</div>
            ))}
            <div ref={endRef} />
          </div>
          <div className={styles.inputRow}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()}
              placeholder="Ask a question..."
              className={styles.chatInput}
            />
            <button className={styles.sendBtn} onClick={send}>➤</button>
          </div>
        </div>
      )}

      {!open && <div className={styles.tooltip}>Need help?</div>}
      <button className={styles.fab} onClick={() => setOpen(!open)}>
        {open ? '✕' : '💬'}
      </button>
    </>
  );
}
