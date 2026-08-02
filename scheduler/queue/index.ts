/**
 * FIFO Task Queue - First In, First Out queue implementation
 *
 * This is the default queue policy for the Scheduler.
 * Tasks are processed in the order they arrive.
 */

import { ITaskQueue } from '../interfaces';
import { Task, Capability } from '../types';

export class FifoTaskQueue implements ITaskQueue {
  private queue: Task[];

  constructor() {
    this.queue = [];
  }

  /**
   * Add a task to the queue
   * @param task - The task to enqueue
   */
  enqueue(task: Task): void {
    this.queue.push(task);
  }

  /**
   * Remove and return the next task from the queue
   * @returns The next task or null if queue is empty
   */
  dequeue(): Task | null {
    if (this.queue.length === 0) {
      return null;
    }

    return this.queue.shift() || null;
  }

  /**
   * Peek at the next task without removing it
   * @returns The next task or null if queue is empty
   */
  peek(): Task | null {
    if (this.queue.length === 0) {
      return null;
    }

    return this.queue[0] || null;
  }

  /**
   * Get the number of tasks in the queue
   * @returns Queue size
   */
  size(): number {
    return this.queue.length;
  }

  /**
   * Check if the queue is empty
   * @returns True if queue is empty
   */
  isEmpty(): boolean {
    return this.queue.length === 0;
  }

  /**
   * Filter tasks by required capabilities
   * @param capabilities - Required capabilities to match
   * @returns Tasks that can run with given capabilities
   */
  filterByCapability(capabilities: Capability[]): Task[] {
    if (!capabilities || capabilities.length === 0) {
      return [...this.queue];
    }

    return this.queue.filter(task => {
      if (!task.requiredCapabilities || task.requiredCapabilities.length === 0) {
        return true;
      }

      // Check if all task requirements are in the provided capabilities
      return task.requiredCapabilities.every(reqCap =>
        capabilities.some(cap => cap.name === reqCap.name)
      );
    });
  }

  /**
   * Get all tasks in the queue (for inspection)
   * @returns Array of all tasks
   */
  getAll(): Task[] {
    return [...this.queue];
  }

  /**
   * Clear the queue
   */
  clear(): void {
    this.queue = [];
  }
}
