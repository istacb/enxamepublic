/**
 * Failure Event Implementation
 * 
 * Concrete implementation of failure events.
 * Each event has unique identification and timestamp.
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
  TaskRecoveryPolicy,
  TaskSchedulingDecision
} from '../types';

/**
 * Generate unique event ID
 */
function generateEventId(): string {
  return `fail_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Create a node failure event
 */
export function createNodeFailureEvent(
  data: NodeFailureData,
  source: 'ORCHESTRATOR' | 'HEARTBEAT' | 'SERVICE_LOADER'
): FailureEvent<NodeFailureData> {
  return {
    id: generateEventId(),
    type: FailureType.NODE_FAILURE,
    timestamp: Date.now(),
    source,
    status: FailureStatus.DETECTED,
    data
  };
}

/**
 * Create a service failure event
 */
export function createServiceFailureEvent(
  data: ServiceFailureData,
  source: 'ORCHESTRATOR' | 'HEARTBEAT' | 'SERVICE_LOADER'
): FailureEvent<ServiceFailureData> {
  return {
    id: generateEventId(),
    type: FailureType.SERVICE_FAILURE,
    timestamp: Date.now(),
    source,
    status: FailureStatus.DETECTED,
    data
  };
}

/**
 * Create a task failure event
 */
export function createTaskFailureEvent(
  data: TaskFailureData,
  source: 'ORCHESTRATOR' | 'HEARTBEAT' | 'SERVICE_LOADER'
): FailureEvent<TaskFailureData> {
  return {
    id: generateEventId(),
    type: FailureType.TASK_FAILURE,
    timestamp: Date.now(),
    source,
    status: FailureStatus.DETECTED,
    data
  };
}

/**
 * Create a capability loss event
 */
export function createCapabilityLossEvent(
  data: CapabilityLossData,
  source: 'ORCHESTRATOR' | 'HEARTBEAT' | 'SERVICE_LOADER'
): FailureEvent<CapabilityLossData> {
  return {
    id: generateEventId(),
    type: FailureType.CAPABILITY_LOSS,
    timestamp: Date.now(),
    source,
    status: FailureStatus.DETECTED,
    data
  };
}

/**
 * Create a communication failure event
 */
export function createCommunicationFailureEvent(
  data: CommunicationFailureData,
  source: 'ORCHESTRATOR' | 'HEARTBEAT' | 'SERVICE_LOADER'
): FailureEvent<CommunicationFailureData> {
  return {
    id: generateEventId(),
    type: FailureType.COMMUNICATION_FAILURE,
    timestamp: Date.now(),
    source,
    status: FailureStatus.DETECTED,
    data
  };
}

/**
 * Mark event as published
 */
export function markEventAsPublished<T extends NodeFailureData | ServiceFailureData | TaskFailureData | CapabilityLossData | CommunicationFailureData>(
  event: FailureEvent<T>
): FailureEvent<T> {
  return {
    ...event,
    status: FailureStatus.PUBLISHED
  };
}

/**
 * Create node recovery event (special case - marks recovery, not failure)
 */
export function createNodeRecoveryEvent(
  nodeId: string
): FailureEvent<NodeFailureData> {
  return {
    id: generateEventId(),
    type: FailureType.NODE_FAILURE,
    timestamp: Date.now(),
    source: 'ORCHESTRATOR',
    status: FailureStatus.RECOVERED,
    data: {
      nodeId,
      reason: 'Node recovered and re-registered'
    }
  };
}

/**
 * Get scheduling decision for a failed task
 * Failover does not execute this decision, only suggests it
 */
export function getTaskSchedulingDecision(
  taskId: string,
  recoveryPolicy: TaskRecoveryPolicy,
  reason: string
): TaskSchedulingDecision {
  let action: 'RETURN_TO_QUEUE' | 'CANCEL' | 'RESCHEDULE';

  switch (recoveryPolicy) {
    case TaskRecoveryPolicy.NEVER_RETRY:
      action = 'CANCEL';
      break;
    case TaskRecoveryPolicy.SAFE_RETRY:
    case TaskRecoveryPolicy.CHECKPOINT:
      action = 'RETURN_TO_QUEUE';
      break;
    default:
      action = 'RETURN_TO_QUEUE';
  }

  return {
    taskId,
    action,
    maintainPosition: action === 'RETURN_TO_QUEUE',
    reason
  };
}
