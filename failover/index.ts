/**
 * Failover Service Implementation
 * 
 * Main Failover service that reports failures to the Orchestrator.
 * Does NOT execute recovery, restart services, or redistribute tasks.
 * Only publishes failure events.
 */

import { IFailover } from './interfaces';
import { IFailureNotifier } from './interfaces';
import {
  FailureEvent,
  NodeFailureData,
  ServiceFailureData,
  TaskFailureData,
  CapabilityLossData,
  CommunicationFailureData
} from './types';
import {
  createNodeFailureEvent,
  createServiceFailureEvent,
  createTaskFailureEvent,
  createCapabilityLossEvent,
  createCommunicationFailureEvent,
  createNodeRecoveryEvent,
  markEventAsPublished
} from './events';
import { createFailureNotifier } from './notifier';

/**
 * Failover service implementation
 */
export class FailoverService implements IFailover {
  private notifier: IFailureNotifier;
  private eventHistory: FailureEvent[] = [];
  private maxHistorySize: number = 1000;

  constructor(notifier?: IFailureNotifier) {
    this.notifier = notifier || createFailureNotifier();
  }

  /**
   * Report a node failure
   * Node is considered unavailable when heartbeats stop within configured limit
   */
  reportNodeFailure(data: NodeFailureData): FailureEvent<NodeFailureData> {
    const event = createNodeFailureEvent(data, 'ORCHESTRATOR');
    return this.publishEvent(event);
  }

  /**
   * Report a service failure
   * Called when Service Loader exhausts all restart attempts
   */
  reportServiceFailure(data: ServiceFailureData): FailureEvent<ServiceFailureData> {
    const event = createServiceFailureEvent(data, 'SERVICE_LOADER');
    return this.publishEvent(event);
  }

  /**
   * Report a task failure
   * Task defines its own recovery policy, Failover only reports the interruption
   */
  reportTaskFailure(data: TaskFailureData): FailureEvent<TaskFailureData> {
    const event = createTaskFailureEvent(data, 'ORCHESTRATOR');
    return this.publishEvent(event);
  }

  /**
   * Report capability loss
   * When a required capability is no longer available on a node
   */
  reportCapabilityLoss(data: CapabilityLossData): FailureEvent<CapabilityLossData> {
    const event = createCapabilityLossEvent(data, 'ORCHESTRATOR');
    return this.publishEvent(event);
  }

  /**
   * Report communication failure
   * When communication channel is lost
   */
  reportCommunicationFailure(
    data: CommunicationFailureData
  ): FailureEvent<CommunicationFailureData> {
    const event = createCommunicationFailureEvent(data, 'ORCHESTRATOR');
    return this.publishEvent(event);
  }

  /**
   * Report node recovery after failure
   * Node must re-execute Discovery process and re-register with Orchestrator
   */
  reportNodeRecovery(nodeId: string): void {
    const event = createNodeRecoveryEvent(nodeId);
    this.publishEvent(event);
  }

  /**
   * Publish event to Orchestrator and store in history
   */
  private publishEvent<T extends NodeFailureData | ServiceFailureData | TaskFailureData | CapabilityLossData | CommunicationFailureData>(
    event: FailureEvent<T>
  ): FailureEvent<T> {
    // Mark as published
    const publishedEvent = markEventAsPublished(event);

    // Publish to Orchestrator via notifier
    this.notifier.publish(publishedEvent).catch(error => {
      console.error('Failed to publish failure event:', error);
    });

    // Store in history (limited size)
    this.eventHistory.push(publishedEvent);
    if (this.eventHistory.length > this.maxHistorySize) {
      this.eventHistory.shift();
    }

    return publishedEvent;
  }

  /**
   * Get recent failure events (for debugging/monitoring)
   */
  getRecentEvents(limit: number = 100): FailureEvent[] {
    const start = Math.max(0, this.eventHistory.length - limit);
    return this.eventHistory.slice(start);
  }

  /**
   * Get event by ID
   */
  getEventById(id: string): FailureEvent | undefined {
    return this.eventHistory.find(event => event.id === id);
  }

  /**
   * Clear event history
   */
  clearHistory(): void {
    this.eventHistory = [];
  }

  /**
   * Set the notifier instance
   */
  setNotifier(notifier: IFailureNotifier): void {
    this.notifier = notifier;
  }

  /**
   * Get current notifier
   */
  getNotifier(): IFailureNotifier {
    return this.notifier;
  }
}

/**
 * Create a new Failover service instance
 */
export function createFailoverService(notifier?: IFailureNotifier): IFailover {
  return new FailoverService(notifier);
}

// Export default instance for convenience
export const failover = createFailoverService();
