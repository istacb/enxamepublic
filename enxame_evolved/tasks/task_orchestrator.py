"""
TaskOrchestrator — Orquestração de Tarefas, Sprints e EIPs
==========================================================
Divide tarefas complexas, planeja sprints, executa EIPs
com seleção automática de perfis e coordenação de peers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from enxame_evolved.agents.evolved_agent import AgentCapability, AgentProfile
from enxame_evolved.profiles.profile_manager import ProfileManager, AgentProfileSpec
from agentes.plugin_manager import PluginManager
from enxame_evolved.multimodal.multimodal_processor import MultiModalProcessor

logger = logging.getLogger("enxame.tasks")


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(slots=True)
class SubTask:
    """Sub-tarefa individual."""
    task_id: str
    title: str
    description: str
    required_capabilities: list[AgentCapability] = field(default_factory=list)
    preferred_specialties: list[str] = field(default_factory=list)
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    assigned_profile: str | None = None
    assigned_peer: str | None = None
    result: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SprintPlan:
    """Plano de sprint."""
    sprint_id: str
    name: str
    goal: str
    tasks: list[SubTask] = field(default_factory=list)
    duration_days: int = 14
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: TaskStatus = TaskStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EIPSpec:
    """Especificação de EIP (Especificação de Implementação)."""
    eip_id: str
    title: str
    description: str
    requirements: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    affected_components: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    priority: TaskPriority = TaskPriority.MEDIUM
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskOrchestrator:
    """
    Orquestrador de tarefas complexas.
    
    Funcionalidades:
    - Decomposição de tarefas em sub-tarefas
    - Seleção automática de perfis por capability
    - Distribuição entre peers do enxame
    - Planejamento e execução de sprints
    - Execução de EIPs com validação
    - Tracking de progresso e dependências
    """
    
    def __init__(
        self,
        agent_id: str,
        profile_manager: ProfileManager,
        plugin_manager: PluginManager,
        multimodal: MultiModalProcessor,
    ) -> None:
        self.agent_id = agent_id
        self.profile_manager = profile_manager
        self.plugin_manager = plugin_manager
        self.multimodal = multimodal
        
        self._sprints: dict[str, SprintPlan] = {}
        self._active_tasks: dict[str, SubTask] = {}
        self._completed_tasks: dict[str, SubTask] = {}
        self._eip_history: list[dict[str, Any]] = []
        
        # Callbacks para execução distribuída
        self._execute_local_callback: callable | None = None
        self._dispatch_to_peer_callback: callable | None = None
    
    def set_execution_callbacks(
        self,
        execute_local: callable,
        dispatch_to_peer: callable,
    ) -> None:
        """Define callbacks para execução local e remota."""
        self._execute_local_callback = execute_local
        self._dispatch_to_peer_callback = dispatch_to_peer
    
    # =========================================================================
    # Decomposição de Tarefas
    # =========================================================================
    
    async def decompose_task(
        self,
        task_description: str,
        context: str | None = None,
        max_subtasks: int = 8,
    ) -> list[SubTask]:
        """
        Decompõe tarefa complexa em sub-tarefas usando LLM.
        
        Retorna lista de SubTask com capabilities necessárias.
        """
        # Selecionar perfil arquiteto/planejador
        profile = await self.profile_manager.select_best_profile(
            f"Planejar e decompor: {task_description}",
            context
        )
        
        # Buscar plugin de planejamento
        planner_plugin = None
        for spec in profile.specialties:
            plugin = self.plugin_manager.get(spec)
            if plugin and hasattr(plugin, 'plan_task'):
                planner_plugin = plugin
                break
        
        if not planner_plugin:
            planner_plugin = self.plugin_manager.get('programador')
        
        # Prompt para decomposição
        prompt = self._build_decomposition_prompt(task_description, context, max_subtasks)
        
        # Executar via Ollama (precisa de acesso ao cliente)
        # Por enquanto, decomposição baseada em regras
        subtasks = self._rule_based_decomposition(task_description, context, max_subtasks)
        
        return subtasks
    
    def _rule_based_decomposition(
        self,
        task_description: str,
        context: str | None,
        max_subtasks: int
    ) -> list[SubTask]:
        """Decomposição baseada em regras (fallback sem LLM)."""
        text = (task_description + " " + (context or "")).lower()
        subtasks = []
        
        # Padrões de decomposição
        patterns = [
            # Documentação
            (["documentar", "documentação", "readme", "docs"], [
                ("Analisar código existente", [AgentCapability.CODE_GENERATION], ["programador"]),
                ("Escrever documentação técnica", [AgentCapability.TEXT_GENERATION], ["redator"]),
                ("Criar exemplos de uso", [AgentCapability.CODE_GENERATION], ["programador"]),
            ]),
            # API/Backend
            (["api", "endpoint", "rest", "backend", "servidor"], [
                ("Desenhar arquitetura da API", [AgentCapability.ARCHITECTURE], ["programador"]),
                ("Implementar endpoints", [AgentCapability.CODE_GENERATION], ["programador"]),
                ("Testar e validar", [AgentCapability.DEBUGGING], ["programador"]),
            ]),
            # Frontend/UI
            (["frontend", "interface", "ui", "react", "vue", "web"], [
                ("Design da interface", [AgentCapability.ARCHITECTURE], ["programador"]),
                ("Implementar componentes", [AgentCapability.CODE_GENERATION], ["programador"]),
                ("Testes de usabilidade", [AgentCapability.DEBUGGING], ["programador"]),
            ]),
            # Banco de dados
            (["banco", "database", "sql", "migração", "schema"], [
                ("Modelar dados", [AgentCapability.ARCHITECTURE], ["programador"]),
                ("Criar migrações", [AgentCapability.CODE_GENERATION], ["programador"]),
                ("Otimizar queries", [AgentCapability.DEBUGGING], ["programador"]),
            ]),
            # Testes
            (["teste", "test", "testing", "cobertura"], [
                ("Planejar estratégia de testes", [AgentCapability.ARCHITECTURE], ["programador"]),
                ("Escrever testes unitários", [AgentCapability.CODE_GENERATION], ["programador"]),
                ("Configurar CI/CD", [AgentCapability.CODE_GENERATION], ["programador"]),
            ]),
            # Multimodal
            (["ocr", "imagem", "pdf", "documento", "foto"], [
                ("Processar anexos multimodais", [AgentCapability.OCR, AgentCapability.DOCUMENT_PROCESSING], []),
                ("Extrair e estruturar dados", [AgentCapability.TEXT_GENERATION], ["redator"]),
            ]),
            # Pesquisa
            (["pesquisar", "investigar", "analisar", "estudo"], [
                ("Busca local (RAG)", [AgentCapability.RAG_LOCAL], []),
                ("Busca distribuída (peers)", [AgentCapability.RAG_DISTRIBUTED], []),
                ("Síntese de resultados", [AgentCapability.TEXT_GENERATION], ["redator"]),
            ]),
        ]
        
        # Encontrar padrão correspondente
        for keywords, subtask_defs in patterns:
            if any(kw in text for kw in keywords):
                for i, (title, caps, specs) in enumerate(subtask_defs[:max_subtasks]):
                    subtasks.append(SubTask(
                        task_id=f"sub-{uuid.uuid4().hex[:8]}",
                        title=title,
                        description=f"Sub-tarefa: {title}",
                        required_capabilities=caps,
                        preferred_specialties=specs,
                        priority=TaskPriority.MEDIUM,
                    ))
                break
        
        # Fallback genérico
        if not subtasks:
            subtasks = [
                SubTask(
                    task_id=f"sub-{uuid.uuid4().hex[:8]}",
                    title="Analisar requisitos",
                    description="Entender e documentar o que precisa ser feito",
                    required_capabilities=[AgentCapability.ARCHITECTURE],
                    preferred_specialties=["programador"],
                ),
                SubTask(
                    task_id=f"sub-{uuid.uuid4().hex[:8]}",
                    title="Implementar solução",
                    description="Desenvolver a funcionalidade principal",
                    required_capabilities=[AgentCapability.CODE_GENERATION],
                    preferred_specialties=["programador"],
                ),
                SubTask(
                    task_id=f"sub-{uuid.uuid4().hex[:8]}",
                    title="Validar e testar",
                    description="Verificar se a implementação atende aos requisitos",
                    required_capabilities=[AgentCapability.DEBUGGING],
                    preferred_specialties=["programador"],
                ),
            ]
        
        return subtasks[:max_subtasks]
    
    def _build_decomposition_prompt(
        self,
        task: str,
        context: str | None,
        max_subtasks: int
    ) -> str:
        return f"""
Decomponha a seguinte tarefa em {max_subtasks} sub-tarefas independentes.

TAREFA: {task}
CONTEXTO: {context or "Nenhum"}

Para cada sub-tarefa, especifique:
1. Título curto
2. Descrição
3. Capabilities necessárias (code_generation, debugging, architecture, rag_local, ocr, etc.)
4. Especialidades preferidas (programador, redator, jurista, medico, etc.)
5. Prioridade (low, medium, high, critical)

Formato JSON:
{{
  "subtasks": [
    {{
      "title": "...",
      "description": "...",
      "required_capabilities": ["code_generation"],
      "preferred_specialties": ["programador"],
      "priority": "medium"
    }}
  ]
}}
"""
    
    # =========================================================================
    # Execução de Tarefas
    # =========================================================================
    
    async def execute_task(
        self,
        task_id: str,
        subtask: str,
        context: str | None,
        profile: AgentProfile,
        sprint_id: str | None = None,
        eip_id: str | None = None,
    ) -> str:
        """Executa uma sub-tarefa com o perfil especificado."""
        
        # Verificar se deve executar localmente ou delegar
        if self._should_delegate(profile):
            return await self._delegate_to_peer(task_id, subtask, context, profile)
        
        return await self._execute_local(task_id, subtask, context, profile)
    
    def _should_delegate(self, profile: AgentProfile) -> bool:
        """Decide se deve delegar para peer."""
        # Delegar se:
        # - Perfil requer capability não disponível localmente
        # - Carga alta
        # - Peer tem perfil mais especializado
        return False  # Por enquanto, executa local
    
    async def _execute_local(
        self,
        task_id: str,
        subtask: str,
        context: str | None,
        profile: AgentProfile,
    ) -> str:
        """Executa localmente via plugin."""
        # Selecionar plugin
        plugin = None
        for spec in profile.specialties:
            plugin = self.plugin_manager.get(spec)
            if plugin:
                break
        
        if not plugin:
            plugin = self.plugin_manager.best_for(subtask)
        
        # Construir prompt
        prompt = plugin.build_prompt(subtask=subtask, context=context)
        
        # Executar via callback (precisa do Ollama do agente)
        if self._execute_local_callback:
            return await self._execute_local_callback(prompt, profile.model)
        
        # Fallback
        return f"[Executado localmente com perfil {profile.name}] {subtask}"
    
    async def _delegate_to_peer(
        self,
        task_id: str,
        subtask: str,
        context: str | None,
        profile: AgentProfile,
    ) -> str:
        """Delega execução para peer do enxame."""
        if self._dispatch_to_peer_callback:
            return await self._dispatch_to_peer_callback(task_id, subtask, context, profile)
        return "[Delegação não implementada]"
    
    # =========================================================================
    # Planejamento de Sprint
    # =========================================================================
    
    async def plan_sprint(self, sprint_spec: dict[str, Any]) -> dict[str, Any]:
        """
        Planeja uma sprint baseada na especificação.
        
        sprint_spec:
        {
            "name": "Sprint 1",
            "goal": "Implementar autenticação",
            "tasks": [
                {"title": "Design API auth", "description": "..."},
                {"title": "Implementar JWT", "description": "..."}
            ],
            "duration_days": 14
        }
        """
        sprint_id = f"sprint-{uuid.uuid4().hex[:8]}"
        
        # Decompor tarefas
        all_subtasks = []
        for task_spec in sprint_spec.get("tasks", []):
            subtasks = await self.decompose_task(
                task_spec.get("title", ""),
                task_spec.get("description"),
            )
            all_subtasks.extend(subtasks)
        
        # Atribuir perfis às sub-tarefas
        for subtask in all_subtasks:
            if subtask.required_capabilities:
                # Converter capabilities para string para match
                caps_str = [c.value for c in subtask.required_capabilities]
                best_profile = await self.profile_manager.select_best_profile(
                    f"{subtask.title} {subtask.description}",
                    f"Capabilities: {', '.join(caps_str)}"
                )
                subtask.assigned_profile = best_profile.name
        
        # Criar plano de sprint
        sprint = SprintPlan(
            sprint_id=sprint_id,
            name=sprint_spec.get("name", "Sprint"),
            goal=sprint_spec.get("goal", ""),
            tasks=all_subtasks,
            duration_days=sprint_spec.get("duration_days", 14),
            start_date=datetime.now(UTC),
        )
        
        self._sprints[sprint_id] = sprint
        
        return {
            "sprint_id": sprint_id,
            "name": sprint.name,
            "goal": sprint.goal,
            "total_subtasks": len(all_subtasks),
            "estimated_duration_days": sprint.duration_days,
            "subtasks": [
                {
                    "task_id": st.task_id,
                    "title": st.title,
                    "description": st.description,
                    "required_capabilities": [c.value for c in st.required_capabilities],
                    "preferred_specialties": st.preferred_specialties,
                    "priority": st.priority.value,
                    "assigned_profile": st.assigned_profile,
                }
                for st in all_subtasks
            ],
        }
    
    async def execute_sprint(self, sprint_id: str) -> dict[str, Any]:
        """Executa uma sprint planejada."""
        sprint = self._sprints.get(sprint_id)
        if not sprint:
            return {"error": f"Sprint {sprint_id} não encontrada"}
        
        sprint.status = TaskStatus.IN_PROGRESS
        results = []
        
        for subtask in sprint.tasks:
            subtask.status = TaskStatus.IN_PROGRESS
            subtask.started_at = datetime.now(UTC)
            
            try:
                profile = self.profile_manager.get(subtask.assigned_profile) if subtask.assigned_profile else None
                if not profile:
                    profile = self.profile_manager.get_default()
                
                result = await self.execute_task(
                    task_id=subtask.task_id,
                    subtask=subtask.description,
                    context=sprint.goal,
                    profile=profile,
                    sprint_id=sprint_id,
                )
                
                subtask.status = TaskStatus.COMPLETED
                subtask.completed_at = datetime.now(UTC)
                subtask.result = result
                
            except Exception as e:
                subtask.status = TaskStatus.FAILED
                subtask.error = str(e)
                logger.error(f"Sub-tarefa {subtask.task_id} falhou: {e}")
            
            results.append({
                "task_id": subtask.task_id,
                "title": subtask.title,
                "status": subtask.status.value,
                "result": subtask.result,
                "error": subtask.error,
            })
        
        # Verificar conclusão
        completed = sum(1 for st in sprint.tasks if st.status == TaskStatus.COMPLETED)
        sprint.status = TaskStatus.COMPLETED if completed == len(sprint.tasks) else TaskStatus.IN_PROGRESS
        
        return {
            "sprint_id": sprint_id,
            "completed": completed,
            "total": len(sprint.tasks),
            "success_rate": completed / len(sprint.tasks) if sprint.tasks else 0,
            "results": results,
        }
    
    # =========================================================================
    # Execução de EIP
    # =========================================================================
    
    async def execute_eip(self, eip_spec: dict[str, Any]) -> dict[str, Any]:
        """
        Executa uma EIP (Especificação de Implementação).
        
        eip_spec:
        {
            "eip_id": "EIP-001",
            "title": "Adicionar suporte a WebSocket",
            "description": "Implementar WebSocket para tempo real",
            "requirements": ["WS server", "Client reconnection", "Auth"],
            "acceptance_criteria": ["Conexão estável", "Reconexão automática"],
            "affected_components": ["kernel", "web_ui"],
            "dependencies": [],
        }
        """
        eip_id = eip_spec.get("eip_id", f"EIP-{uuid.uuid4().hex[:6].upper()}")
        
        # Criar especificação estruturada
        eip = EIPSpec(
            eip_id=eip_id,
            title=eip_spec.get("title", ""),
            description=eip_spec.get("description", ""),
            requirements=eip_spec.get("requirements", []),
            acceptance_criteria=eip_spec.get("acceptance_criteria", []),
            affected_components=eip_spec.get("affected_components", []),
            dependencies=eip_spec.get("dependencies", []),
            priority=TaskPriority(eip_spec.get("priority", "medium")),
        )
        
        logger.info(f"Executando EIP: {eip_id} - {eip.title}")
        
        # Decompor EIP em tarefas
        subtasks = await self._decompose_eip(eip)
        
        # Executar cada sub-tarefa
        results = []
        for subtask in subtasks:
            profile = await self.profile_manager.select_best_profile(
                f"{eip.title}: {subtask.title}",
                f"EIP: {eip.description}"
            )
            subtask.assigned_profile = profile.name
            
            subtask.status = TaskStatus.IN_PROGRESS
            subtask.started_at = datetime.now(UTC)
            
            try:
                result = await self.execute_task(
                    task_id=subtask.task_id,
                    subtask=subtask.description,
                    context=f"EIP {eip_id}: {eip.description}",
                    profile=profile,
                    eip_id=eip_id,
                )
                subtask.status = TaskStatus.COMPLETED
                subtask.completed_at = datetime.now(UTC)
                subtask.result = result
            except Exception as e:
                subtask.status = TaskStatus.FAILED
                subtask.error = str(e)
            
            results.append({
                "task_id": subtask.task_id,
                "title": subtask.title,
                "status": subtask.status.value,
                "profile": subtask.assigned_profile,
                "result": subtask.result,
                "error": subtask.error,
            })
        
        # Validar critérios de aceitação
        validation = await self._validate_eip_acceptance(eip, results)
        
        # Registrar no histórico
        self._eip_history.append({
            "eip_id": eip_id,
            "title": eip.title,
            "status": "completed" if validation["passed"] else "failed",
            "results": results,
            "validation": validation,
            "executed_at": datetime.now(UTC).isoformat(),
        })
        
        return {
            "eip_id": eip_id,
            "title": eip.title,
            "subtasks_executed": len(results),
            "passed": validation["passed"],
            "validation_details": validation,
            "results": results,
        }
    
    async def _decompose_eip(self, eip: EIPSpec) -> list[SubTask]:
        """Decompoe EIP em sub-tarefas técnicas."""
        subtasks = []
        
        # Tarefas baseadas em requisitos
        for i, req in enumerate(eip.requirements):
            subtasks.append(SubTask(
                task_id=f"{eip.eip_id}-req-{i}",
                title=f"Requisito: {req[:50]}",
                description=req,
                required_capabilities=[AgentCapability.CODE_GENERATION, AgentCapability.ARCHITECTURE],
                preferred_specialties=["programador"],
                priority=TaskPriority.HIGH,
            ))
        
        # Tarefas baseadas em componentes afetados
        for comp in eip.affected_components:
            subtasks.append(SubTask(
                task_id=f"{eip.eip_id}-comp-{comp}",
                title=f"Modificar componente: {comp}",
                description=f"Implementar mudanças no componente {comp} para EIP {eip.eip_id}",
                required_capabilities=[AgentCapability.CODE_GENERATION],
                preferred_specialties=["programador"],
                priority=TaskPriority.MEDIUM,
            ))
        
        # Testes
        if eip.acceptance_criteria:
            subtasks.append(SubTask(
                task_id=f"{eip.eip_id}-test",
                title="Testes de aceitação",
                description=f"Validar critérios: {', '.join(eip.acceptance_criteria)}",
                required_capabilities=[AgentCapability.DEBUGGING, AgentCapability.CODE_GENERATION],
                preferred_specialties=["programador"],
                priority=TaskPriority.HIGH,
            ))
        
        # Documentação
        subtasks.append(SubTask(
            task_id=f"{eip.eip_id}-doc",
            title="Documentar implementação",
            description=f"Atualizar docs da EIP {eip.eip_id}",
            required_capabilities=[AgentCapability.TEXT_GENERATION],
            preferred_specialties=["redator"],
            priority=TaskPriority.LOW,
        ))
        
        return subtasks
    
    async def _validate_eip_acceptance(
        self, 
        eip: EIPSpec, 
        results: list[dict]
    ) -> dict[str, Any]:
        """Valida critérios de aceitação da EIP."""
        all_passed = all(r["status"] == "completed" for r in results)
        
        return {
            "passed": all_passed,
            "total_criteria": len(eip.acceptance_criteria),
            "criteria_met": len(eip.acceptance_criteria) if all_passed else 0,
            "subtasks_passed": sum(1 for r in results if r["status"] == "completed"),
            "subtasks_total": len(results),
        }
    
    # =========================================================================
    # Status e Consultas
    # =========================================================================
    
    def get_sprint_status(self, sprint_id: str) -> dict[str, Any] | None:
        sprint = self._sprints.get(sprint_id)
        if not sprint:
            return None
        
        return {
            "sprint_id": sprint.sprint_id,
            "name": sprint.name,
            "goal": sprint.goal,
            "status": sprint.status.value,
            "total_tasks": len(sprint.tasks),
            "completed": sum(1 for t in sprint.tasks if t.status == TaskStatus.COMPLETED),
            "in_progress": sum(1 for t in sprint.tasks if t.status == TaskStatus.IN_PROGRESS),
            "failed": sum(1 for t in sprint.tasks if t.status == TaskStatus.FAILED),
            "tasks": [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "status": t.status.value,
                    "assigned_profile": t.assigned_profile,
                }
                for t in sprint.tasks
            ],
        }
    
    def get_eip_history(self) -> list[dict[str, Any]]:
        return self._eip_history
    
    def list_sprints(self) -> list[dict[str, Any]]:
        return [
            {
                "sprint_id": s.sprint_id,
                "name": s.name,
                "goal": s.goal,
                "status": s.status.value,
                "progress": f"{sum(1 for t in s.tasks if t.status == TaskStatus.COMPLETED)}/{len(s.tasks)}",
            }
            for s in self._sprints.values()
        ]