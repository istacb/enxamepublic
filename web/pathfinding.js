/**
 * Hex Grid A* Pathfinding
 * Pointy-top hex orientation
 * Coordinates: cube (x, y, z) with x + y + z = 0
 */
export const Hex = {
  // Convert axial (q, r) to cube (x, y, z)
  axialToCube(q, r) {
    const x = q;
    const z = r;
    const y = -x - z;
    return { x, y, z };
  },

  cubeToAxial(x, y, z) {
    return { q: x, r: z };
  },

  // Neighbors in cube coordinates
  cubeNeighbors: [
    { x: 1, y: -1, z: 0 }, { x: 1, y: 0, z: -1 }, { x: 0, y: 1, z: -1 },
    { x: -1, y: 1, z: 0 }, { x: -1, y: 0, z: 1 }, { x: 0, y: -1, z: 1 }
  ],

  // Distance between two cube coords
  cubeDistance(a, b) {
    return Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y), Math.abs(a.z - b.z));
  },

  // Lerp between two cube coords
  cubeLerp(a, b, t) {
    return {
      x: a.x + (b.x - a.x) * t,
      y: a.y + (b.y - a.y) * t,
      z: a.z + (b.z - a.z) * t
    };
  },

  // Round cube to nearest hex
  cubeRound(cube) {
    let { x, y, z } = cube;
    const rx = Math.round(x), ry = Math.round(y), rz = Math.round(z);
    const dx = Math.abs(rx - x), dy = Math.abs(ry - y), dz = Math.abs(rz - z);
    if (dx > dy && dx > dz) rx = -ry - rz;
    else if (dy > dz) ry = -rx - rz;
    else rz = -rx - ry;
    return { x: rx, y: ry, z: rz };
  },

  // Line drawing (for path interpolation)
  cubeLineDraw(a, b) {
    const n = this.cubeDistance(a, b);
    const results = [];
    for (let i = 0; i <= n; i++) {
      results.push(this.cubeRound(this.cubeLerp(a, b, n === 0 ? 0 : i / n)));
    }
    return results;
  }
};

/**
 * HexGrid - World representation for pathfinding
 * Maps workstations to hex coordinates
 */
export class HexGrid {
  constructor(width, height, hexSize = 28) {
    this.hexSize = hexSize;
    this.width = width;
    this.height = height;
    this.cols = Math.ceil(width / (hexSize * 1.5));
    this.rows = Math.ceil(height / (hexSize * Math.sqrt(3)));
    this.obstacles = new Set(); // cube coord string keys
    this.workstations = new Map(); // role -> cube coord
  }

  // Screen to axial
  screenToAxial(sx, sy) {
    const { hexSize } = this;
    const x = (sx - width / 2) / (hexSize * 1.5);
    const y = (sy - height / 2 - (x % 2) * hexSize * Math.sqrt(3) / 2) / (hexSize * Math.sqrt(3));
    return this.axialRound(x, y);
  }

  axialRound(q, r) {
    const cube = Hex.axialToCube(q, r);
    const rounded = Hex.cubeRound(cube);
    return Hex.cubeToAxial(rounded.x, rounded.y, rounded.z);
  }

  // Axial to screen center
  axialToScreen(q, r) {
    const { hexSize } = this;
    const cx = this.width / 2 + hexSize * 1.5 * q;
    const cy = this.height / 2 + hexSize * Math.sqrt(3) * (r + q / 2);
    return { x: cx, y: cy };
  }

  // Add obstacle (blocked hex)
  addObstacle(q, r) {
    const cube = Hex.axialToCube(q, r);
    this.obstacles.add(`${cube.x},${cube.y},${cube.z}`);
  }

  // Register workstation for a role
  setWorkstation(role, q, r) {
    const cube = Hex.axialToCube(q, r);
    this.workstations.set(role, cube);
  }

  getWorkstation(role) {
    return this.workstations.get(role);
  }

  // Check if hex is walkable
  isWalkable(cube) {
    const key = `${cube.x},${cube.y},${cube.z}`;
    if (this.obstacles.has(key)) return false;
    // Bounds check
    const { q, r } = Hex.cubeToAxial(cube.x, cube.y, cube.z);
    return q >= -this.cols && q <= this.cols && r >= -this.rows && r <= this.rows;
  }

  // A* Pathfinding
  findPath(startCube, goalCube) {
    const startKey = `${startCube.x},${startCube.y},${startCube.z}`;
    const goalKey = `${goalCube.x},${goalCube.y},${goalCube.z}`;

    if (!this.isWalkable(startCube) || !this.isWalkable(goalCube)) {
      return []; // Direct line fallback handled by caller
    }

    const openSet = new Map(); // key -> { cube, g, f, parent }
    const closedSet = new Set();

    const h = (cube) => Hex.cubeDistance(cube, goalCube) * 10;

    openSet.set(startKey, { cube: startCube, g: 0, f: h(startCube), parent: null });

    while (openSet.size > 0) {
      // Find lowest f
      let currentKey = null, current = null;
      for (const [k, v] of openSet) {
        if (!current || v.f < current.f) { currentKey = k; current = v; }
      }
      if (currentKey === goalKey) {
        // Reconstruct path
        const path = [];
        let node = current;
        while (node) {
          path.push(node.cube);
          node = node.parent;
        }
        return path.reverse();
      }

      openSet.delete(currentKey);
      closedSet.add(currentKey);

      // Neighbors
      for (const dir of Hex.cubeNeighbors) {
        const neighbor = {
          x: current.cube.x + dir.x,
          y: current.cube.y + dir.y,
          z: current.cube.z + dir.z
        };
        const nKey = `${neighbor.x},${neighbor.y},${neighbor.z}`;
        if (closedSet.has(nKey) || !this.isWalkable(neighbor)) continue;

        const g = current.g + 10;
        const existing = openSet.get(nKey);
        if (!existing || g < existing.g) {
          openSet.set(nKey, { cube: neighbor, g, f: g + h(neighbor), parent: current });
        }
      }
    }
    return []; // No path found
  }

  // Get interpolated path as screen coordinates
  getScreenPath(startCube, goalCube, maxPoints = 20) {
    const path = this.findPath(startCube, goalCube);
    if (path.length < 2) return [];

    // Convert to screen coords
    const screenPath = path.map(cube => {
      const { q, r } = Hex.cubeToAxial(cube.x, cube.y, cube.z);
      return this.axialToScreen(q, r);
    });

    // Resample to fixed number of points for smooth animation
    const totalDist = screenPath.reduce((sum, p, i) => {
      if (i === 0) return 0;
      const dx = p.x - screenPath[i-1].x;
      const dy = p.y - screenPath[i-1].y;
      return sum + Math.hypot(dx, dy);
    }, 0);

    if (totalDist === 0) return [screenPath[0]];

    const resampled = [];
    for (let i = 0; i < maxPoints; i++) {
      const targetDist = (i / (maxPoints - 1)) * totalDist;
      let accum = 0;
      for (let j = 1; j < screenPath.length; j++) {
        const dx = screenPath[j].x - screenPath[j-1].x;
        const dy = screenPath[j].y - screenPath[j-1].y;
        const segLen = Math.hypot(dx, dy);
        if (accum + segLen >= targetDist) {
          const t = (targetDist - accum) / segLen;
          resampled.push({
            x: screenPath[j-1].x + dx * t,
            y: screenPath[j-1].y + dy * t
          });
          break;
        }
        accum += segLen;
      }
    }
    return resampled;
  }
}

/** Convert screen coordinates to cube coordinates */
HexGrid.prototype.screenToCube = function(sx, sy) {
  const { hexSize } = this;
  const q = (sx - this.width / 2) / (hexSize * 1.5);
  const r = (sy - this.height / 2) / (hexSize * Math.sqrt(3)) - q / 2;
  return Hex.axialToCube(q, r);
};

// Default workstation positions (relative to canvas center)
export const DEFAULT_WORKSTATIONS = {
  juiz: { q: 0, r: -4 },        // North - bench
  guarda: { q: 4, r: 0 },       // East - gate
  bibliotecaria: { q: 0, r: 4 }, // South - desk
  artista: { q: -3, r: -2 },    // NW - studio
  trabalhadora: { q: 3, r: 2 }, // SE - factory
  idle: { q: 0, r: 0 }          // Center - hive cell
};