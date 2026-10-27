/**
 * Service Lifecycle Manager - Manages the lifecycle state of a Service
 */

import type { IServiceLifecycle } from '../interfaces';
import type { ServiceState } from '../types';

/**
 * Valid state transitions for a Service
 */
const VALID_TRANSITIONS: Record<ServiceState, ServiceState[]> = {
  [ServiceState.Initializing]: [ServiceState.Starting, ServiceState.Failed],
  [ServiceState.Starting]: [ServiceState.Running, ServiceState.Failed, ServiceState.Stopped],
  [ServiceState.Running]: [ServiceState.Stopping, ServiceState.Failed, ServiceState.Finished],
  [ServiceState.Stopping]: [ServiceState.Stopped, ServiceState.Failed],
  [ServiceState.Stopped]: [ServiceState.Initializing, ServiceState.Finished],
  [ServiceState.Failed]: [ServiceState.Initializing],
  [ServiceState.Finished]: [],
  [ServiceState.WaitingDependency]: [ServiceState.Initializing, ServiceState.Failed]
};

/**
 * ServiceLifecycle - Concrete implementation of IServiceLifecycle
 */
export class ServiceLifecycle implements IServiceLifecycle {
  private _currentState: ServiceState;
  private _startedAt?: number;
  private _stateChangeCallbacks: Array<(from: ServiceState, to: ServiceState) => void>;

  constructor(initialState: ServiceState = ServiceState.Initializing) {
    this._currentState = initialState;
    this._stateChangeCallbacks = [];
  }

  /**
   * Get current lifecycle state
   */
  get currentState(): ServiceState {
    return this._currentState;
  }

  /**
   * Get timestamp when the service was started
   */
  get startedAt(): number | undefined {
    return this._startedAt;
  }

  /**
   * Get current uptime in milliseconds
   */
  getUptime(): number {
    if (!this._startedAt) {
      return 0;
    }
    return Date.now() - this._startedAt;
  }

  /**
   * Transition to a new state
   * @param to - Target state
   * @returns true if transition was successful
   */
  transition(to: ServiceState): boolean {
    if (!this.canTransition(to)) {
      console.warn(
        `[ServiceLifecycle] Invalid transition from ${this._currentState} to ${to}`
      );
      return false;
    }

    const from = this._currentState;
    this._currentState = to;

    // Set startedAt when transitioning to Running
    if (to === ServiceState.Running) {
      this._startedAt = Date.now();
    }

    // Clear startedAt when transitioning to Stopped or Finished
    if (to === ServiceState.Stopped || to === ServiceState.Finished) {
      this._startedAt = undefined;
    }

    // Notify callbacks
    this._stateChangeCallbacks.forEach(callback => callback(from, to));

    console.log(`[ServiceLifecycle] Transitioned from ${from} to ${to}`);
    return true;
  }

  /**
   * Check if a state transition is valid
   * @param to - Target state
   * @returns true if transition is valid
   */
  canTransition(to: ServiceState): boolean {
    const validTargets = VALID_TRANSITIONS[this._currentState];
    return validTargets?.includes(to) ?? false;
  }

  /**
   * Check if currently in a specific state
   * @param state - State to check
   * @returns true if in the specified state
   */
  is(state: ServiceState): boolean {
    return this._currentState === state;
  }

  /**
   * Subscribe to state changes
   * @param callback - Function to call on state change
   */
  onChange(callback: (from: ServiceState, to: ServiceState) => void): void {
    this._stateChangeCallbacks.push(callback);
  }

  /**
   * Force set state (for testing or recovery scenarios)
   * @param state - New state
   */
  forceSetState(state: ServiceState): void {
    const from = this._currentState;
    this._currentState = state;
    this._stateChangeCallbacks.forEach(callback => callback(from, state));
  }
}
