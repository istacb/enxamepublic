from ..models.schemas import (
    Mission, MissionStatus, MissionLog, MissionProgress, 
    ResourceUsage, AgentResponse, ValidationResult
)
from ..core.guard import Guard
from ..core.librarian import Librarian
from ..core.scheduler import Scheduler
from ..core.judge import Judge
from ..services.specialists import SpecialistService
from ..logging_config import get_logger
from datetime import datetime
import uuid
import time

logger = get_logger("controller")

class Controller:
    def __init__(
        self, 
        guard: Guard, 
        librarian: Librarian, 
        scheduler: Scheduler, 
        specialists: SpecialistService, 
        judge: Judge
    ):
        self.guard = guard
        self.librarian = librarian
        self.scheduler = scheduler
        self.specialists = specialists
        self.judge = judge

    async def process_request(self, query: str, user_id: str = "anonymous") -> Mission:
        """
        Main orchestration flow:
        Guard -> Librarian -> Scheduler -> Specialists -> Judge
        """
        mission_id = str(uuid.uuid4())
        start_time = time.time()
        
        mission = Mission(
            id=mission_id,
            status=MissionStatus.RUNNING,
            input_query=query,
            logs=[MissionLog(
                timestamp=datetime.utcnow(),
                agent_id="controller",
                action="mission_started",
                details=f"User: {user_id}"
            )]
        )
        
        try:
            # Step 1: Security Check
            validation: ValidationResult = await self.guard.validate(query, user_id)
            if not validation.allowed:
                mission.status = MissionStatus.BLOCKED
                mission.final_answer = f"Blocked by Guard: {', '.join(validation.reasons)}"
                mission.logs.append(MissionLog(
                    timestamp=datetime.utcnow(),
                    agent_id="guard",
                    action="blocked",
                    details=str(validation.reasons)
                ))
                return mission
            
            mission.logs.append(MissionLog(
                timestamp=datetime.utcnow(),
                agent_id="guard",
                action="validated",
                details="Security check passed"
            ))

            # Step 2: Context Retrieval
            context = await self.librarian.search(query)
            mission.logs.append(MissionLog(
                timestamp=datetime.utcnow(),
                agent_id="librarian",
                action="context_retrieved",
                details=f"Found {context.total_results} chunks"
            ))

            # Step 3: Scheduling
            node_id = await self.scheduler.select_agent(query, ["specialist"])
            mission.active_node = node_id
            mission.logs.append(MissionLog(
                timestamp=datetime.utcnow(),
                agent_id="scheduler",
                action="scheduled",
                details=f"Node: {node_id}"
            ))

            # Step 4: Specialist Execution
            responses = await self.specialists.dispatch(query, context, "general")
            mission.logs.append(MissionLog(
                timestamp=datetime.utcnow(),
                agent_id="specialists",
                action="executed",
                details=f"Received {len(responses)} responses"
            ))

            # Step 5: Judgment
            judgment = await self.judge.evaluate(responses)
            
            mission.final_answer = judgment.final_answer
            mission.confidence_score = judgment.confidence
            mission.status = MissionStatus.COMPLETED
            mission.logs.append(MissionLog(
                timestamp=datetime.utcnow(),
                agent_id="judge",
                action="completed",
                details=f"Confidence: {judgment.confidence:.2f}"
            ))

        except Exception as e:
            logger.error(f"Mission failed: {str(e)}")
            mission.status = MissionStatus.FAILED
            mission.final_answer = str(e)
            mission.logs.append(MissionLog(
                timestamp=datetime.utcnow(),
                agent_id="controller",
                action="error",
                error=str(e)
            ))
        
        # Update timing and resource usage (mocked)
        mission.updated_at = datetime.utcnow()
        execution_time = time.time() - start_time
        mission.resource_usage = ResourceUsage(
            cpu_percent=25.0,
            ram_percent=50.0,
            ram_used_mb=1024.0,
            ram_total_mb=8192.0
        )
        
        return mission