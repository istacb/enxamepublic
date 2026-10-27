/**
 * Kernel Types - Type definitions for the Enxame Microkernel
 * 
 * These types define the core abstractions used throughout the Kernel.
 * The Kernel is completely agnostic and knows nothing about IA, LLMs,
 * Missions, Workflows, or any domain-specific concepts.
 */

/**
 * Lifecycle states for a Node
 */
export enum LifecycleState {
  /** Node is starting up */
  Booting = 'Booting',
  /** Node is initializing components */
  Initializing = 'Initializing',
  /** Node is ready to accept work */
  Ready = 'Ready',
  /** Node is actively running */
  Running = 'Running',
  /** Node is shutting down */
  Stopping = 'Stopping',
  /** Node has stopped */
  Stopped = 'Stopped',
  /** Node encountered a fault */
  Faulted = 'Faulted'
}

/**
 * Represents a hardware or software capability offered by the Node
 */
export interface Capability {
  /** Unique identifier for this capability */
  id: string;
  /** Human-readable name */
  name: string;
  /** Capability type (e.g., 'cpu', 'gpu', 'storage', 'ollama') */
  type: string;
  /** Whether this capability is currently available */
  available: boolean;
  /** Optional metadata about the capability */
  metadata?: Record<string, unknown>;
  /** Timestamp when this capability was registered */
  registeredAt: number;
  /** Timestamp when availability last changed */
  lastUpdated?: number;
}

/**
 * Service configuration options
 */
export interface ServiceConfig {
  /** Unique service identifier */
  id: string;
  /** Service name */
  name: string;
  /** Whether the service should start automatically */
  autoStart?: boolean;
  /** Service-specific configuration */
  options?: Record<string, unknown>;
}

/**
 * Event payload structure
 */
export interface KernelEvent<T = unknown> {
  /** Event type/name */
  type: string;
  /** Event payload data */
  payload: T;
  /** Timestamp when event was created */
  timestamp: number;
  /** Source component that emitted the event */
  source?: string;
}

/**
 * Event handler function type
 */
export type EventHandler<T = unknown> = (event: KernelEvent<T>) => void | Promise<void>;

/**
 * Kernel configuration options
 */
export interface KernelConfig {
  /** Node identifier */
  nodeId: string;
  /** Node display name */
  nodeName?: string;
  /** Configuration directory path */
  configPath?: string;
  /** Log level */
  logLevel?: 'debug' | 'info' | 'warn' | 'error';
  /** Additional kernel options */
  [key: string]: unknown;
}

/**
 * Result of service registration
 */
export interface RegistrationResult {
  /** Whether registration was successful */
  success: boolean;
  /** Service identifier */
  serviceId: string;
  /** Error message if registration failed */
  error?: string;
}

/**
 * Node state summary
 */
export interface NodeState {
  /** Current lifecycle state */
  lifecycle: LifecycleState;
  /** Node identifier */
  nodeId: string;
  /** Node name */
  nodeName?: string;
  /** Number of registered services */
  serviceCount: number;
  /** Number of registered capabilities */
  capabilityCount: number;
  /** Uptime in milliseconds */
  uptime: number;
  /** Timestamp when node started */
  startedAt: number;
}
