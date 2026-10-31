/**
 * BeeRenderer - Draws bees with role-specific accessories
 * Pure canvas 2D, programmatic pixel art
 */
import { BEE_ROLES } from './bee-roles.js';

export class BeeRenderer {
  constructor(ctx, hexSize = 28) {
    this.ctx = ctx;
    this.hexSize = hexSize;
    this.beeW = 34;
    this.beeH = 24;
    this._miniCache = new Map(); // role -> OffscreenCanvas for mini avatars
  }

  /** Draw a bee at screen position with given role and state */
  drawBee(x, y, roleKey, state = 'idle', alpha = 1) {
    const role = BEE_ROLES[roleKey] || BEE_ROLES.idle;
    const paused = state === 'paused';
    const working = state === 'working' || state === 'responding';

    this.ctx.save();
    this.ctx.translate(x - this.beeW / 2, y - this.beeH / 2);
    this.ctx.globalAlpha = paused ? 0.35 : alpha;

    // Body stripes
    this._drawBody(role.color);
    // Head
    this._drawHead();
    // Antennae
    this._drawAntennae();
    // Eyes
    this._drawEyes();
    // Wings
    this._drawWings(working);
    // Role accessory
    this._drawAccessory(roleKey);
    // State indicator (working pulse)
    if (working) this._drawWorkingPulse();

    this.ctx.restore();
  }

  /** Draw mini avatar (24x24) for chat messages */
  drawMiniAvatar(ctx, roleKey, size = 24) {
    const cacheKey = `${roleKey}-${size}`;
    if (!this._miniCache.has(cacheKey)) {
      const canvas = new OffscreenCanvas(size, size);
      const c = canvas.getContext('2d');
      const scale = size / 24;
      c.scale(scale, scale);
      this._drawMiniBee(c, roleKey, 1);
      this._miniCache.set(cacheKey, canvas);
    }
    ctx.drawImage(this._miniCache.get(cacheKey), 0, 0, size, size);
  }

  /** Draw bee name label below */
  drawLabel(x, y, nodeId, roleKey, paused) {
    const role = BEE_ROLES[roleKey] || BEE_ROLES.idle;
    this.ctx.save();
    this.ctx.globalAlpha = 1;
    this.ctx.fillStyle = paused ? '#f66' : role.color;
    this.ctx.font = '10px monospace';
    this.ctx.textAlign = 'center';
    this.ctx.fillText(nodeId.replace(/-.*/, ''), x, y + this.beeH / 2 + 14);
    this.ctx.restore();
  }

  /** Draw CPU/RAM bars below bee */
  drawBars(x, y, cpu, ram, maxRam = 8) {
    const bx = x - 30;
    const by = y + this.beeH / 2 + 20;
    this._drawBar(bx, by, 60, 5, Math.min(1, cpu / 100), '#f55');
    this._drawBar(bx, by + 7, 60, 5, 1 - Math.min(1, ram / maxRam), '#55f');
  }

  /** Draw pause indicator top-right */
  drawPauseIndicator(x, y, paused) {
    this.ctx.save();
    this.ctx.fillStyle = paused ? '#f55' : '#4caf50';
    this.ctx.beginPath();
    this.ctx.arc(x + this.beeW / 2 - 4, y - this.beeH / 2 - 4, 4, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.restore();
  }

  /** Draw active task indicator (yellow dot above) */
  drawTaskIndicator(x, y, active) {
    if (!active) return;
    this.ctx.save();
    this.ctx.fillStyle = '#ffeb3b';
    this.ctx.font = '9px monospace';
    this.ctx.textAlign = 'center';
    // Pulsing dot
    const pulse = Math.sin(Date.now() / 200) * 0.5 + 0.5;
    this.ctx.globalAlpha = 0.7 + pulse * 0.3;
    this.ctx.fillText('●', x, y - this.beeH / 2 - 10);
    this.ctx.restore();
  }

  // ===== Private drawing methods =====

  _drawBody(accentColor) {
    const stripes = 5;
    for (let i = 0; i < stripes; i++) {
      const sy = (i * this.beeH) / stripes;
      const sh = this.beeH / stripes;
      this.ctx.fillStyle = i % 2 === 0 ? accentColor : '#1a1a1a';
      this.ctx.fillRect(4, sy, this.beeW - 8, sh);
      this.ctx.strokeStyle = '#000';
      this.ctx.lineWidth = 1;
      this.ctx.strokeRect(4, sy, this.beeW - 8, sh);
    }
  }

  _drawHead() {
    this.ctx.fillStyle = '#1a1a1a';
    this.ctx.beginPath();
    this.ctx.arc(this.beeW / 2, 6, 8, 0, Math.PI * 2);
    this.ctx.fill();
  }

  _drawAntennae() {
    this.ctx.strokeStyle = '#1a1a1a';
    this.ctx.lineWidth = 1.5;
    this.ctx.lineCap = 'round';
    this.ctx.beginPath();
    this.ctx.moveTo(this.beeW / 2 - 2, 4);
    this.ctx.lineTo(this.beeW / 2 - 6, -4);
    this.ctx.moveTo(this.beeW / 2 + 2, 4);
    this.ctx.lineTo(this.beeW / 2 + 6, -4);
    this.ctx.stroke();
  }

  _drawEyes() {
    // Whites
    this.ctx.fillStyle = '#fff';
    this.ctx.beginPath();
    this.ctx.arc(this.beeW / 2 - 3, 5, 2, 0, Math.PI * 2);
    this.ctx.arc(this.beeW / 2 + 3, 5, 2, 0, Math.PI * 2);
    this.ctx.fill();
    // Pupils
    this.ctx.fillStyle = '#000';
    this.ctx.beginPath();
    this.ctx.arc(this.beeW / 2 - 3, 5, 0.7, 0, Math.PI * 2);
    this.ctx.arc(this.beeW / 2 + 3, 5, 0.7, 0, Math.PI * 2);
    this.ctx.fill();
  }

  _drawWings(working) {
    this.ctx.fillStyle = 'rgba(220,230,240,0.55)';
    const wingY = this.beeH / 2;
    const flap = working ? Math.sin(Date.now() / 80) * 3 : 0;

    // Left wing
    this.ctx.beginPath();
    this.ctx.ellipse(2, wingY, 6 + flap, 10, -0.3, 0, Math.PI * 2);
    this.ctx.fill();
    // Right wing
    this.ctx.beginPath();
    this.ctx.ellipse(this.beeW - 2, wingY, 6 + flap, 10, 0.3, 0, Math.PI * 2);
    this.ctx.fill();
  }

  _drawAccessory(roleKey) {
    switch (roleKey) {
      case 'juiz': this._drawToga(); break;
      case 'guarda': this._drawPoliceHat(); break;
      case 'bibliotecaria': this._drawGlassesBooks(); break;
      case 'artista': this._drawLabcoatPalette(); break;
      case 'trabalhadora': this._drawHelmet(); break;
    }
  }

  _drawToga() {
    // Cape
    this.ctx.fillStyle = '#1a1a1a';
    this.ctx.fillRect(0, this.beeH - 6, this.beeW, 6);
    // Gold trim
    this.ctx.fillStyle = '#ffd700';
    this.ctx.fillRect(this.beeW / 2 - 2, this.beeH - 6, 4, 2);
    // Q badge
    this.ctx.fillStyle = '#4caf50';
    this.ctx.font = 'bold 8px monospace';
    this.ctx.textAlign = 'center';
    this.ctx.fillText('⚖', this.beeW / 2, this.beeH - 1);
  }

  _drawPoliceHat() {
    // Hat brim
    this.ctx.fillStyle = '#1565c0';
    this.ctx.fillRect(this.beeW / 2 - 9, -3, 18, 4);
    // Hat crown
    this.ctx.fillRect(this.beeW / 2 - 6, -7, 12, 5);
    // Badge
    this.ctx.fillStyle = '#ffd700';
    this.ctx.beginPath();
    this.ctx.arc(this.beeW / 2, -5, 2.5, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.fillStyle = '#1565c0';
    this.ctx.font = 'bold 6px monospace';
    this.ctx.textAlign = 'center';
    this.ctx.fillText('🛡', this.beeW / 2, -3);
  }

  _drawGlassesBooks() {
    // Glasses
    this.ctx.strokeStyle = '#55f';
    this.ctx.lineWidth = 1.5;
    this.ctx.beginPath();
    this.ctx.arc(this.beeW / 2 - 4, 5, 3.5, 0, Math.PI * 2);
    this.ctx.arc(this.beeW / 2 + 4, 5, 3.5, 0, Math.PI * 2);
    this.ctx.stroke();
    // Bridge
    this.ctx.beginPath();
    this.ctx.moveTo(this.beeW / 2 - 0.5, 5);
    this.ctx.lineTo(this.beeW / 2 + 0.5, 5);
    this.ctx.stroke();

    // Books on back
    this.ctx.fillStyle = '#7b1fa2';
    this.ctx.fillRect(this.beeW / 2 - 6, this.beeH - 10, 12, 8);
    this.ctx.fillStyle = '#e1bee7';
    this.ctx.fillRect(this.beeW / 2 - 5, this.beeH - 9, 3, 6);
    this.ctx.fillRect(this.beeW / 2 - 1, this.beeH - 9, 3, 6);
    this.ctx.fillRect(this.beeW / 2 + 3, this.beeH - 9, 3, 6);
  }

  _drawLabcoatPalette() {
    // Lab coat
    this.ctx.fillStyle = '#fff';
    this.ctx.fillRect(2, this.beeH - 10, this.beeW - 4, 8);
    // Coat buttons
    this.ctx.fillStyle = '#1a1a1a';
    this.ctx.fillRect(this.beeW / 2 - 1, this.beeH - 9, 2, 2);
    this.ctx.fillRect(this.beeW / 2 - 1, this.beeH - 5, 2, 2);
    // Palette
    this.ctx.fillStyle = '#e91e63';
    this.ctx.beginPath();
    this.ctx.ellipse(this.beeW - 4, this.beeH - 3, 5, 4, 0, 0, Math.PI * 2);
    this.ctx.fill();
    // Paint dots
    this.ctx.fillStyle = '#fff';
    this.ctx.beginPath();
    this.ctx.arc(this.beeW - 5, this.beeH - 3, 1, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.fillStyle = '#ffeb3b';
    this.ctx.beginPath();
    this.ctx.arc(this.beeW - 3, this.beeH - 4, 1, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.fillStyle = '#4caf50';
    this.ctx.beginPath();
    this.ctx.arc(this.beeW - 4, this.beeH - 5, 1, 0, Math.PI * 2);
    this.ctx.fill();
  }

  _drawHelmet() {
    // Helmet shell
    this.ctx.fillStyle = '#ffb300';
    this.ctx.fillRect(this.beeW / 2 - 7, -2, 14, 6);
    // Helmet ridge
    this.ctx.fillStyle = '#1a1a1a';
    this.ctx.fillRect(this.beeW / 2 - 5, 2, 10, 3);
    // Reflector strip
    this.ctx.fillStyle = '#fff8';
    this.ctx.fillRect(this.beeW / 2 - 6, -1, 12, 1.5);
  }

  _drawWorkingPulse() {
    const pulse = (Math.sin(Date.now() / 150) + 1) / 2; // 0-1
    this.ctx.strokeStyle = `rgba(76, 175, 80, ${0.3 + pulse * 0.4})`;
    this.ctx.lineWidth = 2;
    this.ctx.beginPath();
    this.ctx.arc(this.beeW / 2, this.beeH / 2, this.beeW / 2 + 4 + pulse * 4, 0, Math.PI * 2);
    this.ctx.stroke();
  }

  _drawMiniBee(ctx, roleKey, alpha) {
    const role = BEE_ROLES[roleKey] || BEE_ROLES.idle;
    const w = 24, h = 18;

    ctx.save();
    ctx.globalAlpha = alpha;

    // Body
    const stripes = 4;
    for (let i = 0; i < stripes; i++) {
      const sy = (i * h) / stripes;
      const sh = h / stripes;
      ctx.fillStyle = i % 2 === 0 ? role.color : '#1a1a1a';
      ctx.fillRect(3, sy, w - 6, sh);
    }
    // Head
    ctx.fillStyle = '#1a1a1a';
    ctx.beginPath();
    ctx.arc(w / 2, 4, 5, 0, Math.PI * 2);
    ctx.fill();
    // Eyes
    ctx.fillStyle = '#fff';
    ctx.beginPath();
    ctx.arc(w / 2 - 2, 3.5, 1.2, 0, Math.PI * 2);
    ctx.arc(w / 2 + 2, 3.5, 1.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.arc(w / 2 - 2, 3.5, 0.4, 0, Math.PI * 2);
    ctx.arc(w / 2 + 2, 3.5, 0.4, 0, Math.PI * 2);
    ctx.fill();
    // Role indicator
    ctx.fillStyle = role.color;
    ctx.font = 'bold 8px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(this._roleSymbol(roleKey), w / 2, h + 2);

    ctx.restore();
  }

  _roleSymbol(roleKey) {
    const symbols = { juiz: '⚖', guarda: '🛡', bibliotecaria: '📚', artista: '🎨', trabalhadora: '👷', idle: '🐝' };
    return symbols[roleKey] || '🐝';
  }

  _drawBar(x, y, w, h, frac, color) {
    this.ctx.fillStyle = '#222';
    this.ctx.fillRect(x, y, w, h);
    this.ctx.fillStyle = color;
    this.ctx.fillRect(x, y, Math.max(0, Math.min(1, frac)) * w, h);
    this.ctx.strokeStyle = '#000';
    this.ctx.strokeRect(x, y, w, h);
  }
}