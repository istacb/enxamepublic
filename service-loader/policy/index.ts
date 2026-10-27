/**
 * Restart Policy - Manages restart attempts for Services
 */

import type { IRestartPolicy } from '../interfaces';
import type { RestartPolicyConfig } from '../types';

/**
 * RestartPolicy - Concrete implementation of IRestartPolicy
 */
export class RestartPolicy implements IRestartPolicy {
  private _enabled: boolean;
  private _maxAttempts: number;
  private _currentAttempt: number;
  private _delayMs: number;

  constructor(config: RestartPolicyConfig) {
    this._enabled = config.enabled;
    this._maxAttempts = config.maxAttempts;
    this._currentAttempt = 0;
    this._delayMs = config.delayMs;
  }

  /**
   * Whether restart is enabled
   */
  get enabled(): boolean {
    return this._enabled;
  }

  /**
   * Maximum number of restart attempts
   */
  get maxAttempts(): number {
    return this._maxAttempts;
  }

  /**
   * Current attempt number
   */
  get currentAttempt(): number {
    return this._currentAttempt;
  }

  /**
   * Delay between restart attempts in milliseconds
   */
  get delayMs(): number {
    return this._delayMs;
  }

  /**
   * Check if retry is allowed
   * @returns true if retry is allowed
   */
  canRetry(): boolean {
    if (!this._enabled) {
      return false;
    }
    return this._currentAttempt < this._maxAttempts;
  }

  /**
   * Increment attempt counter
   */
  incrementAttempt(): void {
    if (this._currentAttempt < this._maxAttempts) {
      this._currentAttempt++;
      console.log(
        `[RestartPolicy] Attempt ${this._currentAttempt}/${this._maxAttempts}`
      );
    }
  }

  /**
   * Reset attempt counter
   */
  reset(): void {
    this._currentAttempt = 0;
    console.log('[RestartPolicy] Reset attempt counter');
  }

  /**
   * Get remaining attempts
   * @returns Number of remaining attempts
   */
  getRemainingAttempts(): number {
    return Math.max(0, this._maxAttempts - this._currentAttempt);
  }

  /**
   * Get delay for next attempt
   * @returns Delay in milliseconds
   */
  getNextDelay(): number {
    return this._delayMs;
  }
}
