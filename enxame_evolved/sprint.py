#!/usr/bin/env python3
"""
SprintPlanner — Planejador de Sprints e Conformidade EIP
========================================================
Gerencia:
- Planejamento de sprints baseado em EIPs
- Divisão de tarefas conforme especificações
- Tracking de progresso e conformidade
- Geração de relatórios de sprint
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("enxame.sprint")


class SprintStatus(Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    REVIEW = "review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EIPStatus(Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"


@dataclass(slots=True)
class EIPSpec:
    """Especificação de EIP (Enxame Improvement Proposal)."""
    eip_id: str
    title: str
    description: str
    status: EIPStatus = EIPStatus.PROPOSED
    author: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    requirements: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    related_files: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SprintTask:
    """Tarefa dentro de um sprint."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sprint_id: str = ""
    eip_id: str | None = None
    title: str = ""
    description: str = ""
    assignee_profile: str = ""  # Perfil de agente responsável
    estimated_hours: float = 0.0
    actual_hours: float = 0.0
    status: str = "todo"  # todo, in_progress, review, done
    dependencies: list[str] = field(default_factory=list)  # task_ids
    deliverables: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Sprint:
    """Sprint de desenvolvimento."""
    sprint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    goal: str = ""
    eip_ids: list[str] = field(default_factory=list)
    start_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_date: datetime = field(default_factory=lambda: datetime.now(UTC) + timedelta(days=14))
    status: SprintStatus = SprintStatus.PLANNING
    tasks: list[SprintTask] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    retrospective: str = ""


class SprintPlanner:
    """
    Planejador de Sprints com conformidade EIP.
    
    Funcionalidades:
    - Criação de sprints baseados em EIPs
    - Divisão automática de tarefas por especialização
    - Atribuição de tarefas a perfis de agentes
    - Tracking de progresso e velocidade
    - Relatórios de conformidade EIP
    - Retrospectivas automatizadas
    """

    # EIPs base do Enxame
    BASE_EIPS = {
        "EIP-0001": EIPSpec(
            eip_id="EIP-0001",
            title="Architecture First",
            description="Toda decisão técnica precedida por especificação arquitetural documentada",
            requirements=[
                "Specs em spec/ antes de implementar",
                "ADRs para decisões arquiteturais",
                "Revisão no Juiz antes de merge",
            ],
            acceptance_criteria=[
                "Nenhuma implementação sem spec",
                "Todas specs versionadas",
                "Juiz valida conformidade",
            ],
        ),
        "EIP-0002": EIPSpec(
            eip_id="EIP-0002",
            title="Resource First",
            description="Eficiência como requisito não negociável",
            requirements=[
                "Zero Docker",
                "Zero frameworks frontend",
                "Dependências mínimas",
                "Código morto = removido",
            ],
            acceptance_criteria=[
                "CPU idle < 5%",
                "Memória < 500MB",
                "Startup < 10s",
                "Storage < 200MB",
            ],
        ),
        "EIP-0003": EIPSpec(
            eip_id="EIP-0003",
            title="Dynamic Capability Discovery",
            description="Descoberta dinâmica de capacidades via mDNS",
            requirements=[
                "mDNS para descoberta",
                "Manifestos de capacidades",
                "Health monitoring",
            ],
            acceptance_criteria=[
                "Peers descobertos em < 5s",
                "Capabilities anunciadas corretamente",
                "Heartbeat 5s, timeout 15s",
            ],
        ),
        "BEE-0001": EIPSpec(
            eip_id="BEE-0001",
            title="Abelha Standalone",
            description="Unidade autônoma offline-first com RAG local",
            requirements=[
                "Funciona isolada",
                "Memória + RAG local",
                "Auto-descoberta mDNS",
                "LOCAL -> ENXAME -> WEB",
            ],
            acceptance_criteria=[
                "Query local < 2s",
                "Descoberta peers automática",
                "Offline funcional",
            ],
        ),
        "BEE-0002": EIPSpec(
            eip_id="BEE-0002",
            title="Protocolo BEE",
            description="Comunicação padronizada entre Abelhas",
            requirements=[
                "Handshake HELLO/ACK",
                "Heartbeat 5s",
                "KNOWLEDGE_QUERY, RESEARCH_REQUEST, MODEL_REQUEST",
                "HMAC auth",
            ],
            acceptance_criteria=[
                "Handshake < 500ms",
                "Heartbeat detecta falha 15s",
                "Queries roteadas corretamente",
            ],
        ),
    }

    def __init__(
        self,
        orchestrator: Any,
        profiles: Any,
    ) -> None:
        self.orchestrator = orchestrator
        self.profiles = profiles
        
        self._eips: dict[str, EIPSpec] = dict(self.BASE_EIPS)
        self._sprints: dict[str, Sprint] = {}
        self._current_sprint: Sprint | None = None
        
        self._sprint_dir = Path.home() / ".enxame" / "sprints"
        self._sprint_dir.mkdir(parents=True, exist_ok=True)
        
        self._initialized = False

    async def initialize(self) -> None:
        """Inicializa planejador."""
        await self._load_sprints()
        self._initialized = True
        logger.info(f"SprintPlanner inicializado com {len(self._eips)} EIPs")

    async def close(self) -> None:
        """Salva estado."""
        await self._save_sprints()

    # =========================================================================
    # Gestão de EIPs
    # =========================================================================

    def get_eip(self, eip_id: str) -> EIPSpec | None:
        return self._eips.get(eip_id)

    def list_eips(self) -> list[EIPSpec]:
        return list(self._eips.values())

    async def create_eip(self, spec: dict) -> EIPSpec:
        """Cria novo EIP."""
        eip = EIPSpec(
            eip_id=spec.get("eip_id", f"EIP-{len(self._eips)+1:04d}"),
            title=spec.get("title", ""),
            description=spec.get("description", ""),
            author=spec.get("author", "system"),
            requirements=spec.get("requirements", []),
            acceptance_criteria=spec.get("acceptance_criteria", []),
            related_files=spec.get("related_files", []),
            metadata=spec.get("metadata", {}),
        )
        self._eips[eip.eip_id] = eip
        logger.info(f"EIP criado: {eip.eip_id}")
        return eip

    async def update_eip_status(self, eip_id: str, status: EIPStatus) -> bool:
        if eip_id in self._eips:
            self._eips[eip_id].status = status
            self._eips[eip_id].updated_at = datetime.now(UTC)
            return True
        return False

    # =========================================================================
    # Planejamento de Sprints
    # =========================================================================

    async def create_sprint(
        self,
        name: str,
        goal: str,
        eip_ids: list[str],
        duration_days: int = 14,
    ) -> Sprint:
        """Cria novo sprint baseado em EIPs."""
        # Validar EIPs
        valid_eips = [eid for eid in eip_ids if eid in self._eips]
        
        sprint = Sprint(
            name=name,
            goal=goal,
            eip_ids=valid_eips,
            start_date=datetime.now(UTC),
            end_date=datetime.now(UTC) + timedelta(days=duration_days),
            status=SprintStatus.PLANNING,
        )
        
        # Gerar tarefas automaticamente baseadas nos EIPs
        sprint.tasks = await self._generate_tasks_for_eips(sprint, valid_eips)
        
        self._sprints[sprint.sprint_id] = sprint
        await self._save_sprints()
        
        logger.info(f"Sprint criado: {sprint.name} ({len(sprint.tasks)} tarefas)")
        return sprint

    async def _generate_tasks_for_eips(self, sprint: Sprint, eip_ids: list[str]) -> list[SprintTask]:
        """Gera tarefas automaticamente baseadas nos EIPs do sprint."""
        tasks = []
        
        # Mapeamento de EIP -> tarefas típicas
        eip_task_templates = {
            "EIP-0001": [
                {"title": "Documentar arquitetura em spec/", "profile": "architect", "hours": 4},
                {"title": "Criar ADRs para decisões", "profile": "architect", "hours": 2},
                {"title": "Configurar Juiz para validação", "profile": "coder", "hours": 3},
            ],
            "EIP-0002": [
                {"title": "Auditar dependências", "profile": "coder", "hours": 3},
                {"title": "Remover código morto", "profile": "coder", "hours": 4},
                {"title": "Otimizar startup e memória", "profile": "coder", "hours": 6},
                {"title": "Benchmark de performance", "profile": "analyst", "hours": 2},
            ],
            "EIP-0003": [
                {"title": "Implementar mDNS discovery", "profile": "coder", "hours": 5},
                {"title": "Criar manifestos de capabilities", "profile": "coder", "hours": 3},
                {"title": "Health monitoring e heartbeat", "profile": "coder", "hours": 4},
            ],
            "BEE-0001": [
                {"title": "Implementar Abelha standalone", "profile": "coder", "hours": 8},
                {"title": "RAG local offline-first", "profile": "coder", "hours": 6},
                {"title": "Política LOCAL->ENXAME->WEB", "profile": "architect", "hours": 4},
                {"title": "Memória SQLite persistente", "profile": "coder", "hours": 3},
            ],
            "BEE-0002": [
                {"title": "Protocolo HELLO/ACK handshake", "profile": "coder", "hours": 4},
                {"title": "Heartbeat e detecção de falha", "profile": "coder", "hours": 3},
                {"title": "Tipos de query (KNOWLEDGE, RESEARCH, MODEL)", "profile": "coder", "hours": 5},
                {"title": "HMAC authentication", "profile": "coder", "hours": 3},
            ],
        }
        
        for eip_id in eip_ids:
            templates = eip_task_templates.get(eip_id, [])
            eip = self._eips.get(eip_id)
            
            for i, tmpl in enumerate(templates):
                task = SprintTask(
                    sprint_id=sprint.sprint_id,
                    eip_id=eip_id,
                    title=f"[{eip_id}] {tmpl['title']}",
                    description=f"EIP: {eip.title if eip else eip_id}\n{tmpl.get('description', '')}",
                    assignee_profile=tmpl.get("profile", "generalist"),
                    estimated_hours=tmpl.get("hours", 4),
                    status="todo",
                    deliverables=[f"Código implementado", f"Testes passando", f"Documentação"],
                    acceptance_criteria=eip.acceptance_criteria if eip else [],
                )
                tasks.append(task)
        
        # Adicionar tarefas transversais
        tasks.extend([
            SprintTask(
                sprint_id=sprint.sprint_id,
                title="Integração e testes end-to-end",
                description="Testar integração completa do sprint",
                assignee_profile="coder",
                estimated_hours=4,
                status="todo",
                dependencies=[t.task_id for t in tasks[-3:]] if len(tasks) >= 3 else [],
            ),
            SprintTask(
                sprint_id=sprint.sprint_id,
                title="Documentação e ADRs",
                description="Atualizar documentação e criar ADRs",
                assignee_profile="architect",
                estimated_hours=2,
                status="todo",
            ),
            SprintTask(
                sprint_id=sprint.sprint_id,
                title="Code review e conformidade Juiz",
                description="Revisar código e validar conformidade EIP",
                assignee_profile="coder",
                estimated_hours=3,
                status="todo",
                dependencies=[t.task_id for t in tasks if t.status != "done"][-5:],
            ),
        ])
        
        return tasks

    async def start_sprint(self, sprint_id: str) -> bool:
        """Inicia sprint."""
        sprint = self._sprints.get(sprint_id)
        if not sprint:
            return False
        
        sprint.status = SprintStatus.ACTIVE
        sprint.start_date = datetime.now(UTC)
        self._current_sprint = sprint
        await self._save_sprints()
        logger.info(f"Sprint iniciado: {sprint.name}")
        return True

    async def complete_sprint(self, sprint_id: str, retrospective: str = "") -> bool:
        """Completa sprint."""
        sprint = self._sprints.get(sprint_id)
        if not sprint:
            return False
        
        sprint.status = SprintStatus.COMPLETED
        sprint.end_date = datetime.now(UTC)
        sprint.retrospective = retrospective
        sprint.metrics = self._calculate_sprint_metrics(sprint)
        
        if self._current_sprint == sprint:
            self._current_sprint = None
        
        await self._save_sprints()
        logger.info(f"Sprint completado: {sprint.name}")
        return True

    def _calculate_sprint_metrics(self, sprint: Sprint) -> dict[str, Any]:
        """Calcula métricas do sprint."""
        total = len(sprint.tasks)
        done = sum(1 for t in sprint.tasks if t.status == "done")
        in_progress = sum(1 for t in sprint.tasks if t.status == "in_progress")
        
        estimated = sum(t.estimated_hours for t in sprint.tasks)
        actual = sum(t.actual_hours for t in sprint.tasks)
        
        return {
            "total_tasks": total,
            "completed": done,
            "in_progress": in_progress,
            "completion_rate": done / total if total > 0 else 0,
            "estimated_hours": estimated,
            "actual_hours": actual,
            "velocity": done / max(1, (sprint.end_date - sprint.start_date).days),
            "eip_coverage": len(set(t.eip_id for t in sprint.tasks if t.eip_id)),
        }

    # =========================================================================
    # Execução de Tarefas de Sprint
    # =========================================================================

    async def execute_task(self, sprint_id: str, task_spec: dict) -> dict:
        """Executa tarefa de sprint usando orquestrador."""
        sprint = self._sprints.get(sprint_id)
        if not sprint:
            return {"error": "Sprint não encontrado"}
        
        task_id = task_spec.get("task_id")
        task = next((t for t in sprint.tasks if t.task_id == task_id), None)
        if not task:
            return {"error": "Tarefa não encontrada"}
        
        # Atualizar status
        task.status = "in_progress"
        task.started_at = datetime.now(UTC)
        
        try:
            # Selecionar perfil
            profile = await self.profiles.select_or_create_profile({
                "task_type": "code",
                "complexity": "medium",
                "domain": "technical",
                "suggested_profile": task.assignee_profile,
            })
            
            # Executar via orquestrador
            result = await self.orchestrator.execute_task(
                task=task.description,
                profile=profile,
                context={
                    "sprint_id": sprint_id,
                    "task_id": task_id,
                    "eip_id": task.eip_id,
                    "acceptance_criteria": task.acceptance_criteria,
                },
                message=f"Implementar: {task.title}",
            )
            
            # Validar critérios de aceitação
            validation = await self._validate_acceptance(task, result)
            
            task.status = "done" if validation["passed"] else "review"
            task.completed_at = datetime.now(UTC)
            if task.started_at:
                task.actual_hours = (task.completed_at - task.started_at).total_seconds() / 3600
            
            task.metadata["execution_result"] = result
            task.metadata["validation"] = validation
            
            await self._save_sprints()
            
            return {
                "task_id": task_id,
                "status": task.status,
                "result": result,
                "validation": validation,
            }
            
        except Exception as e:
            task.status = "todo"  # Reverter para retry
            logger.error(f"Erro executando tarefa {task_id}: {e}")
            return {"error": str(e)}

    async def _validate_acceptance(self, task: SprintTask, result: dict) -> dict:
        """Valida critérios de aceitação usando LLM."""
        if not task.acceptance_criteria:
            return {"passed": True, "details": []}
        
        try:
            from core.ollama.client import OllamaClient, OllamaGenerateRequest
            ollama = OllamaClient(self.orchestrator.kernel.config.ollama_base_url)
            
            prompt = f"""Valide se o resultado atende aos critérios de aceitação:

Tarefa: {task.title}
Descrição: {task.description}
Resultado: {result.get('answer', '')}

Critérios:
{chr(10).join(f'- {c}' for c in task.acceptance_criteria)}

Retorne JSON:
{{
  "passed": true/false,
  "details": [
    {{"criterion": "...", "met": true/false, "evidence": "..."}}
  ]
}}"""
            
            resp = await ollama.generate(
                OllamaGenerateRequest(
                    model=self.orchestrator.kernel.config.model,
                    prompt=prompt,
                    temperature=0.1,
                    num_ctx=4096,
                )
            )
            
            import json
            return json.loads(resp.strip())
        except Exception:
            return {"passed": True, "details": []}

    # =========================================================================
    # Persistência
    # =========================================================================

    async def _load_sprints(self) -> None:
        """Carrega sprints do disco."""
        for sprint_file in self._sprint_dir.glob("*.json"):
            try:
                with open(sprint_file) as f:
                    data = json.load(f)
                sprint = Sprint(**data)
                self._sprints[sprint.sprint_id] = sprint
            except Exception as e:
                logger.error(f"Erro carregando sprint {sprint_file}: {e}")

    async def _save_sprints(self) -> None:
        """Salva sprints no disco."""
        for sprint in self._sprints.values():
            file_path = self._sprint_dir / f"{sprint.sprint_id}.json"
            with open(file_path, "w") as f:
                json.dump(sprint.__dict__, f, indent=2, default=str)

    def get_stats(self) -> dict[str, Any]:
        """Estatísticas do planejador."""
        active = [s for s in self._sprints.values() if s.status == SprintStatus.ACTIVE]
        completed = [s for s in self._sprints.values() if s.status == SprintStatus.COMPLETED]
        
        eip_status = {}
        for eip in self._eips.values():
            eip_status[eip.eip_id] = eip.status.value
        
        return {
            "total_sprints": len(self._sprints),
            "active_sprints": len(active),
            "completed_sprints": len(completed),
            "current_sprint": self._current_sprint.name if self._current_sprint else None,
            "eips": {
                "total": len(self._eips),
                "by_status": {s.value: sum(1 for e in self._eips.values() if e.status == s) for s in EIPStatus},
                "status": eip_status,
            },
            "sprints": [
                {
                    "sprint_id": s.sprint_id,
                    "name": s.name,
                    "status": s.status.value,
                    "progress": self._calculate_sprint_metrics(s).get("completion_rate", 0),
                }
                for s in self._sprints.values()
            ],
        }