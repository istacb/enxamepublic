/**
 * ChatController — transcript, SSE streaming, proveniência e voz (EIP-0010)
 */
import { store } from './store.js';
import { sendChat, streamChat, apiForm } from './api.js';
import { audio } from './audio.js';
import { BeeRenderer } from './bee-renderer.js';
import { getRole } from './bee-roles.js';
import { VoiceController } from './voice.js';

const SOURCE_LABEL = {
  rag_local: '📚 RAG local',
  rag_enxame: '🐝 RAG enxame',
  modelo_local: '💻 Modelo local (CPU)',
  internet_fallback: '🌐 Web (fallback)',
  estudio_cpu: '🎨 Estúdio CPU',
  guarda_local: '🛡️ Guarda local',
  sistema_offline: '📴 Offline',
};

export class ChatController {
  constructor() {
    this.transcript = document.getElementById('transcript');
    this.form = document.getElementById('chat-form');
    this.input = document.getElementById('msg');
    this.sendBtn = document.getElementById('send');
    this.clearBtn = document.getElementById('clear-chat');
    this.exportBtn = document.getElementById('export-chat');
    this.statusEl = document.getElementById('chat-status');
    this.pacingEl = document.getElementById('pacing-notice');
    this.convSelect = document.getElementById('conversation-select');
    this.profileSelect = document.getElementById('profile-select');
    this.targetSelect = document.getElementById('target-node');
    this.newConvBtn = document.getElementById('new-conversation');
    this.attachBtn = document.getElementById('attach-btn');
    this.fileInput = document.getElementById('file-input');

    this._streaming = false;
    this._currentMsgEl = null;
    const offscreen = new OffscreenCanvas(24, 24);
    this._renderer = new BeeRenderer(offscreen.getContext('2d'), 24);

    this.voice = new VoiceController({
      onTranscript: (text, err) => {
        if (text) { this.input.value = text; this.input.focus(); }
        if (err) this._addMessage(err, 'system err');
      },
    });

    this._bindEvents();
  }

  _bindEvents() {
    this.form.addEventListener('submit', e => {
      e.preventDefault();
      this.send();
    });

    this.clearBtn.addEventListener('click', () => this.clear());
    this.exportBtn.addEventListener('click', () => this.export());
    this.input.addEventListener('input', () => this._autoResize());
    this.newConvBtn?.addEventListener('click', () => {
      if (this.convSelect) this.convSelect.value = '';
      this.clear(false);
      this._addMessage('Nova conversa iniciada. O histórico anterior continua salvo em Memória & Conhecimento.', 'system');
    });
    this.convSelect?.addEventListener('change', () => this.clear(false));
    this.attachBtn?.addEventListener('click', () => this.fileInput?.click());
    this.fileInput?.addEventListener('change', () => this._uploadFiles());
  }

  setConversations(list) {
    if (!this.convSelect) return;
    const current = this.convSelect.value;
    this.convSelect.innerHTML = '<option value="">Nova conversa</option>' +
      (list || []).map(c =>
        `<option value="${c.id}">${this._esc(c.title || 'Conversa')} (${c.message_count || 0})</option>`
      ).join('');
    if (current) this.convSelect.value = current;
  }

  setTargetNodes(nodes) {
    if (!this.targetSelect) return;
    const current = this.targetSelect.value || 'auto';
    this.targetSelect.innerHTML = '<option value="auto">Máquina: auto</option>' +
      (nodes || []).map(n =>
        `<option value="${this._esc(n.node_id)}">${this._esc(n.alias || n.node_id)}${n.is_local ? ' (local)' : ''}</option>`
      ).join('');
    this.targetSelect.value = current;
  }

  showPacing(notice, tierLabel) {
    if (!this.pacingEl) return;
    if (notice) {
      this.pacingEl.hidden = false;
      this.pacingEl.textContent = `⏳ ${tierLabel ? `[${tierLabel}] ` : ''}${notice}`;
    } else {
      this.pacingEl.hidden = true;
    }
  }

  /** Send message to enxame */
  async send() {
    const text = this.input.value.trim();
    if (!text || this._streaming) return;

    this.input.value = '';
    this._autoResize();
    this._addMessage(text, 'user');
    this._setStreaming(true);

    const extra = {};
    if (this.convSelect?.value) extra.conversation_id = this.convSelect.value;
    if (this.profileSelect?.value && this.profileSelect.value !== 'auto') extra.profile = this.profileSelect.value;
    if (this.targetSelect?.value && this.targetSelect.value !== 'auto') extra.target_node = this.targetSelect.value;

    try {
      const queued = await sendChat(text, extra);
      if (queued.conversation_id && this.convSelect && !this.convSelect.value) {
        // Nova conversa criada no servidor: registra na lista
        const opt = document.createElement('option');
        opt.value = queued.conversation_id;
        opt.textContent = `${text.slice(0, 40)} (1)`;
        this.convSelect.appendChild(opt);
        this.convSelect.value = queued.conversation_id;
      }
      if (queued.pacing_notice) this.showPacing(queued.pacing_notice, queued.hardware_tier);
      await this._streamResponse(queued.task_id);
    } catch (err) {
      this._addMessage(`Erro ao enviar: ${err.message}`, 'system err');
      this._setStreaming(false);
    }
  }

  /** Stream response from SSE */
  async _streamResponse(taskId) {
    const es = streamChat(taskId);
    let started = false;
    let responseText = '';
    let nodeId = null;
    let role = null;
    let model = null;
    let conversationId = null;

    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);

        if (data.event === 'start') {
          nodeId = data.node_id || null;
          role = data.role || null;
          model = data.model || null;
          conversationId = data.conversation_id || null;
          if (data.pacing_notice) this.showPacing(data.pacing_notice, data.hardware_tier_label || data.hardware_tier);
        } else if (data.event === 'token') {
          if (!started) {
            this._removeTyping();
            started = true;
            this._currentMsgEl = this._addMessage('', 'assistant', nodeId, role, model);
          }
          responseText += data.content || data.text || '';
          this._updateMessageText(this._currentMsgEl, responseText);
        } else if (data.event === 'final') {
          const finalContent = data.content || data.answer || responseText || '(sem resposta)';
          if (!started) {
            this._removeTyping();
            started = true;
            this._currentMsgEl = this._addMessage(finalContent, 'assistant', nodeId, role, data.model || model);
          } else {
            this._updateMessageText(this._currentMsgEl, finalContent);
          }
          if (data.model && this._currentMsgEl) {
            const modelEl = this._currentMsgEl.querySelector('.msg-model');
            if (modelEl) modelEl.textContent = data.model;
          }
          this._attachProvenance(this._currentMsgEl, data);
          if (conversationId && this.convSelect && !this.convSelect.value) {
            const opt = document.createElement('option');
            opt.value = conversationId;
            opt.textContent = `Conversa ${conversationId.slice(0, 8)}`;
            this.convSelect.appendChild(opt);
            this.convSelect.value = conversationId;
          }
          store.incrementStat('calls');
          audio.play('done');
          this._setStreaming(false);
          es.close();
        } else if (data.event === 'end') {
          es.close();
          if (!started) { this._removeTyping(); this._setStreaming(false); }
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
      if (!started) {
        this._removeTyping();
        this._addMessage('Erro de conexão com o enxame.', 'system err');
        audio.play('error');
        this._setStreaming(false);
      }
      es.close();
    };

    this._addTyping();
  }

  /** Provenance stamp: máquina, papel, perfil, modelo, fonte, tempos */
  _attachProvenance(msgEl, data) {
    if (!msgEl) return;
    const prov = data.provenance || {};
    const bubble = msgEl.querySelector('.msg-bubble');
    if (!bubble) return;
    const old = bubble.querySelector('.msg-provenance');
    if (old) old.remove();

    const srcKey = data.source || prov.source_tier || '';
    const srcLabel = SOURCE_LABEL[srcKey] || srcKey || '—';
    const bits = [
      prov.machine_alias ? `🖥️ ${prov.machine_alias}` : null,
      prov.cluster_role ? `🎭 ${prov.cluster_role}` : null,
      prov.agent_profile ? `🧩 ${prov.agent_profile}` : null,
      (data.model || prov.model) ? `⚙️ ${data.model || prov.model}` : null,
      `📡 ${srcLabel}`,
    ].filter(Boolean);
    const times = [];
    if (prov.ttft_ms) times.push(`TTFT ${prov.ttft_ms}ms`);
    if (prov.total_ms) times.push(`total ${prov.total_ms}ms`);
    if (data.confidence !== undefined && data.confidence !== null) {
      times.push(`conf ${(Number(data.confidence) * 100).toFixed(0)}%`);
    }
    if (prov.guardian_action && prov.guardian_action !== 'ALLOW') {
      times.push(`🛡️ ${prov.guardian_action}`);
    }
    const div = document.createElement('div');
    div.className = 'msg-provenance';
    div.title = 'Proveniência auditável da resposta';
    div.innerHTML =
      `<span class="prov-bits">${bits.map(b => this._esc(b)).join(' · ')}</span>` +
      (times.length ? `<span class="prov-times">${times.map(t => this._esc(t)).join(' · ')}</span>` : '');
    // Fontes RAG (documentos consultados)
    const ragSources = prov.rag_sources || data.rag_sources || [];
    if (ragSources.length) {
      const src = document.createElement('div');
      src.className = 'prov-sources';
      src.textContent = `📚 Fontes: ${ragSources.slice(0, 4).join(', ')}`;
      div.appendChild(src);
    }
    bubble.appendChild(div);

    // Botão ouvir esta resposta
    const sender = bubble.querySelector('.msg-sender');
    if (sender && !sender.querySelector('.msg-speak')) {
      const btn = document.createElement('button');
      btn.className = 'msg-speak';
      btn.title = 'Ouvir esta resposta (TTS local)';
      btn.setAttribute('aria-label', 'Ouvir resposta');
      btn.textContent = '🔊';
      btn.addEventListener('click', () => {
        const txt = bubble.querySelector('.msg-text')?.textContent || '';
        this.voice.speak(txt);
      });
      sender.appendChild(btn);
    }
  }

  /** Add message to transcript */
  _addMessage(text, type, nodeId = null, role = null, model = null) {
    const div = document.createElement('div');
    div.className = `msg ${type}`;

    if (type === 'assistant' && nodeId) {
      const roleDef = getRole(role);
      const short = String(nodeId).replace(/-.*/, '');
      div.innerHTML = `
        <div class="msg-avatar">
          <canvas class="bee-mini" width="24" height="24" aria-hidden="true"></canvas>
        </div>
        <div class="msg-bubble">
          <span class="msg-sender">
            ${roleDef.emoji} ${this._esc(short)}
            <span class="msg-role-badge">${this._esc(roleDef.label.toUpperCase())}</span>
            ${model ? `<span class="msg-model" title="Modelo">${this._esc(model)}</span>` : ''}
          </span>
          <span class="msg-text"></span>
        </div>
      `;
      const miniCanvas = div.querySelector('.bee-mini');
      if (miniCanvas) {
        const ctx = miniCanvas.getContext('2d');
        this._renderer.drawMiniAvatar(ctx, roleDef.key, 24);
      }
      this._setRichText(div.querySelector('.msg-text'), text);
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
      div.classList.add('system');
      div.innerHTML = `
        <div class="msg-avatar" aria-hidden="true">🐝</div>
        <div class="msg-bubble"><span class="msg-text"></span></div>
      `;
      this._setRichText(div.querySelector('.msg-text'), text);
    }

    this.transcript.appendChild(div);
    this._scrollToBottom();
    return div;
  }

  /** Renderiza markdown seguro: imagens ![alt](url), **negrito**, `código`, quebras */
  _setRichText(el, text) {
    if (!el) return;
    const raw = String(text || '');
    // Escapa HTML e depois libera construções markdown seguras
    let html = raw
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    html = html
      .replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (_m, alt, src) => {
        const safe = /^(\/|https?:)/.test(src) ? src : '';
        return safe ? `<img class="msg-img" src="${safe}" alt="${alt}" loading="lazy">` : alt;
      })
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
    el.innerHTML = html;
  }

  _esc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  async _uploadFiles() {
    const files = this.fileInput?.files;
    if (!files || !files.length) return;
    const fd = new FormData();
    for (const f of files) fd.append('file', f, f.name);
    fd.append('index_rag', '1');
    this._addMessage(`📎 Enviando ${files.length} arquivo(s) para o RAG…`, 'system');
    try {
      const res = await apiForm('/api/v1/upload', fd);
      const n = (res.rag_indexed || []).length;
      this._addMessage(`✅ ${files.length} arquivo(s) processado(s); ${n} indexado(s) no RAG local e sincronizado(s) com o Bibliotecário.`, 'system');
      audio.play('done');
    } catch (err) {
      this._addMessage(`Falha no upload: ${err.message}`, 'system err');
    } finally {
      this.fileInput.value = '';
    }
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
      if (el) el.textContent = '.'.repeat((i % 3) + 1);
      i++;
    }, 400);
  }

  _updateMessageText(msgEl, text) {
    const textEl = msgEl.querySelector('.msg-text');
    if (textEl) this._setRichText(textEl, text);
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

  clear(withWelcome = true) {
    this.transcript.innerHTML = withWelcome ? `
      <div class="msg system welcome">
        <span class="msg-icon" aria-hidden="true">🐝</span>
        <span>Conversa limpa. Pergunte o que quiser.</span>
      </div>
    ` : '';
  }

  export() {
    const messages = Array.from(this.transcript.querySelectorAll('.msg')).map(el => {
      const type = el.classList.contains('user') ? 'user' :
                   el.classList.contains('assistant') ? 'assistant' : 'system';
      const text = el.querySelector('.msg-text')?.textContent || '';
      const sender = el.querySelector('.msg-sender')?.textContent || '';
      const provenance = el.querySelector('.msg-provenance')?.textContent || '';
      return { type, sender, text, provenance, timestamp: new Date().toISOString() };
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
