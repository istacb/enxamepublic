/**
 * Failover Interfaces
 * 
 * Decoupled interfaces for the Failover service.
 * Failover only reports failures, never executes recovery.
 */

import {
  FailureType,
  FailureStatus,
  FailureEvent,
  NodeFailureData,
  ServiceFailureData,
  TaskFailureData,
  CapabilityLossData,
  CommunicationFailureData,
  TaskSchedulingDecision
} from './types';

/**
 * Main Failover service interface
 * Responsible only for publishing failure events
 */
export interface IFailover {
  /**
   * Report a node failure
   * @param data - Node failure details
   * @returns Published failure event
   */
  reportNodeFailure(data: NodeFailureData): FailureEvent<NodeFailureData>;

  /**
   * Report a service failure
   * @param data - Service failure details
   * @returns Published failure event
   */
  reportServiceFailure(data: ServiceFailureData): FailureEvent<ServiceFailureData>;

  /**
   * Report a task failure
   * @param data - Task failure details
   * @returns Published failure event
   */
  reportTaskFailure(data: TaskFailureData): FailureEvent<TaskFailureData>;

  /**
   * Report capability loss
   * @param data - Capability loss details
   * @returns Published failure event
   */
  reportCapabilityLoss(data: CapabilityLossData): FailureEvent<CapabilityLossData>;

  /**
   * Report communication failure
   * @param data - Communication failure details
   * @returns Published failure event
   */
  reportCommunicationFailure(
    data: CommunicationFailureData
  ): FailureEvent<CommunicationFailureData>;

  /**
   * Report node recovery after failure
   * @param nodeId - ID of recovered node
   */
  reportNodeRecovery(nodeId: string): void;
}

/**
 * Failure event interface
 * Each event has unique identification and timestamp
 */
export interface IFailureEvent {
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

  /** Event payload data */
  data: unknown;
}

/**
 * Failure type interface
 */
export interface IFailureType {
  /** Get all failure types */
  getAllTypes(): FailureType[];

  /** Check if type is valid */
  isValid(type: string): boolean;
}

/**
 * Failure notifier interface
 * Publishes events to Orchestrator via official protocol
 */
export interface IFailureNotifier {
  /**
   * Publish failure event to Orchestrator
   * @param event - Failure event to publish
   * @returns True if published successfully
   */
  publish(event: IFailureEvent): Promise<boolean>;

  /**
   * Subscribe to failure events
   * @param callback - Function to call on event
   */
  subscribe(callback: (event: IFailureEvent) => void): void;
}

/**
 * Node failure interface
 */
export interface INodeFailure {
  /** Node identifier */
  nodeId: string;

  /** Reason for failure */
  reason: string;

  /** Last heartbeat timestamp (if available) */
  lastHeartbeat?: number;

  /** Convert to failure event */
  toEvent(source: 'ORCHESTRATOR' | 'HEARTBEAT' | 'SERVICE_LOADER'): FailureEvent<NodeFailureData>;
}

/**
 * Service failure interface
 */
export interface IServiceFailure {
  /** Node identifier */
  nodeId: string;

  /** Service name */
  serviceName: string;

  /** Number of restart attempts before failure */
  restartAttempts: number;

  /** Error message (optional) */
  error?: string;

  /** Convert to failure event */
  toEvent(source: 'ORCHESTRATOR' | 'HEARTBEAT' | 'SERVICE_LOADER'): FailureEvent<ServiceFailureData>;
}

/**
 * Task failure interface
 */
export interface ITaskFailure {
  /** Task identifier */
  taskId: string;

  /** Node identifier (optional) */
  nodeId?: string;

  /** Recovery policy defined by task */
  recoveryPolicy: 'NEVER_RETRY' | 'SAFE_RETRY' | 'CHECKPOINT';

  /** Reason for failure */
  reason: string;

  /** Convert to failure event */
  toEvent(source: 'ORCHESTRATOR' | 'HEARTBEAT' | 'SERVICE_LOADER'): FailureEvent<TaskFailureData>;

  /** Get scheduling decision for this task */
  getSchedulingDecision(): TaskSchedulingDecision;
}

/**
 * Event listener callback type
 */
export type FailureEventListener = (event: IFailureEvent) => void;

/**
 * Event subscription handle
 */
export interface EventSubscription {
  /** Unsubscribe from events */
  unsubscribe(): void;
}
