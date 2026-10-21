// Enxame UI — piso pixel-art (canvas puro, zero dependências).
// Backend: /api/session, /api/status, /api/chat, /api/chat/stream/{id},
// /api/node/{id}/pause, /api/cluster/discover, /api/cluster/models.
const CANVAS = document.getElementById('hive');
const CTX = CANVAS.getContext('2d');
const NODE_LIST = document.getElementById('node-list');
const TRANSCRIPT = document.getElementById('transcript');
const MSG = document.getElementById('msg');
const SEND = document.getElementById('send');
const PAUSE_ALL = document.getElementById('pause-all');
const CLUSTER_LABEL = document.getElementById('cluster-label');
const DISCOVER_BTN = document.getElementById('discover-btn');
const DISCOVERY_RESULT = document.getElementById('discovery-result');
const MODEL_LIST = document.getElementById('model-list');

let sessionToken = null;
let nodes = [];
let pausedNodes = new Set();
let pausedAll = false;
let tasksTotal = 0;
let calls = 0;
let nacks = 0;

const HEX = 38;
const CX = CANVAS.width / 2;
const CY = CANVAS.height / 2 - 20;

async function api(path, { method = 'GET', body } = {}) {
  const headers = {};
  if (sessionToken) headers['x-session-token'] = sessionToken;
  const opts = { method, headers };
  if (body) { headers['content-type'] = 'application/json'; opts.body = JSON.stringify(body); }
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function init() {
  // /api/session é POST (rota registrada em bees/service.py). O default de api() é GET,
  // então isto devolvia 404, o throw abortava init() antes de registrar os
  // setInterval/listeners, sessionToken ficava vazio e sendMessage() saía em
  // `if (!sessionToken) return` — a UI carregava mas NADA funcionava.
  try {
    const { token } = await api('/api/session', { method: 'POST' });
    sessionToken = token;
  } catch (e) {
    console.error('Falha ao criar sessão:', e);
    CLUSTER_LABEL.textContent = 'cluster: sem sessão';
  }
  loadStatus();
  loadModels();
  setInterval(loadStatus, 2000);
  setInterval(loadModels, 10000);

  PAUSE_ALL.addEventListener('click', () => {
    pausedAll = !pausedAll;
    PAUSE_ALL.classList.toggle('active', pausedAll);
    draw();
  });

  DISCOVER_BTN.addEventListener('click', async () => {
    DISCOVER_BTN.disabled = true;
    DISCOVER_BTN.textContent = 'Descobrindo…';
    try {
      const { peers } = await api('/api/cluster/discover');
      DISCOVERY_RESULT.innerHTML = peers.map(p =>
        `<div style="font-size:0.75rem;margin:2px 0;">${p.node_id} @ ${p.ip}:${p.ws_port} · ${p.role} · ${p.models.join(', ') || '—'}</div>`
      ).join('') || '<div style="font-size:0.75rem;color:#888;">Nenhum peer encontrado na rede</div>';
    } catch (e) {
      DISCOVERY_RESULT.textContent = 'Erro na descoberta: ' + e.message;
    } finally {
      DISCOVER_BTN.disabled = false;
      DISCOVER_BTN.textContent = 'DESCOBRIR REDE';
    }
  });

  SEND.addEventListener('click', sendMessage);
  MSG.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendMessage(); });
}

async function loadStatus() {
  try {
    const st = await api('/api/status');
    nodes = st.agents || [];
    tasksTotal = st.tasks_total || 0;
    CLUSTER_LABEL.textContent = `cluster: ${st.node} · ${nodes.length} nó${nodes.length !== 1 ? 's' : ''}`;
    document.getElementById('c-tasks').textContent = tasksTotal;
    drawNodesList();
    draw();
  } catch (e) {
    // offline: mantém último estado
  }
}

async function loadModels() {
  try {
    const { models, best } = await api('/api/cluster/models');
    MODEL_LIST.innerHTML = models.map(m =>
      `<div style="font-size:0.75rem;margin:2px 0;${m.name === best ? 'color:#0f0;font-weight:bold' : 'color:#aaa'}">● ${m.name} (${m.size_mb.toFixed(1)} MB)${m.name === best ? ' — principal' : ''}</div>`
    ).join('') || '<div style="font-size:0.75rem;color:#888;">Nenhum modelo Ollama instalado</div>';
  } catch (e) {
    MODEL_LIST.textContent = '—';
  }
}

function draw() {
  CTX.clearRect(0, 0, CANVAS.width, CANVAS.height);

  CTX.strokeStyle = '#1a1a1a';
  CTX.lineWidth = 1;
  for (let x = 0; x <= CANVAS.width; x += 40) { CTX.beginPath(); CTX.moveTo(x, 0); CTX.lineTo(x, CANVAS.height); CTX.stroke(); }
  for (let y = 0; y <= CANVAS.height; y += 40) { CTX.beginPath(); CTX.moveTo(0, y); CTX.lineTo(CANVAS.width, y); CTX.stroke(); }

  const n = nodes.length || 1;
  const radius = Math.min(CX, CY) - 60;
  nodes.forEach((node, i) => {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    const x = CX + radius * Math.cos(a);
    const y = CY + radius * Math.sin(a);
    drawNode(x, y, node);
  });
}

function drawNode(x, y, node) {
  const paused = pausedAll || pausedNodes.has(node.node_id);
  const isQueen = node.cluster_role === 'juiz';
  const isLibrarian = node.cluster_role === 'bibliotecaria';
  const alpha = paused ? 0.35 : 1;

  // ---- Corpo da abelha (pixel art) ----
  const bw = 34, bh = 24; // corpo
  CTX.save();
  CTX.translate(x - bw / 2, y - bh / 2);
  CTX.globalAlpha = alpha;

  // listras amarelo / preto
  const stripes = 5;
  for (let i = 0; i < stripes; i++) {
    const sy = (i * bh) / stripes;
    const sh = bh / stripes;
    CTX.fillStyle = i % 2 === 0 ? '#ffd700' : '#1a1a1a';
    CTX.fillRect(4, sy, bw - 8, sh);
    // borda da listra
    CTX.strokeStyle = '#000';
    CTX.lineWidth = 1;
    CTX.strokeRect(4, sy, bw - 8, sh);
  }

  // cabeça
  CTX.fillStyle = '#1a1a1a';
  CTX.beginPath();
  CTX.arc(bw / 2, 6, 8, 0, Math.PI * 2);
  CTX.fill();

  // antenas
  CTX.strokeStyle = '#1a1a1a';
  CTX.lineWidth = 1.5;
  CTX.beginPath();
  CTX.moveTo(bw / 2 - 2, 4);
  CTX.lineTo(bw / 2 - 6, -4);
  CTX.moveTo(bw / 2 + 2, 4);
  CTX.lineTo(bw / 2 + 6, -4);
  CTX.stroke();

  // olhos (branco + pupila)
  CTX.fillStyle = '#fff';
  CTX.beginPath();
  CTX.arc(bw / 2 - 3, 5, 2, 0, Math.PI * 2);
  CTX.arc(bw / 2 + 3, 5, 2, 0, Math.PI * 2);
  CTX.fill();
  CTX.fillStyle = '#000';
  CTX.beginPath();
  CTX.arc(bw / 2 - 3, 5, 0.7, 0, Math.PI * 2);
  CTX.arc(bw / 2 + 3, 5, 0.7, 0, Math.PI * 2);
  CTX.fill();

  // asas (branco translúcido)
  CTX.fillStyle = 'rgba(220,230,240,0.55)';
  CTX.beginPath();
  CTX.ellipse(2, bh / 2, 6, 10, 0, 0, Math.PI * 2);
  CTX.fill();
  CTX.beginPath();
  CTX.ellipse(bw - 2, bh / 2, 6, 10, 0, 0, Math.PI * 2);
  CTX.fill();

  // ---- Toga da rainha (juiz) ----
  if (isQueen) {
    CTX.fillStyle = '#2a2a2a';
    CTX.fillRect(0, bh - 6, bw, 6);
    CTX.fillStyle = '#ffd700';
    CTX.fillRect(bw / 2 - 2, bh - 6, 4, 2);
    CTX.fillStyle = '#0f0';
    CTX.font = '8px monospace';
    CTX.textAlign = 'center';
    CTX.fillText('Q', bw / 2, bh - 1);
  }

  // ---- Capacete de segurança (operárias / agente) ----
  if (!isQueen && !isLibrarian) {
    CTX.fillStyle = '#ffd700';
    CTX.fillRect(bw / 2 - 7, -2, 14, 6);
    CTX.fillStyle = '#1a1a1a';
    CTX.fillRect(bw / 2 - 5, 2, 10, 3);
  }

  // ---- Símbolo bibliotecária ----
  if (isLibrarian) {
    CTX.fillStyle = '#55f';
    CTX.font = '8px monospace';
    CTX.textAlign = 'center';
    CTX.fillText('B', bw / 2, bh - 2);
  }

  CTX.restore();

  // ---- Status do nó (texto ao lado) ----
  CTX.globalAlpha = 1;
  CTX.fillStyle = paused ? '#a33' : (isQueen ? '#0f0' : isLibrarian ? '#55f' : '#aa0');
  CTX.font = '10px monospace';
  CTX.textAlign = 'center';
  CTX.fillText(node.node_id.replace(/-.*/, ''), x, y + bh / 2 + 12);

  // barras CPU / RAM abaixo do nó
  const bx2 = x - 30;
  const cpu = Math.min(1, node.cpu_pct / 100);
  const ram = Math.min(1, node.free_ram_gb / 8);
  drawBar(bx2, y + bh / 2 + 20, 60, 5, cpu, '#f55');
  drawBar(bx2, y + bh / 2 + 27, 60, 5, 1 - ram, '#55f');

  // ponto de pausa (acima direita)
  CTX.fillStyle = paused ? '#f55' : '#0f0';
  CTX.beginPath();
  CTX.arc(x + bw / 2 - 4, y - bh / 2 - 4, 4, 0, Math.PI * 2);
  CTX.fill();

  // tarefa ativa (formiga carregando item)
  if (node.active_tasks > 0) {
    CTX.fillStyle = '#ff0';
    CTX.font = '9px monospace';
    CTX.fillText('●', x, y - bh / 2 - 12);
  }
}

function drawBar(x, y, w, h, frac, color) {
  CTX.fillStyle = '#222';
  CTX.fillRect(x, y, w, h);
  CTX.fillStyle = color;
  CTX.fillRect(x, y, Math.max(0, Math.min(1, frac)) * w, h);
  CTX.strokeStyle = '#000';
  CTX.strokeRect(x, y, w, h);
}

function drawNodesList() {
  NODE_LIST.innerHTML = nodes.map(node => {
    const paused = pausedAll || pausedNodes.has(node.node_id);
    const cpuPct = Math.min(100, (node.cpu_pct || 0));
    const ramUsed = node.max_concurrency ? Math.min(100, (node.active_tasks / node.max_concurrency) * 100) : 0;
    return `<div class="node-item ${paused ? 'paused' : ''}">
      <div class="node-dot"></div>
      <div style="flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${node.node_id}">${node.node_id.replace(/-.*/, '')}</div>
      <div class="bar cpu" style="width:56px"><span style="width:${cpuPct}%"></span></div>
      <div class="bar ram" style="width:56px"><span style="width:${ramUsed}%"></span></div>
      <button class="pause-btn" data-id="${node.node_id}">${paused ? '▶' : '❚❚'}</button>
    </div>`;
  }).join('');

  NODE_LIST.querySelectorAll('.pause-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.id;
      const willPause = !pausedNodes.has(id) && !pausedAll;
      try {
        await api(`/api/node/${id}/pause`, { method: 'POST', body: { paused: willPause } });
        if (willPause) pausedNodes.add(id); else pausedNodes.delete(id);
        draw();
        drawNodesList();
      } catch (e) {
        addMessage(`Erro ao pausar nó: ${e.message}`, 'err');
      }
    });
  });
}

function addMessage(text, cls) {
  const div = document.createElement('div');
  div.className = `msg ${cls || ''}`;
  div.textContent = text;
  TRANSCRIPT.appendChild(div);
  TRANSCRIPT.scrollTop = TRANSCRIPT.scrollHeight;
}

CANVAS.addEventListener('mousedown', (e) => {
  const rect = CANVAS.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  const n = nodes.length || 1;
  const radius = Math.min(CX, CY) - 60;
  for (let i = 0; i < nodes.length; i++) {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    const x = CX + radius * Math.cos(a);
    const y = CY + radius * Math.sin(a);
    const dx = mx - x, dy = my - y;
    if (dx * dx + dy * dy <= HEX * HEX) {
      const id = nodes[i].node_id;
      const willPause = !pausedNodes.has(id) && !pausedAll;
      (async () => {
        try {
          await api(`/api/node/${id}/pause`, { method: 'POST', body: { paused: willPause } });
          if (willPause) pausedNodes.add(id); else pausedNodes.delete(id);
          draw();
          drawNodesList();
        } catch (err) {
          addMessage(`Erro ao pausar nó: ${err.message}`, 'err');
        }
      })();
      return;
    }
  }
});

async function sendMessage() {
  const text = MSG.value.trim();
  if (!text || !sessionToken) return;
  MSG.value = '';
  addMessage(text, 'user');
  const typing = document.createElement('div');
  typing.className = 'msg system typing';
  typing.textContent = 'enxame processa…';
  TRANSCRIPT.appendChild(typing);

  try {
    const { task_id } = await api('/api/chat', { method: 'POST', body: { prompt: text } });
    const es = new EventSource(`/api/chat/stream/${task_id}?session=${sessionToken}`);
    let done = false;
    es.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (!done) { typing.remove(); done = true; }
      if (data.event === 'final') {
        addMessage(data.content || '(sem resposta)', 'assistant');
        es.close();
        calls += 1;
        document.getElementById('c-calls').textContent = calls;
        loadStatus();
      } else if (data.event === 'error') {
        addMessage(`Erro: ${data.message}`, 'err');
        es.close();
      }
    };
    es.onerror = () => { es.close(); if (!done) { typing.remove(); addMessage('Erro de conexão.', 'err'); } };
  } catch (err) {
    typing.remove();
    addMessage(`Erro: ${err.message}`, 'err');
  }
}

init();
