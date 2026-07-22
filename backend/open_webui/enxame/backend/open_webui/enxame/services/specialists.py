from ..models.schemas import AgentResponse, AgentRole, SearchResult
from ..logging_config import get_logger
from typing import List

logger = get_logger("specialists")

class SpecialistService:
    def __init__(self):
        self.specialist_types = [
            "general",
            "programmer",
            "writer",
            "analyst",
            "researcher"
        ]
    
    async def dispatch(
        self, 
        query: str, 
        context: SearchResult, 
        agent_role: str = "general"
    ) -> List[AgentResponse]:
        """
        Dispatch query to specialist agents.
        In production, this calls Ollama via Open WebUI API with specific prompts.
        """
        logger.info(f"Dispatching to {agent_role} specialist: {query[:50]}...")
        
        # Placeholder response
        # Real implementation would call model here
        responses = [
            AgentResponse(
                agent_id=f"specialist-{agent_role}-01",
                role=AgentRole.SPECIALIST,
                content=f"Specialist ({agent_role}) analysis for: {query}",
                confidence=0.85,
                metadata={
                    "model": "llama3",
                    "context_used": len(context.chunks)
                },
                execution_time=0.5
            )
        ]
        
        return responses