/**
 * SidebarController - Manages node list, connection grid, models, stats
 */
import { store } from './store.js';
import { api } from './api.js';
import { getRole, getRoleEmoji, getRoleColor } from './bee-roles.js';

export class SidebarController {
  constructor() {
    this.nodeList = document.getElementById('node-list');
    this.connectionGrid = document.getElementById('connection-grid');
    this.modelList = document.getElementById('model-list');
    this.stats = {
      tasks: document.getElementById('c-tasks'),
      calls: document.getElementById('c-calls'),
      nacks: document.getElementById('c-nacks'),
      peers: document.getElementById('c-peers')
    };
    this.clusterLabel = document.getElementById('cluster-label');
    this.sidebar = document.getElementById('sidebar');
    this.toggleBtn = document.getElementById('sidebar-toggle');
    this.mainGrid = document.querySelector('.main-grid');
    this.overlay = this._createOverlay();

    this._bindEvents();
  }

  _createOverlay() {
    const overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    overlay.addEventListener('click', () => this.setCollapsed(true));
    document.body.appendChild(overlay);
    return overlay;
  }

  _bindEvents() {
    this.toggleBtn.addEventListener('click', () => this.setCollapsed(!this.sidebar.classList.contains('collapsed')));

    // Close sidebar on mobile when clicking a node
    this.nodeList.addEventListener('click', (e) => {
      if (window.innerWidth < 1024 && e.target.closest('.node-item')) {
        this.setCollapsed(true);
      }
    });
  }

  setCollapsed(collapsed) {
    this.sidebar.classList.toggle('collapsed', collapsed);
    this.mainGrid?.classList.toggle('sidebar-collapsed', collapsed);
    this.overlay.classList.toggle('open', collapsed);
    this.toggleBtn.setAttribute('aria-expanded', !collapsed);
    this.toggleBtn.innerHTML = collapsed ? '▶' : '◀';
  }

  /** Update all sidebar sections from store */
  update() {
    this._updateNodeList();
    this._updateConnectionGrid();
    this._updateModels();
    this._updateStats();
    this._updateClusterLabel();
  }

  _updateNodeList() {
    const { nodes, pausedAll, pausedNodes } = store;
    if (!nodes.length) {
      this.nodeList.innerHTML = '<div class="empty-state">Nenhum nó conectado</div>';
      return;
    }

    this.nodeList.innerHTML = nodes.map(node => {
      const paused = pausedAll || pausedNodes.has(node.node_id);
      const roleDef = getRole(node.cluster_role);
      const cpuPct = Math.min(100, node.cpu_pct || 0);
      const ramUsed = node.max_concurrency ? Math.min(100, (node.active_tasks / node.max_concurrency) * 100) : 0;

      return `
        <div class="node-item ${paused ? 'paused' : ''}" data-node-id="${node.node_id}" role="listitem">
          <div class="node-dot" style="background: ${roleDef.color}; box-shadow: 0 0 8px ${roleDef.color};"></div>
          <div class="node-info">
            <span class="node-name" title="${node.node_id}">${node.node_id.replace(/-.*/, '')}</span>
            <span class="node-role">${roleDef.emoji} ${roleDef.label}</span>
          </div>
          <div class="node-bars">
            <div class="bar cpu" title="CPU ${cpuPct.toFixed(0)}%"><span style="width:${cpuPct}%"></span></div>
            <div class="bar ram" title="RAM ${ramUsed.toFixed(0)}%"><span style="width:${ramUsed}%"></span></div>
          </div>
          <button class="pause-btn" data-id="${node.node_id}" aria-label="${paused ? 'Retomar' : 'Pausar'} ${node.node_id}" aria-pressed="${paused}">
            ${paused ? '▶' : '❚❚'}
          </button>
        </div>
      `;
    }).join('');

    // Bind pause buttons
    this.nodeList.querySelectorAll('.pause-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        const willPause = !store.isPaused(id);
        try {
          await api.pauseNode(id, willPause);
          store.setPaused(id, willPause);
        } catch (err) {
          console.error('Pause error:', err);
        }
      });
    });
  }

  _updateConnectionGrid() {
    const { nodes } = store;
    if (!nodes.length) {
      this.connectionGrid.innerHTML = '<div class="empty-state">Sem dados de conexão</div>';
      return;
    }

    this.connectionGrid.innerHTML = nodes.map(node => {
      const cpu = node.cpu_pct || 0;
      const ram = node.free_ram_gb || 0;
      const maxRam = 8; // assume 8GB baseline
      const ramPct = Math.min(100, (1 - ram / maxRam) * 100);
      const load = Math.max(cpu, ramPct);

      let statusClass = 'good', statusText = 'OK';
      if (load > 80) { statusClass = 'bad'; statusText = 'ALTO'; }
      else if (load > 60) { statusClass = 'warn'; statusText = 'MÉDIO'; }

      const roleDef = getRole(node.cluster_role);
      return `
        <div class="conn-item" title="${node.node_id}">
          <span class="conn-label">${roleDef.emoji} ${node.node_id.replace(/-.*/, '')}</span>
          <span class="conn-value ${statusClass}">${statusText}</span>
        </div>
      `;
    }).join('');
  }

  _updateModels() {
    const { models } = store;
    if (!models.length) {
      this.modelList.innerHTML = '<div class="empty-state">Nenhum modelo Ollama</div>';
      return;
    }

    // Parse size_mb (can be string like "1B", "3.2B" or number)
    const parseSize = (s) => {
      if (typeof s === 'number') return s;
      const str = String(s).toUpperCase().trim();
      if (str.endsWith('GB')) return parseFloat(str) * 1024;
      if (str.endsWith('MB')) return parseFloat(str);
      if (str.endsWith('B')) return parseFloat(str) * 1024;
      return parseFloat(str) || 0;
    };

    // Find best (largest non-embedding)
    const nonEmbed = models.filter(m => !m.is_embedding);
    const best = nonEmbed.length 
      ? nonEmbed.reduce((a, b) => parseSize(a.size_mb) > parseSize(b.size_mb) ? a : b) 
      : null;

    this.modelList.innerHTML = models.map(m => {
      const isBest = best && m.name === best.name;
      const sizeMb = parseSize(m.size_mb);
      const sizeDisplay = sizeMb >= 1024 ? `${(sizeMb / 1024).toFixed(1)} GB` : `${sizeMb} MB`;
      return `
        <div class="model-item ${isBest ? 'primary' : ''}" role="listitem">
          <span class="model-dot"></span>
          <span class="model-name">${m.name}</span>
          <span class="model-size">${sizeDisplay}</span>
        </div>
      `;
    }).join('');
  }

  _updateStats() {
    const { tasks, calls, nacks, peers } = store.stats;
    this.stats.tasks.textContent = tasks;
    this.stats.calls.textContent = calls;
    this.stats.nacks.textContent = nacks;
    this.stats.peers.textContent = peers;
  }

  _updateClusterLabel() {
    this.clusterLabel.textContent = store.clusterLabel;
  }
}