'use client';

import { useState, useRef, useEffect } from 'react';
import styles from './ChatInterface.module.css';

function getCurrentTime() {
  return new Date().toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function ChatInterface({ isOpen, onToggle, position = 'right', geoData, analysisResult }) {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    setMessages([
      {
        id: 1,
        sender: 'assistant',
        text: 'Hello! I can help you analyze building footprints and answer questions about your GIS data.',
        timestamp: getCurrentTime(),
      }
    ]);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Auto-notify user when analysis completes
  useEffect(() => {
    if (analysisResult && messages.length > 0) {
      const lastMessage = messages[messages.length - 1];

      if (!lastMessage.text.includes('analysis is complete')) {
        const notificationMessage = {
          id: Date.now(),
          sender: 'assistant',
          text: `Your analysis is complete! I found ${analysisResult.added || 0} added, ${analysisResult.removed || 0} removed, and ${analysisResult.modified || 0} modified buildings. Ask me anything about the results!`,
          timestamp: getCurrentTime(),
        };
        setMessages(prev => [...prev, notificationMessage]);
      }
    }
  }, [analysisResult, messages]);

  const handleSend = async () => {
    if (!inputValue.trim()) return;

    const userMessage = {
      id: Date.now(),
      sender: 'user',
      text: inputValue,
      timestamp: getCurrentTime(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsTyping(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: inputValue,
          conversationHistory: messages,
          context: {
            hasGeoData: !!geoData,
            analysisResult: analysisResult,
          }
        }),
      });

      const data = await response.json();

      const assistantMessage = {
        id: Date.now() + 1,
        sender: 'assistant',
        text: data.message || 'Sorry, I encountered an error. Please try again.',
        timestamp: getCurrentTime(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        id: Date.now() + 1,
        sender: 'assistant',
        text: 'Sorry, I encountered a connection error. Please try again.',
        timestamp: getCurrentTime(),
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleQuickAction = (text) => {
    setInputValue(text);
  };

  const clearChat = () => {
    setMessages([
      {
        id: 1,
        sender: 'assistant',
        text: 'Chat cleared. How can I help you?',
        timestamp: getCurrentTime(),
      }
    ]);
  };

  return (
    <>
      <button
        className={`${styles.toggleButton} ${styles[position]} ${isOpen ? styles.open : ''}`}
        onClick={onToggle}
        aria-label="Toggle chat"
        title={isOpen ? 'Close chat' : 'Open AI assistant'}
      >
        {isOpen ? '✕' : '💬'}
      </button>

      <div className={`${styles.chatPanel} ${styles[position]} ${isOpen ? styles.open : ''}`}>
        <div className={styles.chatHeader}>
          <div className={styles.headerContent}>
            <span className={styles.headerIcon}>🤖</span>
            <div>
              <h3 className={styles.headerTitle}>GIS Assistant</h3>
              <p className={styles.headerSubtitle}>AI-powered analysis help</p>
            </div>
          </div>
          <div className={styles.headerActions}>
            <button
              className={styles.clearButton}
              onClick={clearChat}
              title="Clear chat"
            >
              🗑️
            </button>
            <button className={styles.closeButton} onClick={onToggle}>✕</button>
          </div>
        </div>

        <div className={styles.messagesContainer}>
          {messages.map((message) => (
            <div
              key={message.id}
              className={`${styles.message} ${styles[message.sender]}`}
            >
              <div className={styles.messageContent}>
                <p>{message.text}</p>
                <span className={styles.timestamp}>
                  {message.timestamp}
                </span>
              </div>
            </div>
          ))}

          {isTyping && (
            <div className={`${styles.message} ${styles.assistant}`}>
              <div className={styles.messageContent}>
                <div className={styles.typingIndicator}>
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className={styles.quickActions}>
          <button
            className={styles.quickButton}
            onClick={() => handleQuickAction('How many buildings changed?')}
          >
            📊 Summary
          </button>
          <button
            className={styles.quickButton}
            onClick={() => handleQuickAction('Explain the analysis results in detail')}
          >
            📋 Explain
          </button>
          <button
            className={styles.quickButton}
            onClick={() => handleQuickAction('What should I focus on?')}
          >
            🎯 Focus Areas
          </button>
        </div>

        <div className={styles.inputContainer}>
          <textarea
            className={styles.input}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about your GIS data..."
            rows={1}
          />
          <button
            className={styles.sendButton}
            onClick={handleSend}
            disabled={!inputValue.trim() || isTyping}
          >
            <span className={styles.sendIcon}>📤</span>
          </button>
        </div>
      </div>
    </>
  );
}