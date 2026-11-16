/**
 * ENXAME Colmeia Soberana — App principal (EIP-0010)
 * 5 abas, Ctrl+K no histórico FTS5, polling, telemetria STE-100.
 */
import { store } from './store.js';
import * as api from './api.js';
import { audio } from './audio.js';
import { HiveCanvas } from './hive-canvas.js';
import { ChatController } from './chat.js';
import { SidebarController } from './sidebar.js';

let hiveCanvas = null;
let chatController = null;
let sidebarController = null;
let statusInterval = null;
let modelsInterval = null;
let wsClient = null;

window.hiveCanvas = null;

const TABS = ['colmeia', 'controle', 'galeria', 'inventario', 'memoria'];

async function init() {
  console.log('[ENXAME] Starting Colmeia Soberana…');

  await audio.init();

  chatController = new ChatController();
  sidebarController = new SidebarController();
  sidebarController.onNodesChanged = (nodes) => chatController.setTargetNodes(nodes);
  hiveCanvas = new HiveCanvas();
  hiveCanvas.init();
  window.hiveCanvas = hiveCanvas;

  bindGlobalEvents();
  bindTabs();
  await chatController.voice.init();

  try {
    await api.initSession();
    chatController.setConnected(true);
    await loadInitialData();
    startPolling();
    connectWebSocket();
  } catch (err) {
    console.error('[ENXAME] Session init failed:', err);
    chatController.setConnected(false);
    chatController._addMessage('Falha ao conectar ao backend. Verifique se o serviço está rodando.', 'system err');
  }

  console.log('[ENXAME] Ready');
}

// ---------------------------------------------------------------- tabs
function bindTabs() {
  TABS.forEach(name => {
    document.getElementById(`tab-${name}`)?.addEventListener('click', () => switchTab(name));
  });
}

function switchTab(name) {
  TABS.forEach(n => {
    const tab = document.getElementById(`tab-${n}`);
    const panel = document.getElementById(`panel-${n}`);
    const active = n === name;
    tab?.classList.toggle('active', active);
    tab?.setAttribute('aria-selected', active);
    if (panel) panel.hidden = !active;
  });
  if (name === 'controle') refreshControlTab();
  if (name === 'galeria') refreshGalleryTab();
  if (name === 'inventario') refreshInventoryTab();
  if (name === 'memoria') refreshMemoryTab();
}

// ---------------------------------------------------------------- events
function bindGlobalEvents() {
  document.getElementById('discover-btn').addEventListener('click', async () => {
    const btn = document.getElementById('discover-btn');
    btn.disabled = true;
    btn.textContent = 'Descobrindo…';
    try {
      const data = await api.fetchDiscover();
      const peers = data.peers || data.nodes || [];
      chatController._addMessage(`Descoberta concluída: ${peers.length} peer(s) encontrado(s)`, 'system');
    } catch (err) {
      chatController._addMessage(`Erro na descoberta: ${err.message}`, 'system err');
    } finally {
      btn.disabled = false;
      btn.textContent = 'DESCOBRIR REDE';
    }
  });

  document.getElementById('pause-all').addEventListener('click', async () => {
    const btn = document.getElementById('pause-all');
    const newState = !store.pausedAll;
    try {
      await api.pauseAll(newState);
      store.pausedAll = newState;
      btn.classList.toggle('active', newState);
      btn.setAttribute('aria-pressed', newState);
      audio.play(newState ? 'error' : 'click');
      sidebarController.update();
    } catch (err) {
      console.error('Pause all error:', err);
    }
  });

  // ---- settings modal ----
  const modal = document.getElementById('settings-modal');
  const openSettings = () => { modal.classList.add('open'); loadSettings(); };
  const closeSettings = () => modal.classList.remove('open');
  document.getElementById('settings-btn').addEventListener('click', openSettings);
  document.getElementById('settings-close').addEventListener('click', closeSettings);
  modal.addEventListener('click', (e) => { if (e.target === e.currentTarget) closeSettings(); });

  async function loadSettings() {
    try {
      const cfg = await api.fetchSteConfig();
      document.getElementById('setting-offline').checked = !!cfg.offline_mode;
      document.getElementById('setting-web-fallback').checked = cfg.allow_web !== false;
      const conf = cfg.confidence_threshold ?? cfg.confidence_threshold_enxame ?? 0.7;
      document.getElementById('setting-confidence').value = conf;
      document.getElementById('confidence-value').textContent = Number(conf).toFixed(2);
      const modelSelect = document.getElementById('setting-model');
      const currentModel = cfg.model || cfg.preferred_model || 'auto';
      const { models } = await api.fetchModels().catch(() => ({ models: [] }));
      modelSelect.innerHTML = '<option value="auto">Automático (Recomendado)</option>' +
        (models || []).map(m => `<option value="${m.name}" ${m.name === currentModel ? 'selected' : ''}>${m.name}</option>`).join('');
      const savedToken = localStorage.getItem('enxame_admin_token') || '';
      document.getElementById('setting-admin-token').value = savedToken;
    } catch (err) {
      console.warn('Failed to load settings:', err);
    }
  }

  document.getElementById('setting-confidence').addEventListener('input', (e) => {
    document.getElementById('confidence-value').textContent = parseFloat(e.target.value).toFixed(2);
  });

  document.getElementById('setting-hex-size').addEventListener('input', (e) => {
    document.getElementById('hex-size-value').textContent = e.target.value + 'px';
    if (window.hiveCanvas && window.hiveCanvas.grid) {
      window.hiveCanvas.grid.hexSize = parseInt(e.target.value);
      window.hiveCanvas._bgDirty = true;
    }
  });

  document.getElementById('settings-save').addEventListener('click', async () => {
    const config = {
      offline_mode: document.getElementById('setting-offline').checked,
      allow_web: document.getElementById('setting-web-fallback').checked,
      confidence_threshold: parseFloat(document.getElementById('setting-confidence').value),
      model: document.getElementById('setting-model').value,
    };
    const adminToken = document.getElementById('setting-admin-token').value.trim();
    if (adminToken) localStorage.setItem('enxame_admin_token', adminToken);
    else localStorage.removeItem('enxame_admin_token');
    audio.setEnabled(document.getElementById('setting-sounds').checked);
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (adminToken) headers['X-Admin-Token'] = adminToken;
      const res = await fetch(api.urlFor('/api/v1/settings'), { method: 'POST', headers, body: JSON.stringify(config) });
      if (res.ok) {
        chatController._addMessage('Configurações salvas', 'system');
        closeSettings();
      } else {
        const err = await res.json().catch(() => ({}));
        chatController._addMessage(`Erro ao salvar: ${err.error || res.status} (admin?)`, 'system err');
      }
    } catch (err) {
      chatController._addMessage(`Erro: ${err.message}`, 'system err');
    }
  });

  document.getElementById('settings-reset').addEventListener('click', () => {
    document.getElementById('setting-offline').checked = false;
    document.getElementById('setting-web-fallback').checked = true;
    document.getElementById('setting-confidence').value = 0.7;
    document.getElementById('confidence-value').textContent = '0.70';
    document.getElementById('setting-model').value = 'auto';
    document.getElementById('setting-hex-size').value = 28;
    document.getElementById('hex-size-value').textContent = '28px';
    document.getElementById('setting-animations').checked = true;
    document.getElementById('setting-sounds').checked = true;
  });

  // ---- global search: RAG + histórico ----
  document.getElementById('global-search').addEventListener('keydown', async (e) => {
    if (e.key !== 'Enter') return;
    const query = e.target.value.trim();
    if (!query) return;
    switchTab('memoria');
    const hs = document.getElementById('history-search');
    if (hs) { hs.value = query; hs.dispatchEvent(new Event('input')); }
  });

  // ---- keyboard shortcuts ----
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeSettings();
      if (document.activeElement !== document.getElementById('msg')) chatController.clear();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      switchTab('memoria');
      document.getElementById('history-search')?.focus();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && document.activeElement === document.getElementById('msg')) {
      chatController.send();
    }
  });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopPolling();
    else startPolling();
  });

  bindControlTab();
  bindGalleryTab();
  bindInventoryTab();
  bindMemoryTab();
}

// ---------------------------------------------------------------- data
async function loadInitialData() {
  try {
    const [status, models] = await Promise.all([
      api.fetchStatus(),
      api.fetchModels().catch(() => ({ models: [], best: null }))
    ]);

    store.nodes = status.agents || [];
    store.stats = {
      tasks: status.tasks_total || 0,
      calls: 0,
      nacks: 0,
      peers: (status.agents || []).length
    };
    const alias = status.alias || status.node;
    store.clusterLabel = `cluster: ${alias} · ${(status.agents || []).length} nó${(status.agents || []).length !== 1 ? 's' : ''}`;
    store.models = models.models || [];
    store.ollamaStatus = status.ollama_online === false ? 'none' : (models.models?.length ? 'ok' : 'none');

    sidebarController.update();
    updateOllamaStatus(store.ollamaStatus);
    updateTierBadge(status.hardware || (status.agents || [])[0]);
    if (status.hardware?.pacing_notice) chatController.showPacing(status.hardware.pacing_notice, status.hardware.tier_label);
    chatController.setConnected(true);

    api.fetchConversations()
      .then(d => chatController.setConversations(d.conversations || []))
      .catch(() => {});
  } catch (err) {
    console.error('[ENXAME] Initial load failed:', err);
    chatController.setConnected(false);
    chatController._addMessage(`Erro ao carregar dados: ${err.message}`, 'system err');
  }
}

function startPolling() {
  if (statusInterval) return;

  statusInterval = setInterval(async () => {
    try {
      const status = await api.fetchStatus();
      store.nodes = status.agents || [];
      store.stats.tasks = status.tasks_total || 0;
      store.stats.peers = (status.agents || []).length;
      const alias = status.alias || status.node;
      store.clusterLabel = `cluster: ${alias} · ${(status.agents || []).length} nó${(status.agents || []).length !== 1 ? 's' : ''}`;
      sidebarController.update();
      updateTierBadge(status.hardware || (status.agents || [])[0]);
      chatController.setConnected(true);
    } catch (err) {
      console.warn('[ENXAME] Status poll failed:', err);
      chatController.setConnected(false);
    }
  }, 3000);

  modelsInterval = setInterval(async () => {
    try {
      const { models } = await api.fetchModels();
      store.models = models || [];
      store.ollamaStatus = models?.length ? 'ok' : 'none';
      sidebarController.update();
      updateOllamaStatus(store.ollamaStatus);
    } catch (err) {
      console.warn('[ENXAME] Models poll failed:', err);
    }
  }, 15000);
}

function stopPolling() {
  if (statusInterval) { clearInterval(statusInterval); statusInterval = null; }
  if (modelsInterval) { clearInterval(modelsInterval); modelsInterval = null; }
}

function updateOllamaStatus(status) {
  const el = document.getElementById('ollama-status');
  if (!el) return;
  el.className = 'status-badge';
  if (status === 'ok') { el.classList.add('ok'); el.textContent = 'Ollama: ✓'; }
  else { el.classList.add('err'); el.textContent = 'Ollama: ✗'; }
}

function updateTierBadge(hw) {
  const el = document.getElementById('tier-badge');
  if (!el || !hw) return;
  el.textContent = `CPU: ${hw.tier_label || hw.tier || '—'}`;
  el.classList.remove('ok', 'warn');
  el.classList.add(hw.tier === 'legado' ? 'warn' : 'ok');
  el.title = hw.pacing_notice || hw.cpu_model || '';
}

function connectWebSocket() {
  try {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    wsClient = new WebSocket(`${proto}://${location.host}/ws`);
    wsClient.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'image_job' && !document.getElementById('panel-galeria').hidden) {
          refreshGalleryTab();
        }
        if (msg.type === 'guardian_event' && !document.getElementById('panel-controle').hidden) {
          refreshGuardian();
        }
      } catch { /* noop */ }
    };
    wsClient.onclose = () => setTimeout(connectWebSocket, 8000);
  } catch { /* WS opcional */ }
}

function esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
export function adminToken() { return localStorage.getItem('enxame_admin_token') || ''; }

// ---------------------------------------------------------------- aba Controle
function bindControlTab() {
  document.getElementById('probe-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const alias = document.getElementById('probe-alias').value.trim();
    const mode = document.getElementById('probe-mode').value;
    const endpoint = document.getElementById('probe-endpoint').value.trim();
    if (!endpoint) return;
    const btn = document.getElementById('probe-btn');
    btn.disabled = true; btn.textContent = 'SONDANDO…';
    try {
      const headers = { 'Content-Type': 'application/json' };
      const tok = adminToken();
      if (tok) headers['X-Admin-Token'] = tok;
      const res = await fetch(api.urlFor('/api/v1/machines/probe'), {
        method: 'POST', headers,
        body: JSON.stringify(mode === 'ssh'
          ? { alias, mode, ssh_host: endpoint }
          : { alias, mode, endpoint }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      await refreshInventoryTab();
    } catch (err) {
      document.getElementById('machines-list').innerHTML =
        `<div class="empty-state">Falha na sonda: ${esc(err.message)}</div>`;
    } finally {
      btn.disabled = false; btn.textContent = 'SONDAR';
    }
  });
}

async function refreshControlTab() {
  await Promise.all([refreshRoles(), refreshGuardian(), refreshMachinesCard()]);
}

async function refreshRoles() {
  const tbody = document.getElementById('roles-tbody');
  try {
    const data = await api.fetchRoles();
    const pins = data.pins || {};
    tbody.innerHTML = (data.nodes || []).map(n => {
      const pinned = pins[n.node_id];
      const roles = (n.roles || []).join(', ');
      const options = ['auto', 'rainha', 'juiz', 'bibliotecario', 'guarda', 'worker_general', 'worker_artist']
        .map(r => `<option value="${r}" ${pinned === r || (pinned?.[0] === r) ? 'selected' : ''}>${r}</option>`).join('');
      return `<tr>
        <td>${esc(n.alias || n.node_id)}${n.is_local ? ' <span class="node-local">LOCAL</span>' : ''}</td>
        <td>${esc(n.hardware_tier_label || n.hardware_tier || '—')}</td>
        <td>${esc(roles)}${n.pinned ? ' 📌' : ''}</td>
        <td><select class="role-pin" data-node="${esc(n.node_id)}" aria-label="Fixar papel">${options}</select></td>
      </tr>`;
    }).join('') || '<tr><td colspan="4">Sem nós.</td></tr>';
    tbody.querySelectorAll('.role-pin').forEach(sel => {
      sel.addEventListener('change', async () => {
        try {
          await api.pinRoles(sel.dataset.node, sel.value === 'auto' ? [] : [sel.value], adminToken() || null);
          refreshRoles();
        } catch (err) {
          chatController._addMessage(`Fixação de papel negada: ${err.message} (token admin?)`, 'system err');
        }
      });
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4">Falha: ${esc(err.message)}</td></tr>`;
  }
}

async function refreshGuardian() {
  try {
    const data = await api.fetchGuardianEvents();
    const stats = data.stats || {};
    document.getElementById('guardian-stats').textContent =
      `Total ${stats.total ?? 0} · ALLOW ${stats.allowed ?? 0} · CONTAIN ${stats.contained ?? 0} · BLOCK ${stats.blocked ?? 0}`;
    document.getElementById('guardian-events').innerHTML =
      (data.events || []).map(ev =>
        `<li><span class="ev-action ev-${esc(ev.action)}">${esc(ev.action)}</span>
         <span class="ev-reason">${esc((ev.reasons || []).join('; ') || ev.reason || '')}</span>
         <span class="ev-meta">${esc(ev.client_key || ev.client_id || '')} · ${new Date((ev.timestamp || 0) * 1000).toLocaleString()}</span></li>`
      ).join('') || '<li class="empty-state">Nenhum evento registrado.</li>';
  } catch (err) {
    document.getElementById('guardian-stats').textContent = `Falha: ${err.message}`;
  }
}

async function refreshMachinesCard() {
  try {
    const inv = await api.fetchInventory();
    const remotes = (inv.machines || []).filter(m => !m.is_local && m.transport && !String(m.transport).startsWith('lan:'));
    document.getElementById('machines-list').innerHTML = remotes.map(m =>
      `<div class="mini-card"><strong>${esc(m.alias)}</strong>
       <span>${esc(m.transport || '')}</span>
       <span class="status-badge ${m.status === 'online' ? 'ok' : 'err'}">${esc(m.status)}</span></div>`
    ).join('') || '<div class="empty-state">Nenhuma máquina remota cadastrada.</div>';
  } catch { /* inventário opcional aqui */ }
}

// ---------------------------------------------------------------- aba Galeria
function bindGalleryTab() {
  document.getElementById('img-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const prompt = document.getElementById('img-prompt').value.trim();
    if (!prompt) return;
    const [width, height] = document.getElementById('img-size').value.split('x').map(Number);
    const status = document.getElementById('img-status');
    status.textContent = '⏳ Na fila da CPU… (1 job por vez)';
    try {
      const job = await api.generateImage({
        prompt,
        engine: document.getElementById('img-engine').value,
        width, height,
        steps: parseInt(document.getElementById('img-steps').value) || 4,
      });
      status.textContent = `🎨 Gerando (${job.job_id})… acompanhe na galeria.`;
      document.getElementById('img-prompt').value = '';
      const poll = setInterval(async () => {
        try {
          const cur = await api.fetchImageJob(job.job_id);
          if (cur.status === 'completed' || cur.status === 'failed') {
            clearInterval(poll);
            status.textContent = cur.status === 'completed'
              ? `✅ Imagem pronta em ${cur.width}×${cur.height} (${cur.provenance?.engine || 'cpu'}).`
              : `❌ Falha: ${cur.error || 'desconhecida'}`;
            refreshGalleryTab();
          } else {
            status.textContent = `🎨 ${cur.stage_text || cur.status} (${cur.progress_pct || 0}%)`;
          }
        } catch { clearInterval(poll); }
      }, 1200);
    } catch (err) {
      status.textContent = `❌ ${err.message}`;
    }
  });
}

async function refreshGalleryTab() {
  try {
    const engines = await api.fetchImageEngines();
    const sel = document.getElementById('img-engine');
    const cur = sel.value || 'auto';
    sel.innerHTML = '<option value="auto">Motor: auto</option>' +
      (engines.engines || []).map(e =>
        `<option value="${esc(e.id)}" ${e.available ? '' : 'disabled'}>${esc(e.label)}${e.available ? '' : ' (indisponível)'}</option>`
      ).join('');
    sel.value = cur;
    document.getElementById('img-engines-hint').textContent =
      `Primário: ${engines.primary_engine} · ~${engines.estimated_seconds || '?'}s por imagem em CPU (${engines.hardware_tier || ''}).`;
  } catch { /* noop */ }
  try {
    const gal = await api.fetchGallery();
    const grid = document.getElementById('gallery-grid');
    grid.innerHTML = (gal.images || []).map(img => `
      <figure class="gallery-item" data-job="${esc(img.job_id)}">
        ${img.image_url ? `<img src="${esc(img.image_url)}" alt="${esc(img.prompt || '')}" loading="lazy">` : `<div class="gallery-pending">${esc(img.stage_text || img.status)}</div>`}
        <figcaption title="${esc(img.prompt || '')}">${esc((img.prompt || '').slice(0, 60))}</figcaption>
        <button class="gallery-del" data-job="${esc(img.job_id)}" aria-label="Excluir">✕</button>
      </figure>`).join('') || '<div class="empty-state">Galeria vazia. Gere a primeira imagem acima ou via <code>/img …</code> no chat.</div>';
    grid.querySelectorAll('.gallery-del').forEach(btn => {
      btn.addEventListener('click', async () => {
        try { await api.deleteImage(btn.dataset.job); refreshGalleryTab(); }
        catch (err) { console.warn('delete image:', err); }
      });
    });
  } catch (err) {
    document.getElementById('gallery-grid').innerHTML = `<div class="empty-state">Falha: ${esc(err.message)}</div>`;
  }
}

// ---------------------------------------------------------------- aba Inventário
function bindInventoryTab() {
  document.getElementById('inventory-refresh')?.addEventListener('click', () => refreshInventoryTab());
}

async function refreshInventoryTab() {
  const tbody = document.getElementById('inventory-tbody');
  try {
    const inv = await api.fetchInventory();
    document.getElementById('inventory-updated').textContent =
      `Atualizado em ${new Date((inv.updated_at || Date.now() / 1000) * 1000).toLocaleString()} · ${inv.total_machines || 0} máquina(s)`;
    tbody.innerHTML = (inv.machines || []).map(m => `
      <tr>
        <td>${esc(m.alias || m.node_id)}${m.is_local ? ' <span class="node-local">LOCAL</span>' : ''}<br><small>${esc(m.transport || '')}</small></td>
        <td>${esc(m.os || '—')}<br><small>${esc(m.arch || '')}</small></td>
        <td><small>${esc(m.cpu_model || '—')}</small><br><small>${m.cores_physical ?? '?'}C/${m.cores_logical ?? '?'}T${m.has_avx2 ? ' · AVX2' : ''}</small></td>
        <td>${m.ram_free_gb >= 0 ? Number(m.ram_free_gb).toFixed(1) + ' GB' : '—'}</td>
        <td>${m.disk_free_gb >= 0 ? Number(m.disk_free_gb).toFixed(1) + ' GB' : '—'}</td>
        <td>${esc(m.hardware_tier_label || m.hardware_tier || '—')}</td>
        <td>${m.est_tokens_per_sec ?? '—'}</td>
        <td><span class="status-badge ${m.health_ok ? 'ok' : 'err'}">${m.health_ok ? 'OK' : 'FALHA'}</span>${(m.warnings || []).length ? `<br><small>${esc(m.warnings.join('; '))}</small>` : ''}</td>
        <td><small>${esc((m.roles || []).join(', '))}</small></td>
      </tr>`).join('') || '<tr><td colspan="9">Sem máquinas.</td></tr>';
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9">Falha: ${esc(err.message)}</td></tr>`;
  }
  try {
    const saude = await api.fetchSteSaude();
    document.getElementById('health-cards').innerHTML =
      `<div class="mini-card"><strong>Local: ${saude.ok ? 'SAUDÁVEL' : 'ATENÇÃO'}</strong>
       <span>CPU ${saude.cpu_pct ?? '?'}% · RAM ${saude.ram_pct ?? '?'}% · Disco ${saude.disco_pct ?? '?'}%</span>
       <span>${(saude.avisos || []).join('; ') || 'sem avisos'}</span></div>`;
  } catch { /* noop */ }
}

// ---------------------------------------------------------------- aba Memória
function bindMemoryTab() {
  let debounce = null;
  document.getElementById('history-search')?.addEventListener('input', (e) => {
    clearTimeout(debounce);
    debounce = setTimeout(() => searchHistory(e.target.value.trim()), 220);
  });
  document.getElementById('memory-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fact = document.getElementById('memory-fact').value.trim();
    if (!fact) return;
    try {
      await api.saveMemoryFact(fact, 'manual', chatController.convSelect?.value || null);
      document.getElementById('memory-fact').value = '';
      refreshMemoryTab();
    } catch (err) {
      console.warn('save memory:', err);
    }
  });
  document.getElementById('rag-search-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = document.getElementById('rag-search').value.trim();
    if (!q) return;
    try {
      const res = await api.ragSearch(q);
      document.getElementById('rag-results').innerHTML =
        (res.hits || []).map(h =>
          `<li><strong>${esc(h.title || h.source || '')}</strong> <small>conf ${h.confidence ?? '?'}</small><br><small>${esc((h.text || h.content || '').slice(0, 220))}</small></li>`
        ).join('') || '<li class="empty-state">Sem resultados.</li>';
    } catch (err) {
      document.getElementById('rag-results').innerHTML = `<li class="empty-state">Falha: ${esc(err.message)}</li>`;
    }
  });
  document.getElementById('rag-ingest-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const title = document.getElementById('rag-ingest-title').value.trim() || 'Nota Local';
    const text = document.getElementById('rag-ingest-text').value.trim();
    if (!text) return;
    try {
      await api.ragIngest(title, text);
      document.getElementById('rag-ingest-title').value = '';
      document.getElementById('rag-ingest-text').value = '';
      refreshMemoryTab();
    } catch (err) {
      console.warn('rag ingest:', err);
    }
  });
}

async function searchHistory(q) {
  const box = document.getElementById('history-results');
  if (!q) { box.innerHTML = ''; return; }
  try {
    const res = await api.searchHistory(q);
    box.innerHTML = (res.results || []).map(r =>
      `<li><strong>${esc(r.conversation_title || r.conversation_id || '')}</strong>
       <span class="ev-meta">${esc(r.role || '')}</span><br><small>${esc(r.snippet || '')}</small></li>`
    ).join('') || '<li class="empty-state">Nada encontrado no histórico.</li>';
  } catch (err) {
    box.innerHTML = `<li class="empty-state">Falha: ${esc(err.message)}</li>`;
  }
}

async function refreshMemoryTab() {
  try {
    const convs = await api.fetchConversations();
    chatController.setConversations(convs.conversations || []);
    document.getElementById('memory-conversations').innerHTML =
      (convs.conversations || []).map(c =>
        `<li><strong>${esc(c.title || 'Conversa')}</strong> <small>${c.message_count || 0} msgs</small>
         <button class="btn btn-ghost btn-sm mem-open" data-conv="${esc(c.id)}">ABRIR</button></li>`
      ).join('') || '<li class="empty-state">Nenhuma conversa salva.</li>';
    document.querySelectorAll('.mem-open').forEach(btn => {
      btn.addEventListener('click', () => {
        chatController.convSelect.value = btn.dataset.conv;
        chatController.clear(false);
        switchTab('colmeia');
        api.fetchConversation(btn.dataset.conv).then(conv => {
          (conv.messages || []).forEach(m => {
            if (m.role === 'user') chatController._addMessage(m.content, 'user');
            else if (m.role === 'assistant') chatController._addMessage(m.content, 'assistant', conv.id, null, m.provenance?.model);
          });
        }).catch(() => {});
      });
    });
  } catch { /* noop */ }
  try {
    const mem = await api.fetchMemory();
    const prof = mem.profile || {};
    document.getElementById('memory-profile').textContent =
      `Interações ${prof.interaction_count ?? 0} · Verbosidade ${prof.verbosity ?? '—'} · Idioma ${prof.language ?? 'pt-BR'}`;
    document.getElementById('memory-list').innerHTML =
      (mem.memories || []).map(m =>
        `<li><strong>[${esc(m.category || 'geral')}]</strong> ${esc(m.content || m.fact || '')}
         <button class="btn btn-ghost btn-sm mem-del" data-mem="${m.id}" aria-label="Esquecer">✕</button></li>`
      ).join('') || '<li class="empty-state">Nenhuma memória registrada.</li>';
    document.querySelectorAll('.mem-del').forEach(btn => {
      btn.addEventListener('click', async () => {
        try { await api.deleteMemory(btn.dataset.mem); refreshMemoryTab(); } catch { /* noop */ }
      });
    });
  } catch { /* noop */ }
  try {
    const rag = await api.fetchRagStatus();
    const local = rag.local || {};
    document.getElementById('rag-stats').textContent =
      `Local: ${local.documents ?? 0} docs · ${local.chunks ?? 0} chunks (FTS5) · Bibliotecário: ${(rag.global_catalog?.nodes_indexed ?? 0)} nó(s)`;
    document.getElementById('rag-docs').innerHTML =
      (rag.documents || []).map(d =>
        `<li><strong>${esc(d.title || d.path || '')}</strong> <small>${d.chunks ?? 0} chunks · ${(d.top_terms || []).slice(0, 5).join(', ')}</small></li>`
      ).join('') || '<li class="empty-state">Nenhum documento indexado. Envie arquivos 📎 no chat ou indexe uma nota acima.</li>';
  } catch { /* noop */ }
}

window.addEventListener('beforeunload', () => {
  stopPolling();
  if (wsClient) wsClient.close();
  if (hiveCanvas) hiveCanvas.destroy();
});

document.addEventListener('DOMContentLoaded', init);
