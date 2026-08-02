/**
 * Lifecycle Manager - Manages Node lifecycle states
 * 
 * Implements the ILifecycle interface with the following state machine:
 * Booting → Initializing → Ready → Running → Stopping → Stopped
 *                                              ↓
 *                                           Faulted
 * 
 * This is a core component of the Kernel and must remain stable.
 */

import type { ILifecycle, LifecycleState } from '../interfaces';
import { InvalidStateTransitionError } from '../errors';

/**
 * Valid state transitions map
 */
const VALID_TRANSITIONS: Record<LifecycleState, LifecycleState[]> = {
  [LifecycleState.Booting]: [LifecycleState.Initializing, LifecycleState.Faulted],
  [LifecycleState.Initializing]: [LifecycleState.Ready, LifecycleState.Faulted],
  [LifecycleState.Ready]: [LifecycleState.Running, LifecycleState.Stopping, LifecycleState.Faulted],
  [LifecycleState.Running]: [LifecycleState.Stopping, LifecycleState.Faulted],
  [LifecycleState.Stopping]: [LifecycleState.Stopped, LifecycleState.Faulted],
  [LifecycleState.Stopped]: [], // Terminal state
  [LifecycleState.Faulted]: []  // Terminal state
};

/**
 * LifecycleManager - Concrete implementation of ILifecycle
 */
export class LifecycleManager implements ILifecycle {
  private _currentState: LifecycleState;
  private _startedAt: number;
  private _stateChangeCallbacks: Array<(from: LifecycleState, to: LifecycleState) => void>;

  constructor() {
    this._currentState = LifecycleState.Booting;
    this._startedAt = Date.now();
    this._stateChangeCallbacks = [];
  }

  /**
   * Get current lifecycle state
   */
  get currentState(): LifecycleState {
    return this._currentState;
  }

  /**
   * Get timestamp when lifecycle was initialized
   */
  get startedAt(): number {
    return this._startedAt;
  }

  /**
   * Get current uptime in milliseconds
   */
  getUptime(): number {
    return Date.now() - this._startedAt;
  }

  /**
   * Transition to a new state
   * @param to - Target state
   * @returns true if transition was successful
   * @throws InvalidStateTransitionError if transition is not valid
   */
  transition(to: LifecycleState): boolean {
    const from = this._currentState;
    
    if (!this.canTransition(to)) {
      throw new InvalidStateTransitionError(from, to);
    }

    this._currentState = to;
    
    // Notify all callbacks
    for (const callback of this._stateChangeCallbacks) {
      try {
        callback(from, to);
      } catch (error) {
        // Log but don't propagate callback errors
        console.error(`[Lifecycle] State change callback error:`, error);
      }
    }

    return true;
  }

  /**
   * Check if a state transition is valid
   * @param to - Target state
   * @returns true if transition is valid
   */
  canTransition(to: LifecycleState): boolean {
    const allowedTransitions = VALID_TRANSITIONS[this._currentState];
    return allowedTransitions.includes(to);
  }

  /**
   * Check if currently in a specific state
   * @param state - State to check
   * @returns true if in the specified state
   */
  is(state: LifecycleState): boolean {
    return this._currentState === state;
  }

  /**
   * Subscribe to state changes
   * @param callback - Function to call on state changes
   */
  onChange(callback: (from: LifecycleState, to: LifecycleState) => void): void {
    this._stateChangeCallbacks.push(callback);
  }

  /**
   * Force transition to Faulted state (used for fatal errors)
   */
  fault(): boolean {
    const from = this._currentState;
    if (from === LifecycleState.Stopped || from === LifecycleState.Faulted) {
      return false;
    }
    this._currentState = LifecycleState.Faulted;
    
    for (const callback of this._stateChangeCallbacks) {
      try {
        callback(from, LifecycleState.Faulted);
      } catch (error) {
        console.error(`[Lifecycle] Fault callback error:`, error);
      }
    }
    
    return true;
  }
}
