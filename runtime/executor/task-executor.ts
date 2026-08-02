/**
 * Task Executor Implementation
 * 
 * Responsável pela execução efetiva de uma Task.
 */

import type { ITaskExecutor, IExecutionContext, IAgent } from '../interfaces';
import { TaskExecutionError, RecoveryFailedError } from '../errors';

export class TaskExecutor implements ITaskExecutor {
  private readonly maxRetries: number;

  constructor(maxRetries: number = 2) {
    this.maxRetries = maxRetries;
  }

  /**
   * Executa uma Task dentro de um contexto
   * 
   * NOTA: Esta é uma implementação stub.
   * A execução real será implementada em PRs futuras
   * quando os Resources concretos estiverem disponíveis.
   */
  public async execute(
    context: IExecutionContext,
    agent: IAgent
  ): Promise<unknown> {
    try {
      // Delegate execution to the agent
      const result = await agent.execute();
      return result;
    } catch (error) {
      const cause = error instanceof Error ? error : new Error(String(error));
      throw new TaskExecutionError(
        `Task execution failed: ${cause.message}`,
        context.taskId,
        cause
      );
    }
  }

  /**
   * Tenta recuperar de uma falha
   * 
   * Estratégias de recuperação local:
   * - Recriar Agent
   * - Reinicializar contexto
   * - Alterar estratégia de execução
   * - Utilizar outro Resource local compatível
   */
  public async recover(
    context: IExecutionContext,
    error: Error
  ): Promise<boolean> {
    // Verifica se excedeu máximo de retries
    if (context.attemptCount >= this.maxRetries) {
      return false;
    }

    // Incrementa contador de tentativas
    context.incrementAttempt();

    // Libera recursos atuais para tentar novamente com estado limpo
    context.releaseAllResources();

    // Log de recuperação (pode ser removido em produção)
    console.log(
      `[TaskExecutor] Attempting recovery for task ${context.taskId}, attempt ${context.attemptCount}/${this.maxRetries}`
    );

    // Recuperação bem-sucedida (permite nova tentativa)
    return true;
  }
}
