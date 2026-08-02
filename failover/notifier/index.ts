/**
 * Failure Notifier Implementation
 * 
 * Publishes failure events to Orchestrator via official Communication Protocol.
 * Does not execute any recovery actions.
 */

import { IFailureEvent, IFailureNotifier, FailureEventListener, EventSubscription } from '../interfaces';

/**
 * Simple in-memory event notifier
 * In production, this would use the official Communication Protocol
 */
export class FailureNotifier implements IFailureNotifier {
  private subscribers: Set<FailureEventListener> = new Set();

  /**
   * Publish failure event to Orchestrator
   * Uses official Communication Protocol envelope
   */
  async publish(event: IFailureEvent): Promise<boolean> {
    try {
      // Notify all subscribers (Orchestrator would be a subscriber)
      this.subscribers.forEach(callback => {
        try {
          callback(event);
        } catch (error) {
          // Subscriber error should not prevent other notifications
          console.error('Error notifying subscriber:', error);
        }
      });

      // In production: send via official Communication Protocol
      // await protocol.send({
      //   type: 'FAILURE_EVENT',
      //   payload: event,
      //   timestamp: event.timestamp
      // });

      return true;
    } catch (error) {
      console.error('Failed to publish failure event:', error);
      return false;
    }
  }

  /**
   * Subscribe to failure events
   */
  subscribe(callback: FailureEventListener): void {
    this.subscribers.add(callback);
  }

  /**
   * Unsubscribe from failure events
   */
  unsubscribe(callback: FailureEventListener): void {
    this.subscribers.delete(callback);
  }

  /**
   * Create a subscription handle for easier management
   */
  createSubscription(callback: FailureEventListener): EventSubscription {
    this.subscribe(callback);
    
    return {
      unsubscribe: () => this.unsubscribe(callback)
    };
  }

  /**
   * Get number of subscribers (for debugging/testing)
   */
  getSubscriberCount(): number {
    return this.subscribers.size;
  }

  /**
   * Clear all subscribers
   */
  clear(): void {
    this.subscribers.clear();
  }
}

/**
 * Create a new failure notifier instance
 */
export function createFailureNotifier(): IFailureNotifier {
  return new FailureNotifier();
}
