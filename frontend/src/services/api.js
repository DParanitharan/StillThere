import axios from 'axios';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('authToken') : null;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const uploadShapefile = (formData) => 
  api.post('/api/upload/', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const runAnalysis = (uploadId) => api.post(`/api/analysis/${uploadId}/`);
export const getAnalysisResults = (analysisId) => api.get(`/api/analysis/${analysisId}/results/`);

export default api;