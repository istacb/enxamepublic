/**
 * Kernel - The Enxame Microkernel
 * 
 * The Kernel is responsible for:
 * - Initializing the Node
 * - Loading configuration
 * - Maintaining lifecycle
 * - Providing an internal Event Bus
 * - Registering Services
 * - Registering Capabilities
 * - Starting and stopping Services
 * - Exposing internal Node state
 * 
 * The Kernel does NOT know about:
 * - IA, Ollama, LLM, Prompt
 * - Mission, Workflow, Task
 * - Judge, Orchestrator, Scheduler
 * - Discovery, Heartbeat, Protocol
 * 
 * Design Principles:
 * - K-001: No hot reload - changes require Node restart
 * - K-002: Only changed by official software updates
 * - K-003: Completely agnostic to domain concepts
 * - K-004: Knows only its own Node
 * - K-005: Kernel failure only affects its own Node
 * - K-006: One Node per machine
 */

import type {
  IKernel,
  IServiceRegistry,
  ICapabilityRegistry,
  IEventBus,
  ILifecycle,
  KernelConfig,
  NodeState
} from '../interfaces';
import type { LifecycleState } from '../types';
import { LifecycleManager } from '../lifecycle';
import { EventBus } from '../events';
import { ServiceRegistry } from '../registry';
import { CapabilityRegistry } from '../registry';
import { ConfigLoader } from '../config';
import {
  KernelInitializationError,
  KernelFatalError
} from '../errors';

/**
 * Kernel - Concrete implementation of IKernel
 */
export class Kernel implements IKernel {
  private _nodeId: string;
  private _nodeName?: string;
  private _lifecycle: LifecycleManager;
  private _eventBus: EventBus;
  private _serviceRegistry: ServiceRegistry;
  private _capabilityRegistry: CapabilityRegistry;
  private _configLoader: ConfigLoader;
  private _initialized: boolean;

  constructor() {
    this._nodeId = '';
    this._lifecycle = new LifecycleManager();
    this._eventBus = new EventBus();
    this._serviceRegistry = new ServiceRegistry();
    this._capabilityRegistry = new CapabilityRegistry();
    this._configLoader = new ConfigLoader();
    this._initialized = false;
  }

  /**
   * Get unique identifier for this Node
   */
  get nodeId(): string {
    return this._nodeId;
  }

  /**
   * Get current lifecycle state
   */
  get state(): LifecycleState {
    return this._lifecycle.currentState;
  }

  /**
   * Get whether the kernel is running
   */
  get isRunning(): boolean {
    return this._lifecycle.is(LifecycleState.Running);
  }

  /**
   * Initialize the kernel
   * @param config - Kernel configuration
   * @throws KernelInitializationError if initialization fails
   */
  async initialize(config: KernelConfig): Promise<void> {
    try {
      // Validate configuration
      this._configLoader.validate(config);
      
      // Load configuration
      await this._configLoader.load(config);
      
      // Set node identity
      this._nodeId = config.nodeId;
      this._nodeName = config.nodeName;
      
      // Set kernel reference in service registry
      (this._serviceRegistry as ServiceRegistry).setKernel(this);
      
      // Transition to Initializing state
      this._lifecycle.transition(LifecycleState.Initializing);
      
      // Emit initialization event
      this._eventBus.emit('kernel:initialized', {
        nodeId: this._nodeId,
        nodeName: this._nodeName
      }, 'kernel');
      
      this._initialized = true;
      
      console.log(`[Kernel] Initialized node '${this._nodeId}'`);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this._lifecycle.fault();
      throw new KernelInitializationError(message, { originalError: error });
    }
  }

  /**
   * Start the kernel and all auto-start services
   * @throws KernelFatalError if start fails
   */
  async start(): Promise<void> {
    if (!this._initialized) {
      throw new KernelFatalError('Kernel not initialized. Call initialize() first.');
    }

    try {
      // Transition to Ready state
      this._lifecycle.transition(LifecycleState.Ready);
      
      // Emit ready event
      this._eventBus.emit('kernel:ready', { nodeId: this._nodeId }, 'kernel');
      
      // Start all auto-start services
      await this._serviceRegistry.startAutoServices();
      
      // Transition to Running state
      this._lifecycle.transition(LifecycleState.Running);
      
      // Emit started event
      this._eventBus.emit('kernel:started', {
        nodeId: this._nodeId,
        uptime: 0
      }, 'kernel');
      
      console.log(`[Kernel] Node '${this._nodeId}' started`);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this._lifecycle.fault();
      throw new KernelFatalError(`Failed to start kernel: ${message}`, { originalError: error });
    }
  }

  /**
   * Stop the kernel and all services
   */
  async stop(): Promise<void> {
    if (!this._initialized) {
      return; // Nothing to stop
    }

    try {
      // Transition to Stopping state
      this._lifecycle.transition(LifecycleState.Stopping);
      
      // Emit stopping event
      this._eventBus.emit('kernel:stopping', { nodeId: this._nodeId }, 'kernel');
      
      // Stop all services
      await this._serviceRegistry.stopAll();
      
      // Clear event bus
      this._eventBus.clear();
      
      // Transition to Stopped state
      this._lifecycle.transition(LifecycleState.Stopped);
      
      // Emit stopped event
      this._eventBus.emit('kernel:stopped', {
        nodeId: this._nodeId,
        uptime: this._lifecycle.getUptime()
      }, 'kernel');
      
      console.log(`[Kernel] Node '${this._nodeId}' stopped`);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this._lifecycle.fault();
      console.error(`[Kernel] Error during shutdown:`, error);
      throw new KernelFatalError(`Failed to stop kernel: ${message}`, { originalError: error });
    }
  }

  /**
   * Get current node state summary
   */
  getState(): NodeState {
    return {
      lifecycle: this._lifecycle.currentState,
      nodeId: this._nodeId,
      nodeName: this._nodeName,
      serviceCount: this._serviceRegistry.count(),
      capabilityCount: this._capabilityRegistry.count(),
      uptime: this._lifecycle.getUptime(),
      startedAt: this._lifecycle.startedAt
    };
  }

  /**
   * Get the service registry
   */
  getServiceRegistry(): IServiceRegistry {
    return this._serviceRegistry;
  }

  /**
   * Get the capability registry
   */
  getCapabilityRegistry(): ICapabilityRegistry {
    return this._capabilityRegistry;
  }

  /**
   * Get the event bus
   */
  getEventBus(): IEventBus {
    return this._eventBus;
  }

  /**
   * Get the lifecycle manager
   */
  getLifecycle(): ILifecycle {
    return this._lifecycle;
  }

  /**
   * Register a service (convenience method)
   * @param service - Service to register
   * @returns Registration result
   */
  async registerService(service: import('../interfaces').IService) {
    return this._serviceRegistry.register(service);
  }

  /**
   * Register a capability (convenience method)
   * @param capability - Capability to register
   * @returns true if registration was successful
   */
  registerCapability(capability: import('../types').Capability) {
    return this._capabilityRegistry.register(capability);
  }
}
