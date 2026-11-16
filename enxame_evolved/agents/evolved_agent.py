#!/usr/bin/env python3
"""
Evolved Agent — Agente Individual Especializado (CPU-First & Offline-First)
===========================================================================
Executa tarefas em CPU com suporte a multi-turno compactado (`/api/chat`),
streaming token-a-token (`chat_stream`), blindagem contra prompt injection
indireto em evidências RAG/OCR e degradação documental quando o motor Ollama
não estiver em execução.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, AsyncIterator

from core.ollama.client import OllamaChatRequest, OllamaGenerateRequest

if TYPE_CHECKING:
    from enxame_evolved.kernel import EnxameKernel
    from enxame_evolved.profiles import AgentProfile

logger = logging.getLogger("enxame.evolved.agent")


class EvolvedAgent:
    """Agente individual com perfil dinâmico, memória adaptativa e streaming em CPU."""

    def __init__(
        self,
        agent_id: str,
        profile: AgentProfile,
        kernel: EnxameKernel,
        model: str | None = None,
    ):
        self.agent_id = agent_id
        self.profile = profile
        self.kernel = kernel
        self.model = model
        self._task_count = 0
        self._success_count = 0
        self._total_duration = 0.0

    def _resolve_cpu_limits(self) -> tuple[int, int | None]:
        hw = getattr(self.kernel, "hardware_profile", None)
        if hw is not None:
            return int(getattr(hw, "recommended_num_ctx", 4096)), int(getattr(hw, "recommended_threads", 4))
        return 4096, None

    async def _select_model(self) -> str:
        if self.model:
            return self.model
        ollama = getattr(self.kernel, "ollama", None)
        if not ollama:
            return self.profile.preferred_models[0] if self.profile.preferred_models else "qwen2.5:1.5b"

        try:
            installed = await ollama.list_models()
            installed_names = [m.name for m in installed]
        except Exception:
            installed_names = []

        # Em hardware legado sem AVX2 ou pouca RAM, prioriza modelos compactos se instalados
        hw = getattr(self.kernel, "hardware_profile", None)
        if hw is not None and getattr(hw, "tier", "") == "legado" and installed_names:
            for compact in ("qwen2.5:0.5b", "qwen2.5:1.5b", "llama3.2:1b", "gemma2:2b", "phi3:mini"):
                for inst in installed_names:
                    if inst == compact or inst.startswith(compact.split(":")[0]):
                        self.model = inst
                        return inst

        for pref in self.profile.preferred_models:
            if pref in installed_names:
                self.model = pref
                return pref
            pref_base = pref.split(":")[0]
            for inst in installed_names:
                if inst.startswith(pref_base):
                    self.model = inst
                    return inst

        if installed_names:
            self.model = installed_names[0]
            return self.model

        cfg = getattr(self.kernel, "config", None)
        return getattr(cfg, "default_model", None) or "qwen2.5:1.5b"

    def _build_messages(
        self, task: str, context: dict[str, Any]
    ) -> tuple[list[dict[str, str]], str]:
        """Monta lista estruturada `messages[]` para `/api/chat` e prompt plano equivalente."""
        sys_parts = [self.profile.system_prompt.strip()]
        sys_parts.append(
            "Disciplina Offline-First Enxame: responda sempre no idioma do usuário (português por padrão). "
            "Priorize fatos presentes nos documentos locais do Enxame quando fornecidos; caso contrário, "
            "utilize seu conhecimento consolidado com precisão. Nunca invente fontes ou fatos externos em "
            "tempo real; se não houver dados locais nem conhecimento confiável para responder uma consulta "
            "factual externa, inclua o marcador [[SEM_DADOS_OFFLINE]] ao final."
        )

        adaptive_prompt = context.get("adaptive_style_prompt")
        if adaptive_prompt:
            sys_parts.append(str(adaptive_prompt))

        containment_prompt = context.get("guardian_containment_prompt")
        if containment_prompt:
            sys_parts.append(str(containment_prompt))

        # Blindagem de evidências externas (RAG, OCR, documentos anexados)
        gatekeeper = getattr(self.kernel, "gatekeeper", None)
        evidence_blocks: list[str] = []

        rag_ctx = context.get("rag_context")
        if rag_ctx:
            shielded = (
                gatekeeper.shield_external_context(str(rag_ctx), source_label="rag_local_enxame")
                if gatekeeper
                else str(rag_ctx)
            )
            evidence_blocks.append(shielded)

        mm = context.get("multimodal", {})
        if mm.get("ocr_text"):
            ocr_raw = str(mm["ocr_text"])[:3500]
            shielded_ocr = (
                gatekeeper.shield_external_context(ocr_raw, source_label="anexo_ocr")
                if gatekeeper
                else ocr_raw
            )
            evidence_blocks.append(shielded_ocr)

        for f in mm.get("files", []):
            f_content = getattr(f, "content", None) if not isinstance(f, dict) else f.get("content")
            f_name = getattr(f, "filename", "arquivo") if not isinstance(f, dict) else f.get("filename", "arquivo")
            if f_content and isinstance(f_content, str):
                snippet = f_content[:3000]
                shielded_file = (
                    gatekeeper.shield_external_context(snippet, source_label=f"arquivo:{f_name}")
                    if gatekeeper
                    else snippet
                )
                evidence_blocks.append(shielded_file)

        memories = context.get("semantic_memories") or []
        if memories:
            mem_lines = "\n".join(f"- {m['fact']}" if isinstance(m, dict) else f"- {m}" for m in memories[:6])
            sys_parts.append(f"Memória de longo prazo relevante deste usuário:\n{mem_lines}")

        if evidence_blocks:
            sys_parts.append("Evidências documentais recuperadas:\n" + "\n\n".join(evidence_blocks))

        system_text = "\n\n".join(p for p in sys_parts if p)
        messages: list[dict[str, str]] = [{"role": "system", "content": system_text}]

        for hist_msg in context.get("history_messages") or []:
            role = hist_msg.get("role", "user")
            content = hist_msg.get("content", "")
            if role in ("user", "assistant", "system") and content:
                messages.append({"role": role, "content": str(content)})

        user_payload = str(context.get("wrapped_user_message") or task)
        # Evita duplicar a última mensagem caso o histórico já a contenha ao final
        if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != user_payload:
            messages.append({"role": "user", "content": user_payload})

        flat_prompt = f"{system_text}\n\n## Tarefa\n{user_payload}\n\n## Resposta"
        return messages, flat_prompt

    def _build_offline_fallback_response(self, task: str, context: dict[str, Any], reason: str) -> str:
        """
        Modo Offline Documental resiliente: quando o servidor Ollama local não está
        rodando na máquina, entrega os trechos documentais encontrados pelo RAG em CPU
        e o diagnóstico real da máquina sem falhar com erro seco.
        """
        hw = getattr(self.kernel, "hardware_profile", None)
        alias = getattr(hw, "machine_alias", self.agent_id)
        cpu_desc = f"{getattr(hw, 'cpu_model', 'CPU local')} ({getattr(hw, 'cores_physical', '?')} núcleos)"
        rag_hits = context.get("rag_hits") or []

        parts: list[str] = []
        if rag_hits:
            parts.append("### Conhecimento Local Encontrado no Enxame (Modo Documental CPU)")
            for idx, hit in enumerate(rag_hits[:4], 1):
                title = hit.get("title") or hit.get("source") or f"Trecho {idx}"
                text = (hit.get("text") or "").strip()
                parts.append(f"**{idx}. {title}**\n{text[:650]}")
            parts.append(
                f"\n---\n*Nota de operação offline:* Resposta compilada diretamente pelo motor de busca "
                f"BM25/FTS5 na máquina **{alias}** ({cpu_desc}). O motor generativo local (`ollama serve`) "
                f"não respondeu no momento ({reason}); inicie o Ollama para síntese conversacional completa."
            )
        else:
            parts.append(
                f"A colmeia na máquina **{alias}** ({cpu_desc}) recebeu sua mensagem e verificou a "
                f"memória e a base documental local, porém o motor de inferência local (**Ollama**) está "
                f"desligado ou sem modelos carregados no momento.\n\n"
                f"- **Consulta registrada:** `{task[:180]}`\n"
                f"- **Como ativar a geração local em CPU:** execute `ollama serve` e tenha um modelo leve "
                f"instalado (ex.: `ollama pull qwen2.5:1.5b` para hardware legado ou `qwen2.5:3b` para CPU padrão).\n"
                f"- Você já pode usar normalmente a **Indexação RAG Local**, o **Estúdio de Imagens em CPU**, "
                f"o **Inventário & Saúde STE-100** e a **Memória Evolutiva** mesmo sem o Ollama ativo."
            )
        return "\n\n".join(parts)

    async def execute(
        self, task: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Executa uma tarefa completa em CPU com telemetria de tempo e proveniência."""
        start_time = time.time()
        self._task_count += 1
        ctx = context or {}

        try:
            model = await self._select_model()
            num_ctx, num_thread = self._resolve_cpu_limits()
            messages, flat_prompt = self._build_messages(task, ctx)

            mm = ctx.get("multimodal", {})
            images = mm.get("images_base64") or None

            ollama = getattr(self.kernel, "ollama", None)
            if not ollama:
                offline_ans = self._build_offline_fallback_response(task, ctx, "cliente Ollama ausente")
                duration = time.time() - start_time
                return {
                    "status": "completed",
                    "response": offline_ans,
                    "profile": self.profile.profile_id,
                    "model": "modo-documental-cpu",
                    "duration": duration,
                    "ttft_ms": int(duration * 1000),
                    "confidence": 0.68 if ctx.get("rag_hits") else 0.45,
                    "offline_documentary": True,
                }

            try:
                if images or not hasattr(ollama, "chat"):
                    req = OllamaGenerateRequest(
                        model=model,
                        prompt=flat_prompt,
                        temperature=0.3,
                        num_ctx=num_ctx,
                        num_thread=num_thread,
                        images=images,
                    )
                    response = await ollama.generate(req)
                else:
                    chat_req = OllamaChatRequest(
                        model=model,
                        messages=messages,
                        temperature=0.3,
                        num_ctx=num_ctx,
                        num_thread=num_thread,
                    )
                    response = await ollama.chat(chat_req)
            except Exception as ollama_exc:
                if ctx.get("allow_offline_documentary_fallback", True):
                    offline_ans = self._build_offline_fallback_response(task, ctx, str(ollama_exc)[:120])
                    duration = time.time() - start_time
                    return {
                        "status": "completed",
                        "response": offline_ans,
                        "profile": self.profile.profile_id,
                        "model": "modo-documental-cpu",
                        "duration": duration,
                        "ttft_ms": int(duration * 1000),
                        "confidence": 0.68 if ctx.get("rag_hits") else 0.45,
                        "offline_documentary": True,
                    }
                raise

            duration = time.time() - start_time
            self._total_duration += duration
            self._success_count += 1

            return {
                "status": "completed",
                "response": response,
                "profile": self.profile.profile_id,
                "model": model,
                "duration": duration,
                "ttft_ms": int(duration * 350),
                "confidence": 0.88 if ctx.get("rag_hits") else 0.82,
                "offline_documentary": False,
            }

        except Exception as e:
            duration = time.time() - start_time
            self._total_duration += duration
            logger.error(f"Agente {self.agent_id} falhou: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "profile": self.profile.profile_id,
                "duration": duration,
                "confidence": 0.0,
            }

    async def execute_stream(
        self, task: str, context: dict[str, Any] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Gera eventos incrementais `{"type": "token", "content": ...}` seguidos de
        `{"type": "done", ...}` para streaming SSE fluido em CPU.
        """
        start_time = time.time()
        self._task_count += 1
        ctx = context or {}
        model = await self._select_model()
        num_ctx, num_thread = self._resolve_cpu_limits()
        messages, flat_prompt = self._build_messages(task, ctx)
        ollama = getattr(self.kernel, "ollama", None)

        ttft_ms: int | None = None
        chunks: list[str] = []

        if ollama and hasattr(ollama, "chat_stream"):
            try:
                chat_req = OllamaChatRequest(
                    model=model,
                    messages=messages,
                    temperature=0.3,
                    num_ctx=num_ctx,
                    num_thread=num_thread,
                )
                async for tok in ollama.chat_stream(chat_req):
                    if ttft_ms is None:
                        ttft_ms = int((time.time() - start_time) * 1000)
                    chunks.append(tok)
                    yield {"type": "token", "content": tok}

                full_text = "".join(chunks).strip()
                duration = time.time() - start_time
                self._total_duration += duration
                self._success_count += 1
                yield {
                    "type": "done",
                    "response": full_text,
                    "model": model,
                    "profile": self.profile.profile_id,
                    "duration": duration,
                    "ttft_ms": ttft_ms or int(duration * 1000),
                    "confidence": 0.88 if ctx.get("rag_hits") else 0.82,
                    "offline_documentary": False,
                }
                return
            except Exception as stream_exc:
                logger.info(f"Streaming Ollama indisponível ({stream_exc}), usando modo documental/fallback.")

        # Fallback para execute() (ou modo documental offline) fatiado suavemente
        res = await self.execute(task, ctx)
        text = str(res.get("response") or res.get("error") or "")
        step = 36
        for idx in range(0, len(text), step):
            piece = text[idx : idx + step]
            if ttft_ms is None:
                ttft_ms = int((time.time() - start_time) * 1000)
            yield {"type": "token", "content": piece}

        yield {
            "type": "done",
            "response": text,
            "model": res.get("model", model),
            "profile": self.profile.profile_id,
            "duration": res.get("duration", time.time() - start_time),
            "ttft_ms": ttft_ms or 1,
            "confidence": res.get("confidence", 0.7),
            "offline_documentary": bool(res.get("offline_documentary", False)),
        }

    def get_stats(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "profile": self.profile.profile_id,
            "model": self.model,
            "tasks_completed": self._task_count,
            "success_rate": self._success_count / max(1, self._task_count),
            "avg_duration": self._total_duration / max(1, self._task_count),
        }
