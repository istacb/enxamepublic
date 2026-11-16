/**
 * API Client — Enxame Unificado (EIP-0010)
 *
 * Offline-first / same-origin por padrão: TODAS as chamadas usam URLs
 * relativas (`/api/...`), que funcionam atrás de HTTPS, reverse proxy e
 * previews (`window.location.port === ''`) sem tocar em localhost.
 *
 * Override explícito (opcional):
 *   window.ENXAME_API_BASE = 'http://lan-host:8765'
 *   ou api.setApiBase('http://lan-host:8765')
 */
let _sessionToken = null;
let _apiBase = '';

function _resolveBase() {
  if (typeof window !== 'undefined' && window.ENXAME_API_BASE) {
    return String(window.ENXAME_API_BASE).replace(/\/$/, '');
  }
  return _apiBase;
}

export function setApiBase(url) { _apiBase = String(url || '').replace(/\/$/, ''); }
// Compat legada: força base remota explícita (Juiz / kernel completo)
export function setJuizUrl(url) { setApiBase(url); }
export function setSessionToken(token) { _sessionToken = token; }
export function getSessionToken() { return _sessionToken; }
export function isStandalone() { return true; } // sempre same-origin/unificado
export function apiBase() { return _resolveBase(); }
export function urlFor(path) { return `${_resolveBase()}${path}`; }

export async function api(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (_sessionToken) headers['x-session-token'] = _sessionToken;
  const opts = { method, headers };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(urlFor(path), opts);
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).error || ''; } catch { /* noop */ }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function apiForm(path, formData) {
  const headers = {};
  if (_sessionToken) headers['x-session-token'] = _sessionToken;
  const res = await fetch(urlFor(path), { method: 'POST', headers, body: formData });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ---- Sessão ----
export async function initSession() {
  const { token } = await api('/api/session', { method: 'POST', body: {} });
  _sessionToken = token;
  return token;
}

// ---- Núcleo / cluster ----
export function fetchStatus() { return api('/api/status'); }
export function fetchModels() { return api('/api/cluster/models'); }
export function fetchDiscover() { return api('/api/cluster/discover'); }
export function pauseNode(nodeId, paused) {
  return api(`/api/node/${encodeURIComponent(nodeId)}/pause`, { method: 'POST', body: { paused } });
}
export function pauseAll(paused) { return api('/api/cluster/pause-all', { method: 'POST', body: { paused } }); }

// ---- Chat SSE ----
export async function sendChat(prompt, extra = {}) {
  return api('/api/chat', { method: 'POST', body: { prompt, ...extra } });
}
export function streamChat(taskId) {
  const token = _sessionToken ? `?session=${encodeURIComponent(_sessionToken)}` : '';
  return new EventSource(urlFor(`/api/chat/stream/${encodeURIComponent(taskId)}${token}`));
}

// ---- STE-100 ----
export function fetchSteEstado() { return api('/estado'); }
export function fetchSteSaude() { return api('/saude'); }
export function fetchSteConfig() { return api('/config'); }
export function fetchInventory() { return api('/inventario'); }

// ---- Conversas / memória / RAG (v1) ----
export function fetchConversations() { return api('/api/v1/conversations'); }
export function createConversation(title) { return api('/api/v1/conversations', { method: 'POST', body: { title } }); }
export function fetchConversation(convId) { return api(`/api/v1/conversations/${encodeURIComponent(convId)}`); }
export function deleteConversation(convId) {
  return fetch(urlFor(`/api/v1/conversations/${encodeURIComponent(convId)}`), { method: 'DELETE' })
    .then(res => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.json(); });
}
export function searchHistory(q) { return api(`/api/v1/conversations?q=${encodeURIComponent(q)}`); }
export function fetchMemory() { return api('/api/v1/memory'); }
export function saveMemoryFact(fact, category = 'manual', conversationId = null) {
  return api('/api/v1/memory', { method: 'POST', body: { fact, category, conversation_id: conversationId } });
}
export function updateUserProfile(patch) { return api('/api/v1/memory', { method: 'POST', body: patch }); }
export function deleteMemory(memId) {
  return fetch(urlFor(`/api/v1/memory/${encodeURIComponent(memId)}`), { method: 'DELETE' })
    .then(res => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.json(); });
}
export function fetchRagStatus() { return api('/api/v1/rag/status'); }
export function ragIngest(title, text, domain = 'geral') {
  return api('/api/v1/rag/ingest', { method: 'POST', body: { title, text, domain } });
}
export function ragSearch(q) { return api(`/api/v1/rag/search?q=${encodeURIComponent(q)}`); }

// ---- Papéis / máquinas / guarda ----
export function fetchRoles() { return api('/api/v1/roles'); }
export function pinRoles(nodeId, roles, adminToken = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (adminToken) headers['X-Admin-Token'] = adminToken;
  return fetch(urlFor('/api/v1/roles/pin'), {
    method: 'POST', headers, body: JSON.stringify({ node_id: nodeId, roles }),
  }).then(async res => {
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || `HTTP ${res.status}`);
    return res.json();
  });
}
export function fetchGuardianEvents() { return api('/api/v1/guardian/events'); }
export function fetchSystemStatus() { return api('/api/v1/status'); }

// ---- Voz (STT/TTS) ----
export function fetchAudioCaps() { return api('/api/v1/audio/capabilities'); }
export function transcribeAudio(blob, filename = 'gravacao.webm', language = 'pt') {
  const fd = new FormData();
  fd.append('audio', blob, filename);
  fd.append('language', language);
  return apiForm('/api/v1/audio/transcribe', fd);
}
export async function synthesizeSpeech(text, voice = 'pt-BR') {
  const res = await fetch(urlFor('/api/v1/audio/synthesize'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const ctype = res.headers.get('content-type') || '';
  if (ctype.includes('application/json')) return res.json(); // {audio_base64,...} ou {engine...}
  return { audio_blob: await res.blob(), content_type: ctype };
}

// ---- Estúdio de imagens CPU ----
export function fetchImageEngines() { return api('/api/v1/images/engines'); }
export function fetchGallery() { return api('/api/v1/images/gallery'); }
export function generateImage(payload) { return api('/api/v1/images/generate', { method: 'POST', body: payload }); }
export function fetchImageJob(jobId) { return api(`/api/v1/images/jobs/${encodeURIComponent(jobId)}`); }
export function deleteImage(jobId) {
  return fetch(urlFor(`/api/v1/images/${encodeURIComponent(jobId)}`), { method: 'DELETE' })
    .then(res => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.json(); });
}

// ---- Config runtime ----
export function fetchRuntimeConfig() { return api('/api/v1/config'); }
export function saveRuntimeConfig(cfg) { return api('/api/v1/config', { method: 'POST', body: cfg }); }
