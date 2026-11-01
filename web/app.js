/**
 * ENXAME Hive — Main Application Entry Point
 * Initializes all controllers and manages lifecycle
 */
import { store } from './store.js';
import * as api from './api.js';
import { initSession } from './api.js';
import { audio } from './audio.js';
import { HiveCanvas } from './hive-canvas.js';
import { ChatController } from './chat.js';
import { SidebarController } from './sidebar.js';

// Global controllers
let hiveCanvas = null;
let chatController = null;
let sidebarController = null;
let statusInterval = null;
let modelsInterval = null;

// Expose hiveCanvas globally for settings
window.hiveCanvas = null;

async function init() {
  console.log('[ENXAME] Starting...');

  // Initialize audio (requires user interaction)
  await audio.init();

  // Initialize UI controllers
  chatController = new ChatController();
  sidebarController = new SidebarController();
  hiveCanvas = new HiveCanvas();
  hiveCanvas.init();
  window.hiveCanvas = hiveCanvas;

  // Bind global UI events
  bindGlobalEvents();

  // Create session & start polling
  try {
    await initSession();
    chatController.setConnected(true);
    await loadInitialData();
    startPolling();
  } catch (err) {
    console.error('[ENXAME] Session init failed:', err);
    chatController.setConnected(false);
    chatController._addMessage('Falha ao conectar ao backend. Verifique se o serviço está rodando.', 'system err');
  }

  console.log('[ENXAME] Ready');
}

function bindGlobalEvents() {
  // Discover button
  document.getElementById('discover-btn').addEventListener('click', async () => {
    const btn = document.getElementById('discover-btn');
    btn.disabled = true;
    btn.textContent = 'Descobrindo…';
    try {
      const { peers } = await fetchDiscover();
      // Peers are added to store via status poll, just show toast
      chatController._addMessage(`Descoberta concluída: ${peers.length} peer(s) encontrado(s)`, 'system');
    } catch (err) {
      chatController._addMessage(`Erro na descoberta: ${err.message}`, 'system err');
    } finally {
      btn.disabled = false;
      btn.textContent = 'DESCOBRIR REDE';
    }
  });

  // Pause all button
  document.getElementById('pause-all').addEventListener('click', async () => {
    const btn = document.getElementById('pause-all');
    const newState = !store.pausedAll;
    try {
      await pauseAll(newState);
      store.pausedAll = newState;
      btn.classList.toggle('active', newState);
      btn.setAttribute('aria-pressed', newState);
      audio.play(newState ? 'error' : 'click');
    } catch (err) {
      console.error('Pause all error:', err);
    }
  });

  // Settings button - open modal
  document.getElementById('settings-btn').addEventListener('click', () => {
    openSettingsModal();
  });

  // Settings modal
  function openSettingsModal() {
    const modal = document.getElementById('settings-modal');
    modal.classList.add('open');
    loadSettings();
  }

  function closeSettingsModal() {
    const modal = document.getElementById('settings-modal');
    modal.classList.remove('open');
  }

  document.getElementById('settings-close').addEventListener('click', closeSettingsModal);
  document.getElementById('settings-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeSettingsModal();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeSettingsModal();
    }
  });

  async function loadSettings() {
    try {
      const res = await fetch('/api/v1/config');
      if (res.ok) {
        const cfg = await res.json();
        document.getElementById('setting-offline').checked = cfg.offline_mode || false;
        document.getElementById('setting-web-fallback').checked = cfg.allow_web !== false;
        document.getElementById('setting-confidence').value = cfg.confidence_threshold || 0.7;
        document.getElementById('confidence-value').textContent = (cfg.confidence_threshold || 0.7).toFixed(2);
        document.getElementById('setting-animations').checked = true;
        document.getElementById('setting-sounds').checked = true;
        
        // Populate model select
        const modelSelect = document.getElementById('setting-model');
        const currentModel = cfg.preferred_model || 'auto';
        const modelsRes = await fetch('/api/v1/models');
        if (modelsRes.ok) {
          const { models } = await modelsRes.json();
          modelSelect.innerHTML = '<option value="auto">Automático (Recomendado)</option>' +
            (models || []).map(m => `<option value="${m.name}" ${m.name === currentModel ? 'selected' : ''}>${m.name}</option>`).join('');
        }
      }
    } catch (err) {
      console.warn('Failed to load settings:', err);
    }
  }

  document.getElementById('setting-confidence').addEventListener('input', (e) => {
    document.getElementById('confidence-value').textContent = parseFloat(e.target.value).toFixed(2);
  });

  document.getElementById('setting-hex-size').addEventListener('input', (e) => {
    document.getElementById('hex-size-value').textContent = e.target.value + 'px';
    // Update canvas hex size
    if (window.hiveCanvas && window.hiveCanvas.grid) {
      const newSize = parseInt(e.target.value);
      window.hiveCanvas.grid.hexSize = newSize;
      window.hiveCanvas._bgDirty = true;
    }
  });

  document.getElementById('settings-save').addEventListener('click', async () => {
    const config = {
      offline_mode: document.getElementById('setting-offline').checked,
      allow_web: document.getElementById('setting-web-fallback').checked,
      confidence_threshold: parseFloat(document.getElementById('setting-confidence').value),
      preferred_model: document.getElementById('setting-model').value,
    };
    try {
      const res = await fetch('/api/v1/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      if (res.ok) {
        chatController._addMessage('Configurações salvas', 'system');
        closeSettingsModal();
      } else {
        chatController._addMessage('Erro ao salvar configurações', 'system err');
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

  // Global search (placeholder)
  document.getElementById('global-search').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const query = e.target.value.trim();
      if (query) chatController._addMessage(`Busca: "${query}" — em desenvolvimento`, 'system');
    }
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Escape: clear chat
    if (e.key === 'Escape' && document.activeElement !== document.getElementById('msg')) {
      chatController.clear();
    }
    // Ctrl/Cmd + K: focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      document.getElementById('global-search').focus();
    }
    // Ctrl/Cmd + Enter: send message (when input focused)
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && document.activeElement === document.getElementById('msg')) {
      chatController.send();
    }
  });

  // Visibility change - pause polling when hidden
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopPolling();
    else startPolling();
  });
}

async function loadInitialData() {
  try {
    const [status, models] = await Promise.all([
      api.fetchStatus(),
      api.fetchModels().catch(() => ({ models: [], best: null }))
    ]);

    console.log('[ENXAME] Status:', status);
    console.log('[ENXAME] Models:', models);

    // Update store
    store.nodes = status.agents || [];
    store.stats = {
      tasks: status.tasks_total || 0,
      calls: 0,
      nacks: 0,
      peers: (status.agents || []).length
    };
    store.clusterLabel = `cluster: ${status.node} · ${(status.agents || []).length} nó${(status.agents || []).length !== 1 ? 's' : ''}`;
    store.models = models.models || [];
    store.ollamaStatus = models.models?.length ? 'ok' : 'none';

    // Update UI
    sidebarController.update();
    chatController.setConnected(true);
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
      console.log('[ENXAME] Poll status:', status);
      store.nodes = status.agents || [];
      store.stats.tasks = status.tasks_total || 0;
      store.stats.peers = (status.agents || []).length;
      store.clusterLabel = `cluster: ${status.node} · ${(status.agents || []).length} nó${(status.agents || []).length !== 1 ? 's' : ''}`;
      sidebarController.update();
      chatController.setConnected(true);
    } catch (err) {
      console.warn('[ENXAME] Status poll failed:', err);
      chatController.setConnected(false);
    }
  }, 2000);

  modelsInterval = setInterval(async () => {
    try {
      const { models, best } = await api.fetchModels();
      console.log('[ENXAME] Poll models:', models);
      store.models = models || [];
      store.ollamaStatus = models?.length ? 'ok' : 'none';
      sidebarController.update();
      updateOllamaStatus(models?.length ? 'ok' : 'none');
    } catch (err) {
      console.warn('[ENXAME] Models poll failed:', err);
    }
  }, 10000);
}

function stopPolling() {
  if (statusInterval) { clearInterval(statusInterval); statusInterval = null; }
  if (modelsInterval) { clearInterval(modelsInterval); modelsInterval = null; }
}

function updateOllamaStatus(status) {
  const el = document.getElementById('ollama-status');
  if (!el) return;
  el.className = 'status-badge';
  if (status === 'ok') {
    el.classList.add('ok');
    el.textContent = 'Ollama: ✓';
  } else {
    el.classList.add('err');
    el.textContent = 'Ollama: ✗';
  }
}

// Cleanup on unload
window.addEventListener('beforeunload', () => {
  stopPolling();
  if (hiveCanvas) hiveCanvas.destroy();
});

// Start
document.addEventListener('DOMContentLoaded', init);