/**
 * Execution Context Implementation
 * 
 * Mantém o estado durante a execução de uma Task.
 */

import type { IExecutionContext } from '../interfaces';
import type { ExecutionContext as ExecutionContextType } from '../types';

export class ExecutionContext implements IExecutionContext {
  public readonly taskId: string;
  public readonly payload: Record<string, unknown>;
  public readonly allocatedResources: Set<string>;
  public timeoutMs?: number;
  public attemptCount: number;
  public readonly maxRetries: number;

  constructor(config: ExecutionContextType) {
    this.taskId = config.taskId;
    this.payload = config.payload;
    this.allocatedResources = new Set<string>();
    this.timeoutMs = config.timeoutMs;
    this.attemptCount = config.currentAttempt;
    this.maxRetries = config.maxRetries;
  }

  /**
   * Marca recurso como alocado
   */
  public allocateResource(resourceId: string): void {
    this.allocatedResources.add(resourceId);
  }

  /**
   * Libera recurso alocado
   */
  public releaseResource(resourceId: string): void {
    this.allocatedResources.delete(resourceId);
  }

  /**
   * Libera todos os recursos
   */
  public releaseAllResources(): void {
    this.allocatedResources.clear();
  }

  /**
   * Incrementa contador de tentativas
   */
  public incrementAttempt(): void {
    this.attemptCount++;
  }

  /**
   * Verifica se excedeu máximo de retries
   */
  public hasExceededMaxRetries(): boolean {
    return this.attemptCount >= this.maxRetries;
  }

  /**
   * Converte para formato serializável
   */
  public toJSON(): Record<string, unknown> {
    return {
      taskId: this.taskId,
      payload: this.payload,
      allocatedResources: Array.from(this.allocatedResources),
      timeoutMs: this.timeoutMs,
      attemptCount: this.attemptCount,
      maxRetries: this.maxRetries,
    };
  }
}
