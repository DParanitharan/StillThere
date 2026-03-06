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
      console.log('Upload response data:', data);
      if (onUpload) {
        onUpload(data);
      }
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
        border: '2px dashed #ccc',
        borderRadius: '8px',
        padding: '20px',
        textAlign: 'center',
        cursor: 'pointer',
        backgroundColor: isDragActive ? '#f0f8ff' : '#fff',
      }}
    >
      <input {...getInputProps()} />
      {uploading ? (
        <p>Uploading...</p>
      ) : isDragActive ? (
        <p>Drop the zip file here...</p>
      ) : (
        <p>Drag & drop a shapefile (.zip) here, or click to select</p>
      )}
      {fileName && !uploading && <p style={{ color: '#666', marginTop: '8px' }}>✅ {fileName}</p>}
      {error && <p style={{ color: 'red', marginTop: '8px' }}>❌ {error}</p>}
    </div>
  );
}