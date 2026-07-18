# ENXAME v3 - Sistema de Comunicação Descentralizada com IA

## Visão Geral

O **ENXAME** é um sistema modular, multiplataforma, seguro e **offline-first** para comunicação descentralizada entre PCs, utilizando IA para melhorar o desempenho. O sistema é auto-detectável para os nós, com auto-sincronia, vigilância e capacidade de assumir papéis quando algum dos PCs cai.

## Arquitetura

### Papéis do Sistema

| Papel | Responsabilidades | Acesso à Internet |
|-------|------------------|-------------------|
| **Juiz** | Recebe prompts, distribui tarefas, sintetiza respostas, define papéis por benchmark, monitora heartbeats | Sim (atualizações) |
| **Bibliotecário** | Indexação e pesquisa de arquivos, movimentação de arquivos entre PCs | Sim (fallback) |
| **Worker** | Processamento pesado, geração de respostas baseadas no modelo local | Não |
| **Artista** | Criação de imagens/vídeos, aceleração de workers em ociosidade | Não |
| **Guardião** | Defesa contra prompt injection, malware, ransomware, validação de integridade | Não |

### Perfis de Worker Disponíveis

1. **Contábil + Jurídico Tributário** (`worker_contabil.json`)
2. **Engenharia Civil** (`worker_engenharia.json`)
3. **RH + Jurídico Trabalhista** (`rh_trabalhista.json`) - NOVO
4. **Auxiliar de Vendas** (`auxiliar_vendas.json`) - NOVO
5. **Guardião** (`guardian.json`) - NOVO

## Instalação "Next > Next > Finish"

### Ubuntu/Debian

```bash
sudo ./installers/install_ubuntu.sh
```

**O instalador faz automaticamente:**
- ✅ Instala dependências do sistema (Python, SQLite, etc.)
- ✅ Cria ambiente virtual Python
- ✅ Instala dependências Python
- ✅ Configura serviços systemd (Juiz, Guardian)
- ✅ Instala e configura Ollama com modelos recomendados
- ✅ Configura firewall (se ativo)
- ✅ Cria comando `enxame` para gerenciamento

### Windows

```batch
installers\install_windows.bat
```

**Execute como Administrador.** O instalador faz automaticamente:
- ✅ Verifica/instala Python
- ✅ Instala dependências Python
- ✅ Instala Ollama para Windows
- ✅ Cria atalho na Área de Trabalho
- ✅ Configura firewall do Windows
- ✅ Gera scripts de inicialização

### macOS

```bash
sudo ./installers/install_macos.sh
```

**Requer Homebrew** (será instalado se necessário). O instalador faz automaticamente:
- ✅ Instala Python via Homebrew
- ✅ Instala dependências Python
- ✅ Instala Ollama via Homebrew Cask
- ✅ Configura LaunchAgents para inicialização automática
- ✅ Configura firewall do macOS

## Comandos Úteis

### Linux/macOS

```bash
enxame status    # Ver status dos serviços
enxame start     # Iniciar serviços
enxame stop      # Parar serviços
enxame restart   # Reiniciar serviços
enxame logs      # Ver logs em tempo real
```

### Windows

Use os scripts na pasta de instalação:
- `start_all.bat` - Inicia todos os serviços
- `start_juiz.bat` - Inicia apenas o Juiz
- `start_guardian.bat` - Inicia apenas o Guardian

## API Endpoints

### Juiz (porta 7700)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/v1/perguntar` | POST | Envia uma pergunta ao enxame |
| `/api/v1/workers` | GET | Lista workers ativos |
| `/api/v1/workers/registrar` | POST | Registra um novo worker |
| `/api/v1/buscar` | GET | Busca na base ZIM |
| `/api/v1/health` | GET | Status do serviço |

### Guardian (porta 7720)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/v1/analisar_prompt` | POST | Analisa prompt em busca de injection |
| `/api/v1/verificar_arquivo` | POST | Verifica integridade de arquivo |
| `/api/v1/reportar_incidente` | POST | Reporta incidente de segurança |
| `/api/v1/incidentes` | GET | Lista incidentes registrados |
| `/api/v1/nos` | GET | Lista nós monitorados |
| `/api/v1/quarentena` | GET | Lista arquivos em quarentena |

## Funcionalidades Implementadas

### ✅ Offline-First
- Todas as operações principais funcionam sem internet
- Modelos de IA rodam localmente via Ollama
- Base de conhecimento indexada localmente
- Memória de longo prazo do usuário armazenada localmente

### ✅ Multiplataforma
- Instaladores automáticos para Ubuntu/Debian, Windows e macOS
- Serviços nativos em cada plataforma (systemd, LaunchAgents, Services)
- Comunicação entre plataformas via HTTP/REST

### ✅ Segurança (Guardian)
- Detecção de prompt injection
- Validação de integridade de arquivos (SHA-256)
- Quarentena de arquivos suspeitos
- Monitoramento de confiabilidade de nós
- Registro de incidentes de segurança

### ✅ Failover Automático
- Monitoramento contínuo de heartbeats
- Detecção de falhas em tempo real
- Eleição automática de substitutos para papéis críticos
- Notificação aos demais nós sobre mudanças

### ✅ Memória de Longo Prazo
- Armazenamento de preferências do usuário
- Histórico completo de interações
- Aprendizado de padrões de trabalho
- Recuperação de contexto relevante

### ✅ Perfis Especializados
- Contábil + Jurídico Tributário
- Engenharia Civil
- RH + Jurídico Trabalhista
- Auxiliar de Vendas
- Guardião de Segurança

## Estrutura de Diretórios

```
~/enxame/
├── logs/           # Logs do sistema
├── memory/         # Memória do usuário (SQLite)
├── guardian/       # Dados de segurança
│   ├── security.db
│   └── quarantine/ # Arquivos quarentenados
├── failover/       # Estado do cluster
│   └── estado.db
├── data/           # Bases de conhecimento
│   ├── kb_contabil/
│   ├── kb_engenharia/
│   ├── kb_rh_trabalhista/
│   ├── kb_vendas/
│   └── kb_seguranca/
├── perfis/         # Perfis JSON dos workers
└── .env            # Configuração local
```

## Requisitos Mínimos

- **CPU**: Dual-core 2.0 GHz ou superior
- **RAM**: 4 GB mínimo, 8 GB recomendado
- **Armazenamento**: 10 GB livres
- **Rede**: Ethernet ou Wi-Fi (todos os nós na mesma rede)
- **SO**: Ubuntu 20.04+, Windows 10+, macOS 10.15+

## Tecnologias Utilizadas

- **Python 3.11+** - Linguagem principal
- **FastAPI** - Framework web assíncrono
- **SQLite** - Banco de dados leve
- **Ollama** - Execução local de modelos de IA
- **Systemd/LaunchAgents** - Gerenciamento de serviços
- **NumPy** - Operações numéricas para embeddings

## Próximos Passos

1. **Documentação adicional**: Criar guias específicos para cada perfil
2. **Interface web**: Melhorar o chat HTML existente
3. **Testes automatizados**: Expandir cobertura de testes
4. **Docker**: Melhorar suporte a containers para deploy avançado

## Contribuição

Este projeto é open source. Consulte o repositório original:
https://github.com/istacb/enxamepublic

## Licença

Verifique o arquivo LICENSE no repositório original.

---

**ENXAME v3** - Comunicação descentralizada inteligente para PCs antigos e modernos.
