# 🐝 Manual de Instalação e Uso - Projeto ENXAME

Este manual guia você passo a passo na instalação, configuração e utilização do sistema **ENXAME**, uma arquitetura distribuída de agentes inteligentes.

---

## 📋 Índice

1. [Pré-requisitos](#pré-requisitos)
2. [Estrutura do Projeto](#estrutura-do-projeto)
3. [Instalação](#instalação)
4. [Configuração](#configuração)
5. [Como Rodar o Sistema](#como-rodar-o-sistema)
6. [Acessando a Interface Web](#acessando-a-interface-web)
7. [Uso via API](#uso-via-api)
8. [Comandos Úteis](#comandos-úteis)
9. [Solução de Problemas](#solução-de-problemas)

---

## 1. Pré-requisitos

Antes de começar, certifique-se de ter instalado:

- **Python 3.8 ou superior**
  ```bash
  python --version
  ```
- **pip** (gerenciador de pacotes Python)
- **Git** (para clonar o repositório)
- **Acesso à Internet** (para baixar dependências e modelos)

### Sistemas Operacionais Suportados
- ✅ Linux (Ubuntu, Debian, CentOS)
- ✅ Windows 10/11
- ✅ macOS

---

## 2. Estrutura do Projeto

```
enxame/
├── agentes/           # Agentes especializados e plugins
├── bibliotecario/     # Serviço de indexação e busca de documentos
├── core/              # Núcleo do sistema (cluster, memória, segurança)
├── juiz/              # Orquestrador principal e interface web
│   ├── static/        # Arquivos estáticos (HTML, CSS, JS)
│   │   └── index.html # Interface web do usuário
│   ├── app.py         # Servidor Flask/FastAPI
│   └── requirements.txt
├── start_cluster.sh   # Script de inicialização (Linux/Mac)
├── start_cluster.bat  # Script de inicialização (Windows)
├── requirements.txt   # Dependências principais
└── MANUAL_INSTALACAO_USO.md
```

---

## 3. Instalação

### Passo 1: Clonar o Repositório

```bash
git clone <url-do-repositorio-privado>
cd enxame
```

### Passo 2: Criar Ambiente Virtual (Recomendado)

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### Passo 3: Instalar Dependências

Instale as dependências principais:
```bash
pip install -r requirements.txt
```

Instale as dependências de cada módulo:

```bash
# Juiz (Orquestrador)
pip install -r juiz/requirements.txt

# Bibliotecário (Busca e Indexação)
pip install -r bibliotecario/requirements.txt

# Agentes (Plugins e Ferramentas)
pip install -r agentes/requirements.txt

# Core (Núcleo)
pip install -r core/requirements.txt
```

> 💡 **Dica:** Se algum módulo não tiver `requirements.txt`, instale apenas os principais.

---

## 4. Configuração

### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto (opcional, mas recomendado):

```bash
# .env
JUIZ_HOST=0.0.0.0
JUIZ_PORT=8000
LOG_LEVEL=INFO
SECRET_KEY=sua-chave-secreta-aqui
```

### Configuração de Segurança

O sistema já inclui módulos de segurança em `core/exp/`:
- `input_sanitizer.py`: Sanitização de entradas
- `secure_logger.py`: Logs seguros

Não é necessária configuração adicional para uso básico.

---

## 5. Como Rodar o Sistema

### Opção A: Usando Scripts Automáticos (Recomendado)

**Linux/macOS:**
```bash
chmod +x start_cluster.sh
./start_cluster.sh
```

**Windows:**
```bash
start_cluster.bat
```

### Opção B: Iniciando Manualmente

Se preferir controle total, inicie cada serviço separadamente:

1. **Iniciar o Juiz (Orquestrador Principal):**
   ```bash
   cd juiz
   python app.py
   ```
   O servidor iniciará em `http://0.0.0.0:8000`

2. **Iniciar o Bibliotecário (Opcional - se usar busca de documentos):**
   ```bash
   cd bibliotecario
   python search_service.py
   ```

3. **Iniciar Agentes (Opcional - se rodar agentes como serviços separados):**
   ```bash
   cd agentes
   python worker.py
   ```

> 🚀 **Nota:** Na maioria dos casos, apenas o **Juiz** precisa ser iniciado. Ele gerencia automaticamente a comunicação com os outros módulos.

---

## 6. Acessando a Interface Web

Após iniciar o servidor Juiz, acesse a interface gráfica:

1. Abra seu navegador
2. Digite o endereço:
   - **Localmente:** `http://localhost:8000`
   - **Remotamente:** `http://<IP-DO-SERVIDOR>:8000`

### Funcionalidades da Interface:

- **📝 Envio de Tarefas:** Digite sua pergunta ou comando e envie para o enxame
- **📊 Dashboard:** Visualize agentes conectados, tarefas processadas e status do cluster
- **💬 Histórico:** Acesse as últimas interações armazenadas localmente
- **⚡ Streaming:** Receba respostas em tempo real conforme são geradas

### Exemplo de Uso:

1. No campo de texto, digite: *"Liste os arquivos do diretório atual"*
2. Clique em **"Enviar para o Enxame"**
3. Acompanhe o processamento em tempo real
4. Visualize o resultado formatado

---

## 7. Uso via API

Para integrações programáticas, use a API REST do Juiz.

### Endpoint Principal

**POST** `/api/task`

**Exemplo com cURL:**
```bash
curl -X POST http://localhost:8000/api/task \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Qual a temperatura atual?", "user_id": "usuario123"}'
```

**Exemplo com Python:**
```python
import requests

response = requests.post(
    'http://localhost:8000/api/task',
    json={
        'prompt': 'Liste os processos ativos',
        'user_id': 'admin'
    }
)

print(response.json())
```

### Streaming (Server-Sent Events)

Para receber respostas em tempo real:

**Endpoint:** `/api/task/stream`

**Exemplo com JavaScript (Frontend):**
```javascript
const eventSource = new EventSource('/api/task/stream?prompt=Olá&user_id=user1');

eventSource.onmessage = (event) => {
    console.log('Resposta:', event.data);
};
```

---

## 8. Comandos Úteis

### Verificar Status do Cluster
```bash
curl http://localhost:8000/api/cluster/status
```

### Listar Agentes Ativos
```bash
curl http://localhost:8000/api/agents
```

### Limpar Cache/Memória
```bash
curl -X POST http://localhost:8000/api/clear_memory
```

### Logs em Tempo Real
```bash
# Se estiver usando logging em arquivo
tail -f logs/juiz.log
```

### Parar o Servidor
Pressione `Ctrl+C` no terminal onde o servidor está rodando.

---

## 9. Solução de Problemas

### ❌ Erro: "ModuleNotFoundError"
**Solução:** Certifique-se de que todas as dependências foram instaladas:
```bash
pip install -r requirements.txt
pip install -r juiz/requirements.txt
```

### ❌ Erro: "Port already in use"
**Solução:** Altere a porta no arquivo `.env` ou encerre o processo usando a porta:
```bash
# Linux/macOS
lsof -i :8000
kill -9 <PID>

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### ❌ Interface Web não carrega
**Soluções:**
1. Verifique se o servidor Juiz está rodando
2. Confirme que o arquivo `juiz/static/index.html` existe
3. Limpe o cache do navegador (Ctrl+Shift+R)
4. Verifique o console do navegador (F12) por erros

### ❌ Agentes não respondem
**Soluções:**
1. Verifique os logs do Juiz para mensagens de erro
2. Confirme que os agentes estão registrados corretamente
3. Teste a conexão de rede entre os módulos

### ❌ Erros de Permissão (Linux)
**Solução:**
```bash
chmod +x start_cluster.sh
chmod +x *.sh
```

---

## 📞 Suporte e Contribuição

- **Documentação Adicional:** Consulte os arquivos `README.md` em cada módulo
- **Logs de Erro:** Verifique a pasta `logs/` ou a saída do terminal
- **Segurança:** Revise `SEGURANCA_IMPLEMENTACOES.md` para boas práticas

---

## ✅ Checklist de Instalação Rápida

- [ ] Python 3.8+ instalado
- [ ] Repositório clonado
- [ ] Ambiente virtual criado e ativado
- [ ] Dependências instaladas (`pip install -r ...`)
- [ ] Arquivo `.env` configurado (opcional)
- [ ] Servidor Juiz iniciado
- [ ] Interface web acessível em `http://localhost:8000`
- [ ] Primeira tarefa enviada com sucesso

---

**🎉 Parabéns! Seu sistema ENXAME está pronto para uso!**

Para dúvidas ou melhorias, consulte a documentação de cada módulo ou abra uma issue no repositório.
