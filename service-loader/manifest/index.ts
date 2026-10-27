/**
 * Service Manifest - Manages service definitions from a manifest
 */

import type { IServiceManifest, IServiceDescriptor, IServiceDependency } from '../interfaces';
import type { ServiceDescriptor as ServiceDescriptorData, ServiceType } from '../types';
import { RestartPolicy } from '../policy';

/**
 * ServiceDependency - Concrete implementation of IServiceDependency
 */
class ServiceDependency implements IServiceDependency {
  private _serviceId: string;
  private _required: boolean;

  constructor(serviceId: string, required: boolean = true) {
    this._serviceId = serviceId;
    this._required = required;
  }

  /**
   * Service ID this dependency refers to
   */
  get serviceId(): string {
    return this._serviceId;
  }

  /**
   * Whether this dependency is required (vs optional)
   */
  get required(): boolean {
    return this._required;
  }

  /**
   * Check if this dependency is satisfied
   * @param runningServices - Set of running service IDs
   * @returns true if dependency is satisfied
   */
  isSatisfied(runningServices: Set<string>): boolean {
    // Optional dependencies are always satisfied
    if (!this._required) {
      return true;
    }
    return runningServices.has(this._serviceId);
  }
}

/**
 * ServiceDescriptor - Concrete implementation of IServiceDescriptor
 */
export class ServiceDescriptorImpl implements IServiceDescriptor {
  private _id: string;
  private _name: string;
  private _type: ServiceType;
  private _dependencies: IServiceDependency[];
  private _requirements: string[];
  private _restartPolicy: RestartPolicy;
  private _autoStart: boolean;

  constructor(data: ServiceDescriptorData) {
    this._id = data.id;
    this._name = data.name;
    this._type = data.type;
    this._requirements = data.requirements || [];
    this._autoStart = data.autoStart ?? false;
    
    // Convert dependencies to IServiceDependency array
    this._dependencies = (data.dependencies || []).map(
      depId => new ServiceDependency(depId, true)
    );
    
    // Create restart policy from config
    this._restartPolicy = new RestartPolicy(data.restartPolicy);
  }

  /**
   * Unique service identifier
   */
  get id(): string {
    return this._id;
  }

  /**
   * Service name
   */
  get name(): string {
    return this._name;
  }

  /**
   * Type of service
   */
  get type(): ServiceType {
    return this._type;
  }

  /**
   * Service dependencies
   */
  get dependencies(): IServiceDependency[] {
    return [...this._dependencies];
  }

  /**
   * Required capabilities
   */
  get requirements(): string[] {
    return [...this._requirements];
  }

  /**
   * Restart policy
   */
  get restartPolicy(): RestartPolicy {
    return this._restartPolicy;
  }

  /**
   * Whether the service should start automatically
   */
  get autoStart(): boolean {
    return this._autoStart;
  }

  /**
   * Check if all dependencies are satisfied
   * @param runningServices - Set of running service IDs
   * @returns true if all dependencies are satisfied
   */
  areDependenciesSatisfied(runningServices: Set<string> = new Set()): boolean {
    return this._dependencies.every(dep => dep.isSatisfied(runningServices));
  }

  /**
   * Check if all requirements are met
   * @param availableCapabilities - List of available capability IDs
   * @returns true if all requirements are met
   */
  areRequirementsMet(availableCapabilities: string[]): boolean {
    if (this._requirements.length === 0) {
      return true;
    }
    return this._requirements.every(req => 
      availableCapabilities.includes(req)
    );
  }

  /**
   * Add a dependency
   * @param serviceId - Service ID to depend on
   * @param required - Whether this dependency is required
   */
  addDependency(serviceId: string, required: boolean = true): void {
    this._dependencies.push(new ServiceDependency(serviceId, required));
  }
}

/**
 * ServiceManifest - Concrete implementation of IServiceManifest
 */
export class ServiceManifestImpl implements IServiceManifest {
  private _descriptors: Map<string, ServiceDescriptorImpl>;

  constructor(services: ServiceDescriptorData[]) {
    this._descriptors = new Map();
    services.forEach(service => {
      const descriptor = new ServiceDescriptorImpl(service);
      this._descriptors.set(descriptor.id, descriptor);
    });
  }

  /**
   * Get all service descriptors
   */
  get services(): IServiceDescriptor[] {
    return Array.from(this._descriptors.values());
  }

  /**
   * Validate the manifest
   * @returns true if manifest is valid
   */
  validate(): boolean {
    // Check for duplicate IDs
    const ids = new Set<string>();
    for (const descriptor of this._descriptors.values()) {
      if (ids.has(descriptor.id)) {
        console.error(`[ServiceManifest] Duplicate service ID: ${descriptor.id}`);
        return false;
      }
      ids.add(descriptor.id);
    }

    // Check for circular dependencies
    if (!this.checkCircularDependencies()) {
      console.error('[ServiceManifest] Circular dependencies detected');
      return false;
    }

    return true;
  }

  /**
   * Get service descriptor by ID
   * @param id - Service ID
   * @returns Service descriptor or undefined
   */
  getService(id: string): IServiceDescriptor | undefined {
    return this._descriptors.get(id);
  }

  /**
   * Get all services that should auto-start
   * @returns Array of auto-start service descriptors
   */
  getAutoStartServices(): IServiceDescriptor[] {
    return this.services.filter(s => s.autoStart);
  }

  /**
   * Check for circular dependencies using DFS
   * @returns true if no circular dependencies found
   */
  private checkCircularDependencies(): boolean {
    const visited = new Set<string>();
    const recursionStack = new Set<string>();

    const hasCycle = (serviceId: string): boolean => {
      if (recursionStack.has(serviceId)) {
        return true;
      }

      if (visited.has(serviceId)) {
        return false;
      }

      visited.add(serviceId);
      recursionStack.add(serviceId);

      const descriptor = this._descriptors.get(serviceId);
      if (descriptor) {
        for (const dep of descriptor.dependencies) {
          if (hasCycle(dep.serviceId)) {
            return true;
          }
        }
      }

      recursionStack.delete(serviceId);
      return false;
    };

    for (const serviceId of this._descriptors.keys()) {
      if (hasCycle(serviceId)) {
        return false;
      }
    }

    return true;
  }

  /**
   * Get service count
   * @returns Number of services in manifest
   */
  count(): number {
    return this._descriptors.size;
  }
}
