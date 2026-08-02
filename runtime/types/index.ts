/**
 * Runtime Types
 * 
 * Tipos fundamentais para o Runtime do Enxame.
 */

/**
 * Estados possíveis do Runtime
 */
export type RuntimeState =
  | 'Idle'
  | 'Receiving'
  | 'Validating'
  | 'CreatingAgent'
  | 'Running'
  | 'Completed'
  | 'Canceled'
  | 'Retrying'
  | 'Failed';

/**
 * Estados possíveis de um Agent
 */
export type AgentState =
  | 'Created'
  | 'Initializing'
  | 'Executing'
  | 'Completing'
  | 'Destroying'
  | 'Destroyed';

/**
 * Resultado de uma execução
 */
export interface ExecutionResult {
  /** Identificador único da Task */
  taskId: string;
  
  /** Status da execução */
  status: 'Success' | 'Failed' | 'Canceled' | 'Timeout';
  
  /** Dados de saída (se sucesso) */
  output?: unknown;
  
  /** Erro ocorrido (se falha) */
  error?: string;
  
  /** Timestamp de início */
  startedAt: number;
  
  /** Timestamp de término */
  completedAt: number;
  
  /** Número de tentativas realizadas */
  attempts: number;
}

/**
 * Contexto de execução de uma Task
 */
export interface ExecutionContext {
  /** Identificador da Task */
  taskId: string;
  
  /** Payload da Task */
  payload: Record<string, unknown>;
  
  /** Recursos alocados */
  allocatedResources: string[];
  
  /** Timestamp de criação */
  createdAt: number;
  
  /** Timeout em milissegundos */
  timeoutMs?: number;
  
  /** Número máximo de retries */
  maxRetries: number;
  
  /** Contador de tentativas atuais */
  currentAttempt: number;
}

/**
 * Capacidade necessária para executar uma Task
 */
export interface RequiredCapability {
  /** Tipo de capacidade (ex: 'CPU', 'GPU', 'Ollama') */
  type: string;
  
  /** Quantidade mínima necessária */
  minimum?: number;
  
  /** Características específicas */
  features?: string[];
}

/**
 * Configuração do Runtime
 */
export interface RuntimeConfig {
  /** Número máximo de retries por Task */
  maxRetries: number;
  
  /** Timeout padrão em milissegundos */
  defaultTimeoutMs: number;
  
  /** Capacidade máxima de Tasks simultâneas */
  maxConcurrentTasks: number;
}

/**
 * Status atual do Runtime
 */
export interface RuntimeStatus {
  /** Estado atual */
  state: RuntimeState;
  
  /** Tasks em execução */
  activeTasks: number;
  
  /** Capacidade máxima */
  maxCapacity: number;
  
  /** Saúde do Runtime */
  healthy: boolean;
  
  /** Timestamp do último heartbeat */
  lastHeartbeat: number;
}
