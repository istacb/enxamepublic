// Enxame - Interface mínima
// Toda lógica de negócio pertence ao Kernel

const API_BASE_URL = '/api';

const elements = {
    history: document.getElementById('history'),
    messageInput: document.getElementById('message-input'),
    sendBtn: document.getElementById('send-btn')
};

let conversationHistory = [];

/**
 * Adiciona uma mensagem ao histórico visual
 */
function addMessageToHistory(content, role) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    messageDiv.textContent = content;
    elements.history.appendChild(messageDiv);
    elements.history.scrollTop = elements.history.scrollHeight;
}

/**
 * Envia mensagem para a API e recebe resposta
 */
async function sendMessage(message) {
    if (!message.trim()) return;

    // Adiciona mensagem do usuário ao histórico
    addMessageToHistory(message, 'user');
    conversationHistory.push({ role: 'user', content: message });

    // Limpa input e desabilita botão
    elements.messageInput.value = '';
    elements.sendBtn.disabled = true;

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

        // Adiciona resposta ao histórico
        addMessageToHistory(assistantMessage, 'assistant');
        conversationHistory.push({ role: 'assistant', content: assistantMessage });

    } catch (error) {
        console.error('Erro ao enviar mensagem:', error);
        addMessageToHistory(`Erro: ${error.message}`, 'assistant');
    } finally {
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
    // Event listener para o botão de enviar
    elements.sendBtn.addEventListener('click', () => {
        const message = elements.messageInput.value;
        sendMessage(message);
    });

    // Event listener para Enter (sem Shift)
    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            const message = elements.messageInput.value;
            sendMessage(message);
        }
    });

    // Carrega histórico inicial
    loadHistory();

    // Foca no input
    elements.messageInput.focus();
}

// Inicializa quando DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
