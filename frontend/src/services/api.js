import axios from "axios";

const api = axios.create({
  baseURL: "", // relative — browser sends /api/... to same origin; Next.js rewrite proxies to backend
  headers: { "Content-Type": "application/json" },
  timeout: 1000000, // 5 minutes — SAM takes about 2 min
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
  const res = await fetch(`/api/progress/${sessionId}/`);
  if (!res.ok) return null;
  return res.json();
}

export default api;
