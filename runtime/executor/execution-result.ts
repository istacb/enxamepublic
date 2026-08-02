/**
 * Execution Result Implementation
 * 
 * Representa o resultado final de uma Task.
 */

import type { IExecutionResult } from '../interfaces';
import type { ExecutionResult as ExecutionResultType } from '../types';

export class ExecutionResult implements IExecutionResult {
  public readonly taskId: string;
  public status: 'Success' | 'Failed' | 'Canceled' | 'Timeout';
  public output?: unknown;
  public error?: string;
  public readonly startedAt: number;
  public readonly completedAt: number;
  public readonly attempts: number;

  constructor(config: {
    taskId: string;
    status: 'Success' | 'Failed' | 'Canceled' | 'Timeout';
    output?: unknown;
    error?: string;
    startedAt: number;
    completedAt: number;
    attempts: number;
  }) {
    this.taskId = config.taskId;
    this.status = config.status;
    this.output = config.output;
    this.error = config.error;
    this.startedAt = config.startedAt;
    this.completedAt = config.completedAt;
    this.attempts = config.attempts;
  }

  /**
   * Cria um resultado de sucesso
   */
  public static success(
    taskId: string,
    output: unknown,
    startedAt: number,
    attempts: number
  ): ExecutionResult {
    return new ExecutionResult({
      taskId,
      status: 'Success',
      output,
      startedAt,
      completedAt: Date.now(),
      attempts,
    });
  }

  /**
   * Cria um resultado de falha
   */
  public static failure(
    taskId: string,
    error: string,
    startedAt: number,
    attempts: number
  ): ExecutionResult {
    return new ExecutionResult({
      taskId,
      status: 'Failed',
      error,
      startedAt,
      completedAt: Date.now(),
      attempts,
    });
  }

  /**
   * Cria um resultado de cancelamento
   */
  public static canceled(
    taskId: string,
    startedAt: number,
    attempts: number
  ): ExecutionResult {
    return new ExecutionResult({
      taskId,
      status: 'Canceled',
      startedAt,
      completedAt: Date.now(),
      attempts,
    });
  }

  /**
   * Cria um resultado de timeout
   */
  public static timeout(
    taskId: string,
    startedAt: number,
    attempts: number,
    timeoutMs?: number
  ): ExecutionResult {
    return new ExecutionResult({
      taskId,
      status: 'Timeout',
      error: timeoutMs ? `Task exceeded timeout of ${timeoutMs}ms` : 'Task exceeded timeout',
      startedAt,
      completedAt: Date.now(),
      attempts,
    });
  }

  /**
   * Converte para formato serializável
   */
  public toJSON(): Record<string, unknown> {
    return {
      taskId: this.taskId,
      status: this.status,
      output: this.output,
      error: this.error,
      startedAt: this.startedAt,
      completedAt: this.completedAt,
      attempts: this.attempts,
      duration: this.completedAt - this.startedAt,
    };
  }
}
