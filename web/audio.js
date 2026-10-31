/**
 * Audio - Simple Web Audio API synthesis for bzz sounds
 * No external files, pure synthesis
 */
class AudioEngine {
  constructor() {
    this.ctx = null;
    this.enabled = true;
    this._initPromise = null;
  }

  async init() {
    if (this.ctx) return;
    this._initPromise = (async () => {
      try {
        this.ctx = new (window.AudioContext || window.webkitAudioContext)();
        // Resume on user interaction (autoplay policy)
        document.addEventListener('click', () => this.resume(), { once: true });
        document.addEventListener('keydown', () => this.resume(), { once: true });
      } catch (e) {
        console.warn('Web Audio not available:', e);
        this.enabled = false;
      }
    })();
    return this._initPromise;
  }

  async resume() {
    if (this.ctx && this.ctx.state === 'suspended') await this.ctx.resume();
  }

  // Generate a single "bzz" tone
  _playTone(freq, duration, type = 'square', gain = 0.08, delay = 0) {
    if (!this.enabled || !this.ctx) return;
    const now = this.ctx.currentTime + delay;
    const osc = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    g.gain.value = gain;
    osc.connect(g).connect(this.ctx.destination);
    osc.start(now);
    osc.stop(now + duration);
  }

  // Patterns: 1=task received, 2=completed, 3=error
  async play(pattern) {
    await this.init();
    if (!this.enabled) return;

    switch (pattern) {
      case 'task': // single short bzz
        this._playTone(180, 0.12, 'sawtooth', 0.06);
        this._playTone(220, 0.1, 'square', 0.04, 0.02);
        break;
      case 'done': // double bzz (ascending)
        this._playTone(220, 0.1, 'square', 0.06);
        this._playTone(330, 0.1, 'square', 0.06, 0.12);
        this._playTone(440, 0.08, 'sine', 0.04, 0.2);
        break;
      case 'error': // triple bzz (descending, harsh)
        this._playTone(150, 0.15, 'sawtooth', 0.08);
        this._playTone(120, 0.15, 'sawtooth', 0.08, 0.18);
        this._playTone(90, 0.2, 'sawtooth', 0.1, 0.36);
        break;
      case 'click': // UI click
        this._playTone(800, 0.02, 'sine', 0.02);
        break;
      default:
        this._playTone(200, 0.1, 'square', 0.05);
    }
  }

  setEnabled(val) { this.enabled = val; }
}

export const audio = new AudioEngine();