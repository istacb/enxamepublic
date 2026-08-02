/**
 * Resource Allocator Implementation
 * 
 * Gerencia alocação e liberação de recursos locais.
 */

import type { IResourceAllocator, RequiredCapability } from '../interfaces';
import {
  ResourceAllocationError,
  ResourceReleaseError,
  CapabilityNotAvailableError,
} from '../errors';

export class ResourceAllocator implements IResourceAllocator {
  private allocatedResources: Map<string, Set<string>>; // taskId -> Set<resourceId>
  private availableCapacity: number;
  private maxCapacity: number;

  constructor(maxCapacity: number = 4) {
    this.maxCapacity = maxCapacity;
    this.availableCapacity = maxCapacity;
    this.allocatedResources = new Map();
  }

  /**
   * Aloca recursos necessários para uma execução
   */
  public async allocate(
    requiredCapabilities: RequiredCapability[],
    taskId: string
  ): Promise<string[]> {
    // Verifica disponibilidade
    if (!this.checkAvailability(requiredCapabilities)) {
      throw new CapabilityNotAvailableError(
        'Required capabilities not available',
        requiredCapabilities[0]?.type || 'unknown'
      );
    }

    // Verifica capacidade
    if (this.availableCapacity <= 0) {
      throw new ResourceAllocationError(
        'No capacity available for resource allocation',
        taskId
      );
    }

    const allocatedIds: string[] = [];

    try {
      // Aloca recursos simulados
      for (const capability of requiredCapabilities) {
        const resourceId = `${capability.type}-${taskId}-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
        allocatedIds.push(resourceId);
      }

      // Registra alocação por Task
      this.allocatedResources.set(taskId, new Set(allocatedIds));

      // Decrementa capacidade disponível
      this.availableCapacity--;

      return allocatedIds;
    } catch (error) {
      // Rollback em caso de falha
      await this.release(allocatedIds, taskId);
      throw error;
    }
  }

  /**
   * Libera recursos previamente alocados
   */
  public async release(
    resourceIds: string[],
    taskId: string
  ): Promise<void> {
    try {
      const taskResources = this.allocatedResources.get(taskId);

      if (taskResources) {
        for (const resourceId of resourceIds) {
          taskResources.delete(resourceId);
        }

        // Se não há mais recursos para esta Task, remove entry
        if (taskResources.size === 0) {
          this.allocatedResources.delete(taskId);
          this.availableCapacity++;
        }
      }
    } catch (error) {
      throw new ResourceReleaseError(
        `Failed to release resources: ${error instanceof Error ? error.message : String(error)}`,
        resourceIds[0]
      );
    }
  }

  /**
   * Verifica disponibilidade de capacidades
   */
  public checkAvailability(requiredCapabilities: RequiredCapability[]): boolean {
    // Verificação simplificada
    // Em implementação real, verificaria cada capability específica

    if (requiredCapabilities.length === 0) {
      return true;
    }

    // Verifica se há capacidade disponível
    return this.availableCapacity > 0;
  }

  /**
   * Obtém capacidade atual disponível
   */
  public getAvailableCapacity(): number {
    return this.availableCapacity;
  }

  /**
   * Libera todos os recursos de uma Task
   */
  public async releaseAllByTask(taskId: string): Promise<void> {
    const taskResources = this.allocatedResources.get(taskId);

    if (taskResources) {
      const resourceIds = Array.from(taskResources);
      await this.release(resourceIds, taskId);
    }
  }

  /**
   * Obtém número total de recursos alocados
   */
  public getTotalAllocated(): number {
    let total = 0;
    for (const resources of this.allocatedResources.values()) {
      total += resources.size;
    }
    return total;
  }

  /**
   * Reseta o allocator (apenas para testes)
   */
  public reset(): void {
    this.allocatedResources.clear();
    this.availableCapacity = this.maxCapacity;
  }
}
