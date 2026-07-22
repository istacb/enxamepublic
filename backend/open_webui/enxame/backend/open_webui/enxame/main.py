"""
Main Integration Module for Enxame OS.
Exposes API endpoints for the Mission Control frontend.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from .di import get_container
from .config import settings
from .models.schemas import Mission, MissionStatus, ResourceUsage
from .logging_config import get_logger, setup_logging

logger = get_logger("main")

router = APIRouter(prefix="/enxame", tags=["enxame"])

class QueryRequest(BaseModel):
    query: str
    user_id: str = "anonymous"
    stream: bool = False

class QueryResponse(BaseModel):
    mission_id: str
    answer: str
    confidence: float
    status: str
    execution_time: Optional[float] = None

@router.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    """Handle a user query through the Enxame orchestration layer."""
    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Enxame OS is disabled")
    
    container = get_container()
    controller = container.get("controller")
    
    try:
        import time
        start_time = time.time()
        
        mission = await controller.process_request(
            query=request.query,
            user_id=request.user_id
        )
        
        execution_time = time.time() - start_time
        
        return QueryResponse(
            mission_id=mission.id,
            answer=mission.final_answer or "No answer generated",
            confidence=mission.confidence_score,
            status=mission.status.value,
            execution_time=execution_time
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@router.get("/mission/{mission_id}", response_model=Mission)
async def get_mission(mission_id: str):
    """Get mission details by ID."""
    # In a real app, this would fetch from a database
    # For now, we return a mock structure if needed or raise 404
    raise HTTPException(status_code=404, detail="Mission persistence not implemented in this demo")

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "plugin": "enxame-os",
        "version": "1.0.0",
        "enabled": settings.enabled
    }

# Initialize logging
setup_logging()