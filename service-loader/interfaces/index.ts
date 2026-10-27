/**
 * Service Loader Interfaces - Core interface definitions for the Service Loader
 * 
 * These interfaces define the contracts that all Service Loader components must follow.
 * The Service Loader is completely agnostic and knows nothing about IA, LLMs,
 * Missions, Workflows, or any domain-specific concepts.
 */

import type {
  ServiceType,
  ServiceLoaderState,
  ServiceState,
  ServiceDescriptor,
  ServiceManifest,
  RestartPolicyConfig
} from '../types';

/**
 * IService - Interface for all Services in the Enxame
 * 
 * Services are independent components that can be managed by the Service Loader.
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
  
  /** Service type (permanent or ephemeral) */
  readonly type: ServiceType;
  
  /** Initialize the service */
  initialize(): Promise<void>;
  
  /** Start the service */
  start(): Promise<void>;
  
  /** Stop the service */
  stop(): Promise<void>;
  
  /** Check if the service is healthy */
  isHealthy(): boolean;
}

/**
 * IServiceLoader - Main Service Loader interface
 * 
 * Responsible for managing the lifecycle of all Services within a Node.
 */
export interface IServiceLoader {
  /** Current state of the Service Loader */
  readonly state: ServiceLoaderState;
  
  /** Initialize the Service Loader with a manifest */
  initialize(manifest: ServiceManifest): Promise<void>;
  
  /** Start the Service Loader and all auto-start services */
  start(): Promise<void>;
  
  /** Stop the Service Loader and all managed services */
  stop(): Promise<void>;
  
  /** Get current state summary */
  getState(): ServiceLoaderState;
  
  /** Get count of managed services */
  getServiceCount(): number;
}

/**
 * IServiceManifest - Interface for Service Manifest management
 */
export interface IServiceManifest {
  /** Get all service descriptors */
  services: IServiceDescriptor[];
  
  /** Validate the manifest */
  validate(): boolean;
  
  /** Get service descriptor by ID */
  getService(id: string): IServiceDescriptor | undefined;
  
  /** Get all services that should auto-start */
  getAutoStartServices(): IServiceDescriptor[];
}

/**
 * IServiceDescriptor - Interface for Service Descriptor
 */
export interface IServiceDescriptor {
  /** Unique service identifier */
  readonly id: string;
  
  /** Service name */
  readonly name: string;
  
  /** Type of service */
  readonly type: ServiceType;
  
  /** Service dependencies */
  readonly dependencies: IServiceDependency[];
  
  /** Required capabilities */
  readonly requirements: string[];
  
  /** Restart policy */
  readonly restartPolicy: IRestartPolicy;
  
  /** Whether the service should start automatically */
  readonly autoStart: boolean;
  
  /** Check if all dependencies are satisfied */
  areDependenciesSatisfied(): boolean;
  
  /** Check if all requirements are met */
  areRequirementsMet(availableCapabilities: string[]): boolean;
}

/**
 * IServiceLifecycle - Interface for Service Lifecycle management
 */
export interface IServiceLifecycle {
  /** Current lifecycle state */
  readonly currentState: ServiceState;
  
  /** Timestamp when the service was started */
  readonly startedAt?: number;
  
  /** Get current uptime in milliseconds */
  getUptime(): number;
  
  /** Transition to a new state */
  transition(to: ServiceState): boolean;
  
  /** Check if a state transition is valid */
  canTransition(to: ServiceState): boolean;
  
  /** Check if currently in a specific state */
  is(state: ServiceState): boolean;
  
  /** Subscribe to state changes */
  onChange(callback: (from: ServiceState, to: ServiceState) => void): void;
}

/**
 * IRestartPolicy - Interface for Restart Policy management
 */
export interface IRestartPolicy {
  /** Whether restart is enabled */
  readonly enabled: boolean;
  
  /** Maximum number of restart attempts */
  readonly maxAttempts: number;
  
  /** Current attempt number */
  readonly currentAttempt: number;
  
  /** Delay between restart attempts in milliseconds */
  readonly delayMs: number;
  
  /** Check if retry is allowed */
  canRetry(): boolean;
  
  /** Increment attempt counter */
  incrementAttempt(): void;
  
  /** Reset attempt counter */
  reset(): void;
  
  /** Get remaining attempts */
  getRemainingAttempts(): number;
}

/**
 * IServiceDependency - Interface for Service Dependency
 */
export interface IServiceDependency {
  /** Service ID this dependency refers to */
  readonly serviceId: string;
  
  /** Whether this dependency is required (vs optional) */
  readonly required: boolean;
  
  /** Check if this dependency is satisfied */
  isSatisfied(runningServices: Set<string>): boolean;
}

/**
 * ICapabilityChecker - Interface for checking node capabilities
 */
export interface ICapabilityChecker {
  /** Check if a capability is available */
  hasCapability(capabilityId: string): boolean;
  
  /** Get all available capabilities */
  getAvailableCapabilities(): string[];
  
  /** Check if all required capabilities are available */
  hasAllCapabilities(requirements: string[]): boolean;
}
