/**
 * HiveCanvas - Main canvas controller managing background + foreground layers
 * Background: static office/honeycomb (drawn once, cached)
 * Foreground: animated bees (60fps)
 */
import { HexGrid, DEFAULT_WORKSTATIONS } from './pathfinding.js';
import { BeeRenderer } from './bee-renderer.js';
import { BeeAnimator, BEE_STATES } from './bee-animator.js';
import { store } from './store.js';
import { audio } from './audio.js';

export class HiveCanvas {
  constructor() {
    this.bgCanvas = document.getElementById('hive-bg');
    this.fgCanvas = document.getElementById('hive-fg');
    this.bgCtx = this.bgCanvas.getContext('2d');
    this.fgCtx = this.fgCanvas.getContext('2d');

    this.grid = null;
    this.renderer = null;
    this.animator = null;

    this._bgDirty = true;
    this._animationId = null;
    this._lastFrame = 0;
    this._resizeHandler = this._handleResize.bind(this);

    // Subscribe to store changes
    this._unsubStore = store.subscribe(() => this._onStoreChange());
  }

  /** Initialize canvases, grid, renderer, animator */
  init() {
    // Ensure canvas has dimensions before creating grid
    this._resize();
    window.addEventListener('resize', this._resizeHandler);

    // Create grid with CSS dimensions (not buffer dimensions)
    const cssWidth = this.bgCanvas.clientWidth || window.innerWidth;
    const cssHeight = this.bgCanvas.clientHeight || window.innerHeight;
    this.grid = new HexGrid(cssWidth, cssHeight, 28);

    // Register workstations
    for (const [role, ws] of Object.entries(DEFAULT_WORKSTATIONS)) {
      this.grid.setWorkstation(role, ws.q, ws.r);
    }

    // Create renderer & animator
    this.renderer = new BeeRenderer(this.fgCtx, 28);
    this.animator = new BeeAnimator(this.grid, this.renderer);

    // Initial background draw
    this._drawBackground();

    // Start animation loop
    this._startLoop();

    // Click handler on foreground canvas
    this.fgCanvas.addEventListener('click', this._handleClick.bind(this));
    this.fgCanvas.addEventListener('mousemove', this._handleMouseMove.bind(this));

    console.log('[HiveCanvas] Initialized', cssWidth, 'x', cssHeight, 'DPR:', window.devicePixelRatio || 1);
  }

  /** Cleanup */
  destroy() {
    window.removeEventListener('resize', this._resizeHandler);
    this._unsubStore();
    this._stopLoop();
  }

  /** Store changed - mark background dirty if nodes changed */
  _onStoreChange() {
    this._bgDirty = true;
    // Update animator with current nodes
    if (this.animator && store.nodes) {
      for (const node of store.nodes) {
        this.animator.updateBee(node);
      }
    }
  }

  /** Resize handler */
  _handleResize() {
    this._resize();
    this._bgDirty = true;
    // Recreate grid with new CSS dimensions
    if (this.grid) {
      const cssWidth = this.bgCanvas.clientWidth || window.innerWidth;
      const cssHeight = this.bgCanvas.clientHeight || window.innerHeight;
      this.grid = new HexGrid(cssWidth, cssHeight, 28);
      for (const [role, ws] of Object.entries(DEFAULT_WORKSTATIONS)) {
        this.grid.setWorkstation(role, ws.q, ws.r);
      }
      if (this.animator) this.animator.grid = this.grid;
    }
  }

  _resize() {
    const dpr = window.devicePixelRatio || 1;
    // Canvas is fixed full viewport, use window dimensions
    const w = Math.max(400, window.innerWidth);
    const h = Math.max(300, window.innerHeight);

    for (const canvas of [this.bgCanvas, this.fgCanvas]) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
      canvas.getContext('2d').setTransform(dpr, 0, 0, dpr, 0, 0);
    }
  }

  /** Animation loop */
  _startLoop() {
    this._lastFrame = performance.now();
    this._animationId = requestAnimationFrame(this._loop.bind(this));
  }

  _stopLoop() {
    if (this._animationId) cancelAnimationFrame(this._animationId);
    this._animationId = null;
  }

  _loop(now) {
    const dt = now - this._lastFrame;
    this._lastFrame = now;

    // Update animator
    if (this.animator) this.animator.update(dt);

    // Draw background if dirty
    if (this._bgDirty) {
      this._drawBackground();
      this._bgDirty = false;
    }

    // Draw foreground (bees)
    this._drawForeground();

    this._animationId = requestAnimationFrame(this._loop.bind(this));
  }

  /** Draw static background: office floor, honeycomb grid, workstations */
  _drawBackground() {
    const ctx = this.bgCtx;
    const w = this.bgCanvas.width / (window.devicePixelRatio || 1);
    const h = this.bgCanvas.height / (window.devicePixelRatio || 1);

    ctx.clearRect(0, 0, w, h);

    // 1. Floor - wood texture
    this._drawFloor(ctx, w, h);

    // 2. Honeycomb grid (subtle)
    this._drawHoneycombGrid(ctx, w, h);

    // 3. Workstations (furniture)
    this._drawWorkstations(ctx, w, h);

    // 4. Walls hint (top/bottom edges)
    this._drawWalls(ctx, w, h);
  }

  /** Draw animated foreground: bees */
  _drawForeground() {
    const ctx = this.fgCtx;
    const w = this.fgCanvas.width / (window.devicePixelRatio || 1);
    const h = this.fgCanvas.height / (window.devicePixelRatio || 1);

    ctx.clearRect(0, 0, w, h);

    if (!this.animator || !store.nodes.length) return;

    // Update bees from store
    for (const node of store.nodes) {
      this.animator.updateBee(node);
    }

    // Remove disconnected bees
    const activeIds = new Set(store.nodes.map(n => n.node_id));
    for (const beeId of this.animator.bees.keys()) {
      if (!activeIds.has(beeId)) this.animator.removeBee(beeId);
    }

    // Render all bees
    this.animator.render();

    // Draw bars & indicators for each bee
    for (const bee of this.animator.bees.values()) {
      const node = store.getNode(bee.nodeId);
      if (node) {
        this.renderer.drawBars(bee.x, bee.y, node.cpu_pct || 0, node.free_ram_gb || 0);
        this.renderer.drawPauseIndicator(bee.x, bee.y, store.isPaused(bee.nodeId));
        this.renderer.drawTaskIndicator(bee.x, bee.y, node.active_tasks > 0);
      }
    }
  }

  /** Click on bee -> toggle pause */
  _handleClick(e) {
    const rect = this.fgCanvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    for (const [nodeId, bee] of this.animator.bees) {
      const dx = mx - bee.x;
      const dy = my - bee.y;
      if (dx * dx + dy * dy <= 28 * 28) { // hexSize^2
        const willPause = !store.isPaused(nodeId);
        audio.play('click');
        import('./api.js').then(({ pauseNode }) => pauseNode(nodeId, willPause));
        return;
      }
    }
  }

  /** Mouse move - highlight hovered bee */
  _handleMouseMove(e) {
    const rect = this.fgCanvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    this.fgCanvas.style.cursor = 'default';
    for (const [nodeId, bee] of this.animator.bees) {
      const dx = mx - bee.x;
      const dy = my - bee.y;
      if (dx * dx + dy * dy <= 28 * 28) {
        this.fgCanvas.style.cursor = 'pointer';
        // Could show tooltip here
        break;
      }
    }
  }

  // ===== Background drawing methods =====

  _drawFloor(ctx, w, h) {
    // Wood grain lines
    ctx.fillStyle = '#141414';
    ctx.fillRect(0, 0, w, h);

    ctx.strokeStyle = '#1a1a1a';
    ctx.lineWidth = 1;
    for (let y = 40; y < h; y += 40) {
      ctx.globalAlpha = 0.3;
      ctx.beginPath();
      ctx.moveTo(0, y + Math.sin(y * 0.01) * 2);
      ctx.lineTo(w, y + Math.sin(y * 0.01 + 1) * 2);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // Subtle planks
    ctx.strokeStyle = '#181818';
    for (let x = 80; x < w; x += 80) {
      ctx.beginPath();
      ctx.moveTo(x + Math.sin(x * 0.005) * 1, 0);
      ctx.lineTo(x + Math.sin(x * 0.005 + 2) * 1, h);
      ctx.stroke();
    }
  }

  _drawHoneycombGrid(ctx, w, h) {
    const { hexSize } = this.grid;
    const hexH = Math.sqrt(3) * hexSize;
    const colW = hexSize * 1.5;
    const rowH = hexH;

    const cols = Math.ceil(w / colW) + 2;
    const rows = Math.ceil(h / rowH) + 2;

    ctx.strokeStyle = 'rgba(255,179,0,0.03)';
    ctx.lineWidth = 1;

    for (let col = -1; col <= cols; col++) {
      for (let row = -1; row <= rows; row++) {
        const cx = w / 2 + col * colW;
        const cy = h / 2 + row * rowH + (col % 2) * rowH / 2;

        if (cx < -hexSize || cx > w + hexSize || cy < -hexSize || cy > h + hexSize) continue;

        // Check if this hex is a workstation
        const isWorkstation = this._isWorkstationHex(col, row);
        if (isWorkstation) {
          ctx.strokeStyle = 'rgba(255,179,0,0.12)';
          ctx.lineWidth = 1.5;
        } else {
          ctx.strokeStyle = 'rgba(255,179,0,0.03)';
          ctx.lineWidth = 1;
        }

        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
          const angle = (Math.PI / 3) * i - Math.PI / 6;
          const x = cx + hexSize * Math.cos(angle);
          const y = cy + hexSize * Math.sin(angle);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.stroke();
      }
    }
  }

  _isWorkstationHex(col, row) {
    for (const [, ws] of Object.entries(DEFAULT_WORKSTATIONS)) {
      if (ws.q === col && ws.r === row) return true;
    }
    return false;
  }

  _drawWorkstations(ctx, w, h) {
    const { hexSize } = this.grid;
    const hexH = Math.sqrt(3) * hexSize;
    const colW = hexSize * 1.5;
    const rowH = hexH;

    for (const [role, ws] of Object.entries(DEFAULT_WORKSTATIONS)) {
      const cx = w / 2 + ws.q * colW;
      const cy = h / 2 + ws.r * rowH + (ws.q % 2) * rowH / 2;

      // Draw workstation furniture
      this._drawWorkstation(ctx, cx, cy, role, hexSize);
    }
  }

  _drawWorkstation(ctx, cx, cy, role, hexSize) {
    const roleColors = {
      juiz: '#4caf50',
      guarda: '#2196f3',
      bibliotecaria: '#9c27b0',
      artista: '#e91e63',
      trabalhadora: '#ffb300',
      idle: '#888'
    };
    const color = roleColors[role] || '#888';

    ctx.save();
    ctx.translate(cx, cy);

    // Workstation base (larger hex)
    ctx.strokeStyle = color + '80';
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const angle = (Math.PI / 3) * i - Math.PI / 6;
      const x = hexSize * 1.3 * Math.cos(angle);
      const y = hexSize * 1.3 * Math.sin(angle);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.stroke();

    // Role-specific furniture
    switch (role) {
      case 'juiz':
        this._drawBench(ctx, color);
        break;
      case 'guarda':
        this._drawGate(ctx, color);
        break;
      case 'bibliotecaria':
        this._drawDesk(ctx, color);
        break;
      case 'artista':
        this._drawStudio(ctx, color);
        break;
      case 'trabalhadora':
        this._drawFactory(ctx, color);
        break;
      case 'idle':
        this._drawHiveCell(ctx);
        break;
    }

    ctx.restore();
  }

  _drawBench(ctx, color) {
    // Judge's bench - elevated desk with gavel
    ctx.fillStyle = '#2a2a2a';
    ctx.fillRect(-18, -8, 36, 16);
    ctx.fillStyle = color;
    ctx.fillRect(-16, -6, 32, 3);
    // Gavel
    ctx.fillStyle = '#5d4037';
    ctx.fillRect(-2, -14, 4, 8);
    ctx.fillStyle = '#3e2723';
    ctx.fillRect(-4, -16, 8, 3);
  }

  _drawGate(ctx, color) {
    // Security gate
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(-12, -15, 24, 30);
    // Gate arms
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(-14, -5);
    ctx.lineTo(14, -5);
    ctx.moveTo(-14, 5);
    ctx.lineTo(14, 5);
    ctx.stroke();
    // Monitor
    ctx.fillStyle = '#0d47a1';
    ctx.fillRect(-8, -12, 16, 10);
    ctx.fillStyle = '#64b5f6';
    ctx.fillRect(-6, -10, 12, 6);
  }

  _drawDesk(ctx, color) {
    // Librarian desk with books
    ctx.fillStyle = '#3e2723';
    ctx.fillRect(-20, -10, 40, 20);
    // Books stack
    ctx.fillStyle = '#7b1fa2';
    ctx.fillRect(-15, -20, 10, 12);
    ctx.fillStyle = '#9c27b0';
    ctx.fillRect(-3, -22, 8, 14);
    ctx.fillStyle = '#ba68c8';
    ctx.fillRect(8, -18, 6, 10);
    // Lamp
    ctx.fillStyle = '#ffd700';
    ctx.fillRect(15, -12, 3, 12);
    ctx.fillStyle = '#fff8e1';
    ctx.beginPath();
    ctx.arc(16.5, -14, 5, -Math.PI, 0);
    ctx.fill();
  }

  _drawStudio(ctx, color) {
    // Artist studio - easel
    ctx.strokeStyle = '#5d4037';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    // Easel legs
    ctx.beginPath();
    ctx.moveTo(-12, 10);
    ctx.lineTo(-12, -15);
    ctx.moveTo(12, 10);
    ctx.lineTo(12, -15);
    ctx.stroke();
    // Canvas
    ctx.fillStyle = '#fff';
    ctx.fillRect(-10, -14, 20, 16);
    ctx.strokeStyle = '#3e2723';
    ctx.lineWidth = 1;
    ctx.strokeRect(-10, -14, 20, 16);
    // Paint splatter
    ctx.fillStyle = '#e91e63';
    ctx.fillRect(-8, -10, 3, 3);
    ctx.fillStyle = '#4caf50';
    ctx.fillRect(2, -6, 2, 2);
    ctx.fillStyle = '#ffeb3b';
    ctx.fillRect(6, -12, 2, 2);
  }

  _drawFactory(ctx, color) {
    // Factory station - conveyor + boxes
    ctx.fillStyle = '#2a2a2a';
    ctx.fillRect(-22, -2, 44, 10);
    // Conveyor rollers
    ctx.fillStyle = '#444';
    for (let x = -20; x <= 20; x += 8) {
      ctx.fillRect(x, -1, 4, 8);
    }
    // Boxes
    ctx.fillStyle = '#795548';
    ctx.fillRect(-18, -10, 8, 10);
    ctx.fillStyle = '#5d4037';
    ctx.fillRect(-6, -14, 10, 14);
    ctx.fillStyle = '#8d6e63';
    ctx.fillRect(10, -8, 6, 8);
  }

  _drawHiveCell(ctx) {
    // Generic honeycomb cell
    ctx.strokeStyle = '#ffb30040';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const angle = (Math.PI / 3) * i;
      const x = 18 * Math.cos(angle);
      const y = 18 * Math.sin(angle);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.stroke();
  }

  _drawWalls(ctx, w, h) {
    // Top wall shadow
    const gradient = ctx.createLinearGradient(0, 0, 0, 60);
    gradient.addColorStop(0, 'rgba(0,0,0,0.4)');
    gradient.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, w, 60);

    // Bottom wall shadow
    const gradient2 = ctx.createLinearGradient(0, h, 0, h - 60);
    gradient2.addColorStop(0, 'rgba(0,0,0,0.4)');
    gradient2.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = gradient2;
    ctx.fillRect(0, h - 60, w, 60);
  }
}