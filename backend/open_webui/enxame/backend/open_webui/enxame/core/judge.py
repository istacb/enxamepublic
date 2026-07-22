from ..models.schemas import AgentResponse, JudgmentResult, AgentRole
from ..logging_config import get_logger
from typing import List

logger = get_logger("judge")

class Judge:
    async def evaluate(self, responses: List[AgentResponse]) -> JudgmentResult:
        """
        Merge responses from multiple agents into a single coherent answer.
        Handles conflict resolution and confidence calculation.
        """
        if not responses:
            return JudgmentResult(
                final_answer="No responses received from agents.",
                confidence=0.0,
                reasoning="Empty response list",
                merged_count=0
            )
        
        # Filter out low confidence responses
        valid_responses = [r for r in responses if r.confidence > 0.1]
        if not valid_responses:
            valid_responses = responses  # Fallback to all if all are low confidence
        
        # Calculate weighted average confidence
        total_confidence = sum(r.confidence for r in valid_responses)
        avg_confidence = total_confidence / len(valid_responses) if valid_responses else 0.0
        
        # Simple consolidation: join contents (Future: LLM-based merging)
        contents = [f"[{r.agent_id}]: {r.content}" for r in valid_responses]
        final_text = "\n\n".join(contents)
        
        logger.info(f"Judgment complete. Merged {len(valid_responses)} responses. Confidence: {avg_confidence:.2f}")
        
        return JudgmentResult(
            final_answer=final_text,
            confidence=avg_confidence,
            reasoning="Consolidated from multiple agent responses",
            sources=[r.agent_id for r in valid_responses],
            merged_count=len(valid_responses)
        )