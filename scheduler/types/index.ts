/**
 * Scheduler Types - Type definitions for the Scheduler
 *
 * These types define the core abstractions used throughout the Scheduler.
 * The Scheduler is completely decoupled and only works with Tasks, Nodes, and Capabilities.
 * It knows nothing about Missions, Workflows, Agents, or AI.
 */

/**
 * Scheduling status enumeration
 */
export enum SchedulingStatus {
  /** Task was successfully scheduled to a Node */
  Scheduled = 'scheduled',
  /** Task was queued waiting for resources */
  Queued = 'queued',
  /** Task was rejected (invalid or impossible to schedule) */
  Rejected = 'rejected'
}

/**
 * Queue policy enumeration
 */
export enum QueuePolicy {
  /** First In, First Out */
  FIFO = 'fifo'
  // Future policies can be added here without altering core logic
  // PRIORITY = 'priority',
  // LIFO = 'lifo',
  // SHORTEST_JOB_FIRST = 'sjf'
}

/**
 * Task definition
 */
export interface Task {
  /** Unique task identifier */
  id: string;
  /** Task name/type */
  name: string;
  /** Required capabilities */
  requiredCapabilities: Capability[];
  /** Resource requirements */
  resources?: ResourceRequirements;
  /** Timestamp when task was created */
  createdAt: number;
  /** Optional metadata */
  metadata?: Record<string, unknown>;
}

/**
 * Capability definition
 */
export interface Capability {
  /** Capability name/identifier */
  name: string;
  /** Capability version */
  version?: string;
  /** Additional capability attributes */
  attributes?: Record<string, unknown>;
}

/**
 * Resource requirements for a Task
 */
export interface ResourceRequirements {
  /** Whether GPU is required */
  gpu?: boolean;
  /** Memory requirement in MB */
  memoryMB?: number;
  /** CPU cores required */
  cpuCores?: number;
  /** Whether exclusive access is needed */
  exclusive?: boolean;
}

/**
 * Node information available to Scheduler
 */
export interface NodeInfo {
  /** Unique node identifier */
  id: string;
  /** Node name */
  name: string;
  /** Available capabilities on this Node */
  capabilities: Capability[];
  /** Current capacity status */
  capacity: CapacityInfo;
  /** Whether node is currently available */
  available: boolean;
  /** Optional metadata */
  metadata?: Record<string, unknown>;
}

/**
 * Capacity information for a Node
 */
export interface CapacityInfo {
  /** Whether node has capacity for new tasks */
  hasCapacity: boolean;
  /** Current load percentage (0-100) */
  loadPercentage?: number;
  /** Number of running tasks */
  runningTasks?: number;
  /** Maximum concurrent tasks */
  maxConcurrentTasks?: number;
}

/**
 * Scheduling decision result
 */
export interface SchedulingDecision {
  /** Task ID being scheduled */
  taskId: string;
  /** Selected Node ID (null if not scheduled) */
  nodeId: string | null;
  /** Status of the scheduling decision */
  status: SchedulingStatus;
  /** Optional reason for rejection or queuing */
  reason?: string;
  /** Timestamp of decision */
  timestamp: number;
}

/**
 * Queue status information
 */
export interface QueueStatus {
  /** Number of tasks in queue */
  size: number;
  /** Whether queue is empty */
  isEmpty: boolean;
  /** Policy being used */
  policy: QueuePolicy;
}

/**
 * Default configuration
 */
export interface SchedulerConfig {
  /** Queue policy to use */
  queuePolicy: QueuePolicy;
  /** Enable debug logging */
  debug?: boolean;
}

/**
 * Default scheduler configuration
 */
export const DEFAULT_SCHEDULER_CONFIG: SchedulerConfig = {
  queuePolicy: QueuePolicy.FIFO,
  debug: false
};
