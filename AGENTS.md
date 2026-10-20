# ENXAME v1.0 — Agent Instructions

## Project Overview
Decentralized AI architecture with Python services (FastAPI) + TypeScript kernel/runtime. Zero Docker, zero frontend frameworks.

**Key directories:**
- `kernel/` — TypeScript microkernel (no domain logic)
- `runtime/` — TypeScript execution sandbox
- `juiz/` — Validation/conformance (FastAPI)
- `bibliotecario/` — Knowledge management (FastAPI)
- `agentes/` — Async agent workers
- `guardian/` — Security/auth/audit
- `bees/` — Standalone Python package (pyproject.toml)
- `web/` — Pure HTML/CSS/JS interface (served at `/` by BeeService)
- `api/install/` — Official installers (Linux/macOS/Windows)
- `spec/en/eip/` — Architecture specs (EIP-0001, EIP-0002)

---

## Developer Commands

### Run a Node (Development)
```bash
python3 api/install/run_node.py --env-file /path/to/.env
```
Role/port from `.env` (`ENXAME_NODE_ROLE`, `ENXAME_NODE_PORT`). Roles: `juiz` (port 7700), `bibliotecario` (7701), `agente`.

### Install / Update / Migrate / Uninstall
```bash
./api/install/install      # Install infra + deps
./api/install/update       # Update preserving data
./api/install/migrate      # Migrate from OpenWebUI
./api/install/uninstall    # Full removal
```

### Universal Installer (Cross-Platform)
```bash
python3 bees/install/universal_installer.py --auto          # Fully automatic
python3 bees/install/universal_installer.py --model llama3.2:3b  # Specific model
python3 bees/install/universal_installer.py --no-vision     # Skip vision model
python3 bees/install/universal_installer.py --dry-run       # Simulate only
```

### Bee CLI
```bash
bee start --data-dir ~/.enxame/bee      # Start bee
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

# Installer/uninstaller tests only (15 tests)
python -m pytest bees/install/
```

> ⚠️ There is **no** `juiz.validate` module in this repository, so
> `python -m juiz.validate --all` (previously documented here as "EIP
> conformance validation") fails with `No module named juiz.validate`.
> No EIP conformance validator exists yet.

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
| **EIP-0001: Architecture First** | No implementation without spec in `spec/en/eip/` |
| **EIP-0002: Resource First** | Zero Docker, zero frontend frameworks, minimal deps |
| **Kernel** | TypeScript, no IA/LLM/Mission/Judge references (see `kernel/README.md`) |
| **Services** | Python, independent, registered with Kernel |
| **Web UI** | Pure HTML/CSS/JS, zero business logic, REST to Kernel only |
| **Offline-First** | Local embeddings (sentence-transformers) primary, Ollama fallback |
| **Cluster** | Opt-in auto-cluster when 3+ peers detected (EIP-0009) |

---

## Key Conventions

- **Config**: `.env` files loaded by `run_node.py` — `ENXAME_NODE_ROLE`, `ENXAME_NODE_PORT`, `ENXAME_NODE_ID`
- **Bee Config**: `~/.enxame/bee/config.json` — `offline_mode`, `cluster.enabled`, `embedding_model`, `allow_web`
- **mDNS Discovery**: `core.discovery.mdns_discovery.NodeAnnouncer` for node announcement
- **Bee Discovery**: `bees.discovery.BeeDiscoveryService` for peer discovery with capabilities
- **Async**: Use `asyncio` throughout Python services
- **Dependencies**: Shared base in root `requirements.txt`; subdirs extend with `-r ../requirements.txt`
- **Specs**: All architectural changes require EIP in `spec/en/eip/` before implementation

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

- **No `python -m kernel.main`** — Kernel is TypeScript, not Python. Use `run_node.py` for Python services.
- **No global package.json** — Kernel/runtime are TypeScript but not npm packages (no build step documented).
- **Bees is a separate package** — Has own `pyproject.toml`, install with `pip install -e bees/` if needed.
- **Test discovery** — Root `test/` is nearly empty; real tests in `bees/tests/`.
- **Web UI served by Bee** — Access at `http://localhost:8765/` (not separate server).
- **Offline mode** — Set `offline_mode=true` in config or `BEE_OFFLINE_MODE=true` env var.
- **Cluster config** — Enable with `cluster.enabled=true` in config.json.

---

## File References

- Installer guide: `api/install/README.md`
- Universal installer: `bees/install/universal_installer.py`
- Kernel architecture: `kernel/README.md`
- EIP specs: `spec/en/eip/`
- Bees protocol specs: `bees/spec/`
- Bee CLI: `bees/cli.py`
- Telemetry: `bees/telemetry.py`
- Web UI: `web/`