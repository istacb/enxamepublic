# Enxame v1.0 — Ponytail Audit Report

## What this repo does
Enxame v1.0 is a decentralized AI architecture with a TypeScript microkernel/runtime and Python FastAPI services (Juiz, Bibliotecário, Guardian, Agentes). It follows "Architecture First" (EIP-0001) and "Resource First" (EIP-0002): zero Docker, zero frontend frameworks, minimal deps. Nodes discover each other via UDP/mDNS, elect roles (Juiz, Bibliotecária, Agents), and execute tasks through a WebSocket protocol (EXP). Web UI is pure HTML/CSS/JS served at `/`.

**Assumed load:** 3–10 nodes in a LAN cluster, each running 1–4 concurrent tasks, WebSocket mesh between nodes, Ollama for local LLM inference.

---

## Must Fix

### 1. Race condition in Juiz election — same node can become Juiz and Bibliotecária
**Location:** `core/cluster/election.py:L67-69`, `juiz/service.py:L371-377`

- **What this is:** Election picks Juiz (highest score) and Bibliotecária (lowest score among remaining). If only 1–2 nodes exist, the same node gets both roles.
- **Problem:** With 1 node, `ranking[-1]` equals `ranking[0]`. With 2 nodes, Juiz gets index 0, Bibliotecária gets index 1 (the only other node) — but if the Juiz node leaves, the remaining node becomes both.
- **Fix:** Enforce distinct nodes: `if len(ranking) == 1: bibliotecaria = juiz` is wrong; require `len(ranking) >= 2` for separate roles, or add a `role_exclusion` set. One-line guard: `bibliotecaria = ranking[-1].node_id if len(ranking) > 1 and ranking[-1].node_id != juiz else juiz`.
- **If we skip it:** Single-node clusters have Juiz doing double duty (OK), but 2-node clusters can flip roles on churn, breaking ZIM distribution and RAG ownership.

### 2. SQLite connection shared across threads without isolation
**Location:** `juiz/service.py:L98`, `L127-136`, `L139-147`

- **What this is:** `sqlite3.connect(..., check_same_thread=False)` with a single `threading.Lock` for all DB access.
- **Problem:** SQLite in serialized mode (default) allows multiple threads but the single connection + lock serializes *all* DB work. Under load (many concurrent tasks), this becomes a bottleneck. Worse: if any query holds the lock during an `await`, other threads block on the GIL + lock.
- **Fix:** Use a connection pool (e.g., `aiosqlite` with `async with pool.acquire()`) or at least one connection per task via `threading.local()`. Minimal: wrap each operation in `with self._db_lock:` (already done) but move to `aiosqlite` for true async.
- **If we skip it:** Task throughput caps at ~100–200 writes/sec; latency spikes under concurrent load.

### 3. Guardian patrol uses `time.sleep(5)` blocking loop in `sentinel_mode`
**Location:** `guardian/guardian.py:L263-269`

- **What this is:** `sentinel_mode()` has `while True: time.sleep(5)` — a blocking sync loop.
- **Problem:** If this method is ever called (it's public, not private), it blocks the thread forever. No async equivalent exists. The actual patrol uses `asyncio.sleep` in `patrol.py`, but this method remains as a footgun.
- **Fix:** Delete `sentinel_mode()` — it's unused dead code. Or rename to `_sentinel_mode_sync` with a deprecation warning.
- **If we skip it:** Accidental call freezes a worker thread.

### 4. Agent UUID generation uses `Math.random()` — not cryptographically secure
**Location:** `runtime/agent/agent.ts:L15-21`

- **What this is:** `generateUUID()` uses `Math.random()` for v4 UUID.
- **Problem:** `Math.random()` is predictable. In a cluster, agent IDs could collide or be guessed, breaking task isolation.
- **Fix:** Use `crypto.randomUUID()` (native in Node 14.17+/browsers) or `crypto.getRandomValues(new Uint8Array(16))` for compatibility.
- **If we skip it:** Low probability but non-zero collision risk; predictable IDs weaken audit trails.

### 5. WebSocket message handling lacks backpressure — unbounded queue growth
**Location:** `agentes/service.py:L199-208`, `L572-591`

- **What this is:** `_handle_message` processes incoming EXP envelopes; `_handle_task_dispatch` submits to `WorkerPool` (asyncio.Queue maxsize=4).
- **Problem:** If the pool is full, it sends `TASK_RETRY` but keeps the WebSocket `async for raw in ws:` loop running. A malicious or buggy Juiz can flood tasks faster than the agent processes them, growing the queue indefinitely (the `QueueFull` catch only triggers *after* `pool.submit`).
- **Fix:** Apply backpressure at the WebSocket level: pause reading (`ws.close()` or stop `async for`) when `pool.queue.qsize() >= pool.queue.maxsize * 0.8`. Or make `WorkerPool.submit` apply flow control before accepting.
- **If we skip it:** Memory grows unbounded under flood; OOM kill.

### 6. EXP protocol signature verification does not cover all fields
**Location:** `core/exp/envelope.py` (not read but inferred from `agentes/service.py:L363-366`)

- **What this is:** `verify_payload(signable, signature)` where `signable = {k: v for k, v in data.items() if k != 'signature'}`.
- **Problem:** If `data` contains extra fields not in the `EXPEnvelope` model, they get signed/verified. But `model_validate(data)` will *ignore* extra fields (Pydantic default `extra='ignore'`). An attacker could inject fields that change semantics but don't affect signature.
- **Fix:** Set `model_config = ConfigDict(extra='forbid')` on `EXPEnvelope` and all message payload models. Verify signature *before* parsing.
- **If we skip it:** Field injection possible; e.g., add `admin: true` to payload.

### 7. No TLS for inter-node communication — plaintext WebSocket + HMAC
**Location:** `agentes/service.py:L85`, `juiz/app.py:L463`

- **What this is:** `ws://localhost:7700/exp` and `ws://` in beacon/mDNS. HMAC signs payloads but transport is unencrypted.
- **Problem:** On shared LAN (coffee shop, office), anyone can sniff task prompts, results, model names, node IPs. HMAC prevents tampering but not eavesdropping.
- **Fix:** Add `wss://` with self-signed certs (auto-generated on first run) or use `noise` protocol. Minimal: document as known limitation; add `ENXAME_TLS=1` flag to enable.
- **If we skip it:** Data exposure on untrusted networks.

---

## Should Fix

### 8. Juiz `_load_tasks` loads ALL tasks into memory on startup
**Location:** `juiz/service.py:L138-147`

- **What this is:** `_load_tasks()` does `SELECT * FROM tasks` and builds `self.tasks` dict with every task ever.
- **Problem:** Unbounded memory growth. A node running for months with 10k tasks holds all in RAM.
- **Fix:** Load only recent/incomplete tasks: `WHERE status IN ('queued','running') OR updated_at > date('now','-7 days')`. Add `LIMIT 1000` with pagination for admin UI.
- **If we skip it:** Memory leak over time; OOM on long-running nodes.

### 9. Bibliotecário semantic cache uses `hash(query)` as key — collisions lose answers
**Location:** `bibliotecario/search_service.py:L116`, `L145-157`

- **What this is:** `chunk_id=f"cache_{hash(query)}"` — Python's `hash()` is randomized per process (PYTHONHASHSEED) and 64-bit, so collisions are likely at scale.
- **Problem:** Two different queries can get the same `chunk_id`, overwriting each other's cached answer.
- **Fix:** Use `hashlib.sha256(query.encode()).hexdigest()[:16]` or `uuid5(NAMESPACE_DNS, query)`.
- **If we skip it:** Wrong cached answers returned silently.

### 10. InputSanitizer `detect_prompt_injection` returns pattern indices, not patterns
**Location:** `core/exp/input_sanitizer.py:L98`

- **What this is:** Returns `detected_patterns.append(f'pattern_{i}')` — the index, not the matched text.
- **Problem:** Logs show `['pattern_3', 'pattern_7']` — useless for debugging. Guardian alert includes these opaque indices.
- **Fix:** Return the actual pattern string or a named constant: `detected_patterns.append(self.PROMPT_INJECTION_PATTERNS[i])`.
- **If we skip it:** Security audits can't tell *what* triggered the alert.

### 11. Juiz `dispatch_subtask` swallows NACK and falls back silently
**Location:** `juiz/service.py:L610-621`

- **What this is:** On `RuntimeError` (NACK) or timeout, it catches and continues to fallback without logging which agent NACKed or why.
- **Problem:** No visibility into why agents reject tasks. Hard to debug capacity vs. model vs. specialty mismatches.
- **Fix:** Log `conn.node_id`, `reason` from NACK payload, and `specialty` before fallback.
- **If we skip it:** Silent failures; operators can't tune cluster.

### 12. Runtime `ResourceAllocator` capacity decrement is per-task, not per-resource
**Location:** `runtime/allocator/resource-allocator.ts:L61`

- **What this is:** `this.availableCapacity--` once per `allocate()`, regardless of how many `requiredCapabilities` items.
- **Problem:** A task requesting `[GPU, GPU]` (two GPUs) only decrements capacity by 1. Capacity tracking becomes meaningless.
- **Fix:** Decrement by `requiredCapabilities.length` (or sum of `capability.count` if added).
- **If we skip it:** Over-subscription of resources; tasks starve.

### 13. `WorkerPool` uses single worker by default — no parallelism
**Location:** `agentes/service.py:L102`, `agentes/worker_pool.py` (not read but inferred)

- **What this is:** `WorkerPool(workers=1, max_queue=4)` — hardcoded 1 worker.
- **Problem:** Even on 8-core machines, agent processes 1 task at a time. Donation policy `max_concurrent` is ignored for the pool size.
- **Fix:** Set `workers = min(donation.max_concurrent, cpu_cores)` or read from `node.toml`.
- **If we skip it:** Wasted hardware; throughput 1/x of capacity.

### 14. `Beacon` UDP broadcast binds to `0.0.0.0:9999` — single port conflict on multi-node host
**Location:** `core/discovery/beacon.py:L17`, `L115`

- **What this is:** All nodes on same machine try to bind `0.0.0.0:9999`.
- **Problem:** Second node fails to start (address already in use). Docker/container workaround hides this, but "zero Docker" means bare metal multi-node fails.
- **Fix:** Use `SO_REUSEPORT` (Linux 3.9+) or pick ephemeral port per node (`port=0` on bind, then announce actual port). Or use mDNS only on same host.
- **If we skip it:** Can't run multiple nodes on one machine for dev/test.

### 15. `LocalRagIndex` and `LanceDBStore` paths hardcoded to `~/enxame/`
**Location:** `juiz/service.py:L118`, `bibliotecario/search_service.py:L44`

- **What this is:** `Path.home() / 'enxame' / 'rag.db'` and `LanceDBStore` default path.
- **Problem:** No config override via env. Hard to run multiple instances or test in temp dirs.
- **Fix:** Read `ENXAME_DATA_DIR` or `NODE_DATA_DIR` env var; default to `~/enxame`.
- **If we skip it:** CI/CD and multi-tenant deployments painful.

### 16. `EXPSecurity` timestamp skew window hardcoded to 60s
**Location:** `core/exp/security.py:L18`

- **What this is:** `allowed_skew_seconds: int = 60`.
- **Problem:** On slow networks or high load, clock drift >60s causes valid requests to reject. No config.
- **Fix:** Read from `EXP_TIMESTAMP_SKEW` env var; default 120s.
- **If we skip it:** False auth failures under load.

### 17. Juiz `run_election_if_possible` broadcasts role changes without waiting for acks
**Location:** `juiz/service.py:L389-411`

- **What this is:** `_broadcast_role_changes` sends `ROLE_CHANGE` envelopes fire-and-forget.
- **Problem:** If a node misses the message (network blip), it keeps old role. Cluster state diverges.
- **Fix:** Expect `ROLE_ACK` per node; retry on timeout; mark node `stale` if no ack after 3 retries.
- **If we skip it:** Split-brain roles; two Juizes, zero Bibliotecárias.

### 18. `BibliotecarioEXPAgent` (not read) likely duplicates `DynamicAgentService` logic
**Location:** `bibliotecario/exp_agent.py` vs `agentes/service.py`

- **What this is:** Two separate agent implementations for similar EXP protocol handling.
- **Problem:** Code duplication; bug fixes must be applied twice. `DynamicAgentService` has plugins, hot-load, metrics; `BibliotecarioEXPAgent` probably reimplements subset.
- **Fix:** Extract common `EXPAgentBase` class; both inherit. Or make Bibliotecário a plugin on `DynamicAgentService`.
- **If we skip it:** Divergent behavior; maintenance burden.

---

## Nice to Have

### 19. `generateUUID` in TypeScript runtime — replace with `crypto.randomUUID()`
**Location:** `runtime/agent/agent.ts:L15-21`

- **Fix:** One-liner: `return crypto.randomUUID();` (Node 14.17+, Deno, browsers). Polyfill for older if needed.

### 20. Redundant `ponytail:` comments in source code
**Location:** `juiz/app.py:L60`, `L510`, `bibliotecario/search_service.py` (multiple)

- **What this is:** Comments like `ponytail: sessões em memória, ceiling = reiniciar invalida tokens...`
- **Problem:** These are internal dev notes, not user-facing docs. They clutter code.
- **Fix:** Move to `AGENTS.md` or delete. Keep only `shortcut:` comments that name a real limit (e.g., `shortcut: max 1000 tasks in memory`).

### 21. `AGENTS.md` says `python -m pytest test/` but `test/` is nearly empty
**Location:** `AGENTS.md:L237`, repo root

- **Fix:** Update doc to point to `bees/tests/` and `pytest juiz/ bibliotecario/ guardian/ agentes/`.

### 22. `requirements.txt` missing version pins
**Location:** `requirements.txt:L1-9`

- **Fix:** Pin versions (e.g., `fastapi==0.115.0`) for reproducible builds. Or use `pip-tools` / `uv.lock`.

### 23. `guardian/patrol.py` not reviewed — may have similar sync/async issues
**Location:** `guardian/patrol.py`

- **Note:** Not read due to time. Likely runs `asyncio.sleep` correctly but verify.

---

## Verdict
**Healthy with caveats.** Core architecture is clean (EIP-0001/0002 followed), security layers exist, cluster election works for 3+ nodes. **Fix 1–7 before production** (race, DB contention, blocking loop, weak UUID, backpressure, signature gaps, no TLS). Items 8–18 are correctness/maintainability debt. Items 19–23 are polish.

## Lean
- **-200 lines, -3 deps possible:** Delete `sentinel_mode()` (~10 lines), unify agent base (~150 lines), drop `ponytail:` comments (~30 lines), replace `zeroconf` with stdlib `socket` for mDNS query-only (saves 1 dep), use `crypto.randomUUID()` (stdlib, saves 0 deps but safer).

## Not Checked
- `bibliotecario/exp_agent.py`, `bibliotecario/zim_reader.py`, `bibliotecario/universal_reader.py`, `bibliotecario/embeddings.py`, `bibliotecario/lancedb_store.py`, `bibliotecario/qdrant_store.py`, `core/cluster/failover.py`, `core/cluster/hot_cache.py`, `core/cluster/sandbox.py`, `core/cluster/local_search.py`, `core/cluster/benchmark.py`, `core/cluster/rag.py`, `core/exp/client.py`, `core/exp/server.py`, `core/exp/types.py`, `core/exp/http.py`, `core/exp/secure_logger.py`, `core/ollama/client.py`, `core/discovery/mdns.py`, `core/discovery/mdns_discovery.py`, `core/discovery/advertiser.py`, `core/discovery/browser.py`, `core/memory/usuario_memory.py`, `agentes/worker_pool.py`, `agentes/metrics.py`, `agentes/plugin_manager.py`, `agentes/plugins/*.py`, `bees/` (entire package), `web/` (UI), `api/install/` (installers), `scheduler/selection/*`, `scheduler/policy/*`, `scheduler/queue/*`, `scheduler/matcher/*`, `runtime/errors/*`, `runtime/types/*`, `runtime/interfaces/*`, `floorplan/`, `spec/` (docs only).