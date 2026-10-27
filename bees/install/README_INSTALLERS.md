# ENXAME Bee - Installers Overview

Este diretório contém instaladores "next-next-finish" para todas as plataformas suportadas.

## Estrutura

```
install/
├── install_enxame.py          # Universal installer (Python)
├── install_enxame.sh          # Universal installer (Shell)
├── install_enxame.ps1         # Universal installer (PowerShell Windows)
├── install_enxame.bat         # Windows batch installer
├── install_enxame.iss         # Windows Inno Setup (.iss)
├── build_macos_pkg.sh         # macOS .pkg builder
├── build_deb.sh               # Debian/Ubuntu .deb builder
├── PKGBUILD                   # Arch Linux package
├── enxame-bee.service         # systemd service
├── enxame-bee.sysusers        # Arch sysusers
├── enxame-bee.tmpfiles        # Arch tmpfiles
├── enxame-bee.install         # Arch install script
├── config.json.example        # Config template
└── dist/                      # Output packages (gitignored)
```

## Uso Rápido

### Windows (PowerShell)
```powershell
# Baixar e executar
irm https://github.com/enxame/enxamepublic/raw/main/bees/install/install_enxame.ps1 | iex

# Ou baixar repositorio e executar
git clone https://github.com/enxame/enxamepublic
cd enxamepublic/bees/install
.\install_enxame.ps1
```

### Windows (Batch)
```cmd
install_enxame.bat
```

### Windows (Inno Setup - GUI)
```cmd
# Compilar com Inno Setup 6+
iscc install_enxame.iss
# Gera: dist/enxame-bee-setup-1.0.0.exe
```

### macOS
```bash
# Build e instalar
./build_macos_pkg.sh
sudo installer -pkg dist/enxame-bee-1.0.0-installer.pkg -target /

# Ou instalar pacote ja construido
sudo installer -pkg enxame-bee-1.0.0-installer.pkg -target /
```

### Debian/Ubuntu
```bash
# Build e instalar
./build_deb.sh
sudo dpkg -i dist/enxame-bee_1.0.0-1_amd64.deb
sudo apt-get install -f  # Corrigir dependencias

# Ou instalar pacote ja construido
sudo dpkg -i enxame-bee_1.0.0-1_amd64.deb
sudo apt-get install -f
```

### Arch Linux
```bash
# Build e instalar com makepkg
cd install
makepkg -si --noconfirm

# Ou usar helper AUR
yay -S enxame-bee
paru -S enxame-bee
```

### Linux Genérico (Python)
```bash
# Instalador universal detecta plataforma
python3 install_enxame.py

# Ou script shell
./install_enxame.sh

# Direto com Python installer
python3 -m bees.install.install_bee
```

## Opções Comuns

| Opção | Descrição |
|-------|-----------|
| `--dry-run` | Simula instalacao sem executar |
| `--skip-ollama` | Pula instalacao do Ollama |
| `--skip-model-test` | Pula teste de inferencia do modelo |
| `--force-ollama` | Forca reinstalacao do Ollama |
| `--force-model-download` | Forca redownload do modelo |

## O Que é Instalado

### Componentes Principais
- **ENXAME Bee CLI** (`bee` command)
- **Bibliotecas Python** em `/opt/enxame-bee` (Linux) ou pasta do app
- **Ollama** (runtime de modelos locais)
- **Modelo recomendado** baseado no hardware

### Diretórios de Dados
| Plataforma | Localização |
|------------|-------------|
| Linux | `~/.enxame/bee/` |
| macOS | `~/Library/Application Support/enxame/bee/` |
| Windows | `%LOCALAPPDATA%\enxame\bee\` |

### Serviços Systemd (Linux)
```bash
# Habilitar para usuario atual
systemctl --user enable --now enxame-bee

# Habilitar para usuario especifico (root)
sudo systemctl enable --now enxame-bee@usuario

# Ver logs
journalctl --user -u enxame-bee -f
```

### Serviços macOS (LaunchDaemon)
```bash
# Ollama ja instala como LaunchDaemon
sudo launchctl load -w /Library/LaunchDaemons/com.ollama.ollama.plist
```

### Serviços Windows
```powershell
# Ollama instala como servico automatico
# Bee pode rodar via Task Scheduler ou manual
bee start
```

## Pos-Instalacao

### Verificar Instalacao
```bash
bee status
```

### Iniciar Abelha
```bash
bee start
```

### Descobrir Peers na Rede
```bash
bee discover
```

### Fazer Primeira Query
```bash
bee query "Qual e o seu conhecimento sobre direito tributario?"
```

### Ver Capacidades do Hardware
```bash
bee capabilities
```

## Desinstalacao

### Windows
```powershell
# Via Settings > Apps > ENXAME Bee > Uninstall
# Ou PowerShell
.\uninstall_enxame.ps1
```

### macOS
```bash
sudo pkgutil --forget com.enxame.bee
sudo rm -rf /usr/local/bin/bee /usr/local/lib/enxame-bee
rm -rf ~/.enxame/bee
```

### Debian/Ubuntu
```bash
sudo apt-get remove --purge enxame-bee
sudo apt-get autoremove
```

### Arch Linux
```bash
sudo pacman -Rns enxame-bee
# Remove usuario e dados
sudo userdel enxame 2>/dev/null || true
sudo rm -rf /var/lib/enxame
```

### Linux Genérico
```bash
python3 -m bees.install.uninstall_bee
```

## Troubleshooting

### Ollama nao inicia
```bash
# Linux
sudo systemctl status ollama
sudo systemctl restart ollama

# macOS
launchctl list | grep ollama
brew services restart ollama

# Windows
# Verificar Services.msc > Ollama
```

### Modelo muito grande para hardware
```bash
# Forcar modelo menor
bee config set model "llama3.2:1b"
# Ou reinstalar forçando download
python3 -m bees.install.install_bee --force-model-download
```

### Python nao encontrado
```bash
# Ubuntu/Debian
sudo apt install python3 python3-pip python3-venv

# Arch
sudo pacman -S python python-pip

# Fedora
sudo dnf install python3 python3-pip

# macOS
brew install python3
```

### Permissao negada em /opt/enxame-bee
```bash
sudo chown -R $USER:$USER /opt/enxame-bee
```

### Portas em uso
```bash
# Verificar porta 8765
lsof -i :8765
netstat -tulpn | grep 8765
```

## Construindo Pacotes para Distribuicao

### Windows (Inno Setup)
```cmd
# Instalar Inno Setup 6+
# Compilar
iscc install_enxame.iss
# Saida: dist/enxame-bee-setup-1.0.0.exe
```

### macOS (.pkg)
```bash
./build_macos_pkg.sh
# Saida: dist/enxame-bee-1.0.0-installer.pkg
```

### Debian (.deb)
```bash
./build_deb.sh
# Saida: dist/enxame-bee_1.0.0-1_amd64.deb
```

### Arch (PKGBUILD)
```bash
makepkg -s  # Build only
makepkg -si # Build and install
# Saida: enxame-bee-1.0.0-1-x86_64.pkg.tar.zst
```

## Requisitos de Sistema

| Componente | Minimo | Recomendado |
|------------|--------|-------------|
| Python | 3.10+ | 3.11+ |
| RAM | 4 GB | 8+ GB |
| Disco | 2 GB | 10+ GB |
| CPU | 2 cores | 4+ cores |
| GPU | Opcional | NVIDIA 8GB+ VRAM |

## Suporte

- **Issues**: https://github.com/enxame/enxamepublic/issues
- **Discord**: https://discord.gg/enxame
- **Docs**: https://docs.enxame.dev