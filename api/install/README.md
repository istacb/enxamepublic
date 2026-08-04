# Enxame - Sistema Oficial de Instalação

## Visão Geral

O Enxame possui um sistema de instalação multi-plataforma totalmente automatizado com fluxo **Next > Next > Finish**. Os instaladores detectam automaticamente instalações antigas (Enxame ou OpenWebUI), fazem backup dos dados, removem a versão antiga e instalam a nova versão limpa.

---

## 📦 Instaladores Disponíveis

| Sistema | Arquivo | Requisitos |
|---------|---------|------------|
| **Ubuntu/Debian** | `install-ubuntu.sh` | root/sudo |
| **Windows** | `install-windows.bat` | Administrador |
| **macOS** | `install-macos.sh` | root/sudo |

---

## 🚀 Instalação Rápida

### Ubuntu/Debian Linux

```bash
# Baixe o instalador
wget https://github.com/enxame/enxame/releases/latest/download/install-ubuntu.sh

# Execute como root
sudo bash install-ubuntu.sh
```

**O que acontece:**
1. ✅ Verifica Python 3, Node.js e dependências
2. ✅ Detecta instalações antigas (Enxame ou OpenWebUI)
3. ✅ Para serviços antigos e containers Docker
4. ✅ Cria backup dos dados do usuário
5. ✅ Remove completamente a instalação antiga
6. ✅ Instala a nova versão do Enxame
7. ✅ Restaura dados e configurações
8. ✅ Cria serviço systemd e atalhos

**Localização da instalação:**
- Código: `/opt/enxame`
- Dados: `/var/lib/enxame/data`
- Config: `/etc/enxame/.env`
- Logs: `/var/log/enxame`

---

### Windows

```powershell
# Baixe o instalador
# Clique direito em install-windows.bat > Salvar como

# Execute como Administrador
# Clique direito em install-windows.bat > Executar como Administrador
```

**O que acontece:**
1. ✅ Verifica Python 3 e Node.js (instala via winget se necessário)
2. ✅ Detecta instalações antigas
3. ✅ Para processos antigos
4. ✅ Cria backup dos dados
5. ✅ Remove instalação antiga
6. ✅ Instala nova versão
7. ✅ Restaura dados
8. ✅ Cria atalho na Área de Trabalho

**Localização da instalação:**
- Código: `C:\Program Files\Enxame`
- Dados: `%APPDATA%\Enxame`
- Config: `%APPDATA%\Enxame\Config\.env`
- Logs: `%LOCALAPPDATA%\Enxame\Logs`

---

### macOS

```bash
# Baixe o instalador
curl -LO https://github.com/enxame/enxame/releases/latest/download/install-macos.sh

# Execute como root
sudo bash install-macos.sh
```

**O que acontece:**
1. ✅ Verifica Python 3 e Node.js (instala via Homebrew se necessário)
2. ✅ Detecta instalações antigas
3. ✅ Para processos e containers
4. ✅ Cria backup dos dados
5. ✅ Remove instalação antiga
6. ✅ Instala nova versão
7. ✅ Restaura dados
8. ✅ Cria aplicativo .app e LaunchAgent

**Localização da instalação:**
- Código: `/Applications/Enxame`
- Dados: `~/Library/Application Support/Enxame`
- Config: `~/Library/Preferences/Enxame/.env`
- Logs: `~/Library/Logs/Enxame`

---

## 🔄 Atualização

Todos os instaladores suportam atualização automática. Basta executar o mesmo script novamente.

### Script de Update Multi-Plataforma

```bash
# Linux/macOS
sudo ./api/install/update

# Windows
# Execute update.bat como Administrador
```

**O script de update:**
1. Comunica-se com todos os nodes (Kernel, Bibliotecário, Juiz, Ollama)
2. Notifica shutdown gracioso
3. Cria backup completo
4. Atualiza código via git
5. Atualiza dependências Python e Node
6. Restaura dados e configurações
7. Reinicia serviços
8. Verifica saúde dos serviços

---

## 🗑️ Desinstalação

### Linux/macOS

```bash
sudo ./api/install/uninstall
```

### Windows

```cmd
# Execute como Administrador
uninstall.bat
```

**O que é removido:**
- ✅ Todos os arquivos de código
- ✅ Dados do usuário
- ✅ Configurações
- ✅ Logs
- ✅ Serviços (systemd/LaunchAgent)
- ✅ Atalhos

---

## 🔀 Migração do OpenWebUI

Os instaladores detectam automaticamente instalações do OpenWebUI e oferecem migração:

**Detectado automaticamente:**
- Containers Docker do OpenWebUI
- Diretórios `/var/lib/open-webui`, `/opt/open-webui`
- Configurações `.env` do OpenWebUI
- Bancos de dados antigos

**Ação:**
- Para serviços e containers
- Backup dos dados do usuário
- Remove completamente o OpenWebUI
- Instala o Enxame
- Restaura dados compatíveis

---

## 📡 Descoberta de Nodes

O sistema de instalação comunica-se automaticamente com todos os components do Enxame:

| Componente | Porta | Endpoint de Saúde |
|------------|-------|-------------------|
| Kernel | 8080 | `/api/health` |
| Bibliotecário | 8081 | `/api/health` |
| Juiz | 8082 | `/api/health` |
| Ollama | 11434 | `/api/tags` |

Durante a atualização, o script:
1. Varre todas as portas
2. Notifica cada node para shutdown gracioso
3. Aguarda finalização das operações
4. Procede com a atualização
5. Reinicia os serviços
6. Verifica se todos os nodes estão online

---

## 🛡️ Backup e Segurança

**Dados preservados durante atualização:**
- ✅ Banco de dados (`enxame.db`)
- ✅ Histórico de conversas
- ✅ Configurações (`.env`)
- ✅ Modelos locais (referência apenas)
- ✅ Chaves de API

**Localização dos backups:**
- Linux: `/tmp/enxame_backup_YYYYMMDD_HHMMSS/`
- macOS: `/tmp/enxame_backup_YYYYMMDD_HHMMSS/`
- Windows: `%TEMP%\enxame_backup_YYYYMMDD_HHMMSS\`

Backups são automaticamente removidos após sucesso da instalação.

---

## 📋 Pré-requisitos

### Ubuntu/Debian
- Ubuntu 20.04+ ou Debian 10+
- Python 3.8+
- Node.js 16+ (instalado automaticamente se necessário)
- 2GB RAM mínimo
- 5GB espaço em disco

### Windows
- Windows 10+
- Python 3.8+ (baixar em python.org)
- Node.js 16+ (instalado automaticamente via winget)
- 2GB RAM mínimo
- 5GB espaço em disco

### macOS
- macOS 11+ (Big Sur)
- Python 3.8+
- Homebrew (instalado automaticamente se necessário)
- Node.js 16+
- 2GB RAM mínimo
- 5GB espaço em disco

---

## 🐛 Solução de Problemas

### Instalação falha no Linux
```bash
# Verifique logs
sudo journalctl -u enxame -n 50

# Reinstale
sudo ./api/install/uninstall
sudo ./api/install/install-ubuntu.sh
```

### Instalação falha no Windows
```powershell
# Verifique se está como Administrador
# Execute manualmente o Python
cd "C:\Program Files\Enxame"
python -m kernel.start
```

### Instalação falha no macOS
```bash
# Verifique logs
tail -f ~/Library/Logs/Enxame/enxame.log

# Reinstale
sudo ./api/install/uninstall
sudo ./api/install/install-macos.sh
```

### OpenWebUI não foi removido completamente
```bash
# Remoção manual Linux
sudo docker stop open-webui && sudo docker rm open-webui
sudo rm -rf /var/lib/open-webui /opt/open-webui

# Remoção manual Windows
docker stop open-webui
rmdir /S /Q "%LOCALAPPDATA%\open-webui"

# Remoção manual macOS
docker stop open-webui
rm -rf ~/Library/Application\ Support/open-webui
```

---

## 📞 Suporte

Para issues relacionados à instalação:
- GitHub Issues: https://github.com/enxame/enxame/issues
- Documentação: https://spec.enxame.io

---

## 📄 Licença

Enxame v1.0 - Architecture First, Resource First
