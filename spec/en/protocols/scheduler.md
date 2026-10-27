# Scheduler Protocol Specification

**Version:** 1.0.0  
**Status:** Draft  
**PR:** 4.7  
**Sprint:** 4

---

## 1. Objective

Define the Scheduler as an internal component of the Orchestrator responsible for deciding which Node should execute a Task.

The Scheduler never executes Tasks.

The Scheduler never communicates directly with Nodes.

The Scheduler only analyzes the current state of the Enxame and returns to the Orchestrator the best scheduling decision.

---

## 2. Philosophy

The Scheduler must be:

- **Simple**: Easy to understand and implement.
- **Deterministic**: Predictable decisions based on available data.
- **Event-Oriented**: Triggered by events, not polling.
- **Decoupled**: Independent from other components.
- **Efficient**: Minimal resource consumption.
- **Legacy-Compatible**: Compatible with old hardware.

Every decision must be based exclusively on available information.

No decision should use complex heuristics or AI.

---

## 3. Single Responsibility

The Scheduler has only one responsibility:

**Select the best Node to execute a Task.**

Everything else belongs to the Orchestrator.

---

## 4. Information Source

The Scheduler utilizes exclusively information maintained by the Orchestrator.

Examples:

- Node Registry;
- Discovery;
- Heartbeat;
- Task Queue.

The Scheduler never queries a Node directly.

---

## 5. Events

The Scheduler is event-oriented.

It is executed when any event occurs that may alter scheduling.

Examples:

- New Task arrives.
- Runtime Available.
- New Node registered.
- Node removed.
- Capability changed.
- Failover return.

The Scheduler never uses polling.

---

## 6. Queue

The Scheduler administers the Task queue.

When a new Task arrives:

- Immediately verifies network availability;
- If a compatible Node is available, schedule immediately;
- Otherwise, place the Task in the queue.

When a Runtime becomes available:

- Immediately checks the queue;
- Selects the next compatible Task;
- Schedules execution.

### 6.1 Queue Order

The initial policy will be **FIFO (First In, First Out)**.

The first Task to enter the queue will be the first to be scheduled.

Do not implement priorities in this PR.

The architecture must allow future policies without altering the core Scheduler.

---

## 7. Scheduling Process

Mandatory flow:

```
Receive Task
    ↓
Filter compatible Nodes
    ↓
Remove unavailable Nodes
    ↓
Does an available Node exist?
    ↓
No
    ↓
Queue
    ↓
Yes
    ↓
Select Node
    ↓
Return decision to Orchestrator
```

---

## 8. Selection Criteria

Selection must follow this order:

1. **Compatible Capability**.
2. **Available Capacity**.
3. **First available Node**.

If multiple equivalent Nodes exist:

Select the first available.

The architecture must allow future balancing algorithms without altering the public interface.

### 8.1 Capability Matching

A Task may only be sent to a Node that possesses all necessary Capabilities.

If no Node possesses the required Capabilities:

The Task remains in the queue.

### 8.2 Capacity

Capacity represents the available capacity to receive new Tasks.

If the Node is busy:

It does not participate in scheduling.

### 8.3 GPU and Exclusive Resources

If a Task requires an exclusive resource currently occupied:

The Scheduler does not divide the Task.

The Scheduler does not search for artificial alternatives.

The Task remains in the queue until availability exists.

---

## 9. Tasks

The Scheduler works exclusively with Tasks.

Mission belongs to the Orchestrator.

Workflow belongs to the Orchestrator.

The Scheduler never interprets Missions.

The Scheduler never modifies Workflows.

---

## 10. Communication

The Scheduler never communicates directly with Nodes.

All communication occurs exclusively through the Orchestrator utilizing the official Communication Protocol.

Refer to the [Communication Protocol Specification](./communication-protocol.md).

---

## 11. Interfaces

Create decoupled interfaces for:

- `IScheduler`
- `ISchedulingPolicy`
- `ITaskQueue`
- `ISchedulingDecision`
- `INodeSelection`
- `ICapabilityMatcher`

### 11.1 IScheduler

```typescript
interface IScheduler {
  scheduleTask(task: Task): Promise<ISchedulingDecision>;
  onNodeRegistered(node: NodeInfo): void;
  onNodeRemoved(nodeId: string): void;
  onRuntimeAvailable(nodeId: string): void;
  onCapabilityChanged(nodeId: string, capabilities: Capability[]): void;
  getQueueStatus(): QueueStatus;
}
```

### 11.2 ISchedulingPolicy

```typescript
interface ISchedulingPolicy {
  name: string;
  selectNode(candidates: NodeInfo[], task: Task): NodeInfo | null;
  reorderQueue(queue: Task[]): Task[];
}
```

### 11.3 ITaskQueue

```typescript
interface ITaskQueue {
  enqueue(task: Task): void;
  dequeue(): Task | null;
  peek(): Task | null;
  size(): number;
  isEmpty(): boolean;
  filterByCapability(capabilities: Capability[]): Task[];
}
```

### 11.4 ISchedulingDecision

```typescript
interface ISchedulingDecision {
  taskId: string;
  nodeId: string | null;
  status: 'scheduled' | 'queued' | 'rejected';
  reason?: string;
  timestamp: number;
}
```

### 11.5 INodeSelection

```typescript
interface INodeSelection {
  filterByCapability(nodes: NodeInfo[], required: Capability[]): NodeInfo[];
  filterByCapacity(nodes: NodeInfo[]): NodeInfo[];
  selectFirst(nodes: NodeInfo[]): NodeInfo | null;
}
```

### 11.6 ICapabilityMatcher

```typescript
interface ICapabilityMatcher {
  matches(nodeCapabilities: Capability[], taskRequirements: Capability[]): boolean;
  missingCapabilities(nodeCapabilities: Capability[], taskRequirements: Capability[]): Capability[];
}
```

---

## 12. What the Scheduler Does NOT Do

- Does not execute Tasks.
- Does not create Agents.
- Does not know AI.
- Does not perform Discovery.
- Does not send Heartbeats.
- Does not perform Failover.
- Does not communicate directly with Nodes.
- Does not query Runtime directly.
- Does not implement polling.
- Does not implement Logging.

---

## 13. Acceptance Criteria

This specification is considered complete when:

1. The Scheduler has single responsibility.
2. Works exclusively over Tasks.
3. Utilizes only information from the Orchestrator.
4. Correctly administers the queue.
5. Is event-oriented.
6. Does not use polling.
7. Does not communicate directly with Nodes.
8. Utilizes exclusively the official protocol.
9. Possesses documentation in English and Portuguese.

---

## 14. References

- **EIP-0001**: Architecture First
- **EIP-0002**: Resource First Architecture
- **Communication Protocol**: PR 4.3
- **Orchestrator**: Internal Component
- **Service Loader**: PR 4.6

---

## 15. History

| Date | Version | Author | Description |
| :--- | :--- | :--- | :--- |
| 2024-XX-XX | 1.0.0 | Architect | Initial Draft for PR 4.7 |

