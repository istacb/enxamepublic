/**
 * FIFO Scheduling Policy - First In, First Out policy implementation
 *
 * This is the default scheduling policy for the Scheduler.
 * Tasks are scheduled in the order they arrive.
 */

import { ISchedulingPolicy } from '../interfaces';
import { NodeInfo, Task } from '../types';

export class FifoSchedulingPolicy implements ISchedulingPolicy {
  readonly name: string = 'FIFO';

  /**
   * Select the best node from candidates for a given task
   * Uses simple first-available strategy for FIFO
   * 
   * @param candidates - List of compatible and available nodes
   * @param task - The task being scheduled
   * @returns Selected node or null if none suitable
   */
  selectNode(candidates: NodeInfo[], _task: Task): NodeInfo | null {
    if (!candidates || candidates.length === 0) {
      return null;
    }

    // FIFO policy: select first available node
    return candidates[0] || null;
  }

  /**
   * Reorder queue according to policy
   * For FIFO, the queue remains in original order
   * 
   * @param queue - Current task queue
   * @returns Reordered task queue (same as input for FIFO)
   */
  reorderQueue(queue: Task[]): Task[] {
    // FIFO maintains insertion order
    return [...queue];
  }
}
