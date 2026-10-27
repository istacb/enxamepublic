/**
 * Runtime Service Implementation
 * 
 * Serviço permanente responsável por transformar Tasks em resultados.
 */

import type { IRuntime, IAgent, IExecutionContext, IResourceAllocator } from '../interfaces';
import type {
  RuntimeState,
  RuntimeConfig,
  RuntimeStatus,
  RequiredCapability,
  ExecutionContext as ExecutionContextType,
} from '../types';
import { Agent } from '../agent';
import { ExecutionContext, ExecutionResult, TaskExecutor } from '../executor';
import { ResourceAllocator } from '../allocator';
import {
  RuntimeNotInitializedError,
  RuntimeAlreadyInitializedError,
  TaskReceiveError,
  TaskValidationError,
  CapacityExceededError,
  CapabilityNotAvailableError,
  AgentCreationError,
  TaskExecutionError,
  RecoveryFailedError,
  TaskCanceledError,
  TaskTimeoutError,
} from '../errors';

export class Runtime implements IRuntime {
  private state: RuntimeState;
  private config: RuntimeConfig;
  private allocator: IResourceAllocator;
  private executor: TaskExecutor;
  private activeTasks: Map<string, { agent: IAgent; context: IExecutionContext }>;
  private initialized: boolean;

  constructor(config?: Partial<RuntimeConfig>) {
    this.state = 'Idle';
    this.initialized = false;
    
    this.config = {
      maxRetries: config?.maxRetries ?? 2,
      defaultTimeoutMs: config?.defaultTimeoutMs ?? 30000,
      maxConcurrentTasks: config?.maxConcurrentTasks ?? 4,
    };

    this.allocator = new ResourceAllocator(this.config.maxConcurrentTasks);
    this.executor = new TaskExecutor(this.config.maxRetries);
    this.activeTasks = new Map();
  }

  /**
   * Inicializa o Runtime
   */
  public async initialize(): Promise<void> {
    if (this.initialized) {
      throw new RuntimeAlreadyInitializedError();
    }

    this.state = 'Receiving';
    this.initialized = true;
    this.state = 'Idle';

    console.log('[Runtime] Initialized successfully');
  }

  /**
   * Recebe uma Task para execução
   */
  public async receiveTask(
    taskId: string,
    payload: Record<string, unknown>,
    requiredCapabilities?: RequiredCapability[]
  ): Promise<void> {
    if (!this.initialized) {
      throw new RuntimeNotInitializedError();
    }

    this.state = 'Receiving';

    try {
      // Valida Task
      await this.validateTask(taskId, payload, requiredCapabilities);

      this.state = 'Validating';

      // Verifica capacidade
      if (!this.hasAvailableCapacity()) {
        throw new CapacityExceededError(
          'Runtime capacity exceeded',
          this.activeTasks.size,
          this.config.maxConcurrentTasks
        );
      }

      // Verifica capabilities
      if (requiredCapabilities && requiredCapabilities.length > 0) {
        if (!this.allocator.checkAvailability(requiredCapabilities)) {
          throw new CapabilityNotAvailableError(
            'Required capabilities not available',
            requiredCapabilities[0].type
          );
        }
      }

      this.state = 'CreatingAgent';

      // Cria Agent efêmero
      const agent = await this.createAgent(taskId);

      // Aloca recursos
      const resourceIds = await this.allocator.allocate(
        requiredCapabilities || [],
        taskId
      );

      // Cria contexto de execução
      const context = this.createExecutionContext(
        taskId,
        payload,
        resourceIds,
        requiredCapabilities
      );

      // Inicializa Agent
      await agent.initialize(context);

      // Registra Task ativa
      this.activeTasks.set(taskId, { agent, context });

      this.state = 'Running';

      // Executa Task assincronamente
      this.executeTask(taskId, agent, context).catch((error) => {
        console.error(`[Runtime] Task ${taskId} failed:`, error);
      });

    } catch (error) {
      this.state = 'Failed';
      throw error instanceof TaskReceiveError
        ? error
        : new TaskReceiveError(
            `Failed to receive task: ${error instanceof Error ? error.message : String(error)}`,
            taskId
          );
    } finally {
      if (this.state === 'Failed') {
        // Mantém estado Failed
      } else {
        this.state = 'Running';
      }
    }
  }

  /**
   * Cancela uma Task em execução
   */
  public async cancelTask(taskId: string): Promise<void> {
    const taskData = this.activeTasks.get(taskId);

    if (!taskData) {
      // Task não encontrada, pode já ter sido concluída
      return;
    }

    const { agent, context } = taskData;

    try {
      // Interrompe execução imediatamente
      this.state = 'Canceled';

      // Libera recursos
      await this.allocator.releaseAllByTask(taskId);
      context.releaseAllResources();

      // Destrói Agent
      await agent.destroy();

      // Remove da lista de ativas
      this.activeTasks.delete(taskId);

      console.log(`[Runtime] Task ${taskId} canceled successfully`);
    } catch (error) {
      throw new TaskCanceledError(
        `Failed to cancel task: ${error instanceof Error ? error.message : String(error)}`,
        taskId
      );
    } finally {
      // Retorna ao estado Idle se não há mais tasks
      if (this.activeTasks.size === 0) {
        this.state = 'Idle';
      } else {
        this.state = 'Running';
      }
    }
  }

  /**
   * Obtém status atual do Runtime
   */
  public getStatus(): RuntimeStatus {
    return {
      state: this.state,
      activeTasks: this.activeTasks.size,
      maxCapacity: this.config.maxConcurrentTasks,
      healthy: this.isHealthy(),
      lastHeartbeat: Date.now(),
    };
  }

  /**
   * Verifica se o Runtime está saudável
   */
  public isHealthy(): boolean {
    return (
      this.initialized &&
      this.state !== 'Failed' &&
      this.state !== 'Faulted'
    );
  }

  /**
   * Finaliza o Runtime
   */
  public async shutdown(): Promise<void> {
    console.log('[Runtime] Shutting down...');

    // Cancela todas as tasks ativas
    const taskIds = Array.from(this.activeTasks.keys());
    for (const taskId of taskIds) {
      try {
        await this.cancelTask(taskId);
      } catch (error) {
        console.error(`[Runtime] Error canceling task ${taskId} during shutdown:`, error);
      }
    }

    this.initialized = false;
    this.state = 'Idle';

    console.log('[Runtime] Shutdown complete');
  }

  /**
   * Valida uma Task recebida
   */
  private async validateTask(
    taskId: string,
    payload: Record<string, unknown>,
    requiredCapabilities?: RequiredCapability[]
  ): Promise<void> {
    // Validação básica
    if (!taskId || typeof taskId !== 'string') {
      throw new TaskValidationError('Invalid task ID', taskId, 'taskId is required');
    }

    if (!payload || typeof payload !== 'object') {
      throw new TaskValidationError('Invalid payload', taskId, 'payload must be an object');
    }

    // Validação de capabilities (se necessário)
    if (requiredCapabilities) {
      for (const cap of requiredCapabilities) {
        if (!cap.type || typeof cap.type !== 'string') {
          throw new TaskValidationError(
            'Invalid capability',
            taskId,
            'capability type is required'
          );
        }
      }
    }
  }

  /**
   * Cria um Agent efêmero
   */
  private async createAgent(taskId: string): Promise<IAgent> {
    try {
      const agent = new Agent(taskId);
      return agent;
    } catch (error) {
      throw new AgentCreationError(
        `Failed to create agent: ${error instanceof Error ? error.message : String(error)}`,
        taskId
      );
    }
  }

  /**
   * Cria contexto de execução
   */
  private createExecutionContext(
    taskId: string,
    payload: Record<string, unknown>,
    resourceIds: string[],
    requiredCapabilities?: RequiredCapability[]
  ): IExecutionContext {
    const config: ExecutionContextType = {
      taskId,
      payload,
      allocatedResources: resourceIds,
      createdAt: Date.now(),
      timeoutMs: this.config.defaultTimeoutMs,
      maxRetries: this.config.maxRetries,
      currentAttempt: 0,
    };

    return new ExecutionContext(config);
  }

  /**
   * Executa uma Task com tratamento de erros e retries
   */
  private async executeTask(
    taskId: string,
    agent: IAgent,
    context: IExecutionContext
  ): Promise<void> {
    const startedAt = Date.now();
    let result: ExecutionResult | null = null;

    try {
      // Setup timeout
      const timeoutPromise = new Promise<never>((_, reject) => {
        if (context.timeoutMs) {
          setTimeout(() => {
            reject(new TaskTimeoutError('Task execution timeout', taskId, context.timeoutMs));
          }, context.timeoutMs);
        }
      });

      // Executa com timeout
      const output = await Promise.race([
        this.executor.execute(context, agent),
        timeoutPromise,
      ]);

      // Sucesso
      result = ExecutionResult.success(taskId, output, startedAt, context.attemptCount);
      this.state = 'Completed';

    } catch (error) {
      // Verifica se foi cancelamento
      if (error instanceof TaskCanceledError) {
        result = ExecutionResult.canceled(taskId, startedAt, context.attemptCount);
        this.state = 'Canceled';
      } else if (error instanceof TaskTimeoutError) {
        result = ExecutionResult.timeout(
          taskId,
          startedAt,
          context.attemptCount,
          context.timeoutMs
        );
        this.state = 'Failed';
      } else {
        // Tenta recuperação local
        const canRecover = await this.executor.recover(
          context,
          error instanceof Error ? error : new Error(String(error))
        );

        if (canRecover && !context.hasExceededMaxRetries()) {
          // Retry
          this.state = 'Retrying';
          await this.executeTask(taskId, agent, context);
          return;
        } else {
          // Falha definitiva
          result = ExecutionResult.failure(
            taskId,
            error instanceof Error ? error.message : String(error),
            startedAt,
            context.attemptCount
          );
          this.state = 'Failed';
        }
      }
    } finally {
      // Cleanup: destrói Agent e libera recursos
      await this.cleanupTask(taskId, agent, context);

      // Em implementação real, aqui seria enviado o resultado ao Orchestrator
      if (result) {
        console.log(`[Runtime] Task ${taskId} completed with status: ${result.status}`);
      }
    }
  }

  /**
   * Limpa recursos de uma Task concluída
   * Zero estado residual
   */
  private async cleanupTask(
    taskId: string,
    agent: IAgent,
    context: IExecutionContext
  ): Promise<void> {
    try {
      // Libera recursos do allocator
      await this.allocator.releaseAllByTask(taskId);

      // Libera recursos do contexto
      context.releaseAllResources();

      // Destrói Agent completamente
      await agent.destroy();

      // Remove da lista de ativas
      this.activeTasks.delete(taskId);

      // Retorna ao estado Idle se não há mais tasks
      if (this.activeTasks.size === 0) {
        this.state = 'Idle';
      } else {
        this.state = 'Running';
      }
    } catch (error) {
      console.error(`[Runtime] Error cleaning up task ${taskId}:`, error);
    }
  }

  /**
   * Verifica se há capacidade disponível
   */
  private hasAvailableCapacity(): boolean {
    return this.activeTasks.size < this.config.maxConcurrentTasks;
  }
}
