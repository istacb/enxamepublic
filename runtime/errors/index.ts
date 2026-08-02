/**
 * Runtime Errors
 * 
 * Classes de erro especializadas para o Runtime.
 */

/**
 * Erro base do Runtime
 */
export class RuntimeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'RuntimeError';
  }
}

/**
 * Erro ao receber uma Task
 */
export class TaskReceiveError extends RuntimeError {
  constructor(
    message: string,
    public readonly taskId?: string
  ) {
    super(message);
    this.name = 'TaskReceiveError';
  }
}

/**
 * Erro de validação de Task
 */
export class TaskValidationError extends RuntimeError {
  constructor(
    message: string,
    public readonly taskId?: string,
    public readonly reason?: string
  ) {
    super(message);
    this.name = 'TaskValidationError';
  }
}

/**
 * Erro de capacidade insuficiente
 */
export class CapacityExceededError extends RuntimeError {
  constructor(
    message: string,
    public readonly current: number,
    public readonly maximum: number
  ) {
    super(message);
    this.name = 'CapacityExceededError';
  }
}

/**
 * Erro de capability não disponível
 */
export class CapabilityNotAvailableError extends RuntimeError {
  constructor(
    message: string,
    public readonly requiredType: string
  ) {
    super(message);
    this.name = 'CapabilityNotAvailableError';
  }
}

/**
 * Erro ao criar Agent
 */
export class AgentCreationError extends RuntimeError {
  constructor(
    message: string,
    public readonly taskId?: string
  ) {
    super(message);
    this.name = 'AgentCreationError';
  }
}

/**
 * Erro ao destruir Agent
 */
export class AgentDestructionError extends RuntimeError {
  constructor(
    message: string,
    public readonly agentId?: string
  ) {
    super(message);
    this.name = 'AgentDestructionError';
  }
}

/**
 * Erro de execução de Task
 */
export class TaskExecutionError extends RuntimeError {
  constructor(
    message: string,
    public readonly taskId?: string,
    public readonly cause?: Error
  ) {
    super(message);
    this.name = 'TaskExecutionError';
  }
}

/**
 * Erro de recuperação falha
 */
export class RecoveryFailedError extends RuntimeError {
  constructor(
    message: string,
    public readonly taskId?: string,
    public readonly attempts?: number
  ) {
    super(message);
    this.name = 'RecoveryFailedError';
  }
}

/**
 * Erro de timeout
 */
export class TaskTimeoutError extends RuntimeError {
  constructor(
    message: string,
    public readonly taskId?: string,
    public readonly timeoutMs?: number
  ) {
    super(message);
    this.name = 'TaskTimeoutError';
  }
}

/**
 * Erro de cancelamento
 */
export class TaskCanceledError extends RuntimeError {
  constructor(
    message: string,
    public readonly taskId?: string
  ) {
    super(message);
    this.name = 'TaskCanceledError';
  }
}

/**
 * Erro de alocação de recurso
 */
export class ResourceAllocationError extends RuntimeError {
  constructor(
    message: string,
    public readonly resourceId?: string
  ) {
    super(message);
    this.name = 'ResourceAllocationError';
  }
}

/**
 * Erro de liberação de recurso
 */
export class ResourceReleaseError extends RuntimeError {
  constructor(
    message: string,
    public readonly resourceId?: string
  ) {
    super(message);
    this.name = 'ResourceReleaseError';
  }
}

/**
 * Erro de Runtime não inicializado
 */
export class RuntimeNotInitializedError extends RuntimeError {
  constructor(message: string = 'Runtime not initialized') {
    super(message);
    this.name = 'RuntimeNotInitializedError';
  }
}

/**
 * Erro de Runtime já inicializado
 */
export class RuntimeAlreadyInitializedError extends RuntimeError {
  constructor(message: string = 'Runtime already initialized') {
    super(message);
    this.name = 'RuntimeAlreadyInitializedError';
  }
}

/**
 * Erro de Task não encontrada
 */
export class TaskNotFoundError extends RuntimeError {
  constructor(
    message: string,
    public readonly taskId?: string
  ) {
    super(message);
    this.name = 'TaskNotFoundError';
  }
}
