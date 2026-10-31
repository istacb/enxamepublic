/**
 * API Client - Centralized fetch with session token
 */
let _sessionToken = null;

export function setSessionToken(token) { _sessionToken = token; }
export function getSessionToken() { return _sessionToken; }

export async function api(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (_sessionToken) headers['x-session-token'] = _sessionToken;
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// Specific endpoints
export async function initSession() {
  const { token } = await api('/api/session');
  _sessionToken = token;
  return token;
}

export function fetchStatus() { return api('/api/status'); }
export function fetchModels() { return api('/api/cluster/models'); }
export function fetchDiscover() { return api('/api/cluster/discover'); }
export function pauseNode(nodeId, paused) { return api(`/api/node/${nodeId}/pause`, { method: 'POST', body: { paused } }); }
export function pauseAll(paused) { return api('/api/cluster/pause-all', { method: 'POST', body: { paused } }); }
export function sendChat(prompt) { return api('/api/chat', { method: 'POST', body: { prompt } }); }
export function streamChat(taskId) {
  const url = `/api/chat/stream/${taskId}?session=${_sessionToken}`;
  return new EventSource(url);
}