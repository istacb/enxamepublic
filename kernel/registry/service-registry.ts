/**
 * Service Registry - Manages registered Services
 * 
 * Implements the IServiceRegistry interface.
 * The Service Registry is responsible for maintaining references
 * to registered Services. It does NOT execute services.
 */

import type { IServiceRegistry, IService, RegistrationResult, IKernel } from '../interfaces';
import { ServiceNotFoundError, ServiceRegistrationError, ServiceStartError, ServiceStopError } from '../errors';

/**
 * ServiceRegistry - Concrete implementation of IServiceRegistry
 */
export class ServiceRegistry implements IServiceRegistry {
  private _services: Map<string, IService>;
  private _kernel: IKernel | null = null;

  constructor() {
    this._services = new Map();
  }

  /**
   * Set the kernel reference (called by Kernel during initialization)
   * @param kernel - The kernel instance
   */
  setKernel(kernel: IKernel): void {
    this._kernel = kernel;
  }

  /**
   * Register a service
   * @param service - Service to register
   * @returns Registration result
   */
  async register(service: IService): Promise<RegistrationResult> {
    if (this._services.has(service.id)) {
      return {
        success: false,
        serviceId: service.id,
        error: `Service '${service.id}' is already registered`
      };
    }

    try {
      // Initialize the service if kernel is available
      if (this._kernel) {
        await service.initialize(this._kernel);
      }

      this._services.set(service.id, service);
      
      return {
        success: true,
        serviceId: service.id
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      throw new ServiceRegistrationError(service.id, message);
    }
  }

  /**
   * Unregister a service
   * @param serviceId - ID of service to unregister
   * @returns true if service was unregistered
   */
  async unregister(serviceId: string): Promise<boolean> {
    const service = this._services.get(serviceId);
    
    if (!service) {
      return false;
    }

    try {
      // Stop the service if it's running
      await service.stop();
    } catch (error) {
      console.error(`[ServiceRegistry] Error stopping service '${serviceId}':`, error);
    }

    this._services.delete(serviceId);
    return true;
  }

  /**
   * Get a service by ID
   * @param serviceId - Service identifier
   * @returns Service instance or undefined
   */
  get(serviceId: string): IService | undefined {
    return this._services.get(serviceId);
  }

  /**
   * Get all registered services
   * @returns Iterable of services
   */
  getAll(): Iterable<IService> {
    return this._services.values();
  }

  /**
   * Check if a service is registered
   * @param serviceId - Service identifier
   * @returns true if service is registered
   */
  has(serviceId: string): boolean {
    return this._services.has(serviceId);
  }

  /**
   * Get count of registered services
   * @returns Number of registered services
   */
  count(): number {
    return this._services.size;
  }

  /**
   * Start a specific service
   * @param serviceId - Service identifier
   * @throws ServiceNotFoundError if service not found
   * @throws ServiceStartError if service fails to start
   */
  async startService(serviceId: string): Promise<void> {
    const service = this._services.get(serviceId);
    
    if (!service) {
      throw new ServiceNotFoundError(serviceId);
    }

    try {
      await service.start();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      throw new ServiceStartError(serviceId, message);
    }
  }

  /**
   * Stop a specific service
   * @param serviceId - Service identifier
   * @throws ServiceNotFoundError if service not found
   * @throws ServiceStopError if service fails to stop
   */
  async stopService(serviceId: string): Promise<void> {
    const service = this._services.get(serviceId);
    
    if (!service) {
      throw new ServiceNotFoundError(serviceId);
    }

    try {
      await service.stop();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      throw new ServiceStopError(serviceId, message);
    }
  }

  /**
   * Start all auto-start services
   */
  async startAutoServices(): Promise<void> {
    const promises: Array<Promise<void>> = [];
    
    for (const service of this._services.values()) {
      if (service.autoStart) {
        promises.push(
          service.start().catch(error => {
            console.error(`[ServiceRegistry] Failed to start auto-service '${service.id}':`, error);
          })
        );
      }
    }

    await Promise.all(promises);
  }

  /**
   * Stop all services
   */
  async stopAll(): Promise<void> {
    const promises: Array<Promise<void>> = [];
    
    for (const service of this._services.values()) {
      promises.push(
        service.stop().catch(error => {
          console.error(`[ServiceRegistry] Failed to stop service '${service.id}':`, error);
        })
      );
    }

    await Promise.all(promises);
    this._services.clear();
  }
}
