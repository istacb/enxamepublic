"""Shared profile models to avoid agent/manager import cycles."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

class AgentCapability(str, Enum):
    """Capacidades possíveis de um agente."""
    # Básicas
    TEXT_GENERATION = "text_generation"
    CODE_GENERATION = "code_generation"
    DEBUGGING = "debugging"
    ARCHITECTURE = "architecture"
    
    # Conhecimento
    RAG_LOCAL = "rag_local"
    RAG_DISTRIBUTED = "rag_distributed"
    WEB_SEARCH = "web_search"
    SEMANTIC_MEMORY = "semantic_memory"
    
    # Multimodal
    OCR = "ocr"
    IMAGE_ANALYSIS = "image_analysis"
    DOCUMENT_PROCESSING = "document_processing"
    PHOTO_ANALYSIS = "photo_analysis"
    
    # Orquestração
    TASK_PLANNING = "task_planning"
    SPRINT_ORCHESTRATION = "sprint_orchestration"
    AGENT_COORDINATION = "agent_coordination"
    
    # Especializações
    LEGAL = "legal"
    MEDICAL = "medical"
    FINANCIAL = "financial"
    SCIENTIFIC = "scientific"


@dataclass(slots=True)
class AgentProfile:
    """Perfil dinâmico de um agente."""
    agent_id: str
    name: str
    capabilities: list[AgentCapability] = field(default_factory=list)
    specialties: list[str] = field(default_factory=list)  # Nomes dos plugins
    model: str = "llama3.2:3b"
    system_prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    # Métricas de performance
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    tasks_completed: int = 0
    
    def has_capability(self, cap: AgentCapability) -> bool:
        return cap in self.capabilities
    
    def match_score(self, task_description: str) -> float:
        """Score de compatibilidade com uma tarefa."""
        score = 0.0
        text_lower = task_description.lower()
        
        # Score por capabilities
        cap_keywords = {
            AgentCapability.CODE_GENERATION: ['código', 'code', 'programa', 'script', 'função', 'api'],
            AgentCapability.DEBUGGING: ['bug', 'erro', 'debug', 'falha', 'exception', 'traceback'],
            AgentCapability.ARCHITECTURE: ['arquitetura', 'design', 'estrutura', 'sistema', 'scalab'],
            AgentCapability.OCR: ['ocr', 'imagem', 'pdf', 'escaneado', 'foto', 'leitura'],
            AgentCapability.IMAGE_ANALYSIS: ['analisar imagem', 'visão', 'computer vision', 'foto'],
            AgentCapability.DOCUMENT_PROCESSING: ['documento', 'arquivo', 'pdf', 'word', 'excel'],
            AgentCapability.LEGAL: ['jurídico', 'legal', 'lei', 'contrato', 'processo'],
            AgentCapability.MEDICAL: ['médico', 'saúde', 'diagnóstico', 'paciente'],
            AgentCapability.TASK_PLANNING: ['planejar', 'organizar', 'tarefas', 'sprint', 'roadmap'],
        }
        
        for cap in self.capabilities:
            if cap in cap_keywords:
                for kw in cap_keywords[cap]:
                    if kw in text_lower:
                        score += 2.0
        
        # Score por specialties (plugins)
        for spec in self.specialties:
            if spec.lower() in text_lower:
                score += 3.0
        
        # Bonus por performance histórica
        if self.tasks_completed > 10:
            score *= (1.0 + min(self.success_rate * 0.2, 0.2))
        
        return score

