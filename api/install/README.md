# Enxame - Sistema Oficial de Instalação

## Visão Geral

O Enxame possui um sistema de instalação multi-plataforma totalmente automatizado.
Os instaladores detectam o sistema operacional, fazem backup de instalações antigas,
instalam a nova versão, criam o serviço em segundo plano, um atalho na área de
trabalho e perguntam ao usuário onde instalar e se inicia junto ao boot.

---

## 📦 Instaladores Disponíveis

| Sistema | Arquivo | Requisitos |
|---------|---------|------------|
| **Launcher (auto-detecta o SO)** | `install.sh` | root/sudo |
| **Linux (Ubuntu/Debian)** | `install-linux.sh` | root/sudo |
| **Windows** | `install-windows.bat` | Administrador |
| **macOS** | `install-macos.sh` | root/sudo |
| **Desinstalador (todos)** | `uninstall` | root/sudo |

---

## 🚀 Instalação Rápida

### 1. Baixe o repositório

Os instaladores **não clonam nada sozinhos** — eles esperam rodar de dentro de um
checkout completo do repositório.

```bash
git clone https://github.com/istacb/enxamepublic.git
cd enxamepublic
```

### 2. Execute o instalador

#### Linux (recomendado — launcher detecta o SO automaticamente)

```bash
sudo bash api/install/install.sh
```

Ou diretamente o instalador Linux:

```bash
sudo bash api/install/install-linux.sh
```

#### Windows

Clique direito em `api\install\install-windows.bat` > **Executar como Administrador**.

#### macOS

```bash
sudo bash api/install/install-macos.sh
```

---

## ⚙️ O que o instalador pergunta (novo fluxo)

Durante a instalação, o instalador interage com o usuário:

1. **Pasta de instalação** — onde o código do Enxame será copiado
   (padrão: `/opt/enxame` no Linux, `C:\Program Files\Enxame` no Windows,
   `/Applications/Enxame` no macOS).
2. **Iniciar junto ao boot** — se o serviço deve iniciar automaticamente ao
   ligar o computador (systemd no Linux, LaunchAgent no macOS, tarefa
   agendada no Windows). Padrão: **Sim**.
3. **Função do node** — Juiz, Bibliotecário, Agente ou Automático
   (padrão: Automático).

Após a instalação:

- O código fica na pasta escolhida.
- Dados ficam em `/var/lib/enxame/data` (Linux) ou equivalente.
- Config fica em `/etc/enxame/.env` (Linux) ou equivalente.
- Logs ficam em `/var/log/enxame` (Linux) ou equivalente.
- O serviço roda **em segundo plano** automaticamente.
- Um **atalho na área de trabalho** é criado.

---

## 🖥️ Atalho da Área de Trabalho

Após a instalação, um atalho chamado **Enxame** aparece na área de trabalho.

**Ao duplo-clicar no atalho:**

- Se o serviço já estiver em segundo plano → abre o navegador na URL do Enxame
  (ex.: `http://localhost:7700/`).
- Se o serviço não estiver rodando → inicia o serviço em segundo plano e,
  assim que estiver pronto, abre o navegador.

Isso deixa o Enxame "pronto pra uso" com um único clique.

---

## 🔄 Atualização

Todos os instaladores suportam atualização automática. Basta executar o mesmo
script de instalação novamente — ele preserva dados, configurações e a função
do node.

```bash
# Linux/macOS
sudo bash api/install/install.sh

# Windows
# execute install-windows.bat como Administrador
```

O script de update (`./api/install/update`) também continua disponível para
atualizações mais granulares.

---

## 🗑️ Desinstalação

### Linux/macOS

```bash
sudo bash api/install/uninstall
```

### Windows

```cmd
# Execute como Administrador
uninstall.bat
```

O desinstalador:

1. Pede a **pasta de instalação** (ou detecta automaticamente via `.env`).
2. Para e remove o serviço em segundo plano (systemd / LaunchAgent / tarefa
   agendada).
3. Remove o **atalho da área de trabalho**.
4. Remove dados, logs e configuração.
5. Pergunta se quer remover também o código (preservado por padrão).

---

## 📍 Localização da instalação (padrões)

| Sistema | Código | Dados | Config | Logs |
|---------|--------|-------|--------|------|
| Linux | `/opt/enxame` | `/var/lib/enxame/data` | `/etc/enxame/.env` | `/var/log/enxame` |
| Windows | `C:\Program Files\Enxame` | `%APPDATA%\Enxame` | `%APPDATA%\Enxame\Config\.env` | `%LOCALAPPDATA%\Enxame\Logs` |
| macOS | `/Applications/Enxame` | `~/Library/Application Support/Enxame` | `~/Library/Preferences/Enxame/.env` | `~/Library/Logs/Enxame` |

---

## 📡 Portas e endpoints

| Componente | Porta | Endpoint de Saúde |
|------------|-------|-------------------|
| Juiz | 7700 | `/api/v1/health` |
| Bibliotecário | 7701 | `/api/v1/health` |
| Ollama | 11434 | `/api/tags` |

---

## 🛡️ Backup e Segurança

Backups são feitos automaticamente antes de atualizações em:
- Linux/macOS: `/tmp/enxame_backup_YYYYMMDD_HHMMSS/`
- Windows: `%TEMP%\enxame_backup_YYYYMMDD_HHMMSS\`

---

## 📄 Licença

Enxame v1.0 - Architecture First, Resource First
