'use client';

import { useState } from 'react';
import Navbar from '@/app/components/layout/Navbar';
import styles from './faq.module.css';

const FAQ_DATA = [
  {
    question: 'What does this application do?',
    answer:
      'This tool detects and classifies changes in building footprints using satellite or aerial imagery. Upload a geospatial file (GeoJSON, GeoTIFF, etc.) and the system will identify buildings that are unchanged, modified, or removed.',
  },
  {
    question: 'What file formats are supported for upload?',
    answer:
      'We currently support GeoJSON, GeoTIFF (.tif), and Shapefiles (.shp with accompanying .dbf/.shx). Make sure your file contains valid geospatial data with coordinate reference information.',
  },
  {
    question: 'How does the building classification work?',
    answer:
      'After uploading imagery, the backend uses the Segment Anything Model (SAM) to detect building footprints. These detected footprints are then compared against known building data to classify each as unchanged, modified, or removed.',
  },
  {
    question: 'What do the classification statuses mean?',
    answer:
      'Unchanged (green): The building footprint matches the reference data. Modified (amber): The footprint geometry has changed significantly. Removed (red): A building in the reference data was not detected in the new imagery.',
  },
  {
    question: 'How accurate are the results?',
    answer:
      'Accuracy depends on imagery resolution, cloud cover, and the quality of reference data. The model works best with high-resolution satellite imagery (< 1 m/pixel). Always review results manually for critical decision-making.',
  },
  {
    question: 'Can I search for a specific address on the map?',
    answer:
      'Yes. Use the search bar in the dashboard sidebar to enter an address. The map will pan to that location and place a marker. This uses a geocoding API to resolve addresses to coordinates.',
  },
  {
    question: 'Where is my analysis history stored?',
    answer:
      'Each analysis session is stored on the server with its session ID, uploaded file, and classification results. You can view past sessions on the History page.',
  },
  {
    question: 'How do I use the chat assistant?',
    answer:
      'Click the chat icon in the bottom-right corner of the dashboard. You can ask the assistant questions about your analysis results, building change statistics, or how to use the tool.',
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