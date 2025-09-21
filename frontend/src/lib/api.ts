
export function api(path: string, init?: RequestInit) {
  const base = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
  return fetch(base + path, init);
}
