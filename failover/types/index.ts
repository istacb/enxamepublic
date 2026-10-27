/**
 * Failover Types
 * 
 * Types and enums for the Failover service.
 * Failover is responsible only for detecting and reporting failures.
 */

/**
 * Failure type enumeration
 * Each failure type has clear identification
 */
export enum FailureType {
  /** Service has failed after exhausting restart attempts */
  SERVICE_FAILURE = 'SERVICE_FAILURE',
  
  /** Node is unavailable (heartbeat timeout) */
  NODE_FAILURE = 'NODE_FAILURE',
  
  /** Communication channel lost */
  COMMUNICATION_FAILURE = 'COMMUNICATION_FAILURE',
  
  /** Required capability no longer available */
  CAPABILITY_LOSS = 'CAPABILITY_LOSS',
  
  /** Task was interrupted */
  TASK_FAILURE = 'TASK_FAILURE'
}

/**
 * Failover event status
 */
export enum FailureStatus {
  /** Failure detected */
  DETECTED = 'DETECTED',
  
  /** Event published to Orchestrator */
  PUBLISHED = 'PUBLISHED',
  
  /** Node recovered after failure */
  RECOVERED = 'RECOVERED'
}

/**
 * Recovery policy for tasks
 * Defined by each Task, not by Failover
 */
export enum TaskRecoveryPolicy {
  /** Never retry this task */
  NEVER_RETRY = 'NEVER_RETRY',
  
  /** Safe to retry from beginning */
  SAFE_RETRY = 'SAFE_RETRY',
  
  /** Retry from last checkpoint */
  CHECKPOINT = 'CHECKPOINT'
}

/**
 * Base failure event structure
 */
export interface FailureEventBase {
  /** Unique event identifier */
  id: string;
  
  /** Type of failure */
  type: FailureType;
  
  /** Timestamp of detection */
  timestamp: number;
  
  /** Source of the failure event */
  source: 'ORCHESTRATOR' | 'HEARTBEAT' | 'SERVICE_LOADER';
  
  /** Status of this failure event */
  status: FailureStatus;
}

/**
 * Node-specific failure data
 */
export interface NodeFailureData {
  nodeId: string;
  reason: string;
  lastHeartbeat?: number;
}

/**
 * Service-specific failure data
 */
export interface ServiceFailureData {
  nodeId: string;
  serviceName: string;
  restartAttempts: number;
  error?: string;
}

/**
 * Task-specific failure data
 */
export interface TaskFailureData {
  taskId: string;
  nodeId?: string;
  recoveryPolicy: TaskRecoveryPolicy;
  reason: string;
}

/**
 * Capability loss data
 */
export interface CapabilityLossData {
  nodeId: string;
  capability: string;
  previouslyAvailable: boolean;
}

/**
 * Communication failure data
 */
export interface CommunicationFailureData {
  nodeId?: string;
  channel: string;
  reason: string;
}

/**
 * Union type for all failure data types
 */
export type FailureData = 
  | NodeFailureData
  | ServiceFailureData
  | TaskFailureData
  | CapabilityLossData
  | CommunicationFailureData;

/**
 * Complete failure event with typed data
 */
export interface FailureEvent<T extends FailureData = FailureData> extends FailureEventBase {
  data: T;
}

/**
 * Scheduling decision for failed tasks
 * Returned to Orchestrator, not executed by Failover
 */
export interface TaskSchedulingDecision {
  taskId: string;
  action: 'RETURN_TO_QUEUE' | 'CANCEL' | 'RESCHEDULE';
  maintainPosition: boolean;
  reason: string;
}
