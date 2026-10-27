# Failover Protocol

## Definition

Failover is the service responsible for detecting unavailability and informing the Orchestrator about failures that may compromise the execution of Tasks, Services, or Nodes.

Failover does not execute recovery.

Failover does not restart Services.

Failover does not redistribute Tasks.

Failover only publishes failure events.

All decisions belong to the Orchestrator.

## Philosophy

Failover must be:

- simple;
- lightweight;
- event-oriented;
- decoupled;
- deterministic.

Failures are expected events in the architecture.

## Single Responsibility

Failover has only one responsibility:

Report unavailability.

All recovery belongs to other components of the architecture.

## Failure Sources

Failover can receive events from:

- Orchestrator;
- Heartbeat;
- Service Loader.

It does not perform its own monitoring.

It does not execute polling.

## Failure Types

At minimum:

- Service Failure
- Node Failure
- Communication Failure
- Capability Loss
- Task Failure

Each event must have clear identification.

## Node Failure

When the Orchestrator stops receiving Heartbeats within the configured limit:

The Node will be considered unavailable.

Failover publishes the corresponding event.

The Scheduler and Orchestrator will decide how to proceed.

## Service Failure

When the Service Loader exhausts all restart attempts:

Publish failure event.

Do not attempt additional recovery.

## Task Failure

Each Task defines its own recovery policy.

Examples:

- Never Retry
- Safe Retry
- Checkpoint

Failover only informs that the Task was interrupted.

The decision belongs to the Orchestrator.

## Mission

The loss of a Node never implies automatic cancellation of the Mission.

As long as sufficient resources exist, the Mission should continue.

The Judge may evaluate the impact of the loss on Mission quality.

## Redistribution

Failover never redistributes Tasks.

When necessary:

Tasks return to the queue.

They maintain their original position.

The Scheduler will decide the new destination.

## Node Return

When a Node returns after a failure:

It will execute the official Discovery process again.

It will be treated as available only after new registration with the Orchestrator.

No previous Task will be automatically reassociated.

## Communication

All communication must use exclusively the official Communication Protocol.

Do not create new protocols.

Do not create new envelopes.

## Interfaces

Create decoupled interfaces for:

- IFailover
- IFailureEvent
- IFailureType
- IFailureNotifier
- INodeFailure
- IServiceFailure
- ITaskFailure

## What Failover Does Not Do

- Does not execute Tasks.
- Does not perform Discovery.
- Does not send Heartbeats.
- Does not restart Services.
- Does not restart Nodes.
- Does not schedule Tasks.
- Does not alter Missions.
- Does not interpret quality.
- Does not implement Logging.
- Does not perform physical diagnosis.

## Events

Minimum examples:

- Node Lost
- Node Recovered
- Service Failed
- Task Interrupted
- Capability Lost
- Communication Lost

Each event must have unique identification and timestamp.

## Acceptance Criteria

The PR will be considered complete when:

- Failover has single responsibility.
- Uses exclusively events.
- Does not perform polling.
- Does not execute recovery.
- Does not redistribute Tasks.
- Works exclusively through the Orchestrator.
- Uses the official protocol.
- Has documentation in English and Portuguese.

## Restrictions

- Do not modify Runtime.
- Do not modify Scheduler.
- Do not modify Heartbeat.
- Do not modify Discovery.
- Do not alter existing EIPs.
- Do not create new protocols.
- Do not modify existing documents.
- Add only documents and implementation related to Failover.

Prioritize simplicity, decoupling, and compatibility with legacy hardware.
