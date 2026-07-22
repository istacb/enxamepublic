from ..models.schemas import AgentRole, NodeStatus, ResourceUsage
from ..logging_config import get_logger
from typing import List, Optional
import random

logger = get_logger("scheduler")

class Scheduler:
    def __init__(self):
        self.nodes = {
            "local-node-1": NodeStatus(
                node_id="local-node-1",
                status="active",
                resource_usage=ResourceUsage(
                    cpu_percent=15.0,
                    ram_percent=45.0,
                    ram_used_mb=2048.0,
                    ram_total_mb=8192.0
                ),
                active_missions=0
            )
        }
    
    async def select_agent(self, query: str, available_roles: List[AgentRole]) -> str:
        """
        Select the best agent/node for execution.
        Currently returns a random available node.
        Future: Implement load balancing and GPU awareness.
        """
        active_nodes = [n for n in self.nodes.values() if n.status == "active"]
        if not active_nodes:
            raise RuntimeError("No active nodes available")
        
        selected = random.choice(active_nodes)
        logger.info(f"Scheduled execution on node: {selected.node_id}")
        return selected.node_id
    
    async def get_node_status(self, node_id: str) -> Optional[NodeStatus]:
        """Get status of a specific node."""
        return self.nodes.get(node_id)
    
    async def update_node_resources(self, node_id: str, usage: ResourceUsage):
        """Update resource usage for a node."""
        if node_id in self.nodes:
            self.nodes[node_id].resource_usage = usage