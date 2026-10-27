/**
 * Service Loader - Main implementation for managing service lifecycle
 */

import type { IServiceLoader, ICapabilityChecker } from '../interfaces';
import type { 
  ServiceManifest as ServiceManifestData,
  ServiceLoaderState,
  ServiceState,
  ServiceFailureEvent
} from '../types';
import { ServiceType, DEFAULT_RESTART_CONFIG } from '../types';
import { ServiceManifestImpl } from '../manifest';
import { ServiceLifecycle } from '../lifecycle';
import type { IService } from '../interfaces';

/**
 * Internal service wrapper with lifecycle management
 */
interface ManagedService {
  service: IService;
  lifecycle: ServiceLifecycle;
  descriptor: import('../manifest').ServiceDescriptorImpl;
}

/**
 * ServiceLoader - Concrete implementation of IServiceLoader
 */
export class ServiceLoader implements IServiceLoader {
  private _state: ServiceLoaderState;
  private _manifest: ServiceManifestImpl | null;
  private _services: Map<string, ManagedService>;
  private _runningServices: Set<string>;
  private _capabilityChecker: ICapabilityChecker | null;
  private _failureListener: ((event: ServiceFailureEvent) => void) | null;

  constructor(capabilityChecker?: ICapabilityChecker) {
    this._state = ServiceLoaderState.Initializing;
    this._manifest = null;
    this._services = new Map();
    this._runningServices = new Set();
    this._capabilityChecker = capabilityChecker || null;
    this._failureListener = null;
  }

  /**
   * Current state of the Service Loader
   */
  get state(): ServiceLoaderState {
    return this._state;
  }

  /**
   * Initialize the Service Loader with a manifest
   * @param manifestData - Service manifest data
   */
  async initialize(manifestData: ServiceManifestData): Promise<void> {
    console.log('[ServiceLoader] Initializing...');
    this._state = ServiceLoaderState.Loading;

    try {
      // Create manifest from data
      this._manifest = new ServiceManifestImpl(manifestData.services);

      // Validate manifest
      if (!this._manifest.validate()) {
        throw new Error('Invalid service manifest');
      }

      // Register all services from manifest
      for (const descriptor of this._manifest.services) {
        console.log(`[ServiceLoader] Registered service: ${descriptor.id}`);
      }

      this._state = ServiceLoaderState.Running;
      console.log('[ServiceLoader] Initialized successfully');
    } catch (error) {
      this._state = ServiceLoaderState.Failed;
      const message = error instanceof Error ? error.message : 'Unknown error';
      console.error(`[ServiceLoader] Initialization failed: ${message}`);
      throw error;
    }
  }

  /**
   * Start the Service Loader and all auto-start services
   */
  async start(): Promise<void> {
    if (!this._manifest) {
      throw new Error('Service Loader not initialized. Call initialize() first.');
    }

    console.log('[ServiceLoader] Starting services...');
    this._state = ServiceLoaderState.Running;

    try {
      // Get auto-start services
      const autoStartServices = this._manifest.getAutoStartServices();

      // Sort services by dependencies (topological sort)
      const sortedServices = this.topologicalSort(autoStartServices);

      // Start each service in order
      for (const descriptor of sortedServices) {
        await this.startService(descriptor.id);
      }

      console.log('[ServiceLoader] All services started');
    } catch (error) {
      this._state = ServiceLoaderState.Failed;
      const message = error instanceof Error ? error.message : 'Unknown error';
      console.error(`[ServiceLoader] Failed to start services: ${message}`);
      throw error;
    }
  }

  /**
   * Stop the Service Loader and all managed services
   */
  async stop(): Promise<void> {
    console.log('[ServiceLoader] Stopping all services...');

    try {
      // Stop all services in reverse order
      const serviceIds = Array.from(this._services.keys());
      for (const serviceId of serviceIds.reverse()) {
        await this.stopService(serviceId);
      }

      this._state = ServiceLoaderState.Finished;
      console.log('[ServiceLoader] All services stopped');
    } catch (error) {
      this._state = ServiceLoaderState.Failed;
      const message = error instanceof Error ? error.message : 'Unknown error';
      console.error(`[ServiceLoader] Error during shutdown: ${message}`);
      throw error;
    }
  }

  /**
   * Get current state summary
   */
  getState(): ServiceLoaderState {
    return this._state;
  }

  /**
   * Get count of managed services
   */
  getServiceCount(): number {
    return this._services.size;
  }

  /**
   * Set failure event listener
   * @param listener - Function to call on service failure
   */
  setFailureListener(listener: (event: ServiceFailureEvent) => void): void {
    this._failureListener = listener;
  }

  /**
   * Start a specific service
   * @param serviceId - Service ID to start
   */
  async startService(serviceId: string): Promise<void> {
    if (!this._manifest) {
      throw new Error('Service Loader not initialized');
    }

    const descriptor = this._manifest.getService(serviceId);
    if (!descriptor) {
      throw new Error(`Service not found: ${serviceId}`);
    }

    // Check if already running
    if (this._runningServices.has(serviceId)) {
      console.log(`[ServiceLoader] Service ${serviceId} is already running`);
      return;
    }

    // Check requirements
    if (!this.checkRequirements(descriptor.requirements)) {
      console.warn(
        `[ServiceLoader] Service ${serviceId} requirements not met. Skipping.`
      );
      return;
    }

    // Check dependencies
    if (!descriptor.areDependenciesSatisfied(this._runningServices)) {
      console.log(
        `[ServiceLoader] Service ${serviceId} waiting for dependencies...`
      );
      this._state = ServiceLoaderState.WaitingDependency;
      
      // Wait for dependencies
      await this.waitForDependencies(descriptor);
    }

    // Get or create service instance
    let managedService = this._services.get(serviceId);
    if (!managedService) {
      throw new Error(`Service instance not found: ${serviceId}`);
    }

    try {
      // Initialize service
      managedService.lifecycle.transition(ServiceState.Initializing);
      await managedService.service.initialize();

      // Start service
      managedService.lifecycle.transition(ServiceState.Starting);
      await managedService.service.start();
      managedService.lifecycle.transition(ServiceState.Running);

      this._runningServices.add(serviceId);
      console.log(`[ServiceLoader] Service ${serviceId} started successfully`);
    } catch (error) {
      managedService.lifecycle.transition(ServiceState.Failed);
      
      // Handle failure based on service type
      await this.handleServiceFailure(serviceId, error);
      throw error;
    }
  }

  /**
   * Stop a specific service
   * @param serviceId - Service ID to stop
   */
  async stopService(serviceId: string): Promise<void> {
    const managedService = this._services.get(serviceId);
    if (!managedService) {
      console.warn(`[ServiceLoader] Service ${serviceId} not found`);
      return;
    }

    try {
      managedService.lifecycle.transition(ServiceState.Stopping);
      await managedService.service.stop();
      managedService.lifecycle.transition(ServiceState.Stopped);

      this._runningServices.delete(serviceId);
      console.log(`[ServiceLoader] Service ${serviceId} stopped`);
    } catch (error) {
      managedService.lifecycle.transition(ServiceState.Failed);
      const message = error instanceof Error ? error.message : 'Unknown error';
      console.error(`[ServiceLoader] Error stopping ${serviceId}: ${message}`);
      throw error;
    }
  }

  /**
   * Register a service with the Service Loader
   * @param service - Service instance
   * @param descriptor - Service descriptor
   */
  registerService(
    service: IService,
    descriptor: import('../manifest').ServiceDescriptorImpl
  ): void {
    const lifecycle = new ServiceLifecycle(ServiceState.Initializing);
    this._services.set(service.id, {
      service,
      lifecycle,
      descriptor
    });
    console.log(`[ServiceLoader] Registered service instance: ${service.id}`);
  }

  /**
   * Topological sort of services based on dependencies
   * @param services - Array of service descriptors
   * @returns Sorted array of service descriptors
   */
  private topologicalSort(
    services: import('../interfaces').IServiceDescriptor[]
  ): import('../interfaces').IServiceDescriptor[] {
    const sorted: import('../interfaces').IServiceDescriptor[] = [];
    const visited = new Set<string>();
    const visiting = new Set<string>();

    const visit = (descriptor: import('../interfaces').IServiceDescriptor): void => {
      if (visited.has(descriptor.id)) {
        return;
      }

      if (visiting.has(descriptor.id)) {
        throw new Error(`Circular dependency detected involving ${descriptor.id}`);
      }

      visiting.add(descriptor.id);

      // Visit dependencies first
      for (const dep of descriptor.dependencies) {
        const depDescriptor = this._manifest?.getService(dep.serviceId);
        if (depDescriptor && dep.required) {
          visit(depDescriptor);
        }
      }

      visiting.delete(descriptor.id);
      visited.add(descriptor.id);
      sorted.push(descriptor);
    };

    services.forEach(visit);
    return sorted;
  }

  /**
   * Check if service requirements are met
   * @param requirements - List of required capabilities
   * @returns true if all requirements are met
   */
  private checkRequirements(requirements: string[]): boolean {
    if (requirements.length === 0) {
      return true;
    }

    if (!this._capabilityChecker) {
      // If no capability checker, assume all requirements are met
      return true;
    }

    return this._capabilityChecker.hasAllCapabilities(requirements);
  }

  /**
   * Wait for service dependencies to be satisfied
   * @param descriptor - Service descriptor
   */
  private async waitForDependencies(
    descriptor: import('../manifest').ServiceDescriptorImpl
  ): Promise<void> {
    const timeout = 30000; // 30 second timeout
    const interval = 100; // Check every 100ms
    let elapsed = 0;

    while (elapsed < timeout) {
      if (descriptor.areDependenciesSatisfied(this._runningServices)) {
        return;
      }
      await new Promise(resolve => setTimeout(resolve, interval));
      elapsed += interval;
    }

    throw new Error(
      `Timeout waiting for dependencies of service ${descriptor.id}`
    );
  }

  /**
   * Handle service failure
   * @param serviceId - Service ID that failed
   * @param error - Error that occurred
   */
  private async handleServiceFailure(serviceId: string, error: unknown): Promise<void> {
    const managedService = this._services.get(serviceId);
    if (!managedService) {
      return;
    }

    const { descriptor } = managedService;
    const restartPolicy = descriptor.restartPolicy;

    // Ephemeral services don't restart on normal completion
    if (descriptor.type === ServiceType.Ephemeral) {
      console.log(
        `[ServiceLoader] Ephemeral service ${serviceId} finished normally`
      );
      managedService.lifecycle.transition(ServiceState.Finished);
      this._runningServices.delete(serviceId);
      return;
    }

    // Check if restart is allowed
    if (restartPolicy.canRetry()) {
      this._state = ServiceLoaderState.Restarting;
      restartPolicy.incrementAttempt();

      // Wait before retry
      const delay = restartPolicy.getNextDelay();
      console.log(
        `[ServiceLoader] Retrying ${serviceId} in ${delay}ms (attempt ${restartPolicy.currentAttempt}/${restartPolicy.maxAttempts})`
      );

      await new Promise(resolve => setTimeout(resolve, delay));

      try {
        await this.startService(serviceId);
      } catch (retryError) {
        await this.handleServiceFailure(serviceId, retryError);
      }
    } else {
      // Max attempts reached - publish failure event
      console.error(
        `[ServiceLoader] Service ${serviceId} failed after ${restartPolicy.maxAttempts} attempts`
      );

      const failureEvent: ServiceFailureEvent = {
        serviceId,
        error: error instanceof Error ? error.message : 'Unknown error',
        attempts: restartPolicy.maxAttempts,
        timestamp: Date.now()
      };

      if (this._failureListener) {
        this._failureListener(failureEvent);
      }

      this._runningServices.delete(serviceId);
    }
  }
}
