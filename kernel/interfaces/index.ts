/**
 * Kernel Interfaces - Core interface definitions for the Enxame Microkernel
 * 
 * These interfaces define the contracts that all kernel components must follow.
 * The Kernel is completely agnostic and knows nothing about IA, LLMs,
 * Missions, Workflows, or any domain-specific concepts.
 */

import type { 
  LifecycleState, 
  Capability, 
  ServiceConfig, 
  KernelEvent, 
  EventHandler,
  KernelConfig,
  RegistrationResult,
  NodeState
} from '../types';

/**
 * IKernel - The main Kernel interface
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
 */
export interface IKernel {
  /** Unique identifier for this Node */
  readonly nodeId: string;
  
  /** Current lifecycle state */
  readonly state: LifecycleState;
  
  /** Whether the kernel is running */
  readonly isRunning: boolean;
  
  /** Initialize the kernel */
  initialize(config: KernelConfig): Promise<void>;
  
  /** Start the kernel and all auto-start services */
  start(): Promise<void>;
  
  /** Stop the kernel and all services */
  stop(): Promise<void>;
  
  /** Get current node state summary */
  getState(): NodeState;
  
  /** Get the service registry */
  getServiceRegistry(): IServiceRegistry;
  
  /** Get the capability registry */
  getCapabilityRegistry(): ICapabilityRegistry;
  
  /** Get the event bus */
  getEventBus(): IEventBus;
  
  /** Get the lifecycle manager */
  getLifecycle(): ILifecycle;
}

/**
 * IService - Interface for all Services in the Enxame
 * 
 * Services are independent components that can be registered with the Kernel.
 * Examples: Runtime, Discovery, Heartbeat, Scheduler
 * 
 * Services are independent of Resources. They can always exist,
 * while Resources may appear and disappear during execution.
 */
export interface IService {
  /** Unique service identifier */
  readonly id: string;
  
  /** Service name */
  readonly name: string;
  
  /** Whether the service should start automatically */
  readonly autoStart: boolean;
  
  /** Initialize the service */
  initialize(kernel: IKernel): Promise<void>;
  
  /** Start the service */
  start(): Promise<void>;
  
  /** Stop the service */
  stop(): Promise<void>;
  
  /** Check if the service is healthy */
  isHealthy(): boolean;
}

/**
 * IServiceRegistry - Registry for managing Services
 * 
 * The Service Registry is responsible for maintaining references
 * to registered Services. It does NOT execute services.
 */
export interface IServiceRegistry {
  /** Register a service */
  register(service: IService): Promise<RegistrationResult>;
  
  /** Unregister a service */
  unregister(serviceId: string): Promise<boolean>;
  
  /** Get a service by ID */
  get(serviceId: string): IService | undefined;
  
  /** Get all registered services */
  getAll(): Iterable<IService>;
  
  /** Check if a service is registered */
  has(serviceId: string): boolean;
  
  /** Get count of registered services */
  count(): number;
  
  /** Start a specific service */
  startService(serviceId: string): Promise<void>;
  
  /** Stop a specific service */
  stopService(serviceId: string): Promise<void>;
  
  /** Start all auto-start services */
  startAutoServices(): Promise<void>;
  
  /** Stop all services */
  stopAll(): Promise<void>;
}

/**
 * ICapabilityRegistry - Registry for managing Capabilities
 * 
 * The Capability Registry is responsible for registering
 * capabilities offered by the Node. Capabilities are dynamic
 * and can appear or disappear during execution.
 * 
 * Examples: CPU, GPU, Storage, Ollama, Whisper, Internet
 */
export interface ICapabilityRegistry {
  /** Register a capability */
  register(capability: Capability): boolean;
  
  /** Unregister a capability */
  unregister(capabilityId: string): boolean;
  
  /** Update capability availability */
  setAvailability(capabilityId: string, available: boolean): boolean;
  
  /** Get a capability by ID */
  get(capabilityId: string): Capability | undefined;
  
  /** Get all registered capabilities */
  getAll(): Iterable<Capability>;
  
  /** Get only available capabilities */
  getAvailable(): Iterable<Capability>;
  
  /** Get capabilities by type */
  getByType(type: string): Iterable<Capability>;
  
  /** Check if a capability is registered */
  has(capabilityId: string): boolean;
  
  /** Get count of registered capabilities */
  count(): number;
  
  /** Get count of available capabilities */
  availableCount(): number;
}

/**
 * IEventBus - Internal event bus for the Node
 * 
 * The Event Bus is exclusively internal to the Node.
 * No communication protocol is implemented at this stage.
 */
export interface IEventBus {
  /** Subscribe to an event type */
  on<T>(eventType: string, handler: EventHandler<T>): void;
  
  /** Subscribe to an event type once */
  once<T>(eventType: string, handler: EventHandler<T>): void;
  
  /** Unsubscribe from an event type */
  off<T>(eventType: string, handler: EventHandler<T>): void;
  
  /** Emit an event */
  emit<T>(eventType: string, payload: T, source?: string): void;
  
  /** Remove all listeners for an event type */
  removeAllListeners(eventType: string): void;
  
  /** Remove all listeners */
  clear(): void;
  
  /** Get listener count for an event type */
  listenerCount(eventType: string): number;
}

/**
 * ILifecycle - Lifecycle management for the Node
 * 
 * Manages the Node lifecycle states:
 * Booting → Initializing → Ready → Running → Stopping → Stopped
 *                                            ↓
 *                                         Faulted
 */
export interface ILifecycle {
  /** Current lifecycle state */
  readonly currentState: LifecycleState;
  
  /** Timestamp when the lifecycle was initialized */
  readonly startedAt: number;
  
  /** Get current uptime in milliseconds */
  getUptime(): number;
  
  /** Transition to a new state */
  transition(to: LifecycleState): boolean;
  
  /** Check if a state transition is valid */
  canTransition(to: LifecycleState): boolean;
  
  /** Check if currently in a specific state */
  is(state: LifecycleState): boolean;
  
  /** Subscribe to state changes */
  onChange(callback: (from: LifecycleState, to: LifecycleState) => void): void;
}

/**
 * IKernelConfig - Configuration loader interface
 * 
 * Responsible for loading and validating kernel configuration.
 */
export interface IKernelConfig {
  /** Load configuration from source */
  load(): Promise<KernelConfig>;
  
  /** Validate configuration */
  validate(config: KernelConfig): boolean;
  
  /** Get configuration value by key */
  get<T>(key: string, defaultValue?: T): T | undefined;
  
  /** Set configuration value */
  set(key: string, value: unknown): void;
}
