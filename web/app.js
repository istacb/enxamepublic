/**
 * ENXAME Hive — Main Application Entry Point
 * Initializes all controllers and manages lifecycle
 */
import { store } from './store.js';
import { initSession, fetchStatus, fetchModels, fetchDiscover, pauseNode, pauseAll, sendChat, streamChat } from './api.js';
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

async function init() {
  console.log('[ENXAME] Starting...');

  // Initialize audio (requires user interaction)
  await audio.init();

  // Initialize UI controllers
  chatController = new ChatController();
  sidebarController = new SidebarController();
  hiveCanvas = new HiveCanvas();
  hiveCanvas.init();

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

  // Settings button (placeholder)
  document.getElementById('settings-btn').addEventListener('click', () => {
    chatController._addMessage('Configurações: em desenvolvimento', 'system');
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