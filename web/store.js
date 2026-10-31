/**
 * NodeStore - Reactive state management for hive nodes
 * Simple PubSub pattern, no dependencies
 */
export class NodeStore {
  constructor() {
    this._nodes = [];
    this._subscribers = new Set();
    this._pausedAll = false;
    this._pausedNodes = new Set();
    this._stats = { tasks: 0, calls: 0, nacks: 0, peers: 0 };
    this._clusterLabel = 'cluster: —';
    this._models = [];
    this._ollamaStatus = 'unknown';
  }

  // ---- Nodes ----
  get nodes() { return this._nodes; }
  set nodes(val) { this._nodes = val; this._emit(); }

  getNode(id) { return this._nodes.find(n => n.node_id === id); }

  // ---- Pause state ----
  get pausedAll() { return this._pausedAll; }
  set pausedAll(val) { this._pausedAll = val; this._emit(); }
  togglePausedAll() { this._pausedAll = !this._pausedAll; this._emit(); }

  get pausedNodes() { return this._pausedNodes; }
  isPaused(nodeId) { return this._pausedAll || this._pausedNodes.has(nodeId); }
  setPaused(nodeId, val) {
    if (val) this._pausedNodes.add(nodeId); else this._pausedNodes.delete(nodeId);
    this._emit();
  }
  togglePaused(nodeId) {
    this.setPaused(nodeId, !this.isPaused(nodeId));
  }

  // ---- Stats ----
  get stats() { return this._stats; }
  set stats(val) { this._stats = { ...this._stats, ...val }; this._emit(); }
  incrementStat(key, delta = 1) { this._stats[key] = (this._stats[key] || 0) + delta; this._emit(); }

  // ---- Cluster ----
  get clusterLabel() { return this._clusterLabel; }
  set clusterLabel(val) { this._clusterLabel = val; this._emit(); }

  // ---- Models ----
  get models() { return this._models; }
  set models(val) { this._models = val; this._emit(); }

  // ---- Ollama ----
  get ollamaStatus() { return this._ollamaStatus; }
  set ollamaStatus(val) { this._ollamaStatus = val; this._emit(); }

  // ---- PubSub ----
  subscribe(fn) { this._subscribers.add(fn); return () => this._subscribers.delete(fn); }
  _emit() { this._subscribers.forEach(fn => fn(this)); }
}

// Singleton instance
export const store = new NodeStore();