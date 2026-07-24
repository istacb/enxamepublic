from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ThreatLevel(str, Enum):
    NONE = 'none'
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class AgentRole(str, Enum):
    CONTROLLER = 'controller'
    SCHEDULER = 'scheduler'
    JUDGE = 'judge'
    GUARD = 'guard'
    LIBRARIAN = 'librarian'
    SPECIALIST = 'specialist'


class MissionStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    BLOCKED = 'blocked'
    CANCELLED = 'cancelled'


class ValidationResult(BaseModel):
    allowed: bool
    threat_level: ThreatLevel = ThreatLevel.NONE
    reasons: list[str] = []
    actions: list[str] = []


class DocumentChunk(BaseModel):
    content: str
    source: str
    score: float
    path: str
    metadata: dict[str, Any] = {}


class SearchResult(BaseModel):
    chunks: list[DocumentChunk]
    total_results: int
    query: str


class KnowledgeSource(BaseModel):
    name: str
    type: str
    path: str
    last_indexed: datetime


class AgentResponse(BaseModel):
    agent_id: str
    role: AgentRole
    content: str
    confidence: float = 0.0
    metadata: dict[str, Any] = {}
    execution_time: float | None = None


class JudgmentResult(BaseModel):
    final_answer: str
    confidence: float
    reasoning: str
    sources: list[str] = []
    merged_count: int = 0


class ResourceUsage(BaseModel):
    cpu_percent: float
    ram_percent: float
    ram_used_mb: float
    ram_total_mb: float


class NodeStatus(BaseModel):
    node_id: str
    status: str
    resource_usage: ResourceUsage
    active_missions: int


class MissionLog(BaseModel):
    timestamp: datetime
    agent_id: str
    action: str
    details: str | None = None
    error: str | None = None


class MissionProgress(BaseModel):
    current_step: str
    total_steps: int
    completed_steps: int
    percentage: float


class Mission(BaseModel):
    id: str
    status: MissionStatus = MissionStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None
    input_query: str
    final_answer: str | None = None
    confidence_score: float = 0.0
    logs: list[MissionLog] = []
    progress: MissionProgress | None = None
    resource_usage: ResourceUsage | None = None
    active_node: str | None = None
    cancelled: bool = False
