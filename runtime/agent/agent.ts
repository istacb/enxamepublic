/**
 * Agent Implementation
 * 
 * Implementação de um Agent efêmero.
 * Criado pelo Runtime para executar uma Task específica.
 * Destruído completamente ao término.
 */

import type { IAgent, IExecutionContext } from '../interfaces';
import type { AgentState, ExecutionResult, ExecutionContext } from '../types';

/**
 * Gera um UUID v4 criptograficamente seguro.
 * Usa a API nativa crypto.randomUUID() quando disponível (Node 14.17+,
 * navegadores modernos), com fallback para crypto.getRandomValues.
 */
function generateUUID(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Fallback para ambientes antigos sem crypto.randomUUID.
  const bytes = new Uint8Array(16);
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < 16; i++) {
      bytes[i] = (Math.random() * 256) | 0;
    }
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40; // versão 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // variante RFC 4122
  const hex = (b: number) => b.toString(16).padStart(2, '0');
  return `${hex(bytes[0])}${hex(bytes[1])}${hex(bytes[2])}${hex(bytes[3])}-` +
    `${hex(bytes[4])}${hex(bytes[5])}-${hex(bytes[6])}${hex(bytes[7])}-` +
    `${hex(bytes[8])}${hex(bytes[9])}-${hex(bytes[10])}${hex(bytes[11])}` +
    `${hex(bytes[12])}${hex(bytes[13])}${hex(bytes[14])}${hex(bytes[15])}`;
}

export class Agent implements IAgent {
  public readonly id: string;
  public readonly taskId: string;
  private _state: AgentState;
  private context: ExecutionContext | null = null;
  private executionPromise: Promise<unknown> | null = null;

  constructor(taskId: string) {
    this.id = generateUUID();
    this.taskId = taskId;
    this._state = 'Created';
  }

  public get state(): AgentState {
    return this._state;
  }

  /**
   * Inicializa o Agent com o contexto de execução
   */
  public async initialize(context: ExecutionContext): Promise<void> {
    if (this._state !== 'Created') {
      throw new Error(`Agent cannot be initialized in state: ${this._state}`);
    }

    this.context = context;
    this._state = 'Initializing';

    // Simula inicialização do contexto
    await this.setupContext();

    this._state = 'Executing';
  }

  /**
   * Executa a Task
   * 
   * NOTA: Esta é uma implementação stub.
   * A execução real será implementada em PRs futuras
   * quando os Resources e executores concretos estiverem disponíveis.
   */
  public async execute(): Promise<unknown> {
    if (this._state !== 'Executing') {
      throw new Error(`Agent cannot execute in state: ${this._state}`);
    }

    if (!this.context) {
      throw new Error('Agent context not initialized');
    }

    try {
      // Placeholder para execução real
      // Em PRs futuras, isso delegará para um ITaskExecutor concreto
      const result = await this.performExecution();
      
      this._state = 'Completing';
      return result;
    } catch (error) {
      this._state = 'Failed';
      throw error;
    }
  }

  /**
   * Finaliza a execução e limpa recursos
   */
  public async complete(result: ExecutionResult): Promise<void> {
    if (this._state !== 'Completing' && this._state !== 'Executing') {
      throw new Error(`Agent cannot complete in state: ${this._state}`);
    }

    this._state = 'Destroying';

    // Libera todos os recursos do contexto
    if (this.context) {
      this.context.releaseAllResources();
    }

    // Limpa referências
    this.context = null;
    this.executionPromise = null;

    this._state = 'Destroyed';
  }

  /**
   * Destrói completamente o Agent
   * Zero estado residual
   */
  public async destroy(): Promise<void> {
    if (this._state === 'Destroyed') {
      return; // Já destruído
    }

    this._state = 'Destroying';

    // Garante liberação de recursos
    if (this.context) {
      this.context.releaseAllResources();
      this.context = null;
    }

    this.executionPromise = null;

    // Aguarda microtask para garantir cleanup completo
    await Promise.resolve();

    this._state = 'Destroyed';
  }

  /**
   * Configura o contexto de execução
   */
  private async setupContext(): Promise<void> {
    // Simula setup do contexto
    await Promise.resolve();
  }

  /**
   * Realiza a execução efetiva da Task
   * 
   * Stub para implementação futura
   */
  private async performExecution(): Promise<unknown> {
    if (!this.context) {
      throw new Error('No context available for execution');
    }

    // Placeholder: retorna o payload como output
    // Em PRs futuras, isso usará um executor concreto
    return {
      taskId: this.context.taskId,
      output: this.context.payload,
    };
  }
}
