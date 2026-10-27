/**
 * Kernel Errors - Error classes for the Enxame Microkernel
 * 
 * These errors represent exceptional conditions that can occur
 * during kernel operation. All errors are designed to be caught
 * and handled appropriately by the Node lifecycle management.
 */

/**
 * Base error class for all Kernel errors
 */
export class KernelError extends Error {
  /** Error code for programmatic handling */
  public readonly code: string;
  /** Additional context about the error */
  public readonly context?: Record<string, unknown>;

  constructor(code: string, message: string, context?: Record<string, unknown>) {
    super(message);
    this.name = 'KernelError';
    this.code = code;
    this.context = context;
    
    // Maintain proper stack trace
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, KernelError);
    }
  }
}

/**
 * Thrown when the kernel fails to initialize
 */
export class KernelInitializationError extends KernelError {
  constructor(message: string, context?: Record<string, unknown>) {
    super('KERNEL_INIT_FAILED', message, context);
    this.name = 'KernelInitializationError';
  }
}

/**
 * Thrown when a service registration fails
 */
export class ServiceRegistrationError extends KernelError {
  constructor(serviceId: string, message: string) {
    super('SERVICE_REGISTRATION_FAILED', `Failed to register service '${serviceId}': ${message}`, {
      serviceId
    });
    this.name = 'ServiceRegistrationError';
  }
}

/**
 * Thrown when a service is not found in the registry
 */
export class ServiceNotFoundError extends KernelError {
  constructor(serviceId: string) {
    super('SERVICE_NOT_FOUND', `Service '${serviceId}' not found`, { serviceId });
    this.name = 'ServiceNotFoundError';
  }
}

/**
 * Thrown when a service fails to start
 */
export class ServiceStartError extends KernelError {
  constructor(serviceId: string, message: string) {
    super('SERVICE_START_FAILED', `Failed to start service '${serviceId}': ${message}`, {
      serviceId
    });
    this.name = 'ServiceStartError';
  }
}

/**
 * Thrown when a service fails to stop
 */
export class ServiceStopError extends KernelError {
  constructor(serviceId: string, message: string) {
    super('SERVICE_STOP_FAILED', `Failed to stop service '${serviceId}': ${message}`, {
      serviceId
    });
    this.name = 'ServiceStopError';
  }
}

/**
 * Thrown when capability registration fails
 */
export class CapabilityRegistrationError extends KernelError {
  constructor(capabilityId: string, message: string) {
    super('CAPABILITY_REGISTRATION_FAILED', `Failed to register capability '${capabilityId}': ${message}`, {
      capabilityId
    });
    this.name = 'CapabilityRegistrationError';
  }
}

/**
 * Thrown when a capability is not found
 */
export class CapabilityNotFoundError extends KernelError {
  constructor(capabilityId: string) {
    super('CAPABILITY_NOT_FOUND', `Capability '${capabilityId}' not found`, { capabilityId });
    this.name = 'CapabilityNotFoundError';
  }
}

/**
 * Thrown when an invalid lifecycle state transition is attempted
 */
export class InvalidStateTransitionError extends KernelError {
  constructor(fromState: string, toState: string) {
    super(
      'INVALID_STATE_TRANSITION',
      `Invalid lifecycle state transition from '${fromState}' to '${toState}'`,
      { fromState, toState }
    );
    this.name = 'InvalidStateTransitionError';
  }
}

/**
 * Thrown when the kernel encounters a fatal error
 */
export class KernelFatalError extends KernelError {
  constructor(message: string, context?: Record<string, unknown>) {
    super('KERNEL_FATAL', message, context);
    this.name = 'KernelFatalError';
  }
}

/**
 * Thrown when configuration is invalid or missing
 */
export class ConfigurationError extends KernelError {
  constructor(message: string, context?: Record<string, unknown>) {
    super('CONFIGURATION_ERROR', message, context);
    this.name = 'ConfigurationError';
  }
}
