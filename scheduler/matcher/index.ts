/**
 * Capability Matcher - Handles capability matching logic
 *
 * This component is responsible for matching task requirements
 * against node capabilities. It knows nothing about business logic.
 */

import { ICapabilityMatcher } from '../interfaces';
import { Capability } from '../types';

export class CapabilityMatcher implements ICapabilityMatcher {
  /**
   * Check if node capabilities match task requirements
   * @param nodeCapabilities - Capabilities available on the node
   * @param taskRequirements - Capabilities required by the task
   * @returns True if all requirements are met
   */
  matches(nodeCapabilities: Capability[], taskRequirements: Capability[]): boolean {
    // If no requirements, everything matches
    if (!taskRequirements || taskRequirements.length === 0) {
      return true;
    }

    // If no capabilities but there are requirements, cannot match
    if (!nodeCapabilities || nodeCapabilities.length === 0) {
      return taskRequirements.length === 0;
    }

    // Check each required capability exists in node capabilities
    for (const required of taskRequirements) {
      const found = nodeCapabilities.some(cap => 
        cap.name === required.name && 
        this.versionMatches(cap.version, required.version)
      );

      if (!found) {
        return false;
      }
    }

    return true;
  }

  /**
   * Get missing capabilities
   * @param nodeCapabilities - Capabilities available on the node
   * @param taskRequirements - Capabilities required by the task
   * @returns List of missing capabilities
   */
  missingCapabilities(
    nodeCapabilities: Capability[],
    taskRequirements: Capability[]
  ): Capability[] {
    if (!taskRequirements || taskRequirements.length === 0) {
      return [];
    }

    if (!nodeCapabilities || nodeCapabilities.length === 0) {
      return [...taskRequirements];
    }

    const missing: Capability[] = [];

    for (const required of taskRequirements) {
      const found = nodeCapabilities.some(cap => 
        cap.name === required.name && 
        this.versionMatches(cap.version, required.version)
      );

      if (!found) {
        missing.push(required);
      }
    }

    return missing;
  }

  /**
   * Check if versions match (simple version comparison)
   * @param nodeVersion - Version available on node
   * @param requiredVersion - Version required by task
   * @returns True if versions are compatible
   */
  private versionMatches(nodeVersion?: string, requiredVersion?: string): boolean {
    // If no version specified, assume compatible
    if (!requiredVersion) {
      return true;
    }

    // If node has no version but task requires one, not compatible
    if (!nodeVersion) {
      return false;
    }

    // Simple exact match for now
    // Can be extended for semver comparison in the future
    return nodeVersion === requiredVersion;
  }
}
