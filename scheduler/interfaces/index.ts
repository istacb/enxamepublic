/**
 * Scheduler Interfaces - Decoupled interfaces for the Scheduler
 *
 * These interfaces define the contracts used by the Scheduler component.
 * All implementations must adhere to these interfaces to maintain decoupling.
 */

import {
  Task,
  NodeInfo,
  Capability,
  SchedulingDecision,
  QueueStatus
} from '../types';

/**
 * IScheduler - Main scheduler interface
 *
 * The Scheduler is responsible for selecting the best Node to execute a Task.
 * It never executes Tasks or communicates directly with Nodes.
 */
export interface IScheduler {
  /**
   * Schedule a task for execution
   * @param task - The task to schedule
   * @returns A scheduling decision
   */
  scheduleTask(task: Task): Promise<SchedulingDecision>;

  /**
   * Handle node registration event
   * @param node - The newly registered node information
   */
  onNodeRegistered(node: NodeInfo): void;

  /**
   * Handle node removal event
   * @param nodeId - The ID of the removed node
   */
  onNodeRemoved(nodeId: string): void;

  /**
   * Handle runtime availability event
   * @param nodeId - The ID of the node with available runtime
   */
  onRuntimeAvailable(nodeId: string): void;

  /**
   * Handle capability change event
   * @param nodeId - The ID of the node with changed capabilities
   * @param capabilities - The new capabilities
   */
  onCapabilityChanged(nodeId: string, capabilities: Capability[]): void;

  /**
   * Get current queue status
   * @returns Current queue status information
   */
  getQueueStatus(): QueueStatus;
}

/**
 * ISchedulingPolicy - Policy interface for node selection
 *
 * Allows different scheduling strategies without altering core logic.
 */
export interface ISchedulingPolicy {
  /**
   * Policy name
   */
  name: string;

  /**
   * Select the best node from candidates for a given task
   * @param candidates - List of compatible and available nodes
   * @param task - The task being scheduled
   * @returns Selected node or null if none suitable
   */
  selectNode(candidates: NodeInfo[], task: Task): NodeInfo | null;

  /**
   * Reorder queue according to policy
   * @param queue - Current task queue
   * @returns Reordered task queue
   */
  reorderQueue(queue: Task[]): Task[];
}

/**
 * ITaskQueue - Task queue interface
 *
 * Manages the queue of tasks waiting to be scheduled.
 */
export interface ITaskQueue {
  /**
   * Add a task to the queue
   * @param task - The task to enqueue
   */
  enqueue(task: Task): void;

  /**
   * Remove and return the next task from the queue
   * @returns The next task or null if queue is empty
   */
  dequeue(): Task | null;

  /**
   * Peek at the next task without removing it
   * @returns The next task or null if queue is empty
   */
  peek(): Task | null;

  /**
   * Get the number of tasks in the queue
   * @returns Queue size
   */
  size(): number;

  /**
   * Check if the queue is empty
   * @returns True if queue is empty
   */
  isEmpty(): boolean;

  /**
   * Filter tasks by required capabilities
   * @param capabilities - Required capabilities to match
   * @returns Tasks that can run with given capabilities
   */
  filterByCapability(capabilities: Capability[]): Task[];
}

/**
 * ISchedulingDecision - Scheduling decision result
 *
 * Represents the outcome of a scheduling attempt.
 */
export interface ISchedulingDecision {
  /**
   * Task ID being scheduled
   */
  taskId: string;

  /**
   * Selected Node ID (null if not scheduled)
   */
  nodeId: string | null;

  /**
   * Status of the scheduling decision
   */
  status: 'scheduled' | 'queued' | 'rejected';

  /**
   * Optional reason for rejection or queuing
   */
  reason?: string;

  /**
   * Timestamp of decision
   */
  timestamp: number;
}

/**
 * INodeSelection - Node selection utilities interface
 *
 * Provides filtering and selection operations for nodes.
 */
export interface INodeSelection {
  /**
   * Filter nodes by required capabilities
   * @param nodes - List of nodes to filter
   * @param required - Required capabilities
   * @returns Nodes that have all required capabilities
   */
  filterByCapability(nodes: NodeInfo[], required: Capability[]): NodeInfo[];

  /**
   * Filter nodes by available capacity
   * @param nodes - List of nodes to filter
   * @returns Nodes that have capacity for new tasks
   */
  filterByCapacity(nodes: NodeInfo[]): NodeInfo[];

  /**
   * Select the first node from a list
   * @param nodes - List of nodes
   * @returns First node or null if list is empty
   */
  selectFirst(nodes: NodeInfo[]): NodeInfo | null;
}

/**
 * ICapabilityMatcher - Capability matching interface
 *
 * Handles capability matching logic between tasks and nodes.
 */
export interface ICapabilityMatcher {
  /**
   * Check if node capabilities match task requirements
   * @param nodeCapabilities - Capabilities available on the node
   * @param taskRequirements - Capabilities required by the task
   * @returns True if all requirements are met
   */
  matches(nodeCapabilities: Capability[], taskRequirements: Capability[]): boolean;

  /**
   * Get missing capabilities
   * @param nodeCapabilities - Capabilities available on the node
   * @param taskRequirements - Capabilities required by the task
   * @returns List of missing capabilities
   */
  missingCapabilities(
    nodeCapabilities: Capability[],
    taskRequirements: Capability[]
  ): Capability[];
}
