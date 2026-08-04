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
    statusOllama: document.getElementById('status-ollama')
};

let conversationHistory = [];
let isProcessing = false;

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
        const response = await fetch(`${API_BASE_URL}/status`);
        if (response.ok) {
            const data = await response.json();
            // Status esperados: 'online', 'offline', 'initializing'
            if (data.kernel) updateComponentStatus('kernel', data.kernel);
            if (data.runtime) updateComponentStatus('runtime', data.runtime);
            if (data.bibliotecario) updateComponentStatus('bibliotecario', data.bibliotecario);
            if (data.ollama) updateComponentStatus('ollama', data.ollama);
        }
    } catch (error) {
        // Se não conseguir carregar status, marca todos como offline
        updateComponentStatus('kernel', 'offline');
        updateComponentStatus('runtime', 'offline');
        updateComponentStatus('bibliotecario', 'offline');
        updateComponentStatus('ollama', 'offline');
    }
}

/**
 * Envia mensagem para a API e recebe resposta
 */
async function sendMessage(message) {
    if (!message.trim() || isProcessing) return;

    isProcessing = true;
    elements.sendBtn.disabled = true;

    // Adiciona mensagem do usuário ao histórico
    addMessageToHistory(message, 'user');
    conversationHistory.push({ role: 'user', content: message });

    // Limpa input e reseta altura
    elements.messageInput.value = '';
    elements.messageInput.style.height = 'auto';

    // Mostra indicador "Pensando..."
    showThinking();

    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                messages: conversationHistory
            })
        });

        if (!response.ok) {
            throw new Error(`Erro na requisição: ${response.status}`);
        }

        const data = await response.json();
        const assistantMessage = data.response || data.message || '';

        // Remove indicador e adiciona resposta ao histórico
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
 * Carrega histórico da sessão (se disponível)
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
        // Shift+Enter permite quebra de linha padrão
    });

    // Carrega histórico inicial
    loadHistory();

    // Carrega status dos componentes
    loadComponentStatus();

    // Atualiza status periodicamente (a cada 5 segundos)
    setInterval(loadComponentStatus, 5000);

    // Foca no input
    elements.messageInput.focus();
}

// Inicializa quando DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
