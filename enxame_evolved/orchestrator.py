#!/usr/bin/env python3
"""
TaskOrchestrator — Orquestrador CPU-First & Offline-First Unificado
===================================================================
Coordena a cascata rigorosa de resolução de conhecimento sem duplicar chamadas
de LLM em CPU:
  1. Documentos locais (SQLite FTS5 BM25 `LocalCpuRagEngine` + `Librarian` local)
  2. Documentos do Enxame na LAN (`BibliotecarioGlobalCatalog` + `RESEARCH_REQUEST`)
  3. Conhecimento paramétrico do Modelo Local em CPU (1 única chamada unificada)
  4. Pesquisa na Internet SOMENTE se (1), (2) e (3) não possuírem a informação
     e `allow_web=True` estiver habilitado.

Mantém 100% de compatibilidade com a suíte de regressão existente e anexa
`provenance` auditável (qual máquina, papel, perfil, modelo e tempo respondeu).
"""

from __future__ import annotations

import logging
import platform
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, AsyncIterator

from bees import BeeService
from .discovery import AutoDiscoveryService
from .fast_router import FastIntentRouter
from .multimodal import MultimodalProcessor
from .profiles import AgentProfile, AgentProfileManager

logger = logging.getLogger("enxame.orchestrator")


class TaskStatus(Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    ROUTING = "routing"
    EXECUTING = "executing"
    DELEGATING = "delegating"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class Task:
    """Tarefa a ser executada pelo orquestrador."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = "query"
    description: str = ""
    message: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    profile_id: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    execution_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionPlan:
    """Plano de execução determinístico da tarefa."""

    task_id: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    primary_profile: str | None = None
    fallback_profiles: list[str] = field(default_factory=list)
    delegation_targets: list[str] = field(default_factory=list)
    requires_multimodal: bool = False
    estimated_duration_ms: int = 0


class TaskOrchestrator:
    """Orquestrador distribuído com cascata Offline-First e carimbo de proveniência."""

    def __init__(
        self,
        kernel: Any,
        profiles: AgentProfileManager | None,
        multimodal: MultimodalProcessor | None,
        discovery: AutoDiscoveryService | None,
        bee: BeeService | None,
    ) -> None:
        self.kernel = kernel
        self.profiles = profiles
        self.multimodal = multimodal
        self.discovery = discovery
        self.bee = bee

        self._tasks: dict[str, Task] = {}
        self._execution_history: list[Task] = []
        self._peer_circuit: dict[str, tuple[int, float]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("TaskOrchestrator CPU-First inicializado")

    async def close(self) -> None:
        self._initialized = False

    def get_stats(self) -> dict[str, Any]:
        completed = [t for t in self._execution_history if t.status == TaskStatus.COMPLETED]
        failed = [t for t in self._execution_history if t.status == TaskStatus.FAILED]
        return {
            "active_tasks": len(self._tasks),
            "completed_total": len(completed),
            "failed_total": len(failed),
            "history_size": len(self._execution_history),
        }

    def _peer_available(self, node_id: str) -> bool:
        fails, ts = self._peer_circuit.get(node_id, (0, 0.0))
        if fails < 2:
            return True
        if (time.time() - ts) > 45.0:
            self._peer_circuit.pop(node_id, None)
            return True
        return False

    def _mark_peer_failure(self, node_id: str) -> None:
        fails, _ = self._peer_circuit.get(node_id, (0, 0.0))
        self._peer_circuit[node_id] = (fails + 1, time.time())

    def _mark_peer_success(self, node_id: str) -> None:
        self._peer_circuit.pop(node_id, None)

    def _collect_local_rag(self, query_text: str) -> tuple[str, list[str], list[dict[str, Any]]]:
        """Recupera evidências locais em CPU (<15ms via SQLite FTS5 BM25)."""
        rag_engine = getattr(self.kernel, "rag_engine", None)
        if not rag_engine or not query_text.strip():
            return "", [], []
        hits = rag_engine.search(query_text, top_k=5)
        if not hits:
            return "", [], []
        formatted_chunks: list[str] = []
        sources: list[str] = []
        for idx, h in enumerate(hits, 1):
            src = h.get("title") or h.get("source") or f"doc-{idx}"
            if src not in sources:
                sources.append(src)
            formatted_chunks.append(f"[{idx}] Fonte: {src}\n{h.get('text', '')}")
        return "\n\n".join(formatted_chunks), sources, hits

    def _build_provenance(
        self,
        profile: AgentProfile | None,
        result: dict[str, Any],
        source_tier: str,
        rag_sources: list[str],
        execution_path: list[str],
        started_perf: float,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ctx = context or {}
        hw = getattr(self.kernel, "hardware_profile", None)
        cfg = getattr(self.kernel, "config", None)
        local_node_id = getattr(self.kernel, "node_id", None) or getattr(cfg, "node_id", "bee-local")

        # Verifica se a resposta veio de um peer remoto
        src_field = str(result.get("source") or "local")
        answered_node_id = local_node_id
        answered_alias = getattr(hw, "machine_alias", None) or local_node_id
        if src_field.startswith("peer:"):
            answered_node_id = src_field.split(":", 1)[1]
            answered_alias = answered_node_id

        store = getattr(self.kernel, "store", None)
        pinned = store.get_role_pins().get(answered_node_id) if store else None
        elected_role = None
        if self.bee and getattr(self.bee, "cluster_role", None):
            elected_role = self.bee.cluster_role.value
        active_roles = pinned or ([elected_role] if elected_role else ["rainha", "worker_general"])
        primary_role = active_roles[0] if active_roles else "worker_general"

        total_ms = max(1, int((time.perf_counter() - started_perf) * 1000))
        ttft_ms = int(result.get("ttft_ms") or min(total_ms, max(1, total_ms // 3)))
        ans_text = str(result.get("answer") or "")
        approx_tokens = max(1, len(ans_text) // 4)
        tok_s = round(approx_tokens / max(0.05, total_ms / 1000.0), 1)

        prof_id = getattr(profile, "profile_id", "generalist") if profile else "generalist"
        prof_name = getattr(profile, "name", prof_id) if profile else prof_id
        model_used = (
            result.get("model")
            or (result.get("metadata") or {}).get("model")
            or getattr(cfg, "model", None)
            or "local-cpu"
        )

        return {
            "machine_alias": answered_alias,
            "node_id": answered_node_id,
            "platform": getattr(hw, "os_name", platform.system()),
            "cpu_model": getattr(hw, "cpu_model", ""),
            "cores_physical": getattr(hw, "cores_physical", -1),
            "ram_total_gb": getattr(hw, "ram_total_gb", -1.0),
            "hardware_tier": getattr(hw, "tier", "padrao"),
            "hardware_tier_label": getattr(hw, "tier_label", "CPU Padrão"),
            "cluster_role": primary_role,
            "active_roles": active_roles,
            "agent_profile": prof_id,
            "agent_name": prof_name,
            "model": model_used,
            "source_tier": source_tier,
            "rag_sources": rag_sources,
            "route_trace": [{"step": s} for s in execution_path],
            "confidence": float(result.get("confidence", 0.8)),
            "ttft_ms": ttft_ms,
            "total_ms": total_ms,
            "est_tokens_per_sec": tok_s,
            "pacing_notice": getattr(hw, "pacing_notice", ""),
            "guardian_action": ctx.get("guardian_action", "ALLOW"),
        }

    async def execute_task(
        self,
        task: str,
        profile: AgentProfile,
        context: dict[str, Any],
        message: str = "",
    ) -> dict[str, Any]:
        """
        Executa tarefa com cascata Offline-First rigorosa:
        1. Documentos locais (RAG local)
        2. Documentos do Enxame na LAN (Peers)
        3. Modelo Local em CPU (conhecimento próprio)
        4. Pesquisa na Internet (somente se os anteriores não tiverem a informação)
        """
        started_perf = time.perf_counter()
        user_msg = message or task
        ctx = dict(context or {})

        task_obj = Task(
            task_type=ctx.get("analysis", {}).get("task_type", "query"),
            description=task,
            message=user_msg,
            context=ctx,
            profile_id=getattr(profile, "profile_id", "generalist"),
        )

        self._tasks[task_obj.task_id] = task_obj
        task_obj.status = TaskStatus.ANALYZING
        task_obj.started_at = datetime.now(UTC)

        try:
            plan = await self._create_execution_plan(task_obj, profile)
            task_obj.execution_path.append("planning")

            if (plan.requires_multimodal or ctx.get("attachments")) and not ctx.get("multimodal_processed"):
                if self.multimodal:
                    task_obj.status = TaskStatus.EXECUTING
                    mm_ctx = await self._process_multimodal(ctx, profile)
                    ctx = {**ctx, **mm_ctx}

            # 1. Busca documental local em CPU (FTS5 BM25)
            rag_text, rag_sources, rag_hits = self._collect_local_rag(user_msg)
            source_tier = "modelo_local"
            if rag_hits:
                ctx["rag_context"] = rag_text
                ctx["rag_sources"] = rag_sources
                ctx["rag_hits"] = rag_hits
                source_tier = "rag_local"
                task_obj.execution_path.append("rag_local")

            # 2. Se não encontrou documentos locais e há peers na LAN com conhecimento, consulta Enxame
            peer_evidence = None
            if not rag_hits and plan.delegation_targets:
                task_obj.status = TaskStatus.DELEGATING
                task_obj.execution_path.append("rag_enxame")
                peer_evidence = await self._delegate_to_peers(task_obj, profile, ctx, plan.delegation_targets)
                if peer_evidence and peer_evidence.get("answer"):
                    peer_srcs = (peer_evidence.get("metadata") or {}).get("sources") or ["peer_enxame"]
                    rag_sources = list(peer_srcs)
                    ctx["rag_context"] = str(peer_evidence["answer"])
                    ctx["rag_sources"] = rag_sources
                    source_tier = "rag_enxame"

            # 3. Execução Local unificada em CPU (1 única chamada ao modelo com evidências + memória)
            task_obj.status = TaskStatus.EXECUTING
            task_obj.execution_path.append("local")
            local_result = await self._execute_local(task_obj, profile, ctx)

            ans_raw = str(local_result.get("answer") or "")
            signaled_unknown = FastIntentRouter.model_signaled_unknown(ans_raw)
            clean_answer = ans_raw.replace("[[SEM_DADOS_OFFLINE]]", "").replace("[[sem_dados_offline]]", "").strip()
            local_result["answer"] = clean_answer

            cfg = getattr(self.kernel, "config", None)
            allow_web = bool(
                ctx.get("allow_web_override")
                if "allow_web_override" in ctx
                else (getattr(cfg, "allow_web", False) and not getattr(cfg, "offline_mode", False))
            )

            # Se resultado local (com ou sem documentos locais/enxame) é suficiente e não sinalizou desconhecimento
            if not signaled_unknown and self._is_result_sufficient(local_result, profile):
                if local_result.get("offline_documentary"):
                    source_tier = "rag_local" if rag_hits else "modo_offline_documental"
                prov = self._build_provenance(
                    profile, local_result, source_tier, rag_sources, task_obj.execution_path, started_perf, ctx
                )
                local_result["provenance"] = prov
                local_result.setdefault("metadata", {})["provenance"] = prov
                task_obj.result = local_result
                task_obj.status = TaskStatus.COMPLETED
                await self._record_success(task_obj, local_result)
                return local_result

            # 4. Delegação direta caso não tenha sido consultado no passo 2
            if peer_evidence is None and plan.delegation_targets:
                task_obj.status = TaskStatus.DELEGATING
                task_obj.execution_path.append("enxame")
                peer_result = await self._delegate_to_peers(task_obj, profile, ctx, plan.delegation_targets)
                if self._is_result_sufficient(peer_result, profile):
                    p_srcs = (peer_result.get("metadata") or {}).get("sources") or []
                    prov = self._build_provenance(
                        profile, peer_result, "rag_enxame", p_srcs, task_obj.execution_path, started_perf, ctx
                    )
                    peer_result["provenance"] = prov
                    peer_result.setdefault("metadata", {})["provenance"] = prov
                    task_obj.result = peer_result
                    task_obj.status = TaskStatus.COMPLETED
                    await self._record_success(task_obj, peer_result)
                    return peer_result

            # 5. PESQUISA NA INTERNET — SOMENTE quando nem documentos nem o modelo local sabem!
            if allow_web and self.bee and getattr(self.bee, "_librarian", None):
                task_obj.execution_path.append("internet_fallback")
                web_result = await self.bee._librarian.search_web(user_msg)
                if web_result and web_result.get("answer"):
                    w_srcs = (web_result.get("metadata") or {}).get("sources") or ["internet"]
                    prov = self._build_provenance(
                        profile, web_result, "internet_fallback", w_srcs, task_obj.execution_path, started_perf, ctx
                    )
                    web_result["provenance"] = prov
                    web_result.setdefault("metadata", {})["provenance"] = prov
                    task_obj.result = web_result
                    task_obj.status = TaskStatus.COMPLETED
                    await self._record_success(task_obj, web_result)
                    return web_result

            # 6. Retornar melhor resposta local disponível
            best_result = local_result if local_result.get("answer") else (
                peer_evidence or {"answer": "Não encontrei dados offline suficientes para responder com precisão.", "confidence": 0.3}
            )
            if best_result.get("offline_documentary"):
                source_tier = "rag_local" if rag_hits else "modo_offline_documental"
            prov = self._build_provenance(
                profile, best_result, source_tier, rag_sources, task_obj.execution_path, started_perf, ctx
            )
            best_result["provenance"] = prov
            best_result.setdefault("metadata", {})["provenance"] = prov
            task_obj.result = best_result
            task_obj.status = TaskStatus.COMPLETED
            return best_result

        except Exception as e:
            logger.error(f"Erro na execução da tarefa {task_obj.task_id}: {e}")
            task_obj.status = TaskStatus.FAILED
            task_obj.error = str(e)
            return {"answer": f"Erro na execução: {e}", "confidence": 0.0, "source": "error", "error": str(e)}
        finally:
            task_obj.completed_at = datetime.now(UTC)
            self._execution_history.append(task_obj)
            if len(self._execution_history) > 1000:
                self._execution_history = self._execution_history[-1000:]
            self._tasks.pop(task_obj.task_id, None)

    async def execute_task_stream(
        self,
        task: str,
        profile: AgentProfile,
        context: dict[str, Any],
        message: str = "",
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Versão streaming SSE da cascata Offline-First: entrega tokens em tempo real
        direto da CPU sem esperar a resposta inteira terminar.
        """
        started_perf = time.perf_counter()
        user_msg = message or task
        ctx = dict(context or {})
        execution_path = ["planning"]

        rag_text, rag_sources, rag_hits = self._collect_local_rag(user_msg)
        source_tier = "modelo_local"
        if rag_hits:
            ctx["rag_context"] = rag_text
            ctx["rag_sources"] = rag_sources
            ctx["rag_hits"] = rag_hits
            source_tier = "rag_local"
            execution_path.append("rag_local")

        # Consulta rápida ao catálogo do Bibliotecário na LAN se não houver hits locais
        if not rag_hits and self.discovery:
            plan = await self._create_execution_plan(
                Task(description=task, message=user_msg, context=ctx, profile_id=profile.profile_id),
                profile,
            )
            if plan.delegation_targets:
                execution_path.append("rag_enxame")
                peer_ev = await self._delegate_to_peers(
                    Task(description=task, message=user_msg, context=ctx),
                    profile,
                    ctx,
                    plan.delegation_targets,
                )
                if peer_ev and peer_ev.get("answer"):
                    rag_sources = list((peer_ev.get("metadata") or {}).get("sources") or ["peer_enxame"])
                    ctx["rag_context"] = str(peer_ev["answer"])
                    ctx["rag_sources"] = rag_sources
                    source_tier = "rag_enxame"

        execution_path.append("local_stream")
        from enxame_evolved.agents.evolved_agent import EvolvedAgent

        agent = EvolvedAgent(agent_id="local", profile=profile, kernel=self.kernel)
        collected_tokens: list[str] = []
        done_meta: dict[str, Any] = {}

        async for ev in agent.execute_stream(user_msg, ctx):
            if ev.get("type") == "token":
                tok = str(ev.get("content", ""))
                collected_tokens.append(tok)
                # Oculta o marcador técnico caso apareça no fim do stream
                if "[[SEM_DADOS_OFFLINE]]" not in tok:
                    yield {"type": "token", "content": tok}
            elif ev.get("type") == "done":
                done_meta = ev

        full_ans = "".join(collected_tokens)
        signaled_unknown = FastIntentRouter.model_signaled_unknown(full_ans)
        clean_ans = full_ans.replace("[[SEM_DADOS_OFFLINE]]", "").replace("[[sem_dados_offline]]", "").strip()

        cfg = getattr(self.kernel, "config", None)
        allow_web = bool(
            ctx.get("allow_web_override")
            if "allow_web_override" in ctx
            else (getattr(cfg, "allow_web", False) and not getattr(cfg, "offline_mode", False))
        )

        # Fallback Internet apenas se nem documentos nem o modelo local souberam responder
        if signaled_unknown and allow_web and self.bee and getattr(self.bee, "_librarian", None):
            execution_path.append("internet_fallback")
            web_res = await self.bee._librarian.search_web(user_msg)
            if web_res and web_res.get("answer"):
                clean_ans = str(web_res["answer"])
                source_tier = "internet_fallback"
                rag_sources = list((web_res.get("metadata") or {}).get("sources") or ["internet"])
                yield {"type": "token", "content": "\n\n" + clean_ans}

        if done_meta.get("offline_documentary"):
            source_tier = "rag_local" if rag_hits else "modo_offline_documental"

        exec_summary = {
            "answer": clean_ans,
            "model": done_meta.get("model", "local-cpu"),
            "confidence": done_meta.get("confidence", 0.84),
            "ttft_ms": done_meta.get("ttft_ms", 1),
        }
        prov = self._build_provenance(
            profile, exec_summary, source_tier, rag_sources, execution_path, started_perf, ctx
        )
        yield {
            "type": "done",
            "answer": clean_ans,
            "model": exec_summary["model"],
            "confidence": exec_summary["confidence"],
            "source": source_tier,
            "provenance": prov,
        }

    async def _create_execution_plan(self, task: Task, profile: AgentProfile) -> ExecutionPlan:
        analysis = task.context.get("analysis", {})
        complexity = analysis.get("complexity", "medium")
        requires_multimodal = bool(analysis.get("requires_multimodal", False))

        delegation_targets: list[str] = []
        # 1. Consultar catálogo global do Bibliotecário primeiro (roteamento direcionado por tópico)
        catalog = getattr(self.kernel, "global_catalog", None)
        if catalog and task.message:
            for nid in catalog.find_candidate_nodes(task.message, exclude_node=getattr(self.kernel, "node_id", None)):
                if self._peer_available(nid) and nid not in delegation_targets:
                    delegation_targets.append(nid)

        # 2. Complementar com peers descobertos por capacidade
        if getattr(profile, "peer_delegation", True) and self.discovery:
            for cap in getattr(profile, "capabilities", []):
                peers = self.discovery.get_peers_by_capability(cap)
                for peer in peers:
                    if (
                        peer.node_id not in delegation_targets
                        and getattr(peer, "_reliability_score", 1.0) > 0.7
                        and self._peer_available(peer.node_id)
                    ):
                        delegation_targets.append(peer.node_id)

        fallback_profiles = ["generalist"] if getattr(profile, "profile_id", "generalist") != "generalist" else []
        return ExecutionPlan(
            task_id=task.task_id,
            primary_profile=getattr(profile, "profile_id", "generalist"),
            fallback_profiles=fallback_profiles,
            delegation_targets=delegation_targets[:3],
            requires_multimodal=requires_multimodal,
            estimated_duration_ms=self._estimate_duration(complexity, requires_multimodal),
        )

    def _estimate_duration(self, complexity: str, multimodal: bool) -> int:
        base = {"simple": 2000, "medium": 8000, "complex": 22000}
        est = base.get(complexity, 8000)
        if multimodal:
            est += 10000
        return est

    async def _process_multimodal(self, context: dict, profile: AgentProfile) -> dict[str, Any]:
        attachments = context.get("attachments", [])
        if not attachments or not self.multimodal:
            return {}
        return await self.multimodal.process_attachments(attachments, profile)

    async def _execute_local(self, task: Task, profile: AgentProfile, context: dict) -> dict[str, Any]:
        """Executa localmente em 1 única passagem unificada via EvolvedAgent."""
        try:
            from enxame_evolved.agents.evolved_agent import EvolvedAgent

            agent = EvolvedAgent(agent_id="local", profile=profile, kernel=self.kernel)
            res = await agent.execute(task.message or task.description, context)
            if res.get("status") == "failed":
                return {"answer": "", "confidence": 0.0, "source": "local", "error": res.get("error")}

            return {
                "answer": res.get("response", ""),
                "confidence": float(res.get("confidence", 0.82)),
                "source": "local",
                "model": res.get("model"),
                "ttft_ms": res.get("ttft_ms"),
                "offline_documentary": bool(res.get("offline_documentary", False)),
                "metadata": {
                    "profile": profile.profile_id,
                    "model": res.get("model"),
                    "duration_seconds": res.get("duration", 0.0),
                    "multimodal_context": context.get("multimodal", {}),
                },
            }
        except Exception as e:
            logger.error(f"Execução local falhou: {e}")
            return {"answer": "", "confidence": 0.0, "source": "local", "error": str(e)}

    def _is_result_sufficient(self, result: dict | None, profile: AgentProfile) -> bool:
        if not result or not result.get("answer"):
            return False
        if result.get("offline_documentary"):
            return True
        confidence = float(result.get("confidence", 0.0))
        cfg = getattr(self.kernel, "config", None)
        threshold = float(getattr(cfg, "confidence_threshold_enxame", 0.7))
        if getattr(profile, "complexity_handling", "medium") == "complex":
            threshold *= 0.8
        return confidence >= threshold

    async def _delegate_to_peers(
        self,
        task: Task,
        profile: AgentProfile | None,
        context: dict,
        targets: list[str],
    ) -> dict[str, Any]:
        """Delega consulta de conhecimento para peers descobertos; jamais fabrica resposta."""
        from bees.protocol.messages import BeeMessageType, BeeResearchResult

        best_result = None
        best_confidence = 0.0

        if not self.discovery or not self.bee:
            return {"answer": "", "confidence": 0.0, "source": "peer_failed"}

        for peer_id in targets:
            peer = self.discovery.get_peer(peer_id)
            if not peer:
                continue

            try:
                envelope = self.bee._handler.create_research_request(
                    target_node_id=peer_id,
                    query=task.message,
                    max_results=8,
                    timeout_ms=25000,
                )
                reply = await self.bee._send_with_response(envelope, peer, timeout_ms=30000)
                if (
                    reply is None
                    or reply.source_node_id != peer_id
                    or reply.msg_type != BeeMessageType.RESEARCH_RESULT
                ):
                    self._mark_peer_failure(peer_id)
                    continue

                self._mark_peer_success(peer_id)
                research = BeeResearchResult.from_dict(reply.payload)
                items = [item for item in research.results if item.content.strip()]
                if not items:
                    continue
                peer_result = {
                    "answer": "\n\n".join(item.content for item in items[:3]),
                    "confidence": max(item.confidence for item in items),
                    "source": f"peer:{peer_id}",
                    "model": research.model_used or "peer-rag",
                    "metadata": {
                        "delegated_from": getattr(self.kernel, "node_id", "local"),
                        "sources": [item.source for item in items if item.source],
                        "total_results": research.total_results,
                    },
                }

                if peer_result["confidence"] > best_confidence:
                    best_confidence = peer_result["confidence"]
                    best_result = peer_result
            except Exception as e:
                self._mark_peer_failure(peer_id)
                logger.warning(f"Delegação para {peer_id} falhou: {e}")

        return best_result or {"answer": "", "confidence": 0.0, "source": "peer_failed"}

    async def handle_peer_loss(self, node_id: str) -> None:
        self._mark_peer_failure(node_id)
        for task in self._tasks.values():
            if task.status == TaskStatus.DELEGATING and node_id in task.metadata.get("delegation_targets", []):
                task.metadata["delegation_targets"].remove(node_id)
                logger.info(f"Tarefa {task.task_id} re-roteada devido à perda do peer {node_id}")

    async def _record_success(self, task: Task, result: dict) -> None:
        pass
