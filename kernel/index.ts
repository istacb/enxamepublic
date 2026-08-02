/**
 * Enxame Microkernel - Main Entry Point
 * 
 * This module exports all public APIs for the Enxame Microkernel.
 * The Kernel is the minimal infrastructure required for a Node
 * to participate in the Enxame swarm.
 * 
 * @module @enxame/kernel
 */

// Core Kernel
export { Kernel } from './kernel';

// Types
export { LifecycleState } from './types';
export type {
  Capability,
  ServiceConfig,
  KernelEvent,
  EventHandler,
  KernelConfig,
  RegistrationResult,
  NodeState
} from './types';

// Interfaces
export type {
  IKernel,
  IService,
  IServiceRegistry,
  ICapabilityRegistry,
  IEventBus,
  ILifecycle,
  IKernelConfig
} from './interfaces';

// Implementations
export { LifecycleManager } from './lifecycle';
export { EventBus } from './events';
export { ServiceRegistry, CapabilityRegistry } from './registry';
export { ConfigLoader } from './config';

// Errors
export {
  KernelError,
  KernelInitializationError,
  KernelFatalError,
  ServiceRegistrationError,
  ServiceNotFoundError,
  ServiceStartError,
  ServiceStopError,
  CapabilityRegistrationError,
  CapabilityNotFoundError,
  InvalidStateTransitionError,
  ConfigurationError
} from './errors';
