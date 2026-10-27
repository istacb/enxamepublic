/**
 * Scheduler - Main Scheduler Implementation
 *
 * The Scheduler is an internal component of the Orchestrator responsible for
 * deciding which Node should execute a Task.
 *
 * Key principles:
 * - Never executes Tasks
 * - Never communicates directly with Nodes
 * - Only analyzes state and returns scheduling decisions
 * - Event-oriented (no polling)
 * - Simple, deterministic, and efficient
 */

import { IScheduler } from '../interfaces';
import {
  Task,
  NodeInfo,
  Capability,
  SchedulingDecision,
  QueueStatus,
  SchedulingStatus,
  SchedulerConfig,
  DEFAULT_SCHEDULER_CONFIG
} from '../types';
import { FifoTaskQueue } from '../queue';
import { NodeSelection } from '../selection';
import { FifoSchedulingPolicy } from '../policy';

export class Scheduler implements IScheduler {
  private nodes: Map<string, NodeInfo>;
  private queue: FifoTaskQueue;
  private selection: NodeSelection;
  private policy: FifoSchedulingPolicy;
  private config: SchedulerConfig;

  constructor(config: Partial<SchedulerConfig> = {}) {
    this.nodes = new Map();
    this.queue = new FifoTaskQueue();
    this.selection = new NodeSelection();
    this.policy = new FifoSchedulingPolicy();
    this.config = { ...DEFAULT_SCHEDULER_CONFIG, ...config };
  }

  /**
   * Schedule a task for execution
   * @param task - The task to schedule
   * @returns A scheduling decision
   */
  async scheduleTask(task: Task): Promise<SchedulingDecision> {
    const timestamp = Date.now();

    // Get all available nodes
    const allNodes = Array.from(this.nodes.values());

    if (allNodes.length === 0) {
      // No nodes available, queue the task
      this.queue.enqueue(task);
      return this.createDecision(task.id, null, SchedulingStatus.Queued, 'No nodes available');
    }

    // Select best node using our criteria
    const selectedNode = this.selection.selectBest(
      allNodes,
      task.requiredCapabilities
    );

    if (selectedNode) {
      // Node found, schedule immediately
      return this.createDecision(task.id, selectedNode.id, SchedulingStatus.Scheduled);
    } else {
      // No suitable node, queue the task
      this.queue.enqueue(task);
      
      // Determine reason
      const capableNodes = this.selection.filterByCapability(allNodes, task.requiredCapabilities);
      const reason = capableNodes.length === 0
        ? 'No node with required capabilities'
        : 'No node with available capacity';
      
      return this.createDecision(task.id, null, SchedulingStatus.Queued, reason);
    }
  }

  /**
   * Handle node registration event
   * @param node - The newly registered node information
   */
  onNodeRegistered(node: NodeInfo): void {
    this.nodes.set(node.id, node);
    
    // Check if we can schedule queued tasks
    this.processQueue();
  }

  /**
   * Handle node removal event
   * @param nodeId - The ID of the removed node
   */
  onNodeRemoved(nodeId: string): void {
    this.nodes.delete(nodeId);
    // Note: Tasks already scheduled to this node will need to be handled by Orchestrator
  }

  /**
   * Handle runtime availability event
   * @param nodeId - The ID of the node with available runtime
   */
  onRuntimeAvailable(nodeId: string): void {
    const node = this.nodes.get(nodeId);
    if (node) {
      node.available = true;
      node.capacity.hasCapacity = true;
      this.nodes.set(nodeId, node);
      
      // Check if we can schedule queued tasks
      this.processQueue();
    }
  }

  /**
   * Handle capability change event
   * @param nodeId - The ID of the node with changed capabilities
   * @param capabilities - The new capabilities
   */
  onCapabilityChanged(nodeId: string, capabilities: Capability[]): void {
    const node = this.nodes.get(nodeId);
    if (node) {
      node.capabilities = capabilities;
      this.nodes.set(nodeId, node);
      
      // Check if we can schedule queued tasks
      this.processQueue();
    }
  }

  /**
   * Get current queue status
   * @returns Current queue status information
   */
  getQueueStatus(): QueueStatus {
    return {
      size: this.queue.size(),
      isEmpty: this.queue.isEmpty(),
      policy: this.config.queuePolicy
    };
  }

  /**
   * Process queued tasks when resources become available
   */
  private processQueue(): void {
    if (this.queue.isEmpty()) {
      return;
    }

    const allNodes = Array.from(this.nodes.values());
    
    if (allNodes.length === 0) {
      return;
    }

    // Try to schedule the next task in queue
    const nextTask = this.queue.peek();
    
    if (nextTask) {
      const selectedNode = this.selection.selectBest(
        allNodes,
        nextTask.requiredCapabilities
      );

      if (selectedNode) {
        // Remove from queue and schedule
        this.queue.dequeue();
        // In a real implementation, this would notify the Orchestrator
        // For now, we just remove it from the queue
      }
    }
  }

  /**
   * Create a scheduling decision object
   */
  private createDecision(
    taskId: string,
    nodeId: string | null,
    status: SchedulingStatus,
    reason?: string
  ): SchedulingDecision {
    return {
      taskId,
      nodeId,
      status,
      reason,
      timestamp: Date.now()
    };
  }

  /**
   * Get all registered nodes (for debugging/inspection)
   */
  getAllNodes(): NodeInfo[] {
    return Array.from(this.nodes.values());
  }

  /**
   * Clear all state (for testing)
   */
  clear(): void {
    this.nodes.clear();
    this.queue.clear();
  }
}
