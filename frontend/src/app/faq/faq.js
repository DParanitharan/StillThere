'use client';

import { useState } from 'react';
import Navbar from '@/app/components/layout/Navbar';
import styles from './faq.module.css';

const FAQ_DATA = [
  {
    question: 'What does this application do?',
    answer:
      'Upload your geospatial file, and our system compares building footprints against current Google Satellite imagery to detect changes over time. Results are displayed on an interactive map with buildings colour coded as added, removed, and modified, along with search and filter capabilities.',
  },
  {
    question: 'What model powers the change detection?',
    answer:
      "The Footprint Change Checker uses Meta's Segment Anything Model (SAM) to detect and analyse changes in building footprints.",
  },
  {
    question: 'What file formats are supported for upload?',
    answer:
      'We accept .zip, .shp, .shx, .dbf, and .prj files. These are standard GIS file formats used for geospatial data.',
  },
  {
    question: 'How do I use the search and filter features?',
    answer:
      'After analysis, use the search bar on the map to find specific locations. The filter tab allows you to narrow results based on various criteria.',
  },
  {
    question: 'Can I save my analysis results?',
    answer:
      'Yes! After completing an analysis, click the \'Save Workflow\' button to save it. You can access all saved workflows from the \'Past Workflows\' page.',
  },
  {
    question: 'How do I use the chatbot feature?',
    answer:
      'Click the chatbot icon on the bottom-left corner of any page to open it. You can ask customised queries about your analysis results, for example: "Show all buildings within 500m that have been modified" or "How many buildings were added in this area?"',
  },
  {
    question: 'Is my data secure?',
    answer:
      'Yes, all uploaded files are processed securely and stored with encryption. We follow industry-standard security practices.',
  },
  {question: 'How do I get help?',
    answer: 'You can use the AI chatbot available on every page (bottom-left corner) or contact our support team through the Help section.',
  },
];

export default function FAQPage() {
  const [openIndex, setOpenIndex] = useState(null);

  const toggle = (i) => setOpenIndex((prev) => (prev === i ? null : i));

  return (
    <div className={styles.page}>
      <Navbar />
      <div className={styles.container}>
        <h1 className={styles.title}>Frequently Asked Questions</h1>
        <p className={styles.subtitle}>
          Everything you need to know about using the Building Footprint Change Detection tool.
        </p>

        <div className={styles.list}>
          {FAQ_DATA.map((item, i) => (
            <div key={i} className={`${styles.item} ${openIndex === i ? styles.itemOpen : ''}`}>
              <button className={styles.question} onClick={() => toggle(i)}>
                <span>{item.question}</span>
                <span className={styles.icon}>{openIndex === i ? '−' : '+'}</span>
              </button>
              {openIndex === i && (
                <div className={styles.answer}>
                  <p>{item.answer}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}