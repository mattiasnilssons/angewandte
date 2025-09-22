// frontend/src/lib/api.ts
export function api(path: string, init?: RequestInit) {
  const base = import.meta.env.VITE_API_BASE || '';
  return fetch(base + path, init);
}

// NEW: give XHR the same base URL
export function apiUrl(path: string) {
  const base = import.meta.env.VITE_API_BASE || '';
  return base + path;
}
