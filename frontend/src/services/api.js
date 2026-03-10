import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL || "",
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("authToken") : null;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.error ||
      error.response?.data?.detail ||
      error.message ||
      "An unexpected error occurred.";
    return Promise.reject(new Error(message));
  },
);

export const uploadShapefile = (formData) =>
  api.post("/api/upload/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

export const runAnalysis = (uploadId) => api.post(`/api/analysis/${uploadId}/`);
export const getAnalysisResults = (analysisId) =>
  api.get(`/api/analysis/${analysisId}/results/`);

export default api;
