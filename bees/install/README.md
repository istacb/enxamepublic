# Instaladores e Desinstaladores da Abelha

Este diretório contém scripts para instalação e remoção completa da Abelha.

## Estrutura

```
install/
├── install_bee.py          # Instalador principal (Python)
├── uninstall_bee.py        # Desinstalador principal (Python)
├── install-bee.sh          # Wrapper bash para Linux/macOS
├── uninstall-bee.sh        # Wrapper bash para Linux/macOS
├── install-bee.ps1         # Wrapper PowerShell para Windows (TODO)
└── uninstall-bee.ps1       # Wrapper PowerShell para Windows (TODO)
```

## Instalação Rápida

### Linux/macOS

```bash
# Método recomendado (pipe direto)
curl -fsSL https://.../install-bee.sh | bash

# Ou baixar e executar
wget https://.../install-bee.sh
chmod +x install-bee.sh
./install-bee.sh

# Com opções
./install-bee.sh --dry-run           # Simular sem instalar
./install-bee.sh --force-ollama      # Forçar reinstalação do Ollama
./install-bee.sh --skip-model-test   # Pular teste de inferência
```

### Windows (PowerShell)

```powershell
# TODO: Implementar
# Execute o instalador Python diretamente
python install_bee.py
```

### Instalação Manual (Python)

```bash
cd bees/install
python install_bee.py

# Opções disponíveis:
# --force-ollama         Forçar reinstalação do Ollama
# --force-model-download Forçar redownload do modelo
# --dry-run              Simular instalação
# --skip-model-test      Pular teste de inferência
```

## Desinstalação

### Linux/macOS

```bash
# Remover apenas a Abelha
./uninstall-bee.sh

# Remover Abelha + Ollama
./uninstall-bee.sh --remove-ollama

# Manter documentos indexados
./uninstall-bee.sh --keep-data

# Simular sem remover
./uninstall-bee.sh --dry-run

# Confirmar automaticamente (sem prompt)
./uninstall-bee.sh -y
```

### Windows (PowerShell)

```powershell
# TODO: Implementar
python uninstall_bee.py --remove-ollama
```

### Desinstalação Manual (Python)

```bash
cd bees/install
python uninstall_bee.py

# Opções disponíveis:
# --remove-ollama        Também remover Ollama
# --force-remove-ollama  Forçar remoção mesmo se não instalado pela Abelha
# --keep-data            Manter documentos e índices
# --dry-run              Simular desinstalação
# -y, --yes              Confirmar automaticamente
```

## O Que é Instalado

### Diretórios

| Caminho | Conteúdo |
|---------|----------|
| `~/.enxame/bee/` | Diretório principal da Abelha |
| `~/.enxame/bee/models/` | Modelos baixados (se aplicável) |
| `~/.enxame/bee/documents/` | Documentos indexados |
| `~/.enxame/bee/index/` | Índices vetoriais (LanceDB) |
| `~/.enxame/bee/memory/` | Memória e contexto (SQLite) |
| `~/.cache/enxame/` | Cache temporário |

### Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `~/.enxame/bee/manifest.json` | Manifesto da instalação |
| `~/.enxame/bee/install.log` | Log da instalação |
| `/usr/local/bin/ollama` | Binário do Ollama (Linux) |
| `/etc/systemd/system/ollama.service` | Serviço systemd (Linux) |

### Sistema

| Componente | Linux | macOS | Windows |
|------------|-------|-------|---------|
| Ollama binary | ✓ | ✓ | ✓ |
| Systemd service | ✓ | - | - |
| Launchd daemon | - | ✓ | - |
| Windows service | - | - | ✓ |

## Seleção Automática de Modelo

O instalador detecta hardware e seleciona modelo adequado:

| RAM Disponível | Modelo Recomendado | Categoria |
|----------------|-------------------|-----------|
| < 4 GB | qwen2:0.5b | tiny |
| 4-8 GB | llama3.2:1b | small |
| 8-16 GB | llama3.2:3b | medium |
| 16-32 GB | llama3:8b | large |
| > 32 GB | llama3.1:8b | xl |

**Com GPU dedicada:** Pode subir uma categoria se VRAM ≥ 8GB.

## Fluxo de Instalação

```
1. Detectar hardware (CPU, RAM, GPU, OS)
2. Verificar Ollama instalado
   ├─ Se não existir → Instalar
   └─ Se existir → Verificar versão
3. Selecionar modelo recomendado
   ├─ Analisar RAM + VRAM + CPU
   └─ Escolher categoria adequada
4. Baixar modelo via `ollama pull`
5. Testar inferência real
   ├─ Se falhar → Tentar modelo inferior
   └─ Se sucesso → Continuar
6. Salvar manifesto
7. Exibir status final
```

## Fluxo de Desinstalação

```
1. Verificar estado atual
2. Confirmar com usuário (exceto -y)
3. Parar serviços rodando
4. Remover diretórios da Abelha
   ├─ ~/.enxame/bee/
   └─ ~/.cache/enxame/
5. Se --remove-ollama:
   ├─ Parar serviço Ollama
   └─ Desinstalar Ollama
6. Limpar shell configs (.bashrc, .zshrc)
7. Exibir resumo
```

## Troubleshooting

### Falha na instalação do Ollama (Linux)

```bash
# Instalar manualmente
curl -fsSL https://ollama.com/install.sh | sh

# Depois executar instalador da Abelha
python install_bee.py --skip-ollama
```

### Modelo muito grande para hardware

```bash
# Forçar modelo menor
python install_bee.py --force-model-download

# Ou editar manifest e baixar manualmente
ollama pull llama3.2:1b
```

### Ollama não inicia automaticamente

```bash
# Linux
sudo systemctl start ollama
sudo systemctl enable ollama

# macOS
launchctl load -w /Library/LaunchDaemons/com.ollama.ollama.plist
```

### Espaço em disco insuficiente

```bash
# Limpar cache
rm -rf ~/.cache/enxame

# Remover modelos não usados
ollama rm <nome-do-modelo>
```

## Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `BEE_HOME` | `~/.enxame/bee` | Diretório base da Abelha |
| `OLLAMA_HOST` | `127.0.0.1:11434` | Host do Ollama |
| `OLLAMA_MODELS` | `~/.ollama/models` | Diretório de modelos |

## Logs

Após instalação, verifique:

```bash
# Log da instalação
cat ~/.enxame/bee/install.log

# Status da Abelha
python -c "from bees.install.install_bee import print_status; import json; m=json.load(open('~/.enxame/bee/manifest.json')); print_status(m)"
```

## Segurança

- Scripts verificam integridade antes de executar
- Ollama é baixado apenas de fontes oficiais
- Modelos são verificados após download
- Teste de inferência confirma funcionamento
- Manifesto registra auditoria completa

## Próximos Passos

Após instalação bem-sucedida:

```bash
# Verificar status
bee status

# Iniciar Abelha
bee start

# Ver outras Abelhas na rede
bee discover

# Fazer primeira consulta
bee query "Qual é o seu conhecimento sobre X?"
```

Documentação completa em: `bees/docs/`
