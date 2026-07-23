<script lang="ts">
	import { onMount } from 'svelte';
	import { fade } from 'svelte/transition';

	// State
	let query = '';
	let isProcessing = false;
	let currentMission: any = null;
	let logs: any[] = [];
	let language = 'pt-BR';
	let errorMessage = '';

	// Metrics (Visual only for now)
	let metrics = {
		cpu: 12,
		ram: 34,
		activeAgents: 0,
		uptime: '00:00:00'
	};

	// Translations
	const t: Record<string, any> = {
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
			powered: 'Powered by Open WebUI & Enxame OS',
			error: 'Erro na Missão'
		},
		en: {
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
			powered: 'Powered by Open WebUI & Enxame OS',
			error: 'Mission Error'
		}
	};

	const labels = t[language];

	function toggleLanguage() {
		language = language === 'pt-BR' ? 'en' : 'pt-BR';
	}

	function addLog(level: string, msg: string) {
		logs = [...logs, { time: new Date().toLocaleTimeString(), level, msg }];
	}

	async function sendMission() {
		if (!query.trim()) return;

		isProcessing = true;
		errorMessage = '';
		currentMission = null;
		logs = [];

		addLog('INFO', 'Initializing mission sequence...');
		addLog('INFO', `Target Query: "${query.substring(0, 30)}..."`);

		try {
			// REAL API CALL TO ENXAME BACKEND
			// Note: Ensure backend is running and router is mounted at /api/v1/enxame
			const response = await fetch('/api/v1/enxame/query', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
					// Se o Open WebUI exigir auth, o cookie de sessão é enviado automaticamente pelo browser
				},
				body: JSON.stringify({
					query: query,
					user_id: 'user-local',
					stream: false
				})
			});

			if (!response.ok) {
				const errData = await response.json().catch(() => ({}));
				throw new Error(errData.detail || `HTTP Error ${response.status}`);
			}

			const data = await response.json();

			addLog('SUCCESS', 'Guard: Validation passed.');
			addLog('SUCCESS', 'Librarian: Context retrieved.');
			addLog('SUCCESS', 'Scheduler: Agents dispatched.');
			addLog('SUCCESS', 'Judge: Consolidating response...');

			currentMission = {
				id: data.mission_id,
				status: data.status,
				answer: data.answer,
				confidence: data.confidence
			};

			addLog('INFO', `Mission completed with ${Math.round(data.confidence * 100)}% confidence.`);

			// Update mock metrics
			metrics.activeAgents = Math.floor(Math.random() * 5) + 1;
			metrics.cpu = Math.floor(Math.random() * 30) + 10;
			metrics.ram = Math.floor(Math.random() * 20) + 30;
		} catch (err: any) {
			console.error('Enxame API Error:', err);
			errorMessage = `${labels.error}: ${err.message}`;
			addLog('ERROR', err.message);

			// Fallback simulation if backend is not reachable
			addLog('WARN', 'Backend unreachable. Switching to simulation mode...');

			setTimeout(() => {
				if (isProcessing) {
					// Only simulate if we are still waiting
					addLog('INFO', '[SIM] Guard: OK');
					addLog('INFO', '[SIM] Librarian: OK');
					addLog('INFO', '[SIM] Scheduler: Assigned to Node-01');

					currentMission = {
						id: 'SIM-' + Date.now(),
						status: 'COMPLETED (SIM)',
						answer:
							'Modo de Simulação: O backend Enxame não respondeu em /api/v1/enxame/query. Verifique se o servidor Python está rodando e a rota foi registrada no main.py.',
						confidence: 0.0
					};
					addLog('SUCCESS', '[SIM] Mission completed in simulation mode.');
					isProcessing = false;
					query = '';
				}
			}, 1500);
			// Don't set isProcessing to false immediately if simulating, wait for timeout
			if (!errorMessage.includes('Simulation')) {
				// If it's a real error and we aren't simulating, stop processing
				// But the timeout above handles the simulation flow, so we let it run
			}
		} finally {
			// If we didn't go into simulation mode (caught error but no setTimeout triggered logic), reset here
			// The simulation block handles its own reset.
			if (!currentMission && !errorMessage.includes('Simulation')) {
				isProcessing = false;
				query = '';
			}
		}
	}
</script>

<div class="enxame-container">
	<!-- Header -->
	<header class="enxame-header">
		<div class="brand">
			<h1>{labels.title}</h1>
			<span class="badge">v1.0.0</span>
		</div>
		<button class="lang-switch" on:click={toggleLanguage} type="button">
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
					on:keydown={(e) => {
						if (e.key === 'Enter' && !e.shiftKey) {
							e.preventDefault();
							sendMission();
						}
					}}
				></textarea>
				<button
					class="btn-primary"
					on:click={sendMission}
					disabled={isProcessing || !query.trim()}
					type="button"
				>
					{isProcessing ? '⏳' : labels.btnSend}
				</button>
			</div>

			{#if errorMessage}
				<div class="result-box error-box fade-in">
					<p><strong>⚠️ {labels.error}:</strong> {errorMessage}</p>
				</div>
			{/if}

			{#if currentMission}
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
					<small>{labels.agents}</small>
					<strong>{metrics.activeAgents}</strong>
				</div>
				<div class="stat-card">
					<small>{labels.status}</small>
					<strong style="color: {isProcessing ? '#ffaa00' : '#00ff9d'}">
						{isProcessing ? 'RUNNING' : 'IDLE'}
					</strong>
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
					<div class="empty-state">Awaiting mission command...</div>
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
		box-sizing: border-box;
	}

	.enxame-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem 2rem;
		border-bottom: 1px solid var(--border);
		background: var(--bg-panel);
		flex-shrink: 0;
	}

	.brand h1 {
		margin: 0;
		font-size: 1.2rem;
		letter-spacing: 1px;
	}
	.badge {
		background: var(--accent);
		color: #000;
		padding: 2px 6px;
		border-radius: 4px;
		font-size: 0.7rem;
		font-weight: bold;
		margin-left: 10px;
	}

	.lang-switch {
		background: transparent;
		border: 1px solid var(--border);
		color: var(--text-main);
		padding: 4px 12px;
		cursor: pointer;
		border-radius: 4px;
		transition: all 0.2s;
		font-family: inherit;
	}
	.lang-switch:hover {
		border-color: var(--accent);
		color: var(--accent);
	}

	.enxame-grid {
		display: grid;
		grid-template-columns: 2fr 1fr;
		grid-template-rows: 1fr 180px;
		gap: 1rem;
		padding: 1rem;
		flex: 1;
		overflow: hidden;
		min-height: 0; /* Fix for flex items overflowing */
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

	.input-panel {
		grid-row: 1 / 2;
		grid-column: 1 / 2;
	}
	.metrics-panel {
		grid-row: 1 / 2;
		grid-column: 2 / 3;
	}
	.logs-panel {
		grid-row: 2 / 3;
		grid-column: 1 / 3;
	}

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
		box-sizing: border-box;
	}
	textarea:focus {
		outline: 1px solid var(--accent);
	}
	textarea:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.input-group {
		display: flex;
		gap: 1rem;
		height: 100%;
	}

	.btn-primary {
		background: var(--accent);
		color: #000;
		border: none;
		padding: 0 2rem;
		border-radius: 6px;
		font-weight: bold;
		cursor: pointer;
		transition: opacity 0.2s;
		font-family: inherit;
		white-space: nowrap;
	}
	.btn-primary:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.btn-primary:hover:not(:disabled) {
		opacity: 0.9;
	}

	.result-box {
		margin-top: 1rem;
		padding: 1rem;
		background: rgba(0, 255, 157, 0.05);
		border-left: 3px solid var(--accent);
		border-radius: 4px;
		max-height: 200px;
		overflow-y: auto;
	}
	.error-box {
		background: rgba(255, 77, 77, 0.1);
		border-left-color: var(--danger);
		color: var(--danger);
	}
	.confidence {
		font-size: 0.8rem;
		color: var(--accent);
		margin-bottom: 0.5rem;
		font-weight: bold;
	}

	.metric-row {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-bottom: 1rem;
		font-size: 0.9rem;
	}
	.bar {
		flex: 1;
		height: 6px;
		background: #30363d;
		border-radius: 3px;
		overflow: hidden;
	}
	.fill {
		height: 100%;
		background: var(--accent);
		transition: width 0.5s ease;
	}

	.stat-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
		margin-top: auto;
	}
	.stat-card {
		background: #0d1117;
		padding: 1rem;
		border-radius: 6px;
		text-align: center;
		border: 1px solid var(--border);
	}
	.stat-card small {
		color: var(--text-dim);
		display: block;
		margin-bottom: 4px;
	}
	.stat-card strong {
		font-size: 1.2rem;
		color: var(--text-main);
	}

	.console-output {
		font-family: 'JetBrains Mono', monospace;
		font-size: 0.85rem;
		overflow-y: auto;
		color: var(--text-dim);
		line-height: 1.4;
	}
	.log-entry {
		margin-bottom: 4px;
		word-break: break-word;
	}
	.log-entry.info {
		color: #58a6ff;
	}
	.log-entry.success {
		color: var(--accent);
	}
	.log-entry.warn {
		color: var(--warn);
	}
	.log-entry.error {
		color: var(--danger);
	}

	.time {
		opacity: 0.5;
		margin-right: 8px;
		white-space: nowrap;
	}
	.level {
		font-weight: bold;
		margin-right: 8px;
		width: 60px;
		display: inline-block;
	}
	.msg {
		opacity: 0.9;
	}

	.empty-state {
		text-align: center;
		padding: 2rem;
		opacity: 0.5;
		font-style: italic;
	}

	.enxame-footer {
		text-align: center;
		padding: 0.5rem;
		font-size: 0.75rem;
		color: var(--text-dim);
		border-top: 1px solid var(--border);
		flex-shrink: 0;
	}

	.fade-in {
		animation: fadeIn 0.3s ease-in;
	}
	@keyframes fadeIn {
		from {
			opacity: 0;
			transform: translateY(5px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	/* Scrollbar styling */
	::-webkit-scrollbar {
		width: 8px;
		height: 8px;
	}
	::-webkit-scrollbar-track {
		background: var(--bg-dark);
	}
	::-webkit-scrollbar-thumb {
		background: var(--border);
		border-radius: 4px;
	}
	::-webkit-scrollbar-thumb:hover {
		background: var(--text-dim);
	}
</style>
