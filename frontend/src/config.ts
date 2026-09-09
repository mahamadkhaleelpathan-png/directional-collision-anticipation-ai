// Centralized backend connection config for the AI Collision Anticipation app.
//
// Local development (no env vars): falls back to same-origin `/api` and `/ws`,
// which the Vite dev server proxies to http://127.0.0.1:8000.
//
// Production (Vercel frontend + separate backend): set VITE_API_URL and
// VITE_WS_URL at build time (Vercel project env) to point at the deployed
// FastAPI backend, e.g. VITE_API_URL=https://api.example.com and
// VITE_WS_URL=wss://api.example.com.

const strip = (value: string | undefined): string =>
  (value ?? '').trim().replace(/\/+$/, '');

const API_URL = strip(import.meta.env.VITE_API_URL);
const WS_URL = strip(import.meta.env.VITE_WS_URL);

/** Base URL for REST calls. `/api` prefix is appended here once. */
export const API_BASE = API_URL ? `${API_URL}/api` : '/api';

/** Absolute WebSocket URL for a server path (e.g. `/ws/jobs/{jobId}`). */
export function wsUrl(path: string): string {
  if (WS_URL) return `${WS_URL}${path}`;
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}${path}`;
}