"use client";

import api from "@/services/api";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import styles from "./FileUpload.module.css";

export default function FileUpload({ onUpload }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [fileName, setFileName] = useState(null);

  const onDrop = useCallback(
    async (acceptedFiles) => {
      const file = acceptedFiles[0];
      if (!file) return;

      if (!file.name.toLowerCase().endsWith(".zip")) {
        setError("Please upload a ZIP file containing your shapefile.");
        return;
      }

      setError(null);
      setUploading(true);
      setFileName(file.name);

      try {
        const formData = new FormData();
        formData.append("file", file);

        const response = await api.post("/api/upload/", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });

        onUpload(file, response.data.geojson, response.data.session_id);
      } catch (err) {
        console.error("Upload error:", err);
        setError(
          err?.response?.data?.error || "Upload failed. Please try again.",
        );
      } finally {
        setUploading(false);
      }
    },
    [onUpload],
  );

  const onDropRejected = useCallback((fileRejections) => {
    console.error("Rejected files:", fileRejections);
    setError("File rejected. Please upload a valid .zip shapefile archive.");
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    accept: {
      "application/zip": [".zip"],
      "application/x-zip-compressed": [".zip"],
    },
    maxFiles: 1,
  });

  return (
    <div className={styles.container}>
      <h3 className={styles.title}>Upload Shapefile</h3>
      <div
        {...getRootProps()}
        className={`${styles.dropzone} ${isDragActive ? styles.active : ""}`}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <p>Uploading...</p>
        ) : (
          <>
            <span className={styles.uploadIcon}>📁</span>
            <p>Drag & drop a ZIP file here</p>
            <p className={styles.subtext}>or click to browse</p>
          </>
        )}
      </div>
      {fileName && !error && (
        <div className={styles.fileInfo}>✓ {fileName}</div>
      )}
      {error && <p className={styles.error}>{error}</p>}
      <p className={styles.hint}>
        Upload ZIP containing .shp, .shx, .dbf, .prj files
      </p>
    </div>
  );
}
