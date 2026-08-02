/**
 * Node Selection - Handles node filtering and selection
 *
 * This component provides utilities for filtering nodes by capability
 * and capacity, and selecting the best node from candidates.
 */

import { INodeSelection } from '../interfaces';
import { NodeInfo, Capability } from '../types';
import { CapabilityMatcher } from '../matcher';

export class NodeSelection implements INodeSelection {
  private capabilityMatcher: CapabilityMatcher;

  constructor() {
    this.capabilityMatcher = new CapabilityMatcher();
  }

  /**
   * Filter nodes by required capabilities
   * @param nodes - List of nodes to filter
   * @param required - Required capabilities
   * @returns Nodes that have all required capabilities
   */
  filterByCapability(nodes: NodeInfo[], required: Capability[]): NodeInfo[] {
    if (!nodes || nodes.length === 0) {
      return [];
    }

    return nodes.filter(node => 
      this.capabilityMatcher.matches(node.capabilities, required)
    );
  }

  /**
   * Filter nodes by available capacity
   * @param nodes - List of nodes to filter
   * @returns Nodes that have capacity for new tasks
   */
  filterByCapacity(nodes: NodeInfo[]): NodeInfo[] {
    if (!nodes || nodes.length === 0) {
      return [];
    }

    return nodes.filter(node => 
      node.available && 
      node.capacity.hasCapacity
    );
  }

  /**
   * Select the first node from a list
   * @param nodes - List of nodes
   * @returns First node or null if list is empty
   */
  selectFirst(nodes: NodeInfo[]): NodeInfo | null {
    if (!nodes || nodes.length === 0) {
      return null;
    }

    return nodes[0];
  }

  /**
   * Select best node from candidates using the standard criteria:
   * 1. Compatible capability
   * 2. Available capacity
   * 3. First available node
   * 
   * @param nodes - List of candidate nodes
   * @param requiredCapabilities - Capabilities required by task
   * @returns Selected node or null if none suitable
   */
  selectBest(
    nodes: NodeInfo[], 
    requiredCapabilities: Capability[]
  ): NodeInfo | null {
    if (!nodes || nodes.length === 0) {
      return null;
    }

    // Step 1: Filter by capability
    const capableNodes = this.filterByCapability(nodes, requiredCapabilities);
    
    if (capableNodes.length === 0) {
      return null;
    }

    // Step 2: Filter by capacity
    const availableNodes = this.filterByCapacity(capableNodes);
    
    if (availableNodes.length === 0) {
      return null;
    }

    // Step 3: Select first available
    return this.selectFirst(availableNodes);
  }
}
