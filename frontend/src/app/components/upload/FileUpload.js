'use client';

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { uploadShapefile } from '@/services/api';

export default function FileUpload({ onUpload }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [fileName, setFileName] = useState(null);

  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;
    const file = acceptedFiles[0];
    setFileName(file.name);
    setUploading(true);
    setError(null);
    try {
      const data = await uploadShapefile(file);
      if (onUpload) onUpload(data);
    } catch (err) {
      console.error('Upload failed:', err);
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  }, [onUpload]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/zip': ['.zip'] },
    multiple: false,
  });

  return (
    <div
      {...getRootProps()}
      style={{
        border: `2px dashed ${isDragActive ? '#60a5fa' : 'rgba(255,255,255,0.15)'}`,
        borderRadius: '10px',
        padding: '24px 16px',
        textAlign: 'center',
        cursor: 'pointer',
        background: isDragActive ? 'rgba(59,130,246,0.08)' : 'rgba(255,255,255,0.03)',
        transition: 'all 0.2s',
      }}
    >
      <input {...getInputProps()} />
      {uploading ? (
        <p style={{ color: '#94a3b8', fontSize: 13 }}>⏳ Uploading…</p>
      ) : (
        <>
          <p style={{ color: '#cbd5e1', fontSize: 13, fontWeight: 500 }}>
            {isDragActive ? 'Drop the file here…' : 'Drop your shapefile (.zip) here'}
          </p>
          <p style={{ color: '#64748b', fontSize: 11, marginTop: 4 }}>ZIP files only</p>
        </>
      )}
      {fileName && !uploading && (
        <p style={{ color: '#4ade80', fontSize: 12, marginTop: 8 }}>✅ {fileName}</p>
      )}
      {error && (
        <p style={{ color: '#f87171', fontSize: 12, marginTop: 8 }}>❌ {error}</p>
      )}
    </div>
  );
}