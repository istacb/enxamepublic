# ENXAME v1.0 — Agent Instructions

## Project Overview
Decentralized AI architecture: one Python service (the **bee**, aiohttp) that
works standalone and forms a swarm with other bees over mDNS. Zero Docker,
zero frontend frameworks, zero TypeScript.

**Key directories:**
- `bees/` — **The product.** Standalone Python package (own `pyproject.toml`):
  `service.py`, `cli.py`, `cluster/` (election, failover, global index),
  `protocol/`, `discovery.py`, `librarian.py`, `memory.py`, and the single
  installer in `bees/install/`
- `web/` — Pure HTML/CSS/JS interface (served at `/` by BeeService)
- `bibliotecario/` — RAG modules the bee imports: `embeddings`, `indexer`,
  `lancedb_store`, `universal_reader`, `web_client`, `zim_reader`
- `guardian/` — Prompt inspection, answer curation, anomaly patrol
- `core/` — Shared infra: mDNS discovery, signed HTTP, EXP security, compat shims
- `bees/spec/` — Product specs (BEE-000x) plus the EIPs the bee implements
  (0001, 0002, 0003, 0004, 0009)

Removed because nothing used them: `kernel/`, `runtime/`, `scheduler/`,
`service-loader/`, `failover/` (TypeScript with no `package.json`/`tsconfig`
anywhere, so uncompilable), and `api/`, `juiz/`, `agentes/`, `enxame_evolved/`
(a second FastAPI stack on port 7700 that only imported itself). Also gone:
`cli/`, `security/`, `test/`, root `requirements.txt`, and all tracked `.pyc`.

Removed as a consequence: `core/cluster/` and `core/memory/` were imported
**only** by that legacy stack, so they became orphans when it went away — the
bee has its own election in `bees/cluster/` and its own memory in
`bees/memory.py`. The root `spec/` tree (101 files, every document duplicated in
`en/` and `pt-BR/`) described the previous architecture — missions, workflows,
specializations, microkernel — of which exactly **one** file mentioned the bee.
The EIPs that do describe live code were consolidated into `bees/spec/`; the
rest stays in Git history.

---

## Developer Commands

### Run a bee (Development)
```bash
cd <repo-root>
python -m bees.service --host 0.0.0.0 --port 8765 --data-dir /tmp/bee1 --log-level INFO
```
Must be run as a **module from the repo root** — `bees/service.py` uses relative
imports and imports `core`, so `python bees/service.py` fails. Roles are not
configured: with 3+ bees they are **elected** at runtime (Juiz, Bibliotecária,
Guarda, Workers). One data-dir per bee — it holds `identity.json`, `config.json`,
`documents/` and the RAG index.

### Install — ONE command (the supported path)
```bash
python3 install-bee-smart.py --auto     # Windows: py install-bee-smart.py --auto
python3 install-bee-smart.py --dry-run  # Detect + show the plan, change nothing
```

Single implementation: `bees/install/bee_installer.py`. It checks Python,
installs Ollama if missing, recommends and pulls a model for the hardware,
creates `.venv-bee`, writes `<data-dir>/config.json` and `identity.json`, asks
about joining a swarm when it finds other bees on the network, and prints the
two commands that start the bee.

Flags: `--data-dir`, `--node-id`, `--bee-port`, `--cluster` / `--no-cluster`,
`--install-service`, `--no-shortcuts`, `--model`, `--skip-model`, `--ollama-url`,
`--uninstall`, `--legacy-env`.

### Run the bee
```bash
cd <repo-root>
.venv-bee/bin/python -m bees.service --host 0.0.0.0 --port 8765 --data-dir <data-dir>
# then open http://localhost:8765/
```
`python bees/service.py` does not work — relative imports plus `core` require
running it as a module from the repo root. The bee serves `web/` at `/` and the
same UI API the swarm uses (`/api/session`, `/api/chat`, `/api/status`,
`/api/cluster/discover`, `/api/guardian`).

### There is no legacy stack any more
`api/install/`, `juiz/`, `agentes/` and `enxame_evolved/` were deleted, together
with the `--legacy-env` flag and `generate_env_file()` in the installer (their
only consumer was `api/install/run_node.py`). Nothing in the bee imported them.
If you need them back they are in git history before commit
`Remove stack antiga`.

### Bee CLI
```bash
bee start --data-dir /tmp/bee1          # Start bee (one data-dir per bee)
bee query "sua pergunta"                 # Local query
bee discover                             # Discover peers
bee status                               # Full status
bee capabilities                         # Hardware caps + model recommendations
bee config show                          # Show config
```

### Test
```bash
# Full suite from the repo root (70 tests: bees/tests + bees/install)
python -m pytest bees/

# Bee core only (55 tests)
python -m pytest bees/tests/

# Installer/uninstaller tests only (45 tests)
python -m pytest bees/install/
```

> ⚠️ There is **no** EIP conformance validator in this repository. The
> `python -m juiz.validate --all` documented here before never existed, and the
> `juiz/` package (a FastAPI process from the removed legacy stack, not a
> validator) has been deleted.

### Lint / Typecheck (bees module)
```bash
cd bees
ruff check .
mypy .
```
Config: `bees/pyproject.toml` — ruff line-length=100, target-version=py310; mypy python_version=3.10, disallow_untyped_defs=true.

---

## Architecture Constraints (Must Follow)

| Principle | Rule |
|-----------|------|
| **EIP-0001: Architecture First** | No implementation without spec in `bees/spec/` |
| **EIP-0002: Resource First** | Zero Docker, zero frontend frameworks, minimal deps |
| **One service** | The bee (`bees/service.py`) is the product. No microkernel, no separate processes. |
| **Web UI** | Pure HTML/CSS/JS, zero business logic, served by the bee at `/`, REST to the bee's own `/api/*` |
| **Offline-First** | Local embeddings (sentence-transformers) primary, Ollama fallback |
| **Cluster** | Opt-in auto-cluster when 3+ peers detected (EIP-0009) |

---

## Key Conventions

- **Config**: `.env` files loaded by `run_node.py` — `ENXAME_NODE_ROLE`, `ENXAME_NODE_PORT`, `ENXAME_NODE_ID`
- **Bee Config**: `<data-dir>/config.json`, where `<data-dir>` is what
  `bees.config.get_default_data_dir()` returns (`~/.local/share/enxame/bee`
  on Linux, `%LOCALAPPDATA%\enxame\bee` on Windows,
  `~/Library/Application Support/enxame/bee` on macOS) unless overridden by
  `--data-dir` or `BEE_DATA_DIR` — keys include `offline_mode`,
  `cluster.enabled`, `embedding_model`, `allow_web`
- **mDNS Discovery**: `core.discovery.mdns_discovery.NodeAnnouncer` for node announcement
- **Bee Discovery**: `bees.discovery.BeeDiscoveryService` for peer discovery with capabilities
- **Async**: Use `asyncio` throughout Python services
- **Dependencies**: the installer owns them (`PYTHON_REQUIREMENTS` in
  `bees/install/bee_installer.py`, installed into `.venv-bee`). For manual
  setups use `bees/requirements.txt` or `pip install -e bees`. There is no
  root `requirements.txt` — the one that existed listed only legacy-stack
  packages (fastapi/uvicorn/typer) and omitted `aiohttp` and `cryptography`,
  so following it produced a bee that could not even import.
- **Specs**: All architectural changes require EIP in `bees/spec/` before implementation

---

## New Features (v1.0+)

### Offline-First Core
- **Local Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (384 dim) as primary
- **Ollama Fallback**: Only used if local embeddings unavailable
- **OCR**: Bundled tesseract support via `pytesseract`
- **Vision Models**: Smart download ≤2B params (`moondream:1.8b`, `qwen2-vl:2b`)
- **Offline Mode**: `offline_mode=true` disables all external calls

### Web UI v2 (served at `http://localhost:8765/`)
- **Peer Panel**: Real-time discovered bees with capabilities, load, models
- **File Upload**: Drag-drop PDF/DOCX/TXT/images → `/api/v1/ingest`
- **Settings Panel**: Offline mode, web fallback, confidence thresholds, model selection
- **Offline Badge**: Prominent indicator when offline_mode active
- **Export**: Conversation export to Markdown/JSON

### API Endpoints (BeeService)
```
GET  /health                    # Health check
GET  /api/v1/status             # Kernel, Runtime, Bibliotecário, Ollama, Peers, offline_mode
POST /api/v1/query              # LOCAL -> ENXAME -> WEB pipeline
GET  /api/v1/capabilities       # Capabilities + models + load
GET  /api/v1/peers              # Discovered peers with full manifest
POST /api/v1/ingest             # File upload (multipart)
GET  /api/v1/cluster            # Cluster status (EIP-0009)
```

### Auto-Cluster Opt-in (EIP-0009)
- Installer detects 3+ peers via mDNS → prompts to enable cluster
- Roles: Juiz, Bibliotecário, Guarda, Workers (auto-elected)
- Config: `cluster.enabled=true` in `config.json`
- Features: Failover, global index, intelligent routing

### Telemetry / Update Check (Opt-in)
- Anonymous stats: OS, RAM, CPU, GPU, model, queries, peers
- Weekly GitHub release check
- Opt-in prompt at install, stored in `telemetry.json`
- Zero PII: no IPs, no query content, no personal IDs

---

## Common Pitfalls

- **No `python bees/service.py`** — relative imports + `core` require `python -m bees.service` from the repo root.
- **No TypeScript, no package.json** — the `.ts` directories were removed; there is no build step in this repo.
- **Bees is a separate package** — Has own `pyproject.toml`, install with `pip install -e bees/` if needed.
- **Test discovery** — Tests live in `bees/tests/` and `bees/install/test_installers.py`; run `python -m pytest bees/`. The root `test/` directory was removed (it held a single empty fixture).
- **Web UI served by Bee** — Access at `http://localhost:8765/` (not separate server).
- **Offline mode** — Set `offline_mode=true` in config or `BEE_OFFLINE_MODE=true` env var.
- **Cluster config** — `cluster.enabled` in `<data-dir>/config.json`. The
  installer writes it (`--cluster` / `--no-cluster`, or the prompt it shows when
  it finds other bees). Set it to `false` to keep a bee out of the swarm: it then
  skips mDNS announcement entirely, so peers cannot elect it.

---

## File References

- Installer guide: `README.md` (§ Instalação) — one command
- Installer implementation: `bees/install/bee_installer.py` (the only one)
- Installer support modules: `bees/install/cluster_setup.py` (config.json,
  swarm opt-in, mDNS discovery), `bees/install/bee_setup.py` (shortcuts,
  systemd/LaunchAgent/schtasks service)
- Shims that delegate to it: `install-bee-smart.py` (repo root),
  `bees/install/universal_installer.py` (PyInstaller/AppImage entry point)
- Specs (product BEE-000x and EIPs): `bees/spec/`
- Bee CLI: `bees/cli.py`
- Telemetry: `bees/telemetry.py`
- Web UI: `web/`