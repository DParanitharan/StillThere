import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
  timeout: 1000000, // ~16 minutes — SAM segmentation is CPU-bound
});

api.interceptors.request.use((config) => {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("authToken") : null;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const uploadShapefile = async (file) => {
  const formData = new FormData();
  formData.append("file", file);
  const res = await api.post("/api/upload/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
};

export async function extractBuildings(sessionId) {
  const res = await api.post("/api/extract-buildings/", {
    session_id: sessionId,
  });
  return res.data;
}

export const runAnalysis = (uploadId) => api.post(`/api/analysis/${uploadId}/`);
export const getAnalysisResults = (analysisId) =>
  api.get(`/api/analysis/${analysisId}/results/`);

export async function pollProgress(sessionId) {
  const res = await api.get(`/api/progress/${sessionId}/`);
  return res.data;
}

export async function getClassificationResult(sessionId) {
  const res = await api.get(`/api/results/${sessionId}/`);
  return res.data;
}

export async function geocodeAddress(address) {
  const res = await api.get("/api/geocode/", { params: { address } });
  return res.data;
}

export default api;
