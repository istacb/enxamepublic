/**
 * Capability Registry - Manages registered Capabilities
 * 
 * Implements the ICapabilityRegistry interface.
 * The Capability Registry is responsible for registering
 * capabilities offered by the Node. Capabilities are dynamic
 * and can appear or disappear during execution.
 * 
 * Examples: CPU, GPU, Storage, Ollama, Whisper, Internet
 */

import type { ICapabilityRegistry, Capability } from '../interfaces';

/**
 * CapabilityRegistry - Concrete implementation of ICapabilityRegistry
 */
export class CapabilityRegistry implements ICapabilityRegistry {
  private _capabilities: Map<string, Capability>;

  constructor() {
    this._capabilities = new Map();
  }

  /**
   * Register a capability
   * @param capability - Capability to register
   * @returns true if registration was successful
   */
  register(capability: Capability): boolean {
    if (this._capabilities.has(capability.id)) {
      // Update existing capability
      const existing = this._capabilities.get(capability)!;
      existing.available = capability.available;
      existing.metadata = capability.metadata;
      existing.lastUpdated = Date.now();
      return false; // Not a new registration
    }

    this._capabilities.set(capability.id, {
      ...capability,
      registeredAt: Date.now()
    });
    
    return true;
  }

  /**
   * Unregister a capability
   * @param capabilityId - ID of capability to unregister
   * @returns true if capability was unregistered
   */
  unregister(capabilityId: string): boolean {
    return this._capabilities.delete(capabilityId);
  }

  /**
   * Update capability availability
   * @param capabilityId - ID of capability to update
   * @param available - New availability status
   * @returns true if capability was updated
   */
  setAvailability(capabilityId: string, available: boolean): boolean {
    const capability = this._capabilities.get(capabilityId);
    
    if (!capability) {
      return false;
    }

    capability.available = available;
    capability.lastUpdated = Date.now();
    return true;
  }

  /**
   * Get a capability by ID
   * @param capabilityId - Capability identifier
   * @returns Capability instance or undefined
   */
  get(capabilityId: string): Capability | undefined {
    return this._capabilities.get(capabilityId);
  }

  /**
   * Get all registered capabilities
   * @returns Iterable of capabilities
   */
  getAll(): Iterable<Capability> {
    return this._capabilities.values();
  }

  /**
   * Get only available capabilities
   * @returns Iterable of available capabilities
   */
  *getAvailable(): Iterable<Capability> {
    for (const capability of this._capabilities.values()) {
      if (capability.available) {
        yield capability;
      }
    }
  }

  /**
   * Get capabilities by type
   * @param type - Capability type to filter by
   * @returns Iterable of matching capabilities
   */
  *getByType(type: string): Iterable<Capability> {
    for (const capability of this._capabilities.values()) {
      if (capability.type === type) {
        yield capability;
      }
    }
  }

  /**
   * Check if a capability is registered
   * @param capabilityId - Capability identifier
   * @returns true if capability is registered
   */
  has(capabilityId: string): boolean {
    return this._capabilities.has(capabilityId);
  }

  /**
   * Get count of registered capabilities
   * @returns Number of registered capabilities
   */
  count(): number {
    return this._capabilities.size;
  }

  /**
   * Get count of available capabilities
   * @returns Number of available capabilities
   */
  availableCount(): number {
    let count = 0;
    for (const capability of this._capabilities.values()) {
      if (capability.available) {
        count++;
      }
    }
    return count;
  }
}
