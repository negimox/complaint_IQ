import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 90_000, // 90s to accommodate cloud cold starts (e.g. Render free tier)
});

// Response interceptor — normalize and enrich error messages
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.code === 'ECONNABORTED' || err.message?.toLowerCase().includes('timeout')) {
      return Promise.reject(
        new Error(
          `Request timed out connecting to ${BASE_URL}. If the backend is waking up from idle (e.g. Render free tier cold start), please wait 30-60 seconds and retry.`
        )
      );
    }
    if (err.code === 'ERR_NETWORK' || !err.response) {
      return Promise.reject(
        new Error(
          `Unable to connect to backend server at ${BASE_URL}. Ensure the backend is active, healthy, and allowing CORS requests.`
        )
      );
    }
    const status = err.response.status;
    const data = err.response.data;
    let message = 'An unexpected server error occurred';

    if (typeof data?.detail === 'string') {
      message = data.detail;
    } else if (Array.isArray(data?.detail)) {
      message = data.detail.map((d: any) => d.msg ?? JSON.stringify(d)).join(', ');
    } else if (typeof data?.message === 'string') {
      message = data.message;
    } else if (typeof data === 'string' && data.length > 0) {
      message = data;
    } else if (status >= 500) {
      message = `Server Error (${status}): The backend encountered an internal error. Check the FastAPI server logs.`;
    } else if (err.message) {
      message = err.message;
    }

    return Promise.reject(new Error(message));
  }
);
