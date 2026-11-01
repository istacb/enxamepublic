/**
 * ChatController - Manages transcript, streaming, input
 */
import { store } from './store.js';
import { api, sendChat, streamChat } from './api.js';
import { audio } from './audio.js';
import { BeeRenderer } from './bee-renderer.js';
import { getRole, getRoleEmoji, getRoleColor } from './bee-roles.js';

export class ChatController {
  constructor() {
    this.transcript = document.getElementById('transcript');
    this.form = document.getElementById('chat-form');
    this.input = document.getElementById('msg');
    this.sendBtn = document.getElementById('send');
    this.clearBtn = document.getElementById('clear-chat');
    this.exportBtn = document.getElementById('export-chat');
    this.statusEl = document.getElementById('chat-status');

    this._streaming = false;
    this._currentMsgEl = null;
    // Offscreen canvas for mini avatars
    const offscreen = new OffscreenCanvas(24, 24);
    this._renderer = new BeeRenderer(offscreen.getContext('2d'), 24);

    this._bindEvents();
  }

  _bindEvents() {
    this.form.addEventListener('submit', e => {
      e.preventDefault();
      this.send();
    });

    this.clearBtn.addEventListener('click', () => this.clear());
    this.exportBtn.addEventListener('click', () => this.export());

    // Auto-resize input
    this.input.addEventListener('input', () => this._autoResize());
  }

  /** Send message to enxame */
  async send() {
    const text = this.input.value.trim();
    if (!text || this._streaming) return;

    this.input.value = '';
    this._autoResize();
    this._addMessage(text, 'user');
    this._setStreaming(true);

    try {
      const { task_id } = await sendChat(text);
      await this._streamResponse(task_id);
    } catch (err) {
      this._addMessage(`Erro ao enviar: ${err.message}`, 'system err');
      this._setStreaming(false);
    }
  }

  /** Stream response from SSE */
  async _streamResponse(taskId) {
    const es = streamChat(taskId);
    let done = false;
    let responseText = '';
    let nodeId = null;
    let role = null;
    let model = null;

    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);

        if (data.event === 'start') {
          nodeId = data.node_id || null;
          role = data.role || null;
          model = data.model || null;
        } else if (data.event === 'token') {
          if (!done) {
            this._removeTyping();
            done = true;
            this._currentMsgEl = this._addMessage('', 'assistant', nodeId, role, model);
          }
          responseText += data.content;
          this._updateMessageText(this._currentMsgEl, responseText);
        } else if (data.event === 'final') {
          if (!done) {
            this._removeTyping();
            done = true;
            this._currentMsgEl = this._addMessage(data.content || '(sem resposta)', 'assistant', nodeId, role, model);
          } else {
            this._updateMessageText(this._currentMsgEl, data.content || responseText);
          }
          store.incrementStat('calls');
          audio.play('done');
          this._setStreaming(false);
          es.close();
        } else if (data.event === 'error') {
          this._removeTyping();
          this._addMessage(`Erro: ${data.message}`, 'system err');
          audio.play('error');
          this._setStreaming(false);
          es.close();
        }
      } catch (e) {
        console.warn('Stream parse error:', e);
      }
    };

    es.onerror = () => {
      if (!done) {
        this._removeTyping();
        this._addMessage('Erro de conexão com o enxame.', 'system err');
        audio.play('error');
        this._setStreaming(false);
      }
      es.close();
    };

    // Show typing indicator
    this._addTyping();
  }

  /** Add message to transcript */
  _addMessage(text, type, nodeId = null, role = null, model = null) {
    const div = document.createElement('div');
    div.className = `msg ${type}`;

    if (type === 'assistant' && nodeId) {
      // Assistant message with avatar
      const roleDef = getRole(role);
      div.innerHTML = `
        <div class="msg-avatar">
          <canvas class="bee-mini" width="24" height="24" aria-hidden="true"></canvas>
        </div>
        <div class="msg-bubble">
          <span class="msg-sender">
            ${roleDef.emoji} ${nodeId.replace(/-.*/, '')}
            <span class="msg-role-badge">${roleDef.label.toUpperCase()}</span>
            ${model ? `<span class="msg-model" title="Modelo">${model}</span>` : ''}
          </span>
          <span class="msg-text"></span>
        </div>
      `;
      // Draw mini avatar
      const miniCanvas = div.querySelector('.bee-mini');
      if (miniCanvas) {
        const ctx = miniCanvas.getContext('2d');
        this._renderer.drawMiniAvatar(ctx, roleDef.key, 24);
      }
      const textEl = div.querySelector('.msg-text');
      textEl.textContent = text;
    } else if (type === 'user') {
      div.innerHTML = `
        <div class="msg-avatar" aria-hidden="true">👤</div>
        <div class="msg-bubble">
          <span class="msg-sender">Você</span>
          <span class="msg-text"></span>
        </div>
      `;
      div.querySelector('.msg-text').textContent = text;
    } else {
      // System message
      div.classList.add('system');
      div.innerHTML = `
        <div class="msg-avatar" aria-hidden="true">🐝</div>
        <div class="msg-bubble"><span class="msg-text"></span></div>
      `;
      div.querySelector('.msg-text').textContent = text;
    }

    this.transcript.appendChild(div);
    this._scrollToBottom();
    return div;
  }

  _addTyping() {
    const div = document.createElement('div');
    div.className = 'msg system typing';
    div.id = 'typing-indicator';
    div.innerHTML = `
      <div class="msg-avatar" aria-hidden="true">🐝</div>
      <div class="msg-bubble"><span class="msg-text">enxame processando<span class="dots">...</span></span></div>
    `;
    this.transcript.appendChild(div);
    this._scrollToBottom();
    this._animateDots(div.querySelector('.dots'));
  }

  _removeTyping() {
    const typing = document.getElementById('typing-indicator');
    if (typing) typing.remove();
  }

  _animateDots(el) {
    let i = 0;
    const interval = setInterval(() => {
      if (!document.getElementById('typing-indicator')) { clearInterval(interval); return; }
      el.textContent = '.'.repeat((i % 3) + 1);
      i++;
    }, 400);
  }

  _updateMessageText(msgEl, text) {
    const textEl = msgEl.querySelector('.msg-text');
    if (textEl) textEl.textContent = text;
    this._scrollToBottom();
  }

  _setStreaming(streaming) {
    this._streaming = streaming;
    this.sendBtn.disabled = streaming;
    this.input.disabled = streaming;
    if (!streaming) this.input.focus();
  }

  _scrollToBottom() {
    this.transcript.scrollTop = this.transcript.scrollHeight;
  }

  _autoResize() {
    this.input.style.height = 'auto';
    this.input.style.height = Math.min(this.input.scrollHeight, 120) + 'px';
  }

  clear() {
    this.transcript.innerHTML = `
      <div class="msg system welcome">
        <span class="msg-icon" aria-hidden="true">🐝</span>
        <span>Conversa limpa. Pergunte o que quiser.</span>
      </div>
    `;
  }

  export() {
    const messages = Array.from(this.transcript.querySelectorAll('.msg')).map(el => {
      const type = el.classList.contains('user') ? 'user' :
                   el.classList.contains('assistant') ? 'assistant' : 'system';
      const text = el.querySelector('.msg-text')?.textContent || '';
      const sender = el.querySelector('.msg-sender')?.textContent || '';
      return { type, sender, text, timestamp: new Date().toISOString() };
    });
    const blob = new Blob([JSON.stringify(messages, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `enxame-chat-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  /** Update connection status indicator */
  setConnected(connected) {
    this.statusEl.classList.toggle('disconnected', !connected);
    this.statusEl.querySelector('span:last-child').textContent = connected ? 'Conectado' : 'Desconectado';
  }
}