/**
 * Runtime Interfaces
 * 
 * Interfaces desacopladas para o Runtime do Enxame.
 */

import type {
  RuntimeState,
  AgentState,
  ExecutionResult,
  ExecutionContext,
  RequiredCapability,
  RuntimeConfig,
  RuntimeStatus,
} from '../types';

/**
 * Interface do Runtime
 * 
 * Serviço permanente responsável por transformar Tasks em resultados.
 */
export interface IRuntime {
  /**
   * Inicializa o Runtime
   */
  initialize(): Promise<void>;

  /**
   * Recebe uma Task para execução
   * @param taskId Identificador único da Task
   * @param payload Dados da Task
   * @param requiredCapabilities Capacidades necessárias
   */
  receiveTask(
    taskId: string,
    payload: Record<string, unknown>,
    requiredCapabilities?: RequiredCapability[]
  ): Promise<void>;

  /**
   * Cancela uma Task em execução
   * @param taskId Identificador da Task a cancelar
   */
  cancelTask(taskId: string): Promise<void>;

  /**
   * Obtém status atual do Runtime
   */
  getStatus(): RuntimeStatus;

  /**
   * Verifica se o Runtime está saudável
   */
  isHealthy(): boolean;

  /**
   * Finaliza o Runtime
   */
  shutdown(): Promise<void>;
}

/**
 * Interface de um Agent efêmero
 * 
 * Criado pelo Runtime para executar uma Task específica.
 * Destruído completamente ao término.
 */
export interface IAgent {
  /**
   * Identificador único do Agent
   */
  readonly id: string;

  /**
   * Identificador da Task sendo executada
   */
  readonly taskId: string;

  /**
   * Estado atual do Agent
   */
  readonly state: AgentState;

  /**
   * Inicializa o Agent
   */
  initialize(context: ExecutionContext): Promise<void>;

  /**
   * Executa a Task
   */
  execute(): Promise<unknown>;

  /**
   * Finaliza a execução e limpa recursos
   */
  complete(result: ExecutionResult): Promise<void>;

  /**
   * Destrói completamente o Agent
   * Zero estado residual
   */
  destroy(): Promise<void>;
}

/**
 * Interface do Executor de Tasks
 * 
 * Responsável pela execução efetiva de uma Task.
 */
export interface ITaskExecutor {
  /**
   * Executa uma Task dentro de um contexto
   * @param context Contexto de execução
   * @param agent Agent responsável
   */
  execute(context: ExecutionContext, agent: IAgent): Promise<unknown>;

  /**
   * Tenta recuperar de uma falha
   * @param context Contexto da execução falha
   * @param error Erro ocorrido
   */
  recover(context: ExecutionContext, error: Error): Promise<boolean>;
}

/**
 * Interface do Contexto de Execução
 * 
 * Mantém o estado durante a execução de uma Task.
 */
export interface IExecutionContext {
  /**
   * Identificador da Task
   */
  taskId: string;

  /**
   * Payload da Task
   */
  payload: Record<string, unknown>;

  /**
   * Recursos atualmente alocados
   */
  allocatedResources: Set<string>;

  /**
   * Timeout em milissegundos
   */
  timeoutMs?: number;

  /**
   * Contador de tentativas
   */
  attemptCount: number;

  /**
   * Máximo de tentativas permitidas
   */
  maxRetries: number;

  /**
   * Marca recurso como alocado
   */
  allocateResource(resourceId: string): void;

  /**
   * Libera recurso alocado
   */
  releaseResource(resourceId: string): void;

  /**
   * Libera todos os recursos
   */
  releaseAllResources(): void;
}

/**
 * Interface do Alocador de Recursos
 * 
 * Gerencia alocação e liberação de recursos locais.
 */
export interface IResourceAllocator {
  /**
   * Aloca recursos necessários para uma execução
   * @param requiredCapabilities Capacidades necessárias
   * @param taskId Identificador da Task
   */
  allocate(
    requiredCapabilities: RequiredCapability[],
    taskId: string
  ): Promise<string[]>;

  /**
   * Libera recursos previamente alocados
   * @param resourceIds Identificadores dos recursos
   * @param taskId Identificador da Task
   */
  release(resourceIds: string[], taskId: string): Promise<void>;

  /**
   * Verifica disponibilidade de capacidades
   * @param requiredCapabilities Capacidades necessárias
   */
  checkAvailability(requiredCapabilities: RequiredCapability[]): boolean;

  /**
   * Obtém capacidade atual disponível
   */
  getAvailableCapacity(): number;

  /**
   * Libera todos os recursos de uma Task
   * @param taskId Identificador da Task
   */
  releaseAllByTask(taskId: string): Promise<void>;
}

/**
 * Interface do Resultado de Execução
 * 
 * Representa o resultado final de uma Task.
 */
export interface IExecutionResult {
  /**
   * Identificador da Task
   */
  taskId: string;

  /**
   * Status da execução
   */
  status: 'Success' | 'Failed' | 'Canceled' | 'Timeout';

  /**
   * Dados de saída (se sucesso)
   */
  output?: unknown;

  /**
   * Erro ocorrido (se falha)
   */
  error?: string;

  /**
   * Timestamp de início
   */
  startedAt: number;

  /**
   * Timestamp de término
   */
  completedAt: number;

  /**
   * Número de tentativas realizadas
   */
  attempts: number;

  /**
   * Converte para formato serializável
   */
  toJSON(): Record<string, unknown>;
}
