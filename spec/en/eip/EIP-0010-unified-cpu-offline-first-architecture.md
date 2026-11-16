# EIP-0010: Unified CPU-First, Offline-First Architecture & Swarm Control UI

## Status

**Active** — v2.1 Implementation (2026-11-16)

## Summary

Unifies `bees/`, `enxame_evolved/`, `guardian/`, `core/`, and `web/` with the 5-layer operational contract from `MANUAL-ASD-STE100-PAINEL-REMOTO.md`, optimizing the entire Swarm for **CPU-only hardware** (including legacy non-AVX2 CPUs), **strict Offline-First execution**, single-pass streaming responses, adaptive long-term user memory, free local CPU image generation, offline-first bidirectional voice, and end-to-end machine/model provenance.

## Technical Specification

1. **CPU Hardware Classification (`HardwareTier`)**: Classifies each machine into `legado` (`<4 cores`, `<6 GB RAM`, or no `AVX2`), `padrao`, or `performance`, surfacing transparent speed expectations (`est_tok_s`, `est_img_s`) while keeping internal routing invisible to the user.
2. **Strict Offline-First Cascade**:
   - Stage 1: Adaptive Memory + Local Documents (SQLite FTS5 BM25 / LanceDB + offline ZIM);
   - Stage 2: Distributed LAN Swarm Documents (routed via Bibliotecário `TopicSketch`);
   - Stage 3: Local CPU Model Parametric Knowledge (single streaming pass via Ollama `/api/chat`);
   - Stage 4: Web Search Fallback — invoked **only** when Stages 1–3 lack the answer, `offline_mode=False`, `allow_web=True`, and `InternetGate` authorizes access.
3. **Two-Level Roles**: Cluster Node Role (`juiz`, `bibliotecario`, `guarda`, `worker`, `worker_artist` across `1..N` nodes with optional manual role pinning) separated from Cognitive Agent Profile (`generalist`, `coder`, `architect`, `researcher`, `analyst`, `legal`, `medical`, `creative`, `artist`).
4. **4-Layer Guardian Security**: Input Gatekeeper (`ALLOW`, `CONTAIN` with cryptographic per-request nonce delimiters, `BLOCK`), Indirect Prompt Injection Shield on RAG/Web/OCR snippets, secret redaction (`sem_segredos()`), and async `GuardianPatrol`.
5. **Unified SQLite WAL Persistence**: Multi-turn chat sessions (`conversations`, `messages`, `messages_fts`), portable `ConversationContextManager` with rolling summaries, and background `AdaptiveUserMemory` consolidation.
6. **Offline-First Voice & Free CPU Image Studio**: Backend STT (`faster-whisper` INT8 CPU) + TTS (`piper-tts` / OS offline TTS) with browser Speech API fallback; async single-worker CPU image queue supporting `stable-diffusion.cpp` GGUF, `diffusers` 1–4 step `sd-turbo`/`tiny-sd`/`LCM`, local ComfyUI/Forge, and zero-dependency offline Pillow procedural studio with optical quality checks.
7. **End-to-End `ProvenanceStamp`**: Every message and generated image records and displays `machine_alias`, `node_id`, `hardware_tier`, `cluster_role`, `agent_profile`, `model`, `source_tier`, `rag_sources`, `route_trace`, `ttft_ms`, and `total_ms`.
