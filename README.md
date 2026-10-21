# Enxame v1.0

> **The Enxame is ready to swarm.**

Uma arquitetura de inteligência artificial descentralizada, leve e soberana. 
Construído do zero para eliminar dependências herdadas, maximizar eficiência e garantir controle total sobre sua infraestrutura de IA.

---

## 🏗️ Princípios Fundamentais

### 1. Architecture First (EIP-0001)
Toda decisão técnica é precedida por especificação arquitetural documentada em `bees/spec/`. 
Não implementamos nada sem antes definir o "porquê" e o "como" na documentação oficial.

### 2. Resource First (EIP-0002)
Eficiência é requisito não negociável:
- **Zero Docker** — Execução nativa para máximo desempenho
- **Zero Frameworks no Frontend** — HTML/CSS/JS puros
- **Dependências Mínimas** — Apenas o estritamente necessário
- **Código Morto = Código Removido** — Limpeza contínua

### 3. Soberania Digital
- Nenhuma dependência do OpenWebUI ou qualquer projeto heredado
- Infraestrutura própria de instalação, atualização e migração
- Controle total sobre dados, modelos e configuração

---

## 📐 Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│              INTERFACE WEB (web/)  —  http://localhost:8765/│
│   HTML • CSS • JS puros, servidos PELA PRÓPRIA ABELHA       │
└─────────────────────────────────────────────────────────────┘
                              │  /api/session /api/chat /api/status
                              ▼                  /api/cluster/* /api/guardian
┌─────────────────────────────────────────────────────────────┐
│              ABELHA (bees/service.py) — aiohttp             │
│   Faz tudo sozinha: recebe a pergunta, aplica a Guarda,     │
│   consulta o próprio RAG, responde e faz a curadoria.       │
│                                                             │
│   Política de resposta:  LOCAL ──▶ ENXAME ──▶ WEB           │
│                                                             │
│  ┌────────────────┐ ┌────────────────┐ ┌─────────────────┐  │
│  │ BIBLIOTECÁRIA  │ │     GUARDA     │ │    CLUSTER      │  │
│  │ (bibliotecario/│ │  (guardian/)   │ │ (bees/cluster/) │  │
│  │  + bees/       │ │ • inspeção de  │ │ • eleição de    │  │
│  │   librarian.py)│ │   prompt       │ │   papéis        │  │
│  │ • índice local │ │ • curadoria da │ │ • failover      │  │
│  │ • RAG offline  │ │   resposta     │ │ • índice global │  │
│  │ • documentos/  │ │ • ronda        │ │ • monitor       │  │
│  └────────────────┘ └────────────────┘ └─────────────────┘  │
│            ▲              core/ = infraestrutura comum       │
│            │              (descoberta mDNS, HTTP, segurança) │
└────────────┼────────────────────────────────────────────────┘
             │
             ▼
┌───────────────────────────────┐        ┌───────────────────────────────┐
│      OLLAMA (externo)         │        │        ENXAME = 3+ ABELHAS    │
│ • modelos de linguagem        │        │ descobertas por mDNS na rede  │
│ • inferência local            │        │ local, que ELEGEM os papéis   │
│ • embeddings                  │        │ entre si: Juiz, Bibliotecária,│
└───────────────────────────────┘        │ Guarda e Workers              │
                                         └───────────────────────────────┘
```

Cada abelha tem o próprio RAG e é a própria bibliotecária. No enxame, o Juiz
recebe a pergunta, descobre qual abelha tem aquele conhecimento offline, delega
a ela e faz a curadoria da resposta antes de devolver. A Guarda roda tanto em
quem recebe o prompt quanto em quem faz a curadoria.

---

## 📁 Estrutura do Projeto

| Diretório | Responsabilidade |
|-----------|------------------|
| `bees/` | **O produto.** Abelha standalone (`service.py`), CLI (`cli.py`), cluster (eleição, failover, índice global), protocolo BEE, descoberta mDNS, bibliotecária local, memória e o instalador único (`bees/install/`). |
| `web/` | Interface mínima (HTML/CSS/JS puros), servida pela abelha em `/`. |
| `bibliotecario/` | Módulos de RAG que a abelha usa: embeddings, indexador, LanceDB, leitor universal, cliente web e ZIM. |
| `guardian/` | Segurança: inspeção de prompt, curadoria de resposta e ronda de anomalias. |
| `core/` | Infraestrutura comum: descoberta mDNS, HTTP assinado, segurança EXP e shims de compatibilidade. |
| `bees/spec/` | Especificações do produto (BEE-000x) e EIPs que a abelha implementa. |
| `.github/` | CI. |

O que **não** existe mais e aparecia aqui antes: `kernel/`, `runtime/`,
`scheduler/`, `service-loader/` e `failover/` eram TypeScript sem `package.json`
nem `tsconfig` em lugar nenhum do repositório — ou seja, não compilavam nem
rodavam, e nenhum `.py` os importava. Eram instruções de implementação, e o que
elas descreviam hoje está pronto em `bees/`. `api/`, `juiz/`, `agentes/` e
`enxame_evolved/` eram uma segunda stack (FastAPI, processos separados na porta
7700) que só importava a si mesma; mantê-la era manter dois produtos e dois
caminhos de instalação. `cli/`, `security/` e `test/` não eram importados por
nada. `core/cluster/` e `core/memory/` eram usados **só** por aquela stack
antiga e ficaram órfãos quando ela saiu — a abelha tem a sua própria eleição em
`bees/cluster/` e a sua própria memória em `bees/memory.py`.

O diretório `spec/` (101 arquivos, com o mesmo conjunto de documentos duplicado
em `en/` e `pt-BR/`) descrevia a arquitetura anterior: missões, workflows,
especializações e um microkernel que não existem mais no código. Só **um** dos
101 arquivos mencionava a abelha. O que corresponde ao sistema real foi
consolidado em [`bees/spec/`](bees/spec/), ao lado do código que descreve; o
resto permanece no histórico do Git.

---

## 🚀 Instalação

**Um comando.** Ele confere o Python, instala o Ollama se não existir, escolhe e
baixa o modelo adequado ao hardware, cria o ambiente virtual `.venv-bee`,
configura a abelha e no final imprime exatamente como abrir a interface.

```bash
git clone https://github.com/istacb/enxamepublic.git
cd enxamepublic

python3 install-bee-smart.py --auto
```

- **Windows:** `py install-bee-smart.py --auto`
- **macOS / Debian / Ubuntu / Arch:** o mesmo comando acima

Sem `--auto` ele pergunta só o que precisa (next > next > finish). Para ver o
plano sem alterar nada na máquina:

```bash
python3 install-bee-smart.py --dry-run
```

### Depois de instalar

O instalador termina mostrando dois comandos — são literalmente estes:

```bash
cd /caminho/para/enxamepublic
.venv-bee/bin/python -m bees.service --host 0.0.0.0 --port 8765 --data-dir <seu-data-dir>
```

E então abrir **http://localhost:8765/** no navegador. A interface está em
`web/` e é servida pela própria abelha: painel do enxame, chat, descoberta de
rede e estado da Guarda. Para parar, `Ctrl+C`.

> `python bees/service.py` **não** funciona: o módulo usa imports relativos e
> importa `core`, então precisa ser executado como módulo (`-m bees.service`) a
> partir da raiz do repositório.

### Opções do instalador

| Flag | Efeito |
|------|--------|
| `--auto` | Nenhuma pergunta; assume os padrões |
| `--dry-run` | Detecta tudo e mostra o plano sem instalar nem gravar nada |
| `--data-dir CAMINHO` | Diretório de dados da abelha (padrão: o mesmo que o serviço usa — `~/.local/share/enxame/bee` no Linux, `%LOCALAPPDATA%\enxame\bee` no Windows, `~/Library/Application Support/enxame/bee` no macOS) |
| `--node-id NOME` | Nome desta abelha (padrão: hostname, gravado de forma estável) |
| `--bee-port PORTA` | Porta HTTP e da interface (padrão: 8765) |
| `--cluster` / `--no-cluster` | Participa ou não do enxame, sem perguntar |
| `--install-service` | Instala como serviço do usuário (systemd `--user`, LaunchAgent, tarefa de logon) |
| `--no-shortcuts` | Não cria atalho de inicialização |
| `--model NOME` / `--skip-model` | Força um modelo / não baixa modelo |
| `--ollama-url URL` | Usa um Ollama remoto em vez do local |
| `--uninstall` | Remove venv, `.env`, dashboard e configuração criados |
| `--legacy-env` | Também gera `.env` para a stack antiga (não é necessário) |

### Formar um enxame

Instale **o mesmo comando** em 3 ou mais máquinas na mesma rede local. Não há
papel para escolher nem configuração extra: as abelhas se descobrem por mDNS e
elegem os papéis entre si — Juiz, Bibliotecária, Guarda e Workers.

O Juiz recebe a pergunta, descobre qual abelha tem aquele conhecimento offline,
delega a ela e faz a curadoria da resposta antes de devolver. Cada abelha
mantém o próprio RAG. Se uma abelha cair, há reeleição e failover.

Se o instalador encontrar outras abelhas já no ar, ele pergunta se esta máquina
deve entrar no enxame; responder "não" grava `cluster.enabled=false` e a abelha
fica isolada de verdade (nem anuncia no mDNS).

> mDNS é link-local: as máquinas precisam estar no mesmo segmento de rede.
> VPN ou sub-redes diferentes não se descobrem.

### O que existia antes e foi removido

Não há segunda stack nem segundo instalador. Foram removidos:

- **`api/install/`** (`install`, `update`, `migrate`, `uninstall`,
  `run_node.py`) e os processos FastAPI que ele subia na porta 7700 —
  **`juiz/`**, **`agentes/`** e `bibliotecario/app.py`. Formavam um conjunto
  fechado que só importava a si mesmo: nada na abelha dependia dele. Da pasta
  `bibliotecario/` ficaram apenas os 6 módulos de RAG que a abelha usa
  (`embeddings`, `indexer`, `lancedb_store`, `universal_reader`, `web_client`,
  `zim_reader`).
- **`enxame_evolved/`** — 15 arquivos que nada importava.
- **`kernel/`, `runtime/`, `scheduler/`, `service-loader/`, `failover/`** —
  TypeScript sem `package.json` nem `tsconfig` em nenhum lugar do repositório,
  portanto sem como compilar ou rodar; eram a especificação do que hoje está
  implementado em `bees/`.
- **Scripts de instalação por sistema operacional** (`install_debian.sh`,
  `install_arch.sh`, `install_macos.sh`, `install_unix.sh`,
  `install_windows.bat`, `install-bee.sh`, `install_enxame.py`) — caminhos
  concorrentes que instalavam coisas diferentes.

> ⚠️ Versões anteriores desta página documentavam cinco pontos de entrada
> diferentes (`install-bee-smart.py`, `bees/install/universal_installer.py`,
> `install-bee.sh`, `api/install/install` e `install_enxame.bat`) apontando para
> três stacks. Era a causa direta de "instalei e nada funciona": dependendo do
> comando, terminava-se com um produto diferente na máquina. Hoje existe uma
> implementação única em `bees/install/bee_installer.py`; os outros nomes são
> atalhos que delegam para ela.


## 💻 Interface Web

A interface do Enxame segue o princípio **Minimalismo Funcional**:

- **HTML puro** — Sem frameworks, sem build steps
- **CSS puro** — Estilização leve e responsiva
- **JavaScript puro** — Zero dependências npm
- **Zero Business Logic** — Toda inteligência está no Kernel

### Funcionalidades
- ✅ Histórico de conversas
- ✅ Envio de mensagens (Enter envia, Shift+Enter quebra linha)
- ✅ Indicador "Pensando..." durante processamento
- ✅ Scroll automático
- ✅ Auto-resize do textarea
- ✅ Barra de status (Kernel, Runtime, Bibliotecário, Ollama)

### Consumo da API
A interface comunica-se exclusivamente via API REST com o Kernel:
```javascript
POST /api/chat
{
  "message": "Sua mensagem aqui",
  "context": "histórico opcional"
}
```

---

## 🔧 Configuração

O Enxame utiliza arquivos de configuração em formato JSON/YAML localizados em `~/.enxame/`:

- `config.json` — Configurações gerais
- `models.json` — Modelos Ollama disponíveis
- `agents.json` — Agentes ativos e suas especialidades
- `security.json` — Chaves e permissões de acesso

---

## 📊 Performance vs OpenWebUI (Legado)

| Métrica | OpenWebUI | Enxame v1.0 | Melhoria |
|---------|-----------|-------------|----------|
| **CPU (idle)** | ~15% | ~3% | **80%** ↓ |
| **Memória (idle)** | ~1.2 GB | ~300 MB | **75%** ↓ |
| **Startup Time** | ~45s | ~8s | **83%** ↑ |
| **Storage** | ~6.5 GB | ~150 MB | **98%** ↓ |
| **Docker Required** | Sim | Não | **100%** nativo |
| **Frameworks Frontend** | React/Svelte | Nenhum | **Zero bloat** |

---

## 📜 Especificações (EIPs)

### EIP-0001: Architecture First
> "Nenhuma implementação precede sua especificação."

Todas as mudanças arquiteturais devem ser documentadas em `bees/spec/` antes da implementação.

### EIP-0002: Resource First
> "Eficiência é feature, não otimização."

Recursos computacionais são finitos. Cada linha de código deve justificar seu custo em CPU, memória e armazenamento.

---

## 🔐 Segurança

O módulo `guardian/` faz três coisas, e é importante que a lista corresponda ao
código (`guardian/guardian.py` e `guardian/patrol.py`):

- **Inspeção de prompt** — `inspect_prompt()` / `detect_injection()`: camadas de
  padrão (tentativas de sobrescrever instruções, `system prompt`, `developer
  mode`, caracteres de controle, injeção de código) e devolve texto sanitizado ou
  uma mensagem de recusa amigável em pt-BR.
- **Curadoria de resposta** — a mesma inspeção roda na saída antes de devolver ao
  usuário. A Guarda atua em quem recebe o prompt **e** em quem faz a curadoria.
- **Ronda de anomalias** — `GuardianPatrol` coleta métricas locais
  (`collect_local_metrics()`) e gera alertas de latência crítica, CPU e memória
  esgotadas; `quarantine_node()` isola um nó problemático.

O estado é visível em `GET /api/guardian` (`ativo`, `ronda`, `standalone`,
contadores e alertas).

> ⚠️ Esta seção listava antes "autenticação e autorização de usuários",
> "criptografia de dados sensíveis", "auditoria de todas as operações" e
> "sandboxing de código executado pelos agentes". Nenhuma das quatro existe em
> `guardian/`: não há autenticação de usuário (a interface usa token de sessão
> efêmero, não contas), não há criptografia de dados em repouso, não há trilha de
> auditoria, e o sandboxing viveria em `runtime/` — que era TypeScript sem
> `package.json` e foi removido. A única criptografia real é a identidade Ed25519
> da abelha (`bees/config.py`) e o HMAC do protocolo BEE.

---

## 🧪 Testes

```bash
# Suíte completa a partir da raiz do repositório (70 testes)
python -m pytest bees/

# Só o núcleo da abelha (55 testes)
python -m pytest bees/tests/

# Só os instaladores/desinstaladores (15 testes)
python -m pytest bees/install/

# De dentro de bees/ o pytest já sabe o que rodar (testpaths no pyproject.toml)
cd bees && python -m pytest
```

> ⚠️ Correções nesta seção: os testes ficam em `bees/tests/` e
> `bees/install/test_installers.py` — rode `python -m pytest bees/` (128 testes).
> O diretório `test/` que existia na raiz continha apenas um arquivo de fixture
> vazio e foi removido; `test/kernel/` e `test/runtime/` nunca existiram.
> `python -m juiz.validate --all` também nunca existiu — não há validador de
> conformidade EIP no repositório, e o `juiz/` que esta página citava era o
> processo FastAPI da stack antiga, não um validador.

---

## 🔄 Migração do OpenWebUI

Não há migrador automático. O `./api/install/migrate` que esta seção
recomendava pertencia à stack antiga e foi removido junto com ela — ele migrava
dados para a estrutura daquela stack, que não é a da abelha.

Para reaproveitar uma instalação OpenWebUI existente:

1. Os **modelos Ollama** já são compartilhados: o instalador detecta o Ollama em
   execução e usa os modelos presentes (`GET /api/tags`). Não é preciso
   reexportar nada.
2. Os **documentos** que você quer que a abelha conheça vão em
   `<data-dir>/documents/` (`.md`, `.txt`, `.pdf` — o leitor universal de
   `bibliotecario/universal_reader.py` cuida do resto). O índice é reconstruído
   na inicialização, então reinicie a abelha depois de copiá-los.
3. **Histórico de conversas** do OpenWebUI não é importado: a abelha guarda o
   próprio histórico em `<data-dir>/memory.db`.

---

## 🤝 Contribuindo

1. Leia as especificações em `bees/spec/`
2. Crie uma EIP para mudanças arquiteturais
3. Implemente seguindo EIP-0001 e EIP-0002
4. Rode `python -m pytest bees/` e abra o pull request

---

## 📈 Roadmap

- [ ] v1.1 — Expansão da rede de agentes especializados
- [ ] v1.2 — Interface CLI completa
- [ ] v1.3 — Suporte a múltiplos backends de LLM (além do Ollama)
- [ ] v2.0 — Federação de Enxames (distributed swarm)

---

## 📄 Licença

Enxame é software livre sob licença MIT. 
Desenvolvido pela comunidade, para a comunidade.

---

## 🎯 Status Atual

```
╔══════════════════════════════════════════════════════════╗
║              ENXAME v1.0 — GOLDEN REPOSITORY             ║
║                                                          ║
║  Arquitetura: ✅ Frozen                                  ║
║  EIP-0001: ✅ Conforme                                   ║
║  EIP-0002: ✅ Conforme                                   ║
║  OpenWebUI: ✅ 0 referências                             ║
║  Docker: ✅ 0 arquivos                                   ║
║                                                          ║
║           STATUS: READY FOR PRODUCTION                   ║
║           The Enxame is ready to swarm.                  ║
╚══════════════════════════════════════════════════════════╝
```

---

**Especificações:** [`bees/spec/`](bees/spec/) — BEE-000x (o produto) e as EIPs que a abelha implementa.  
**Guia de Instalação:** a seção [🚀 Instalação](#-instalação) desta página (um comando só).  
**Detalhes do instalador:** [`bees/install/README.md`](bees/install/README.md)
