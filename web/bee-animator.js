/**
 * BeeAnimator - State machine for bee animations
 * Handles: idle, walking, working, paused, responding
 */
import { HexGrid, DEFAULT_WORKSTATIONS, Hex } from './pathfinding.js';

export const BEE_STATES = {
  IDLE: 'idle',
  WALKING: 'walking',
  WORKING: 'working',
  PAUSED: 'paused',
  RESPONDING: 'responding'
};

export class BeeAnimator {
  constructor(grid, renderer) {
    this.grid = grid;
    this.renderer = renderer;
    this.bees = new Map(); // nodeId -> bee state
    this.lastUpdate = 0;
  }

  /** Initialize or update bee from node data */
  updateBee(node) {
    const nodeId = node.node_id;
    const role = node.cluster_role || 'idle';
    const paused = node.paused === true;
    const activeTasks = node.active_tasks > 0;

    let bee = this.bees.get(nodeId);
    const now = performance.now();

    if (!bee) {
      // New bee - spawn at center, then walk to workstation
      bee = {
        nodeId,
        role,
        x: this.grid.width / 2,
        y: this.grid.height / 2,
        targetX: this.grid.width / 2,
        targetY: this.grid.height / 2,
        state: BEE_STATES.IDLE,
        path: [],
        pathIndex: 0,
        arrivedAt: 0,
        idleTimer: 0,
        idleTarget: null,
        lastStateChange: now
      };
      this.bees.set(nodeId, bee);
      // Plan initial path to workstation
      this._planPathToWorkstation(bee);
    }

    // Update role if changed
    if (bee.role !== role) {
      bee.role = role;
      this._planPathToWorkstation(bee);
    }

    // Handle pause state (highest priority)
    if (paused) {
      if (bee.state !== BEE_STATES.PAUSED) {
        bee.state = BEE_STATES.PAUSED;
        bee.lastStateChange = now;
      }
      return;
    }

    // Handle responding state (temporary highlight)
    if (activeTasks && bee.state === BEE_STATES.WORKING) {
      if (bee.state !== BEE_STATES.RESPONDING) {
        bee.state = BEE_STATES.RESPONDING;
        bee.lastStateChange = now;
        bee.respondUntil = now + 2000; // 2s highlight
      }
      return;
    }
    if (bee.state === BEE_STATES.RESPONDING && now > (bee.respondUntil || 0)) {
      bee.state = BEE_STATES.WORKING;
    }

    // State machine
    switch (bee.state) {
      case BEE_STATES.WALKING:
        this._updateWalking(bee, now);
        break;
      case BEE_STATES.WORKING:
        this._updateWorking(bee, now);
        break;
      case BEE_STATES.IDLE:
        this._updateIdle(bee, now);
        break;
    }
  }

  /** Remove bee (node disconnected) */
  removeBee(nodeId) {
    this.bees.delete(nodeId);
  }

  /** Update all bees - call each frame */
  update(deltaTime) {
    const now = performance.now();
    for (const bee of this.bees.values()) {
      if (bee.state === BEE_STATES.WALKING) {
        this._updateWalking(bee, now);
      } else if (bee.state === BEE_STATES.IDLE) {
        this._updateIdle(bee, now);
      }
    }
  }

  /** Render all bees */
  render() {
    for (const bee of this.bees.values()) {
      this.renderer.drawBee(bee.x, bee.y, bee.role, bee.state);
      this.renderer.drawLabel(bee.x, bee.y, bee.nodeId, bee.role, bee.state === BEE_STATES.PAUSED);
      // Note: bars and indicators drawn by HiveCanvas after this
    }
  }

  // ===== Private methods =====

  _planPathToWorkstation(bee) {
    const ws = DEFAULT_WORKSTATIONS[bee.role] || DEFAULT_WORKSTATIONS.idle;
    const startCube = this.grid.screenToCube(bee.x, bee.y);
    const goalCube = Hex.axialToCube(ws.q, ws.r);
    const path = this.grid.getScreenPath(startCube, goalCube);

    if (path.length > 1) {
      bee.path = path;
      bee.pathIndex = 0;
      bee.targetX = path[path.length - 1].x;
      bee.targetY = path[path.length - 1].y;
      bee.state = BEE_STATES.WALKING;
    } else {
      // Already there or no path
      bee.x = this.grid.width / 2;
      bee.y = this.grid.height / 2;
      bee.state = BEE_STATES.IDLE;
    }
  }

  _updateWalking(bee, now) {
    if (bee.pathIndex >= bee.path.length - 1) {
      // Arrived
      bee.x = bee.targetX;
      bee.y = bee.targetY;
      bee.state = BEE_STATES.WORKING;
      bee.arrivedAt = now;
      return;
    }

    // Move along path
    const speed = 60; // px per second
    const dt = (now - this.lastUpdate) / 1000;
    this.lastUpdate = now;

    const target = bee.path[bee.pathIndex + 1];
    const dx = target.x - bee.x;
    const dy = target.y - bee.y;
    const dist = Math.hypot(dx, dy);
    const step = speed * dt;

    if (dist <= step) {
      bee.x = target.x;
      bee.y = target.y;
      bee.pathIndex++;
    } else {
      bee.x += (dx / dist) * step;
      bee.y += (dy / dist) * step;
    }
  }

  _updateWorking(bee, now) {
    // After working for a while, maybe go idle
    const workDuration = now - bee.arrivedAt;
    if (workDuration > 30000 + Math.random() * 30000) { // 30-60s
      this._planIdleWander(bee);
    }
  }

  _updateIdle(bee, now) {
    if (bee.idleTarget) {
      // Walking to idle spot
      const dx = bee.idleTarget.x - bee.x;
      const dy = bee.idleTarget.y - bee.y;
      const dist = Math.hypot(dx, dy);
      const speed = 30; // slower when wandering
      const dt = (now - this.lastUpdate) / 1000;
      this.lastUpdate = now;

      if (dist <= speed * dt) {
        bee.x = bee.idleTarget.x;
        bee.y = bee.idleTarget.y;
        bee.idleTarget = null;
        bee.idleTimer = now;
      } else {
        bee.x += (dx / dist) * speed * dt;
        bee.y += (dy / dist) * speed * dt;
      }
    } else if (now - bee.idleTimer > 5000 + Math.random() * 10000) {
      // Pick new idle spot
      this._planIdleWander(bee);
    }
  }

  _planIdleWander(bee) {
    // Random point near center
    const angle = Math.random() * Math.PI * 2;
    const radius = 80 + Math.random() * 120;
    bee.idleTarget = {
      x: this.grid.width / 2 + Math.cos(angle) * radius,
      y: this.grid.height / 2 + Math.sin(angle) * radius
    };
    bee.state = BEE_STATES.IDLE; // technically walking but we reuse IDLE with target
    // Plan path
    const startCube = this.grid.screenToCube(bee.x, bee.y);
    const goalCube = this.grid.screenToCube(bee.idleTarget.x, bee.idleTarget.y);
    const path = this.grid.getScreenPath(startCube, goalCube);
    if (path.length > 1) {
      bee.path = path;
      bee.pathIndex = 0;
      bee.state = BEE_STATES.WALKING;
    }
  }
}