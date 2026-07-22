<script lang="ts">
  import { onMount } from 'svelte';
  import { fade } from 'svelte/transition';

  // State
  let query = '';
  let isProcessing = false;
  let currentMission = null;
  let logs = [];
  let language = 'pt-BR';
  
  // Mock Metrics
  let metrics = {
    cpu: 12,
    ram: 34,
    activeAgents: 3,
    uptime: '02:14:55'
  };

  // Translations
  const t = {
    'pt-BR': {
      title: 'Controle de Missão',
      placeholder: 'Descreva sua missão...',
      btnSend: 'Iniciar Missão',
      status: 'Status',
      agents: 'Agentes',
      timeline: 'Linha do Tempo',
      resources: 'Recursos',
      cpu: 'CPU',
      ram: 'RAM',
      logs: 'Logs do Sistema',
      powered: 'Powered by Open WebUI & Enxame OS'
    },
    'en': {
      title: 'Mission Control',
      placeholder: 'Describe your mission...',
      btnSend: 'Start Mission',
      status: 'Status',
      agents: 'Agents',
      timeline: 'Timeline',
      resources: 'Resources',
      cpu: 'CPU',
      ram: 'RAM',
      logs: 'System Logs',
      powered: 'Powered by Open WebUI & Enxame OS'
    }
  };

  const labels = t[language];

  function toggleLanguage() {
    language = language === 'pt-BR' ? 'en' : 'pt-BR';
  }

  async function sendMission() {
    if (!query.trim()) return;
    
    isProcessing = true;
    logs = [{ time: new Date().toLocaleTimeString(), level: 'INFO', msg: 'Mission initialized...' }];
    
    // Simulate API Call
    setTimeout(() => {
      logs.push({ time: new Date().toLocaleTimeString(), level: 'INFO', msg: 'Guard: Validation passed.' });
      logs.push({ time: new Date().toLocaleTimeString(), level: 'INFO', msg: 'Librarian: Context retrieved.' });
      logs.push({ time: new Date().toLocaleTimeString(), level: 'INFO', msg: 'Scheduler: Assigned to Node-01.' });
      
      setTimeout(() => {
        isProcessing = false;
        currentMission = {
          id: 'M-' + Math.floor(Math.random() * 10000),
          status: 'COMPLETED',
          answer: 'Esta é uma resposta simulada do Enxame OS. A arquitetura está pronta para integração.',
          confidence: 0.95
        };
        logs.push({ time: new Date().toLocaleTimeString(), level: 'SUCCESS', msg: 'Judge: Response consolidated.' });
      }, 1500);
    }, 800);
    
    query = '';
  }
</script>

<div class="enxame-container">
  <!-- Header -->
  <header class="enxame-header">
    <div class="brand">
      <h1>{labels.title}</h1>
      <span class="badge">v1.0.0</span>
    </div>
    <button class="lang-switch" on:click={toggleLanguage}>
      {language === 'pt-BR' ? '🇧🇷 PT' : '🇺🇸 EN'}
    </button>
  </header>

  <!-- Main Grid -->
  <main class="enxame-grid">
    
    <!-- Chat / Input Area -->
    <section class="panel input-panel">
      <div class="input-group">
        <textarea 
          bind:value={query} 
          placeholder={labels.placeholder} 
          disabled={isProcessing}
        ></textarea>
        <button 
          class="btn-primary" 
          on:click={sendMission} 
          disabled={isProcessing || !query.trim()}
        >
          {isProcessing ? '⏳' : labels.btnSend}
        </button>
      </div>
      
      {if currentMission}
        <div class="result-box fade-in">
          <div class="confidence">Confidence: {(currentMission.confidence * 100).toFixed(0)}%</div>
          <p>{currentMission.answer}</p>
        </div>
      {/if}
    </section>

    <!-- Metrics Sidebar -->
    <aside class="panel metrics-panel">
      <h3>{labels.resources}</h3>
      <div class="metric-row">
        <span>{labels.cpu}</span>
        <div class="bar"><div class="fill" style="width: {metrics.cpu}%"></div></div>
        <span>{metrics.cpu}%</span>
      </div>
      <div class="metric-row">
        <span>{labels.ram}</span>
        <div class="bar"><div class="fill" style="width: {metrics.ram}%"></div></div>
        <span>{metrics.ram}%</span>
      </div>
      
      <div class="stat-grid">
        <div class="stat-card">
          <small>Agents</small>
          <strong>{metrics.activeAgents}</strong>
        </div>
        <div class="stat-card">
          <small>Uptime</small>
          <strong>{metrics.uptime}</strong>
        </div>
      </div>
    </aside>

    <!-- Logs Console -->
    <section class="panel logs-panel">
      <h3>{labels.logs}</h3>
      <div class="console-output">
        {#each logs as log}
          <div class="log-entry {log.level.toLowerCase()}">
            <span class="time">[{log.time}]</span>
            <span class="level">{log.level}</span>
            <span class="msg">{log.msg}</span>
          </div>
        {/each}
        {#if logs.length === 0}
          <div class="empty-state">Awaiting mission...</div>
        {/if}
      </div>
    </section>
  </main>

  <footer class="enxame-footer">
    {labels.powered}
  </footer>
</div>

<style>
  :global(.enxame-container) {
    --bg-dark: #0f1115;
    --bg-panel: #161b22;
    --accent: #00ff9d;
    --text-main: #e6edf3;
    --text-dim: #8b949e;
    --border: #30363d;
    --danger: #ff4d4d;
    --warn: #ffaa00;
    
    font-family: 'JetBrains Mono', monospace;
    background-color: var(--bg-dark);
    color: var(--text-main);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .enxame-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 2rem;
    border-bottom: 1px solid var(--border);
    background: var(--bg-panel);
  }

  .brand h1 { margin: 0; font-size: 1.2rem; letter-spacing: 1px; }
  .badge { 
    background: var(--accent); color: #000; 
    padding: 2px 6px; border-radius: 4px; 
    font-size: 0.7rem; font-weight: bold; margin-left: 10px;
  }
  
  .lang-switch {
    background: transparent; border: 1px solid var(--border);
    color: var(--text-main); padding: 4px 12px; cursor: pointer;
    border-radius: 4px; transition: all 0.2s;
  }
  .lang-switch:hover { border-color: var(--accent); color: var(--accent); }

  .enxame-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    grid-template-rows: 1fr 150px;
    gap: 1rem;
    padding: 1rem;
    flex: 1;
    overflow: hidden;
  }

  .panel {
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .input-panel { grid-row: 1 / 2; grid-column: 1 / 2; }
  .metrics-panel { grid-row: 1 / 2; grid-column: 2 / 3; }
  .logs-panel { grid-row: 2 / 3; grid-column: 1 / 3; }

  textarea {
    width: 100%;
    background: #0d1117;
    border: 1px solid var(--border);
    color: var(--text-main);
    padding: 1rem;
    border-radius: 6px;
    resize: none;
    flex: 1;
    font-family: inherit;
    min-height: 100px;
  }
  textarea:focus { outline: 1px solid var(--accent); }

  .input-group { display: flex; gap: 1rem; height: 100%; }
  
  .btn-primary {
    background: var(--accent); color: #000;
    border: none; padding: 0 2rem;
    border-radius: 6px; font-weight: bold;
    cursor: pointer; transition: opacity 0.2s;
  }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

  .result-box {
    margin-top: 1rem;
    padding: 1rem;
    background: rgba(0, 255, 157, 0.05);
    border-left: 3px solid var(--accent);
    border-radius: 4px;
  }
  .confidence { font-size: 0.8rem; color: var(--accent); margin-bottom: 0.5rem; }

  .metric-row {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 1rem; font-size: 0.9rem;
  }
  .bar {
    flex: 1; height: 6px; background: #30363d;
    border-radius: 3px; overflow: hidden;
  }
  .fill { height: 100%; background: var(--accent); }

  .stat-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;
    margin-top: auto;
  }
  .stat-card {
    background: #0d1117; padding: 1rem;
    border-radius: 6px; text-align: center;
    border: 1px solid var(--border);
  }
  .stat-card small { color: var(--text-dim); display: block; }
  .stat-card strong { font-size: 1.2rem; color: var(--text-main); }

  .console-output {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    overflow-y: auto;
    color: var(--text-dim);
  }
  .log-entry { margin-bottom: 4px; }
  .log-entry.info { color: #58a6ff; }
  .log-entry.success { color: var(--accent); }
  .log-entry.warn { color: var(--warn); }
  .log-entry.error { color: var(--danger); }
  
  .time { opacity: 0.5; margin-right: 8px; }
  .level { font-weight: bold; margin-right: 8px; width: 60px; display: inline-block; }

  .enxame-footer {
    text-align: center;
    padding: 0.5rem;
    font-size: 0.75rem;
    color: var(--text-dim);
    border-top: 1px solid var(--border);
  }

  .fade-in { animation: fadeIn 0.3s ease-in; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
</style>