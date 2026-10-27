#!/usr/bin/env python3
"""
TaskOrchestrator — Orquestrador de Tarefas Inteligente
======================================================
Orquestra execução de tarefas usando:
- Perfis de agentes apropriados
- Delegação para peers (swarm intelligence)
- Processamento multimodal
- Fallback LOCAL -> ENXAME -> WEB
- Rastreamento de execução e métricas
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from bees import BeeService
from bees.protocol.messages import BeeState
from .discovery import AutoDiscoveryService, DiscoveredPeer
from .profiles import AgentProfileManager, AgentProfile
from .multimodal import MultimodalProcessor

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
    """Tarefa a ser executada."""
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
    execution_path: list[str] = field(default_factory=list)  # local, peer:node_id, web
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionPlan:
    """Plano de execução da tarefa."""
    task_id: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    primary_profile: str | None = None
    fallback_profiles: list[str] = field(default_factory=list)
    delegation_targets: list[str] = field(default_factory=list)  # peer node_ids
    requires_multimodal: bool = False
    estimated_duration_ms: int = 0


class TaskOrchestrator:
    """
    Orquestra execução de tarefas no Enxame.
    
    Fluxo:
    1. Análise da tarefa
    2. Criação de plano de execução
    3. Seleção de perfil primário
    4. Execução LOCAL (RAG + LLM)
    5. Se falha/baixa confiança -> Delegar para PEER
    6. Se falha -> Fallback WEB (se permitido)
    7. Agregação e retorno
    """

    def __init__(
        self,
        kernel: Any,
        profiles: AgentProfileManager,
        multimodal: MultimodalProcessor,
        discovery: AutoDiscoveryService,
        bee: BeeService,
    ) -> None:
        self.kernel = kernel
        self.profiles = profiles
        self.multimodal = multimodal
        self.discovery = discovery
        self.bee = bee
        
        self._tasks: dict[str, Task] = {}
        self._execution_history: list[Task] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Inicializa orquestrador."""
        self._initialized = True
        logger.info("TaskOrchestrator inicializado")

    async def close(self) -> None:
        """Fecha orquestrador."""
        pass

    async def execute_task(
        self,
        task: str,
        profile: AgentProfile,
        context: dict[str, Any],
        message: str,
    ) -> dict[str, Any]:
        """
        Executa tarefa completa com orquestração LOCAL -> ENXAME -> WEB.
        
        Returns:
            Dict com answer, source, confidence, metadata
        """
        task_obj = Task(
            task_type=context.get("analysis", {}).get("task_type", "query"),
            description=task,
            message=message,
            context=context,
            profile_id=profile.profile_id,
        )
        
        self._tasks[task_obj.task_id] = task_obj
        task_obj.status = TaskStatus.ANALYZING
        task_obj.started_at = datetime.now(UTC)
        
        try:
            # 1. Criar plano de execução
            plan = await self._create_execution_plan(task_obj, profile)
            task_obj.execution_path.append("planning")
            
            # 2. Processar multimodal se necessário
            multimodal_context = {}
            if plan.requires_multimodal or context.get("attachments"):
                task_obj.status = TaskStatus.EXECUTING
                multimodal_context = await self._process_multimodal(context, profile)
                context = {**context, **multimodal_context}
            
            # 3. EXECUÇÃO LOCAL
            task_obj.execution_path.append("local")
            local_result = await self._execute_local(task_obj, profile, context)
            
            if self._is_result_sufficient(local_result, profile):
                task_obj.result = local_result
                task_obj.status = TaskStatus.COMPLETED
                await self._record_success(task_obj, local_result)
                return local_result
            
            # 4. DELEGAÇÃO PARA PEERS (ENXAME)
            if plan.delegation_targets:
                task_obj.status = TaskStatus.DELEGATING
                task_obj.execution_path.append("enxame")
                peer_result = await self._delegate_to_peers(task_obj, profile, context, plan.delegation_targets)
                
                if self._is_result_sufficient(peer_result, profile):
                    task_obj.result = peer_result
                    task_obj.status = TaskStatus.COMPLETED
                    await self._record_success(task_obj, peer_result)
                    return peer_result
            
            # 5. FALLBACK WEB
            if self.kernel.config.allow_web and self.bee._librarian:
                task_obj.execution_path.append("web")
                web_result = await self.bee._librarian.search_web(task)
                task_obj.result = web_result
                task_obj.status = TaskStatus.COMPLETED
                await self._record_success(task_obj, web_result)
                return web_result
            
            # 6. Fallback: melhor resultado disponível
            best_result = local_result or peer_result or {"answer": "Não consegui processar a tarefa.", "confidence": 0.0}
            task_obj.result = best_result
            task_obj.status = TaskStatus.COMPLETED
            return best_result
            
        except Exception as e:
            logger.error(f"Erro na execução da tarefa {task_obj.task_id}: {e}")
            task_obj.status = TaskStatus.FAILED
            task_obj.error = str(e)
            task_obj.completed_at = datetime.now(UTC)
            return {"answer": f"Erro na execução: {e}", "confidence": 0.0, "source": "error", "error": str(e)}
        finally:
            task_obj.completed_at = datetime.now(UTC)
            self._execution_history.append(task_obj)
            # Manter apenas últimas 1000
            if len(self._execution_history) > 1000:
                self._execution_history = self._execution_history[-1000:]

    async def _create_execution_plan(self, task: Task, profile: AgentProfile) -> ExecutionPlan:
        """Cria plano de execução baseado na tarefa e perfil."""
        analysis = task.context.get("analysis", {})
        complexity = analysis.get("complexity", "medium")
        requires_multimodal = analysis.get("requires_multimodal", False)
        
        # Identificar peers para delegação
        delegation_targets = []
        required_caps = profile.capabilities
        
        if profile.peer_delegation and self.discovery:
            # Buscar peers com capacidades complementares
            for cap in required_caps:
                peers = self.discovery.get_peers_by_capability(cap)
                for peer in peers:
                    if peer.node_id not in delegation_targets and peer._reliability_score > 0.7:
                        delegation_targets.append(peer.node_id)
        
        # Fallback profiles
        fallback_profiles = []
        if profile.profile_id != "generalist":
            fallback_profiles.append("generalist")
        
        return ExecutionPlan(
            task_id=task.task_id,
            primary_profile=profile.profile_id,
            fallback_profiles=fallback_profiles,
            delegation_targets=delegation_targets[:3],  # Max 3 peers
            requires_multimodal=requires_multimodal,
            estimated_duration_ms=self._estimate_duration(complexity, requires_multimodal),
        )

    def _estimate_duration(self, complexity: str, multimodal: bool) -> int:
        base = {"simple": 2000, "medium": 10000, "complex": 30000}
        est = base.get(complexity, 10000)
        if multimodal:
            est += 15000
        return est

    async def _process_multimodal(self, context: dict, profile: AgentProfile) -> dict[str, Any]:
        """Processa anexos multimodais."""
        attachments = context.get("attachments", [])
        if not attachments:
            return {}
        
        return await self.multimodal.process_attachments(attachments, profile)

    async def _execute_local(self, task: Task, profile: AgentProfile, context: dict) -> dict[str, Any]:
        """Executa tarefa localmente usando Bibliotecário + LLM."""
        try:
            # Usar Bibliotecário local para RAG
            if self.bee and self.bee._librarian:
                result = await self.bee._librarian.search(task.message)
                
                # Se tem perfil especializado, ajustar resposta
                if profile.profile_id != "generalist" and profile.system_prompt:
                    result = await self._refine_with_profile(result, profile, task.message)
                
                return {
                    "answer": result.get("answer", ""),
                    "confidence": result.get("confidence", 0.0),
                    "source": "local",
                    "metadata": {
                        "profile": profile.profile_id,
                        "pipeline": result.get("metadata", {}),
                        "multimodal_context": context.get("multimodal", {}),
                    }
                }
            
            # Fallback: LLM direto
            return await self._llm_direct(task.message, profile)
            
        except Exception as e:
            logger.error(f"Execução local falhou: {e}")
            return {"answer": "", "confidence": 0.0, "source": "local", "error": str(e)}

    async def _refine_with_profile(self, result: dict, profile: AgentProfile, message: str) -> dict:
        """Refina resultado usando prompt do perfil."""
        try:
            from core.ollama.client import OllamaClient, OllamaGenerateRequest
            ollama = OllamaClient(self.kernel.config.ollama_base_url)
            
            prompt = f"""{profile.system_prompt}

Pergunta original: {message}
Resposta base: {result.get('answer', '')}

Refine a resposta mantendo a precisão factual mas aplicando sua especialização."""
            
            resp = await ollama.generate(
                OllamaGenerateRequest(
                    model=profile.metadata.get("selected_model", self.kernel.config.model),
                    prompt=prompt,
                    temperature=profile.temperature,
                    num_ctx=profile.max_tokens,
                )
            )
            
            result["answer"] = resp.strip()
            result["metadata"]["refined_by_profile"] = profile.profile_id
            return result
        except Exception:
            return result

    async def _llm_direct(self, message: str, profile: AgentProfile) -> dict[str, Any]:
        """Execução direta via LLM."""
        try:
            from core.ollama.client import OllamaClient, OllamaGenerateRequest
            ollama = OllamaClient(self.kernel.config.ollama_base_url)
            
            prompt = f"{profile.system_prompt}\n\nPergunta: {message}"
            
            resp = await ollama.generate(
                OllamaGenerateRequest(
                    model=profile.metadata.get("selected_model", self.kernel.config.model),
                    prompt=prompt,
                    temperature=profile.temperature,
                    num_ctx=profile.max_tokens,
                )
            )
            
            return {
                "answer": resp.strip(),
                "confidence": 0.6,
                "source": "local_llm",
                "metadata": {"profile": profile.profile_id},
            }
        except Exception as e:
            return {"answer": f"Erro: {e}", "confidence": 0.0, "source": "error"}

    def _is_result_sufficient(self, result: dict, profile: AgentProfile) -> bool:
        """Verifica se resultado é suficiente."""
        if not result or not result.get("answer"):
            return False
        
        confidence = result.get("confidence", 0.0)
        threshold = self.kernel.config.confidence_threshold_enxame
        
        # Perfis especializados podem ter threshold menor
        if profile.complexity_handling == "complex":
            threshold *= 0.8
        
        return confidence >= threshold

    async def _delegate_to_peers(
        self, 
        task: Task, 
        profile: AgentProfile, 
        context: dict, 
        targets: list[str]
    ) -> dict[str, Any]:
        """Delega tarefa para peers descobertos."""
        best_result = None
        best_confidence = 0.0
        
        for peer_id in targets:
            peer = self.discovery.get_peer(peer_id)
            if not peer:
                continue
            
            try:
                # Enviar RESEARCH_REQUEST via protocolo BEE
                envelope = self.bee._handler.create_research_request(
                    target_node_id=peer_id,
                    query=task.message,
                    max_results=10,
                    timeout_ms=30000,
                )
                
                # TODO: Implementar envio real via WebSocket/HTTP
                # Por enquanto, simular
                logger.info(f"Delegando para peer {peer_id}: {task.message[:50]}...")
                
                # Simular resultado do peer
                peer_result = {
                    "answer": f"[Peer {peer_id[:8]}] Resultado simulado para: {task.message}",
                    "confidence": 0.7,
                    "source": f"peer:{peer_id}",
                    "metadata": {"delegated_from": self.kernel.node_id},
                }
                
                if peer_result["confidence"] > best_confidence:
                    best_confidence = peer_result["confidence"]
                    best_result = peer_result
                    
            except Exception as e:
                logger.warning(f"Delegação para {peer_id} falhou: {e}")
        
        return best_result or {"answer": "", "confidence": 0.0, "source": "peer_failed"}

    async def handle_peer_loss(self, node_id: str) -> None:
        """Lida com perda de peer durante execução."""
        # Cancelar tarefas delegadas para este peer
        for task in self._tasks.values():
            if task.status == TaskStatus.DELEGATING and node_id in task.metadata.get("delegation_targets", []):
                task.metadata["delegation_targets"].remove(node_id)
                logger.info(f"Tarefa {task.task_id} re-roteada devido à perda do peer {node_id}")

    async def _record_success(self, task: Task, result: dict) -> None:
        """Registra execução bem-sucedida para métricas."""
        if task.profile_id:
            latency = 0
            if task.started_at and task.completed_at:
                latency = (task.completed_at - task.started_at).total_seconds() * 1000
            await self.profiles.record_execution(
                task.profile_id,
                success=True,
                latency_ms=latency,
                delegated="peer" in result.get("source", ""),
            )

    def get_stats(self) -> dict[str, Any]:
        """Estatísticas do orquestrador."""
        total = len(self._execution_history)
        completed = sum(1 for t in self._execution_history if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self._execution_history if t.status == TaskStatus.FAILED)
        
        sources = {}
        for t in self._execution_history:
            if t.result:
                src = t.result.get("source", "unknown")
                sources[src] = sources.get(src, 0) + 1
        
        return {
            "total_tasks": total,
            "completed": completed,
            "failed": failed,
            "success_rate": completed / total if total > 0 else 0,
            "sources": sources,
            "active_tasks": sum(1 for t in self._tasks.values() if t.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED)),
        }