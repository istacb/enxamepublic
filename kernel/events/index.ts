/**
 * Event Bus - Internal event bus for the Node
 * 
 * Implements the IEventBus interface.
 * The Event Bus is exclusively internal to the Node.
 * No communication protocol is implemented at this stage.
 */

import type { IEventBus, KernelEvent, EventHandler } from '../interfaces';

/**
 * Internal listener entry
 */
interface ListenerEntry<T = unknown> {
  handler: EventHandler<T>;
  once: boolean;
}

/**
 * EventBus - Concrete implementation of IEventBus
 */
export class EventBus implements IEventBus {
  private _listeners: Map<string, Array<ListenerEntry>>;

  constructor() {
    this._listeners = new Map();
  }

  /**
   * Subscribe to an event type
   * @param eventType - Type of event to subscribe to
   * @param handler - Handler function to call when event is emitted
   */
  on<T>(eventType: string, handler: EventHandler<T>): void {
    if (!this._listeners.has(eventType)) {
      this._listeners.set(eventType, []);
    }
    
    const listeners = this._listeners.get(eventType)!;
    listeners.push({ handler, once: false });
  }

  /**
   * Subscribe to an event type once (auto-unsubscribe after first call)
   * @param eventType - Type of event to subscribe to
   * @param handler - Handler function to call when event is emitted
   */
  once<T>(eventType: string, handler: EventHandler<T>): void {
    if (!this._listeners.has(eventType)) {
      this._listeners.set(eventType, []);
    }
    
    const listeners = this._listeners.get(eventType)!;
    listeners.push({ handler, once: true });
  }

  /**
   * Unsubscribe from an event type
   * @param eventType - Type of event to unsubscribe from
   * @param handler - Handler function to remove
   */
  off<T>(eventType: string, handler: EventHandler<T>): void {
    if (!this._listeners.has(eventType)) {
      return;
    }
    
    const listeners = this._listeners.get(eventType)!;
    const filtered = listeners.filter(entry => entry.handler !== handler);
    this._listeners.set(eventType, filtered);
  }

  /**
   * Emit an event
   * @param eventType - Type of event to emit
   * @param payload - Event payload data
   * @param source - Optional source component identifier
   */
  emit<T>(eventType: string, payload: T, source?: string): void {
    const event: KernelEvent<T> = {
      type: eventType,
      payload,
      timestamp: Date.now(),
      source
    };

    if (!this._listeners.has(eventType)) {
      return;
    }

    const listeners = this._listeners.get(eventType)!;
    
    // Create a copy to avoid issues with modifications during iteration
    const listenersCopy = [...listeners];
    
    for (const entry of listenersCopy) {
      try {
        const result = entry.handler(event);
        
        // Handle promise-based handlers
        if (result instanceof Promise) {
          result.catch(error => {
            console.error(`[EventBus] Async handler error for '${eventType}':`, error);
          });
        }
      } catch (error) {
        console.error(`[EventBus] Handler error for '${eventType}':`, error);
      }
    }

    // Remove 'once' listeners after emission
    const remainingListeners = listeners.filter(entry => !entry.once);
    this._listeners.set(eventType, remainingListeners);
  }

  /**
   * Remove all listeners for an event type
   * @param eventType - Type of event to clear listeners for
   */
  removeAllListeners(eventType: string): void {
    this._listeners.delete(eventType);
  }

  /**
   * Remove all listeners for all event types
   */
  clear(): void {
    this._listeners.clear();
  }

  /**
   * Get listener count for an event type
   * @param eventType - Type of event to count listeners for
   * @returns Number of listeners
   */
  listenerCount(eventType: string): number {
    if (!this._listeners.has(eventType)) {
      return 0;
    }
    return this._listeners.get(eventType)!.length;
  }

  /**
   * Get all registered event types
   * @returns Iterable of event type names
   */
  getEventTypes(): Iterable<string> {
    return this._listeners.keys();
  }
}
