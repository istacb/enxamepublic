/**
 * Service Loader Types - Type definitions for the Service Loader
 * 
 * These types define the core abstractions used throughout the Service Loader.
 * The Service Loader is completely agnostic and knows nothing about IA, LLMs,
 * Missions, Workflows, or any domain-specific concepts.
 */

/**
 * Service type enumeration
 */
export enum ServiceType {
  /** Permanent services run continuously */
  Permanent = 'permanent',
  /** Ephemeral services run once and terminate */
  Ephemeral = 'ephemeral'
}

/**
 * Service Loader states
 */
export enum ServiceLoaderState {
  /** Service Loader is initializing */
  Initializing = 'Initializing',
  /** Loading Service definitions from Manifest */
  Loading = 'Loading',
  /** Service Loader is actively managing Services */
  Running = 'Running',
  /** Waiting for a dependency to be satisfied */
  WaitingDependency = 'Waiting Dependency',
  /** Attempting to restart a failed Service */
  Restarting = 'Restarting',
  /** Service Loader encountered a fatal error */
  Failed = 'Failed',
  /** Service Loader completed its work */
  Finished = 'Finished'
}

/**
 * Service lifecycle states
 */
export enum ServiceState {
  /** Service is being initialized */
  Initializing = 'Initializing',
  /** Service is starting */
  Starting = 'Starting',
  /** Service is running */
  Running = 'Running',
  /** Service is stopping */
  Stopping = 'Stopping',
  /** Service has stopped */
  Stopped = 'Stopped',
  /** Service has failed */
  Failed = 'Failed',
  /** Service has finished normally (ephemeral) */
  Finished = 'Finished',
  /** Service is waiting for dependencies */
  WaitingDependency = 'Waiting Dependency'
}

/**
 * Service descriptor definition
 */
export interface ServiceDescriptor {
  /** Unique service identifier */
  id: string;
  /** Service name */
  name: string;
  /** Type of service (permanent or ephemeral) */
  type: ServiceType;
  /** Service dependencies */
  dependencies: string[];
  /** Required capabilities */
  requirements: string[];
  /** Restart policy configuration */
  restartPolicy: RestartPolicyConfig;
  /** Whether the service should start automatically */
  autoStart: boolean;
}

/**
 * Restart policy configuration
 */
export interface RestartPolicyConfig {
  /** Whether restart is enabled */
  enabled: boolean;
  /** Maximum number of restart attempts */
  maxAttempts: number;
  /** Delay between restart attempts in milliseconds */
  delayMs: number;
}

/**
 * Service manifest structure
 */
export interface ServiceManifest {
  /** List of service descriptors */
  services: ServiceDescriptor[];
}

/**
 * Restart configuration defaults
 */
export interface RestartConfig {
  /** Default maximum attempts (5) */
  defaultMaxAttempts: number;
  /** Default delay between attempts */
  defaultDelayMs: number;
}

/**
 * Service failure event payload
 */
export interface ServiceFailureEvent {
  /** Service ID that failed */
  serviceId: string;
  /** Error message */
  error: string;
  /** Number of restart attempts made */
  attempts: number;
  /** Timestamp of failure */
  timestamp: number;
}

/**
 * Default restart configuration
 */
export const DEFAULT_RESTART_CONFIG: RestartConfig = {
  defaultMaxAttempts: 5,
  defaultDelayMs: 1000
};
