from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class ThreatLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AgentRole(str, Enum):
    CONTROLLER = "controller"
    SCHEDULER = "scheduler"
    JUDGE = "judge"
    GUARD = "guard"
    LIBRARIAN = "librarian"
    SPECIALIST = "specialist"

class MissionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"

class ValidationResult(BaseModel):
    allowed: bool
    threat_level: ThreatLevel = ThreatLevel.NONE
    reasons: List[str] = []
    actions: List[str] = []

class DocumentChunk(BaseModel):
    content: str
    source: str
    score: float
    path: str
    metadata: Dict[str, Any] = {}

class SearchResult(BaseModel):
    chunks: List[DocumentChunk]
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
    metadata: Dict[str, Any] = {}
    execution_time: Optional[float] = None

class JudgmentResult(BaseModel):
    final_answer: str
    confidence: float
    reasoning: str
    sources: List[str] = []
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
    details: Optional[str] = None
    error: Optional[str] = None

class MissionProgress(BaseModel):
    current_step: str
    total_steps: int
    completed_steps: int
    percentage: float

class Mission(BaseModel):
    id: str
    status: MissionStatus = MissionStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    input_query: str
    final_answer: Optional[str] = None
    confidence_score: float = 0.0
    logs: List[MissionLog] = []
    progress: Optional[MissionProgress] = None
    resource_usage: Optional[ResourceUsage] = None
    active_node: Optional[str] = None
    cancelled: bool = False