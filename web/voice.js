/**
 * VoiceController — STT/TTS offline-first (Enxame CPU)
 * - STT: MediaRecorder -> POST /api/v1/audio/transcribe -> texto no #msg
 * - TTS: POST /api/v1/audio/synthesize -> toca áudio (blob ou base64)
 * Degradação graciosa quando microfone/endpoint indisponível.
 */
import { transcribeAudio, synthesizeSpeech, fetchAudioCaps } from './api.js';
import { audio } from './audio.js';

export class VoiceController {
  constructor({ onTranscript, onStateChange } = {}) {
    this.onTranscript = onTranscript || (() => {});
    this.onStateChange = onStateChange || (() => {});
    this.recBtn = document.getElementById('voice-record');
    this.speakBtn = document.getElementById('voice-speak');
    this.recState = document.getElementById('voice-rec-state');
    this._recorder = null;
    this._chunks = [];
    this._recording = false;
    this._caps = null;
    this._player = new Audio();
    this._bind();
  }

  _bind() {
    this.recBtn?.addEventListener('click', () => this.toggleRecording());
    this.speakBtn?.addEventListener('click', () => this.speakLastAssistant());
  }

  async init() {
    try {
      this._caps = await fetchAudioCaps();
    } catch {
      this._caps = { stt: { available: true }, tts: { available: true } };
    }
    const micOk = !!(navigator.mediaDevices?.getUserMedia) && window.MediaRecorder;
    if (!micOk && this.recBtn) {
      this.recBtn.disabled = true;
      this.recBtn.title = 'Microfone indisponível neste navegador';
    }
    this._setState('idle');
  }

  _setState(s, hint = '') {
    this._state = s;
    this.recBtn?.classList.toggle('recording', s === 'recording');
    this.recBtn?.classList.toggle('busy', s === 'transcribing');
    if (this.recState) {
      this.recState.textContent =
        s === 'recording' ? '● gravando… clique para parar' :
        s === 'transcribing' ? '⏳ transcrevendo na CPU…' :
        s === 'speaking' ? '🔊 falando…' : (hint || '');
    }
    this.onStateChange(s);
  }

  async toggleRecording() {
    if (this._recording) { this.stopRecording(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : '';
      this._recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      this._chunks = [];
      this._recorder.ondataavailable = (e) => { if (e.data.size) this._chunks.push(e.data); };
      this._recorder.onstop = () => this._handleRecordingStop(stream);
      this._recorder.start();
      this._recording = true;
      this._setState('recording');
      audio.play('click');
    } catch (err) {
      this.onTranscript('', `Microfone bloqueado: ${err.message}`);
    }
  }

  stopRecording() {
    if (this._recorder && this._recording) {
      this._recording = false;
      this._setState('transcribing');
      this._recorder.stop();
    }
  }

  async _handleRecordingStop(stream) {
    stream.getTracks().forEach(t => t.stop());
    try {
      const blob = new Blob(this._chunks, { type: this._recorder.mimeType || 'audio/webm' });
      if (!blob.size) throw new Error('áudio vazio');
      const res = await transcribeAudio(blob, 'gravacao.webm', 'pt');
      const text = (res.text || '').trim();
      this._setState('idle');
      if (text) {
        this.onTranscript(text, '');
        audio.play('done');
      } else {
        this.onTranscript('', 'Não entendi o áudio. Tente falar mais perto do microfone.');
      }
    } catch (err) {
      this._setState('idle');
      this.onTranscript('', `Falha no STT: ${err.message}`);
    }
  }

  async speak(text) {
    const clean = String(text || '').replace(/[#*`_>\[\]()!]/g, '').trim().slice(0, 1200);
    if (!clean) return false;
    try {
      this._setState('speaking');
      const res = await synthesizeSpeech(clean, 'pt-BR');
      let objectUrl = null;
      if (res.audio_blob) {
        objectUrl = URL.createObjectURL(res.audio_blob);
      } else if (res.audio_base64) {
        const bin = atob(res.audio_base64);
        const buf = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
        objectUrl = URL.createObjectURL(new Blob([buf], { type: res.content_type || 'audio/wav' }));
      }
      if (objectUrl) {
        await new Promise((resolve) => {
          this._player.onended = resolve;
          this._player.onerror = resolve;
          this._player.src = objectUrl;
          this._player.play().catch(resolve);
        });
        URL.revokeObjectURL(objectUrl);
      } else if (res.text && 'speechSynthesis' in window) {
        // Fallback: navegador lê em voz alta quando TTS local indisponível
        await new Promise((resolve) => {
          const u = new SpeechSynthesisUtterance(res.text || clean);
          u.lang = 'pt-BR';
          u.onend = resolve; u.onerror = resolve;
          speechSynthesis.speak(u);
        });
      }
      this._setState('idle');
      return true;
    } catch (err) {
      this._setState('idle');
      console.warn('TTS falhou:', err);
      return false;
    }
  }

  speakLastAssistant() {
    const items = document.querySelectorAll('#transcript .msg.assistant .msg-text');
    const last = items.length ? items[items.length - 1].textContent : '';
    if (last) this.speak(last);
  }
}
