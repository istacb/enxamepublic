# Scheduler

The Scheduler is an internal component of the Orchestrator responsible for deciding which Node should execute a Task.

## Overview

The Scheduler follows these key principles:

- **Never executes Tasks** - It only makes scheduling decisions
- **Never communicates directly with Nodes** - All communication goes through the Orchestrator
- **Event-oriented** - Triggered by events, not polling
- **Simple and deterministic** - Predictable decisions based on available data
- **Efficient** - Minimal resource consumption
- **Legacy-compatible** - Works with old hardware

## Architecture

```
┌─────────────────┐
│  Orchestrator   │
│                 │
│  ┌───────────┐  │
│  │ Scheduler │  │
│  │           │  │
│  │ - Queue   │  │
│  │ - Policy  │  │
│  │ - Matcher │  │
│  │ - Select  │  │
│  └───────────┘  │
└─────────────────┘
       │
       │ Uses info from
       ▼
┌─────────────────┐
│  Node Registry  │
│  Discovery      │
│  Heartbeat      │
│  Task Queue     │
└─────────────────┘
```

## Components

### Types (`types/`)

Core type definitions:
- `Task` - Task definition with capabilities and requirements
- `NodeInfo` - Node information available to Scheduler
- `Capability` - Capability definition
- `SchedulingDecision` - Result of a scheduling attempt
- `SchedulingStatus` - Enum for scheduling outcomes
- `QueuePolicy` - Queue policy enumeration (FIFO)

### Interfaces (`interfaces/`)

Decoupled interfaces:
- `IScheduler` - Main scheduler interface
- `ISchedulingPolicy` - Policy interface for node selection
- `ITaskQueue` - Task queue interface
- `ISchedulingDecision` - Scheduling decision result
- `INodeSelection` - Node selection utilities
- `ICapabilityMatcher` - Capability matching logic

### Queue (`queue/`)

FIFO Task Queue implementation:
- `FifoTaskQueue` - First In, First Out queue

### Policy (`policy/`)

Scheduling policy implementations:
- `FifoSchedulingPolicy` - FIFO scheduling strategy

### Matcher (`matcher/`)

Capability matching:
- `CapabilityMatcher` - Matches task requirements against node capabilities

### Selection (`selection/`)

Node selection utilities:
- `NodeSelection` - Filters and selects nodes based on criteria

### Main Scheduler (`index.ts`)

The main `Scheduler` class implementing `IScheduler`:
- Manages node registry
- Handles task scheduling
- Processes event callbacks
- Maintains task queue

## Usage

```typescript
import { Scheduler } from './scheduler';
import { Task, Capability, NodeInfo } from './scheduler/types';

// Create scheduler instance
const scheduler = new Scheduler();

// Register a node
const node: NodeInfo = {
  id: 'node-1',
  name: 'Worker Node 1',
  capabilities: [
    { name: 'GPU', version: '1.0' },
    { name: 'CPU', version: '2.0' }
  ],
  capacity: { hasCapacity: true, loadPercentage: 0 },
  available: true
};

scheduler.onNodeRegistered(node);

// Schedule a task
const task: Task = {
  id: 'task-1',
  name: 'ML Training',
  requiredCapabilities: [{ name: 'GPU' }],
  createdAt: Date.now()
};

const decision = await scheduler.scheduleTask(task);
console.log(decision); 
// { taskId: 'task-1', nodeId: 'node-1', status: 'scheduled', timestamp: ... }
```

## Events

The Scheduler responds to these events:

| Event | Method | Description |
|-------|--------|-------------|
| Node Registered | `onNodeRegistered()` | New node added to cluster |
| Node Removed | `onNodeRemoved()` | Node removed from cluster |
| Runtime Available | `onRuntimeAvailable()` | Node runtime became available |
| Capability Changed | `onCapabilityChanged()` | Node capabilities updated |

## Scheduling Criteria

The Scheduler uses this order for node selection:

1. **Compatible Capability** - Node must have all required capabilities
2. **Available Capacity** - Node must have capacity for new tasks
3. **First Available** - Select first node that meets criteria

## Queue Behavior

- **Policy**: FIFO (First In, First Out)
- Tasks are queued when no suitable node is available
- Queue is processed automatically when resources become available
- Architecture allows future policies without core changes

## What the Scheduler Does NOT Do

- ❌ Execute Tasks
- ❌ Create Agents
- ❌ Know about AI/ML
- ❌ Perform Discovery
- ❌ Send Heartbeats
- ❌ Perform Failover
- ❌ Communicate directly with Nodes
- ❌ Query Runtime directly
- ❌ Use polling
- ❌ Implement logging

## Acceptance Criteria

- [x] Single responsibility (only selects nodes for tasks)
- [x] Works exclusively with Tasks
- [x] Uses only Orchestrator-provided information
- [x] Correctly manages queue
- [x] Event-oriented (no polling)
- [x] No direct Node communication
- [x] Uses official Communication Protocol
- [x] Documentation in English and Portuguese

## References

- [Scheduler Protocol Specification](../spec/en/protocols/scheduler.md)
- [Especificação do Protocolo Scheduler](../spec/pt-BR/protocols/scheduler.md)
- [Communication Protocol](../spec/en/protocols/communication-protocol.md)
