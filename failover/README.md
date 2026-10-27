# Failover Service

## Overview

The Failover service is responsible for detecting unavailability and informing the Orchestrator about failures that may compromise the execution of Tasks, Services, or Nodes.

**Key Principle:** Failover only publishes failure events. It does NOT execute recovery, restart services, or redistribute tasks. All decisions belong to the Orchestrator.

## Installation

```bash
# The failover module is part of the Enxame project
import { createFailoverService, FailureType } from './failover';
```

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
│   Heartbeat     │────▶│              │────▶│ Orchestrator │
│   Service       │     │              │     │              │
│   Loader        │────▶│   Failover   │     │  (decides)   │
│   Orchestrator  │────▶│              │     │              │
└─────────────────┘     └──────────────┘     └──────────────┘
                              │
                              ▼
                       Publish Events
                       (No Recovery)
```

## Usage

### Basic Usage

```typescript
import { createFailoverService, FailureType, TaskRecoveryPolicy } from './failover';

// Create failover service instance
const failover = createFailoverService();

// Report a node failure (when heartbeats stop)
failover.reportNodeFailure({
  nodeId: 'node-123',
  reason: 'Heartbeat timeout exceeded',
  lastHeartbeat: Date.now() - 60000
});

// Report a service failure (after Service Loader exhausts restart attempts)
failover.reportServiceFailure({
  nodeId: 'node-123',
  serviceName: 'Runtime',
  restartAttempts: 5,
  error: 'Service failed to start after 5 attempts'
});

// Report a task failure
failover.reportTaskFailure({
  taskId: 'task-456',
  nodeId: 'node-123',
  recoveryPolicy: TaskRecoveryPolicy.SAFE_RETRY,
  reason: 'Node became unavailable during execution'
});

// Report capability loss
failover.reportCapabilityLoss({
  nodeId: 'node-123',
  capability: 'GPU',
  previouslyAvailable: true
});

// Report communication failure
failover.reportCommunicationFailure({
  nodeId: 'node-123',
  channel: 'heartbeat',
  reason: 'Connection lost'
});

// Report node recovery (after re-discovery and re-registration)
failover.reportNodeRecovery('node-123');
```

### Custom Notifier

```typescript
import { createFailoverService, createFailureNotifier } from './failover';

// Create custom notifier
const customNotifier = createFailureNotifier();

// Subscribe to failure events
customNotifier.subscribe((event) => {
  console.log('Failure event:', event.type, event.id);
  // Send to Orchestrator via official Communication Protocol
});

// Create failover with custom notifier
const failover = createFailoverService(customNotifier);
```

### Event History

```typescript
// Get recent failure events
const recentEvents = failover.getRecentEvents(50);

// Get specific event by ID
const event = failover.getEventById('fail_1234567890_abc123');

// Clear history
failover.clearHistory();
```

## Failure Types

| Type | Description | Source |
|------|-------------|--------|
| `NODE_FAILURE` | Node is unavailable (heartbeat timeout) | Heartbeat/Orchestrator |
| `SERVICE_FAILURE` | Service failed after exhausting restart attempts | Service Loader |
| `TASK_FAILURE` | Task was interrupted | Orchestrator |
| `CAPABILITY_LOSS` | Required capability no longer available | Orchestrator |
| `COMMUNICATION_FAILURE` | Communication channel lost | Orchestrator |

## Task Recovery Policies

Each Task defines its own recovery policy:

- **NEVER_RETRY**: Task should not be retried
- **SAFE_RETRY**: Task can be safely retried from beginning
- **CHECKPOINT**: Task should retry from last checkpoint

Failover only reports the interruption. The Orchestrator decides the action based on the policy.

## What Failover Does NOT Do

❌ Execute Tasks  
❌ Perform Discovery  
❌ Send Heartbeats  
❌ Restart Services  
❌ Restart Nodes  
❌ Schedule Tasks  
❌ Redistribute Tasks  
❌ Alter Missions  
❌ Interpret quality  
❌ Implement Logging  
❌ Perform physical diagnosis  

## Integration with Other Components

### Service Loader
When Service Loader exhausts all restart attempts for a permanent Service, it calls `reportServiceFailure()`.

### Heartbeat
When Heartbeat detects a Node has stopped sending heartbeats, it informs the Orchestrator, which calls `reportNodeFailure()`.

### Scheduler
Failover does NOT interact directly with Scheduler. Failed Tasks return to the queue, and Scheduler decides their new destination.

### Orchestrator
All failure events are published to the Orchestrator, which makes all recovery decisions.

## API Reference

### IFailover

```typescript
interface IFailover {
  reportNodeFailure(data: NodeFailureData): FailureEvent<NodeFailureData>;
  reportServiceFailure(data: ServiceFailureData): FailureEvent<ServiceFailureData>;
  reportTaskFailure(data: TaskFailureData): FailureEvent<TaskFailureData>;
  reportCapabilityLoss(data: CapabilityLossData): FailureEvent<CapabilityLossData>;
  reportCommunicationFailure(data: CommunicationFailureData): FailureEvent<CommunicationFailureData>;
  reportNodeRecovery(nodeId: string): void;
}
```

### IFailureNotifier

```typescript
interface IFailureNotifier {
  publish(event: IFailureEvent): Promise<boolean>;
  subscribe(callback: (event: IFailureEvent) => void): void;
}
```

## Events

All events have:
- Unique ID (`id`)
- Failure type (`type`)
- Timestamp (`timestamp`)
- Source (`source`: ORCHESTRATOR | HEARTBEAT | SERVICE_LOADER)
- Status (`status`: DETECTED | PUBLISHED | RECOVERED)
- Payload data (`data`)

## Philosophy

Failover follows these principles:

- **Simple**: Minimal code, clear responsibilities
- **Lightweight**: Low resource consumption
- **Event-oriented**: Reacts to events, no polling
- **Decoupled**: No direct dependencies on other components
- **Deterministic**: Same input produces same output

Failures are expected events in the architecture, not exceptional conditions.

## License

Part of the Enxame project. See main LICENSE file.
