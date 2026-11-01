/**
 * API Client - Centralized fetch with session token
 * Auto-detects standalone Bee mode vs full Enxame kernel
 */
let _sessionToken = null;
let _juizUrl = 'http://localhost:7700'; // Juiz for auth/session (full kernel mode)
let _isStandalone = false;
let _baseUrl = ''; // Same origin when standalone

function _detectMode() {
  // If page is served from a port other than 7700, we're in standalone Bee mode
  const port = window.location.port;
  
  if (port && port !== '7700' && port !== '') {
    _isStandalone = true;
    _baseUrl = `${window.location.protocol}//${window.location.hostname}:${port}`;
    console.log('[ENXAME] Standalone Bee mode detected, base URL:', _baseUrl);
  }
}

_detectMode();

export function setJuizUrl(url) { _juizUrl = url; _isStandalone = false; }
export function setSessionToken(token) { _sessionToken = token; }
export function getSessionToken() { return _sessionToken; }
export function isStandalone() { return _isStandalone; }

export async function api(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (_sessionToken) headers['x-session-token'] = _sessionToken;
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);
  
  // In standalone mode, use same-origin relative paths
  const url = _isStandalone ? path : `${_juizUrl}${path}`;
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// Specific endpoints
export async function initSession() {
  // In standalone mode, use Bee's /api/session (no auth needed, just generates token)
  const url = _isStandalone ? '/api/session' : `${_juizUrl}/api/session`;
  const { token } = await fetch(url, { 
    method: 'POST', 
    headers: { 'Content-Type': 'application/json' } 
  }).then(res => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  });
  _sessionToken = token;
  return token;
}

export function fetchStatus() { return api('/api/status'); }
export function fetchModels() { return api('/api/cluster/models'); }
export function fetchDiscover() { 
  const headers = { 'Content-Type': 'application/json' };
  if (_sessionToken) headers['x-session-token'] = _sessionToken;
  return fetch(_isStandalone ? '/api/cluster/discover' : `${_juizUrl}/api/cluster/discover`, { headers }).then(res => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  });
}
export function pauseNode(nodeId, paused) { return api(`/api/node/${nodeId}/pause`, { method: 'POST', body: { paused } }); }
export function pauseAll(paused) { return api('/api/cluster/pause-all', { method: 'POST', body: { paused } }); }

// Export sendChat and streamChat as named exports for chat.js
export async function sendChat(prompt) { 
  return api('/api/chat', { method: 'POST', body: { prompt } }); 
}
export function streamChat(taskId) {
  const url = _isStandalone 
    ? `/api/chat/stream/${taskId}?session=${_sessionToken}`
    : `${_juizUrl}/api/chat/stream/${taskId}?session=${_sessionToken}`;
  return new EventSource(url);
}

// All functions are exported individually above.