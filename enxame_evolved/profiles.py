#!/usr/bin/env python3
"""
AgentProfileManager — Gerenciador de Perfis de Agentes Dinâmicos
=================================================================
Cria, evolui e seleciona perfis de agentes automaticamente baseado em:
- Análise de tarefa e intenção
- Capacidades locais e de peers
- Histórico de performance
- Feedback de execução
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bees import BeeService
from .discovery import AutoDiscoveryService, DiscoveredPeer

logger = logging.getLogger("enxame.profiles")


@dataclass(slots=True)
class AgentProfile:
    """Perfil de agente com especialização e capacidades."""
    profile_id: str
    name: str
    description: str
    domain: str  # general, technical, legal, medical, financial, creative, etc.
    capabilities: list[str] = field(default_factory=list)
    required_models: list[str] = field(default_factory=list)
    preferred_models: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)  # search, code, ocr, image, calc, etc.
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    complexity_handling: str = "medium"  # simple, medium, complex
    peer_delegation: bool = True
    multimodal: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    usage_count: int = 0
    success_rate: float = 1.0
    avg_latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProfilePerformance:
    """Métricas de performance de um perfil."""
    profile_id: str
    total_executions: int = 0
    successful: int = 0
    failed: int = 0
    total_latency_ms: float = 0.0
    peer_delegations: int = 0
    local_executions: int = 0
    last_used: datetime | None = None
    feedback_scores: list[float] = field(default_factory=list)


class AgentProfileManager:
    """
    Gerencia perfis de agentes dinamicamente.
    
    Funcionalidades:
    - Perfis base pré-definidos (generalist, coder, researcher, etc.)
    - Criação automática de perfis especializados
    - Seleção inteligente baseada em análise de tarefa
    - Evolução contínua baseada em performance
    - Sincronização com peers para delegação
    """

    # Perfis base do sistema
    BASE_PROFILES = {
        "generalist": {
            "name": "Generalista",
            "description": "Agente de propósito geral para tarefas diversas",
            "domain": "general",
            "capabilities": ["rag", "vector_search", "embeddings", "query"],
            "tools": ["search", "memory"],
            "system_prompt": "Você é um assistente geral útil e preciso. Responda de forma clara e concisa.",
            "temperature": 0.7,
            "complexity_handling": "medium",
        },
        "coder": {
            "name": "Programador",
            "description": "Especialista em desenvolvimento de software",
            "domain": "technical",
            "capabilities": ["rag", "vector_search", "code_analysis", "code_generation"],
            "required_models": ["codellama", "deepseek-coder", "qwen2.5-coder"],
            "preferred_models": ["qwen2.5-coder:7b", "deepseek-coder:6.7b"],
            "tools": ["code", "search", "terminal", "git"],
            "system_prompt": "Você é um engenheiro de software sênior. Escreva código limpo, testável e bem documentado. Siga boas práticas e padrões da indústria.",
            "temperature": 0.2,
            "complexity_handling": "complex",
            "multimodal": False,
        },
        "researcher": {
            "name": "Pesquisador",
            "description": "Especialista em pesquisa e análise de informações",
            "domain": "general",
            "capabilities": ["rag", "vector_search", "deep_research", "synthesis"],
            "tools": ["search", "web", "academic", "citation"],
            "system_prompt": "Você é um pesquisador rigoroso. Forneça respostas baseadas em evidências, cite fontes e apresente múltiplas perspectivas.",
            "temperature": 0.3,
            "complexity_handling": "complex",
        },
        "analyst": {
            "name": "Analista",
            "description": "Especialista em análise de dados e negócios",
            "domain": "financial",
            "capabilities": ["rag", "data_analysis", "visualization", "reporting"],
            "tools": ["calc", "chart", "sql", "excel"],
            "system_prompt": "Você é um analista de dados sênior. Forneça insights acionáveis baseados em dados, com visualizações quando apropriado.",
            "temperature": 0.3,
            "complexity_handling": "medium",
        },
        "creative": {
            "name": "Criativo",
            "description": "Especialista em tarefas criativas e de conteúdo",
            "domain": "creative",
            "capabilities": ["creative_writing", "content_generation", "storytelling"],
            "tools": ["image", "text", "brainstorm"],
            "system_prompt": "Você é um diretor criativo. Produza conteúdo original, envolvente e adaptado ao público-alvo.",
            "temperature": 0.8,
            "complexity_handling": "medium",
            "multimodal": True,
        },
        "legal": {
            "name": "Jurídico",
            "description": "Especialista em direito e conformidade",
            "domain": "legal",
            "capabilities": ["legal_research", "contract_analysis", "compliance"],
            "required_models": ["legal-llm"],
            "tools": ["search", "document", "citation"],
            "system_prompt": "Você é um advogado especializado. Forneça análises jurídicas precisas, cite legislação e jurisprudência relevantes.",
            "temperature": 0.1,
            "complexity_handling": "complex",
        },
        "medical": {
            "name": "Médico",
            "description": "Especialista em saúde e medicina",
            "domain": "medical",
            "capabilities": ["medical_knowledge", "symptom_analysis", "literature_review"],
            "required_models": ["medllama", "biomistral"],
            "tools": ["search", "pubmed", "clinical"],
            "system_prompt": "Você é um médico. Forneça informações médicas baseadas em evidências, sempre recomende consulta profissional.",
            "temperature": 0.1,
            "complexity_handling": "complex",
        },
        "architect": {
            "name": "Arquiteto",
            "description": "Especialista em arquitetura de sistemas e software",
            "domain": "technical",
            "capabilities": ["system_design", "architecture_review", "tech_decisions"],
            "tools": ["diagram", "code", "documentation"],
            "system_prompt": "Você é um arquiteto de software principal. Projete sistemas escaláveis, resilientes e mainteníveis. Documente decisões (ADRs).",
            "temperature": 0.3,
            "complexity_handling": "complex",
        },
    }

    def __init__(
        self,
        node_id: str,
        discovery: AutoDiscoveryService,
        bee_service: BeeService,
    ) -> None:
        self.node_id = node_id
        self.discovery = discovery
        self.bee = bee_service
        
        self._profiles: dict[str, AgentProfile] = {}
        self._performance: dict[str, ProfilePerformance] = {}
        self._profile_dir = Path.home() / ".enxame" / "profiles"
        self._profile_dir.mkdir(parents=True, exist_ok=True)
        
        self._initialized = False

    async def initialize(self) -> None:
        """Inicializa perfis base e carrega salvos."""
        # Carregar perfis base
        for pid, spec in self.BASE_PROFILES.items():
            profile = AgentProfile(
                profile_id=pid,
                name=spec["name"],
                description=spec["description"],
                domain=spec["domain"],
                capabilities=spec.get("capabilities", []),
                required_models=spec.get("required_models", []),
                preferred_models=spec.get("preferred_models", []),
                tools=spec.get("tools", []),
                system_prompt=spec.get("system_prompt", ""),
                temperature=spec.get("temperature", 0.7),
                complexity_handling=spec.get("complexity_handling", "medium"),
                multimodal=spec.get("multimodal", False),
            )
            self._profiles[pid] = profile
            self._performance[pid] = ProfilePerformance(profile_id=pid)

        # Carregar perfis customizados salvos
        await self._load_custom_profiles()
        
        # Verificar modelos disponíveis e ajustar
        await self._sync_with_available_models()
        
        self._initialized = True
        logger.info(f"Profile Manager inicializado com {len(self._profiles)} perfis")

    async def close(self) -> None:
        """Salva perfis customizados."""
        await self._save_custom_profiles()

    def _get_available_models(self) -> list[str]:
        """Retorna modelos disponíveis no Ollama local."""
        if self.bee and hasattr(self.bee, '_librarian') and self.bee._librarian:
            return self.bee._librarian.get_available_models()
        return []

    async def _sync_with_available_models(self) -> None:
        """Sincroniza perfis com modelos disponíveis."""
        available = set(self._get_available_models())
        
        for profile in self._profiles.values():
            # Verificar required_models
            missing_required = [m for m in profile.required_models if m not in available]
            if missing_required:
                logger.warning(f"Perfil {profile.profile_id} requer modelos indisponíveis: {missing_required}")
            
            # Ajustar preferred_models para disponíveis
            profile.preferred_models = [m for m in profile.preferred_models if m in available]
            if not profile.preferred_models and available:
                profile.preferred_models = [list(available)[0]]

    async def _load_custom_profiles(self) -> None:
        """Carrega perfis customizados do disco."""
        for profile_file in self._profile_dir.glob("*.json"):
            try:
                with open(profile_file) as f:
                    data = json.load(f)
                profile = AgentProfile(**data)
                self._profiles[profile.profile_id] = profile
                self._performance[profile.profile_id] = ProfilePerformance(profile_id=profile.profile_id)
                logger.info(f"Perfil customizado carregado: {profile.profile_id}")
            except Exception as e:
                logger.error(f"Erro ao carregar {profile_file}: {e}")

    async def _save_custom_profiles(self) -> None:
        """Salva perfis customizados (não base) no disco."""
        base_ids = set(self.BASE_PROFILES.keys())
        for pid, profile in self._profiles.items():
            if pid not in base_ids:
                file_path = self._profile_dir / f"{pid}.json"
                with open(file_path, "w") as f:
                    json.dump(profile.__dict__, f, indent=2, default=str)

    # =========================================================================
    # Seleção e Criação de Perfis
    # =========================================================================

    async def select_or_create_profile(self, analysis: dict) -> AgentProfile:
        """
        Seleciona melhor perfil existente ou cria novo baseado na análise.
        
        Args:
            analysis: Dict com task_type, complexity, domain, requires_multimodal, etc.
        
        Returns:
            AgentProfile selecionado ou criado
        """
        task_type = analysis.get("task_type", "query")
        complexity = analysis.get("complexity", "medium")
        domain = analysis.get("domain", "general")
        requires_multimodal = analysis.get("requires_multimodal", False)
        suggested = analysis.get("suggested_profile")
        
        # 1. Se sugerido explicitamente e existe, usar
        if suggested and suggested in self._profiles:
            profile = self._profiles[suggested]
            return await self._prepare_profile(profile, analysis)
        
        # 2. Buscar por domain match
        domain_profiles = [p for p in self._profiles.values() if p.domain == domain]
        if domain_profiles:
            # Filtrar por complexidade e multimodal
            candidates = [p for p in domain_profiles 
                         if p.complexity_handling == complexity or p.complexity_handling == "complex"
                         and (not requires_multimodal or p.multimodal)]
            if candidates:
                return await self._prepare_profile(max(candidates, key=self._profile_score), analysis)
        
        # 3. Buscar por task_type match
        task_map = {
            "code": "coder",
            "research": "researcher",
            "analysis": "analyst",
            "creative": "creative",
            "planning": "architect",
            "document": "researcher",
            "image": "creative",
        }
        mapped = task_map.get(task_type)
        if mapped and mapped in self._profiles:
            return await self._prepare_profile(self._profiles[mapped], analysis)
        
        # 4. Fallback: generalist
        if "generalist" in self._profiles:
            return await self._prepare_profile(self._profiles["generalist"], analysis)
        
        # 5. Criar perfil dinâmico
        return await self._create_dynamic_profile(analysis)

    def _profile_score(self, profile: AgentProfile) -> float:
        """Score para seleção de perfil."""
        perf = self._performance.get(profile.profile_id)
        if not perf or perf.total_executions == 0:
            return 0.5  # Neutro para novos
        
        success_rate = perf.successful / perf.total_executions
        avg_latency = perf.total_latency_ms / perf.total_executions
        recency = 1.0
        if perf.last_used:
            hours_ago = (datetime.now(UTC) - perf.last_used).total_seconds() / 3600
            recency = max(0.1, 1.0 - hours_ago / 168)  # Decay em 1 semana
        
        return success_rate * 0.5 + recency * 0.3 + (1.0 / (1.0 + avg_latency / 1000)) * 0.2

    async def _prepare_profile(self, profile: AgentProfile, analysis: dict) -> AgentProfile:
        """Prepara perfil para execução (ajusta modelo, etc)."""
        # Selecionar melhor modelo disponível
        available = set(self._get_available_models())
        if profile.preferred_models:
            for model in profile.preferred_models:
                if model in available:
                    profile.metadata["selected_model"] = model
                    break
            else:
                profile.metadata["selected_model"] = list(available)[0] if available else None
        
        profile.usage_count += 1
        profile.updated_at = datetime.now(UTC)
        return profile

    async def _create_dynamic_profile(self, analysis: dict) -> AgentProfile:
        """Cria perfil dinamicamente baseado na análise."""
        task_type = analysis.get("task_type", "query")
        domain = analysis.get("domain", "general")
        complexity = analysis.get("complexity", "medium")
        requires_multimodal = analysis.get("requires_multimodal", False)
        
        # Template por domain
        domain_templates = {
            "technical": {"base": "coder", "tools": ["code", "terminal", "git"]},
            "financial": {"base": "analyst", "tools": ["calc", "chart", "sql"]},
            "legal": {"base": "legal", "tools": ["search", "document"]},
            "medical": {"base": "medical", "tools": ["pubmed", "clinical"]},
            "creative": {"base": "creative", "tools": ["image", "brainstorm"]},
            "general": {"base": "generalist", "tools": ["search", "memory"]},
        }
        
        template = domain_templates.get(domain, domain_templates["general"])
        base_profile = self._profiles.get(template["base"], self._profiles["generalist"])
        
        # Criar novo perfil
        profile_id = f"dynamic_{domain}_{task_type}_{uuid.uuid4().hex[:8]}"
        profile = AgentProfile(
            profile_id=profile_id,
            name=f"{domain.title()} {task_type.title()} Specialist",
            description=f"Perfil dinâmico para {task_type} no domínio {domain}",
            domain=domain,
            capabilities=base_profile.capabilities.copy(),
            tools=template["tools"].copy(),
            system_prompt=base_profile.system_prompt,
            temperature=base_profile.temperature,
            complexity_handling=complexity,
            multimodal=requires_multimodal,
            metadata={"dynamic": True, "base_profile": template["base"]},
        )
        
        # Adicionar capacidades baseadas na análise
        if requires_multimodal:
            profile.capabilities.extend(["image_analysis", "ocr", "document_processing"])
            profile.tools.extend(["ocr", "image"])
        
        self._profiles[profile_id] = profile
        self._performance[profile_id] = ProfilePerformance(profile_id=profile_id)
        
        logger.info(f"Perfil dinâmico criado: {profile_id}")
        return profile

    async def create_profile(self, spec: dict) -> dict:
        """Cria perfil customizado via API."""
        profile_id = spec.get("profile_id") or f"custom_{uuid.uuid4().hex[:8]}"
        
        profile = AgentProfile(
            profile_id=profile_id,
            name=spec.get("name", "Custom Profile"),
            description=spec.get("description", ""),
            domain=spec.get("domain", "general"),
            capabilities=spec.get("capabilities", []),
            required_models=spec.get("required_models", []),
            preferred_models=spec.get("preferred_models", []),
            tools=spec.get("tools", []),
            system_prompt=spec.get("system_prompt", ""),
            temperature=spec.get("temperature", 0.7),
            max_tokens=spec.get("max_tokens", 2048),
            complexity_handling=spec.get("complexity_handling", "medium"),
            multimodal=spec.get("multimodal", False),
            metadata=spec.get("metadata", {}),
        )
        
        self._profiles[profile_id] = profile
        self._performance[profile_id] = ProfilePerformance(profile_id=profile_id)
        await self._save_custom_profiles()
        
        return {"profile_id": profile_id, "status": "created"}

    async def list_profiles(self) -> list[dict]:
        """Lista todos os perfis disponíveis."""
        return [
            {
                "profile_id": p.profile_id,
                "name": p.name,
                "description": p.description,
                "domain": p.domain,
                "capabilities": p.capabilities,
                "tools": p.tools,
                "complexity": p.complexity_handling,
                "multimodal": p.multimodal,
                "usage_count": p.usage_count,
                "success_rate": self._performance.get(p.profile_id, ProfilePerformance(p.profile_id)).successful / max(1, self._performance.get(p.profile_id, ProfilePerformance(p.profile_id)).total_executions),
            }
            for p in self._profiles.values()
        ]

    # =========================================================================
    # Evolução e Sincronização
    # =========================================================================

    async def record_execution(self, profile_id: str, success: bool, latency_ms: float, delegated: bool = False) -> None:
        """Registra execução para evolução do perfil."""
        if profile_id not in self._performance:
            self._performance[profile_id] = ProfilePerformance(profile_id=profile_id)
        
        perf = self._performance[profile_id]
        perf.total_executions += 1
        if success:
            perf.successful += 1
        else:
            perf.failed += 1
        perf.total_latency_ms += latency_ms
        perf.last_used = datetime.now(UTC)
        if delegated:
            perf.peer_delegations += 1
        else:
            perf.local_executions += 1

    async def record_feedback(self, profile_id: str, score: float) -> None:
        """Registra feedback do usuário (0.0 a 1.0)."""
        if profile_id in self._performance:
            self._performance[profile_id].feedback_scores.append(score)

    async def evolve_profiles(self) -> None:
        """Evolui perfis baseado em performance."""
        for pid, perf in self._performance.items():
            if pid not in self._profiles:
                continue
            if perf.total_executions < 5:
                continue  # Poucos dados
            
            profile = self._profiles[pid]
            success_rate = perf.successful / perf.total_executions
            
            # Ajustar temperatura baseado em sucesso
            if success_rate > 0.9 and profile.temperature > 0.1:
                profile.temperature = max(0.1, profile.temperature - 0.05)
            elif success_rate < 0.5 and profile.temperature < 1.0:
                profile.temperature = min(1.0, profile.temperature + 0.1)
            
            # Marcar para revisão se performance ruim
            if success_rate < 0.3:
                profile.metadata["needs_review"] = True
                logger.warning(f"Perfil {pid} com performance baixa: {success_rate:.1%}")

    async def evaluate_peer_for_profiles(self, peer: DiscoveredPeer) -> None:
        """Avalia peer descoberto para criar perfis de delegação."""
        # Criar perfil de delegação para peer se tem capacidades únicas
        unique_caps = set(peer.capabilities) - set().union(*[set(p.capabilities) for p in self._profiles.values()])
        if unique_caps:
            profile_id = f"peer_{peer.node_id[:8]}"
            if profile_id not in self._profiles:
                profile = AgentProfile(
                    profile_id=profile_id,
                    name=f"Peer {peer.node_id[:8]} Delegate",
                    description=f"Delegação para peer {peer.node_id} com capacidades: {', '.join(unique_caps)}",
                    domain="delegation",
                    capabilities=list(unique_caps),
                    tools=["peer_delegate"],
                    system_prompt=f"Você delega tarefas para o peer {peer.node_id} que possui capacidades especializadas.",
                    temperature=0.5,
                    complexity_handling="medium",
                    peer_delegation=True,
                    metadata={"peer_node_id": peer.node_id, "auto_created": True},
                )
                self._profiles[profile_id] = profile
                self._performance[profile_id] = ProfilePerformance(profile_id=profile_id)
                logger.info(f"Perfil de delegação criado para peer: {profile_id}")

    async def sync_capabilities_with_peers(self, peers: list[DiscoveredPeer]) -> None:
        """Sincroniza capacidades conhecidas com peers ativos."""
        for peer in peers:
            await self.evaluate_peer_for_profiles(peer)

    def get_stats(self) -> dict[str, Any]:
        """Estatísticas do gerenciador de perfis."""
        return {
            "total_profiles": len(self._profiles),
            "base_profiles": len(self.BASE_PROFILES),
            "custom_profiles": len(self._profiles) - len(self.BASE_PROFILES),
            "dynamic_profiles": sum(1 for p in self._profiles.values() if p.metadata.get("dynamic")),
            "peer_delegation_profiles": sum(1 for p in self._profiles.values() if p.peer_delegation),
            "profiles": [
                {
                    "profile_id": pid,
                    "name": p.name,
                    "domain": p.domain,
                    "usage": p.usage_count,
                    "success_rate": perf.successful / max(1, perf.total_executions),
                    "avg_latency_ms": perf.total_latency_ms / max(1, perf.total_executions),
                }
                for pid, (p, perf) in zip(self._profiles.keys(), self._performance.items())
            ],
        }