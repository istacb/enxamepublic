// Enxame - Interface oficial HTML/CSS/JS puro
// Toda lógica de negócio pertence ao Kernel

const API_BASE_URL = '/api';

const elements = {
    history: document.getElementById('history'),
    messageInput: document.getElementById('message-input'),
    sendBtn: document.getElementById('send-btn'),
    statusKernel: document.getElementById('status-kernel'),
    statusRuntime: document.getElementById('status-runtime'),
    statusBibliotecario: document.getElementById('status-bibliotecario'),
    statusOllama: document.getElementById('status-ollama'),
    statusPeers: document.getElementById('status-peers'),
    peerCount: document.getElementById('peer-count'),
    offlineBadge: document.getElementById('offline-badge'),
    uploadBtn: document.getElementById('upload-btn'),
    settingsBtn: document.getElementById('settings-btn'),
    uploadModal: document.getElementById('upload-modal'),
    exportModal: document.getElementById('export-modal'),
    dropZone: document.getElementById('drop-zone'),
    fileInput: document.getElementById('file-input'),
    uploadProgress: document.getElementById('upload-progress'),
    progressFill: document.getElementById('progress-fill'),
    progressText: document.getElementById('progress-text'),
    cancelUpload: document.getElementById('cancel-upload'),
    confirmUpload: document.getElementById('confirm-upload'),
    cancelExport: document.getElementById('cancel-export'),
    confirmExport: document.getElementById('confirm-export'),
    peerList: document.getElementById('peer-list'),
    tabBtns: document.querySelectorAll('.tab-btn'),
    tabContents: document.querySelectorAll('.tab-content'),
    saveSettings: document.getElementById('save-settings'),
    settingOffline: document.getElementById('setting-offline'),
    settingAllowWeb: document.getElementById('setting-allow-web'),
    settingConfEnxame: document.getElementById('setting-conf-enxame'),
    settingConfWeb: document.getElementById('setting-conf-web'),
    settingModel: document.getElementById('setting-model'),
    confEnxameValue: document.getElementById('conf-enxame-value'),
    confWebValue: document.getElementById('conf-web-value'),
};

let conversationHistory = [];
let isProcessing = false;
let selectedFiles = [];
let currentConfig = {};

/**
 * Adiciona uma mensagem ao histórico visual
 */
function addMessageToHistory(content, role) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    messageDiv.textContent = content;
    elements.history.appendChild(messageDiv);
    scrollToBottom();
}

/**
 * Adiciona indicador "Pensando..."
 */
function showThinking() {
    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'thinking';
    thinkingDiv.id = 'thinking-indicator';
    thinkingDiv.innerHTML = 'Pensando<span class="thinking-dots"></span>';
    elements.history.appendChild(thinkingDiv);
    scrollToBottom();
}

/**
 * Remove indicador "Pensando..."
 */
function hideThinking() {
    const thinkingIndicator = document.getElementById('thinking-indicator');
    if (thinkingIndicator) {
        thinkingIndicator.remove();
    }
}

/**
 * Scroll automático para o final do histórico
 */
function scrollToBottom() {
    elements.history.scrollTop = elements.history.scrollHeight;
}

/**
 * Auto resize do textarea
 */
function autoResizeTextarea() {
    elements.messageInput.style.height = 'auto';
    elements.messageInput.style.height = elements.messageInput.scrollHeight + 'px';
}

/**
 * Atualiza estado de um componente na barra de status
 */
function updateComponentStatus(componentId, status) {
    const element = document.getElementById(`status-${componentId}`);
    if (element) {
        element.classList.remove('online', 'offline', 'initializing');
        if (status) {
            element.classList.add(status);
        }
    }
}

/**
 * Carrega status dos componentes
 */
async function loadComponentStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/v1/status`);
        if (response.ok) {
            const data = await response.json();
            if (data.kernel) updateComponentStatus('kernel', data.kernel);
            if (data.runtime) updateComponentStatus('runtime', data.runtime);
            if (data.bibliotecario) updateComponentStatus('bibliotecario', data.bibliotecario);
            if (data.ollama) updateComponentStatus('ollama', data.ollama);
            
            if (data.peers !== undefined) {
                elements.peerCount.textContent = data.peers;
            }
            
            if (data.offline_mode) {
                elements.offlineBadge.style.display = 'flex';
            } else {
                elements.offlineBadge.style.display = 'none';
            }
            
            // Atualizar configurações locais
            currentConfig = { ...currentConfig, ...data };
        }
    } catch (error) {
        updateComponentStatus('kernel', 'offline');
        updateComponentStatus('runtime', 'offline');
        updateComponentStatus('bibliotecario', 'offline');
        updateComponentStatus('ollama', 'offline');
        elements.peerCount.textContent = '0';
    }
}

/**
 * Carrega lista de peers
 */
async function loadPeers() {
    try {
        const response = await fetch(`${API_BASE_URL}/v1/peers`);
        if (response.ok) {
            const data = await response.json();
            renderPeers(data.peers || []);
        }
    } catch (error) {
        console.log('Erro ao carregar peers:', error);
    }
}

/**
 * Renderiza lista de peers
 */
function renderPeers(peers) {
    if (!peers || peers.length === 0) {
        elements.peerList.innerHTML = '<div class="empty-state">Nenhuma abelha descoberta</div>';
        return;
    }
    
    elements.peerList.innerHTML = peers.map(peer => `
        <div class="peer-card ${peer.state === 'RUNNING' ? 'online' : ''}">
            <div class="peer-header">
                <span class="peer-name">${peer.node_id}</span>
                <span class="peer-role">${peer.role}</span>
            </div>
            <div class="peer-details">
                <div class="peer-detail">
                    <span class="peer-detail-label">Host:</span>
                    <span>${peer.host}:${peer.port}</span>
                </div>
                <div class="peer-detail">
                    <span class="peer-detail-label">Carga:</span>
                    <span>${(peer.load * 100).toFixed(0)}%</span>
                </div>
                <div class="peer-detail">
                    <span class="peer-detail-label">Estado:</span>
                    <span>${peer.state}</span>
                </div>
            </div>
            ${peer.capabilities && peer.capabilities.length > 0 ? `
                <div class="peer-caps">
                    ${peer.capabilities.slice(0, 8).map(cap => `<span class="cap-tag">${cap}</span>`).join('')}
                    ${peer.capabilities.length > 8 ? `<span class="cap-tag">+${peer.capabilities.length - 8}</span>` : ''}
                </div>
            ` : ''}
        </div>
    `).join('');
}

/**
 * Envia mensagem para a API e recebe resposta
 */
async function sendMessage(message) {
    if (!message.trim() || isProcessing) return;

    isProcessing = true;
    elements.sendBtn.disabled = true;

    addMessageToHistory(message, 'user');
    conversationHistory.push({ role: 'user', content: message });

    elements.messageInput.value = '';
    elements.messageInput.style.height = 'auto';

    showThinking();

    try {
        const response = await fetch(`${API_BASE_URL}/v1/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: message
            })
        });

        if (!response.ok) {
            throw new Error(`Erro na requisição: ${response.status}`);
        }

        const data = await response.json();
        const assistantMessage = data.answer || data.message || '';

        hideThinking();
        addMessageToHistory(assistantMessage, 'assistant');
        conversationHistory.push({ role: 'assistant', content: assistantMessage });

    } catch (error) {
        console.error('Erro ao enviar mensagem:', error);
        hideThinking();
        addMessageToHistory(`Erro: ${error.message}`, 'assistant');
    } finally {
        isProcessing = false;
        elements.sendBtn.disabled = false;
        elements.messageInput.focus();
    }
}

/**
 * Carrega histórico da sessão
 */
async function loadHistory() {
    try {
        const response = await fetch(`${API_BASE_URL}/history`);
        if (response.ok) {
            const data = await response.json();
            if (data.messages && Array.isArray(data.messages)) {
                conversationHistory = data.messages;
                data.messages.forEach(msg => {
                    addMessageToHistory(msg.content, msg.role);
                });
            }
        }
    } catch (error) {
        console.log('Nenhum histórico disponível ou erro ao carregar:', error);
    }
}

/**
 * Upload de arquivo
 */
async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    elements.uploadProgress.style.display = 'block';
    elements.progressFill.style.width = '10%';
    elements.progressText.textContent = 'Enviando...';
    elements.confirmUpload.disabled = true;
    
    try {
        const response = await fetch(`${API_BASE_URL}/v1/ingest`, {
            method: 'POST',
            body: formData
        });
        
        elements.progressFill.style.width = '50%';
        elements.progressText.textContent = 'Processando...';
        
        if (!response.ok) {
            throw new Error(`Erro no upload: ${response.status}`);
        }
        
        const data = await response.json();
        elements.progressFill.style.width = '100%';
        elements.progressText.textContent = 'Concluído!';
        
        setTimeout(() => {
            closeUploadModal();
            addMessageToHistory(`📎 Arquivo "${file.name}" processado (${data.chunks} chunks)`, 'assistant');
        }, 1000);
        
    } catch (error) {
        console.error('Erro no upload:', error);
        elements.progressText.textContent = `Erro: ${error.message}`;
        elements.progressFill.style.background = '#e74c3c';
    }
}

/**
 * Manipulação do modal de upload
 */
function openUploadModal() {
    elements.uploadModal.style.display = 'flex';
    selectedFiles = [];
    elements.uploadProgress.style.display = 'none';
    elements.progressFill.style.width = '0%';
    elements.progressFill.style.background = '#3498db';
    elements.confirmUpload.disabled = true;
}

function closeUploadModal() {
    elements.uploadModal.style.display = 'none';
    elements.fileInput.value = '';
}

function handleFiles(files) {
    selectedFiles = Array.from(files);
    if (selectedFiles.length > 0) {
        elements.confirmUpload.disabled = false;
        elements.dropZone.querySelector('p').textContent = `${selectedFiles.length} arquivo(s) selecionado(s)`;
    }
}

/**
 * Modal de exportação
 */
function openExportModal() {
    elements.exportModal.style.display = 'flex';
}

function closeExportModal() {
    elements.exportModal.style.display = 'none';
}

function exportConversation(format) {
    let content;
    if (format === 'markdown') {
        content = conversationHistory.map(msg => `**${msg.role === 'user' ? 'Você' : 'Enxame'}**: ${msg.content}`).join('\n\n');
    } else {
        content = JSON.stringify(conversationHistory, null, 2);
    }
    
    const blob = new Blob([content], { type: format === 'markdown' ? 'text/markdown' : 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `enxame-conversa-${Date.now()}.${format === 'markdown' ? 'md' : 'json'}`;
    a.click();
    URL.revokeObjectURL(url);
    
    closeExportModal();
}

/**
 * Configurações
 */
async function loadSettings() {
    try {
        // Tentar carregar config do servidor
        const response = await fetch(`${API_BASE_URL}/v1/capabilities`);
        if (response.ok) {
            const data = await response.json();
            // Preencher modelo se disponível
            if (data.models && data.models.length > 0) {
                elements.settingModel.value = data.models[0];
            }
        }
    } catch (error) {
        console.log('Erro ao carregar configurações:', error);
    }
    
    // Carregar do localStorage
    const saved = localStorage.getItem('enxame-settings');
    if (saved) {
        const settings = JSON.parse(saved);
        elements.settingOffline.checked = settings.offline_mode || false;
        elements.settingAllowWeb.checked = settings.allow_web || false;
        elements.settingConfEnxame.value = settings.confidence_threshold_enxame || 0.7;
        elements.settingConfWeb.value = settings.confidence_threshold_web || 0.8;
        elements.confEnxameValue.textContent = parseFloat(elements.settingConfEnxame.value).toFixed(2);
        elements.confWebValue.textContent = parseFloat(elements.settingConfWeb.value).toFixed(2);
        if (settings.model) elements.settingModel.value = settings.model;
    }
}

function saveSettings() {
    const settings = {
        offline_mode: elements.settingOffline.checked,
        allow_web: elements.settingAllowWeb.checked,
        confidence_threshold_enxame: parseFloat(elements.settingConfEnxame.value),
        confidence_threshold_web: parseFloat(elements.settingConfWeb.value),
        model: elements.settingModel.value,
    };
    
    localStorage.setItem('enxame-settings', JSON.stringify(settings));
    
    // Atualizar valores visuais
    elements.confEnxameValue.textContent = settings.confidence_threshold_enxame.toFixed(2);
    elements.confWebValue.textContent = settings.confidence_threshold_web.toFixed(2);
    
    // Notificar usuário
    const originalText = elements.saveSettings.textContent;
    elements.saveSettings.textContent = 'Salvo!';
    elements.saveSettings.style.background = '#27ae60';
    setTimeout(() => {
        elements.saveSettings.textContent = originalText;
        elements.saveSettings.style.background = '';
    }, 2000);
    
    // Aplicar modo offline visualmente
    if (settings.offline_mode) {
        elements.offlineBadge.style.display = 'flex';
    } else {
        elements.offlineBadge.style.display = 'none';
    }
}

/**
 * Abas da sidebar
 */
function switchTab(tabName) {
    elements.tabBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    elements.tabContents.forEach(content => {
        content.style.display = content.id === `tab-${tabName}` ? 'block' : 'none';
    });
    
    if (tabName === 'peers') {
        loadPeers();
    }
}

/**
 * Inicializa a interface
 */
function init() {
    // Auto resize do textarea
    elements.messageInput.addEventListener('input', autoResizeTextarea);

    // Event listener para o botão de enviar
    elements.sendBtn.addEventListener('click', () => {
        const message = elements.messageInput.value;
        sendMessage(message);
    });

    // Event listener para Enter (sem Shift) e Shift+Enter (quebra linha)
    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            const message = elements.messageInput.value;
            sendMessage(message);
        }
    });

    // Upload modal
    elements.uploadBtn.addEventListener('click', openUploadModal);
    elements.cancelUpload.addEventListener('click', closeUploadModal);
    elements.dropZone.addEventListener('click', () => elements.fileInput.click());
    elements.dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        elements.dropZone.style.borderColor = '#3498db';
        elements.dropZone.style.background = '#f8faff';
    });
    elements.dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        elements.dropZone.style.borderColor = '#ddd';
        elements.dropZone.style.background = '';
    });
    elements.dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        elements.dropZone.style.borderColor = '#ddd';
        elements.dropZone.style.background = '';
        handleFiles(e.dataTransfer.files);
    });
    elements.fileInput.addEventListener('change', (e) => handleFiles(e.target.files));
    elements.confirmUpload.addEventListener('click', () => {
        selectedFiles.forEach(file => uploadFile(file));
    });

    // Export modal
    elements.confirmExport.addEventListener('click', () => {
        const format = document.querySelector('input[name="export-format"]:checked').value;
        exportConversation(format);
    });
    elements.cancelExport.addEventListener('click', closeExportModal);

    // Settings
    elements.settingsBtn.addEventListener('click', () => switchTab('settings'));
    elements.saveSettings.addEventListener('click', saveSettings);
    elements.settingConfEnxame.addEventListener('input', () => {
        elements.confEnxameValue.textContent = parseFloat(elements.settingConfEnxame.value).toFixed(2);
    });
    elements.settingConfWeb.addEventListener('input', () => {
        elements.confWebValue.textContent = parseFloat(elements.settingConfWeb.value).toFixed(2);
    });

    // Tabs
    elements.tabBtns.forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Fechar modais clicando no overlay
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', () => {
            closeUploadModal();
            closeExportModal();
        });
    });

    // Carrega histórico inicial
    loadHistory();

    // Carrega status dos componentes
    loadComponentStatus();

    // Carrega peers
    loadPeers();

    // Carrega configurações
    loadSettings();

    // Atualiza status periodicamente (a cada 5 segundos)
    setInterval(() => {
        loadComponentStatus();
        loadPeers();
    }, 5000);

    // Foca no input
    elements.messageInput.focus();
}

// Inicializa quando DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}