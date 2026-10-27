# Event Catalog

## Purpose

This document defines the Event Catalog within the Enxame architecture.

An Event represents an immutable architectural fact.

Events represent transitions between states, not states themselves.

This document formalizes the architectural event model used throughout Enxame.

## Design Principles

The Event model follows these principles:

- **Immutability** - Events never change after publication.
- **Transition Representation** - Events represent state transitions, not states.
- **Component Ownership** - Each component publishes only its own events.
- **Independence** - Events remain independent from infrastructure and transport mechanisms.
- **Identifier Reuse** - Events reuse existing domain identifiers whenever sufficient.

## Event Ownership

Each architectural component SHALL publish only its own events.

Components SHALL NEVER publish events on behalf of other components.

Event ownership is determined by the component that originates the event:

- Mission events are published by the component managing Mission state transitions.
- Workflow events are published by the Orchestrator.
- Task events are published by the component deriving Tasks from Workflows.
- Execution events are published by Runtime.

Ownership determines publication responsibility, not consumption rights.

## Event Lifecycle

### Publication

An event is published when a state transition occurs.

Publication makes the event available to interested consumers.

The publishing component determines when an event is published based on architectural transitions.

### Consumption

Any component MAY consume any published event, including its own.

Consuming an event SHALL NEVER modify the event itself.

Consumption is independent from publication.

A component may consume events without being the publisher.

### Immutability

Events SHALL NEVER be modified after publication.

Once published, an event becomes an immutable architectural fact.

If additional information is required, a new event SHALL be published.

## Event Persistence

Permanent event persistence is NOT required by the architecture.

Event retention SHALL be considered an implementation policy based on available resources.

Persistence decisions belong to implementation, not architecture.

The architecture does not mandate event storage duration or strategy.

## Event Identification

Events SHALL reuse existing domain identifiers whenever sufficient.

The architecture SHALL NOT introduce additional identifiers when Mission, Workflow and Task identifiers already provide the required context.

Event identification relies on:

- Mission identifier for Mission-related events
- Workflow identifier for Workflow-related events
- Task identifier for Task-related events
- Execution identifier for execution-related events

Additional identifiers SHALL only be introduced when domain identifiers are insufficient.

## Event Independence

Events SHALL NOT know:

- Publishers
- Consumers
- Transport mechanisms
- Communication protocols
- Infrastructure

Events are pure architectural facts.

Event definition remains independent from event distribution.

## Event Hierarchy

Events SHALL NOT form inheritance hierarchies.

Events are independent architectural facts.

Each event type stands alone without parent-child relationships.

Event composition occurs through correlation via domain identifiers, not through inheritance.

## Event Catalog

The following events constitute the minimum architectural vocabulary.

Implementation-specific events belong to future documentation.

### Mission Events

#### MissionCreated

Published when a Mission is created with a defined user intent.

Indicates the beginning of a Mission lifecycle.

#### MissionCompleted

Published when the User declares a Mission completed.

Indicates successful Mission conclusion by User decision.

#### MissionCancelled

Published when a Mission is cancelled.

Indicates Mission termination before completion.

### Workflow Events

#### WorkflowDerived

Published when a Workflow is derived from a Mission by the Orchestrator.

Indicates creation of an immutable execution plan.

#### WorkflowCompleted

Published when all Tasks derived from a Workflow have been executed.

Indicates Workflow logical work completion.

Does not imply Mission completion.

#### WorkflowCancelled

Published when a Workflow is cancelled before completion.

Indicates Workflow termination.

### Task Events

#### TaskCreated

Published when a Task is derived from a Workflow.

Indicates creation of a unit of domain work.

#### TaskCompleted

Published when a Task's logical work has been performed.

Indicates successful Task execution.

#### TaskFailed

Published when a Task execution fails.

Indicates Task execution failure without modifying the Task.

### Execution Events

#### ExecutionStarted

Published when Runtime begins executing a Task.

Indicates initiation of an execution attempt.

#### ExecutionCompleted

Published when Runtime successfully completes an execution attempt.

Indicates successful execution of a Task.

#### ExecutionFailed

Published when Runtime fails to complete an execution attempt.

Indicates execution failure, which may trigger retry.

## Architectural Invariants

The following invariants MUST be maintained throughout the Event model:

- Events SHALL represent architectural facts.
- Events SHALL represent transitions rather than states.
- Events SHALL remain immutable after publication.
- Components SHALL publish only their own events.
- Existing domain identifiers SHALL be reused whenever possible.
- Event persistence SHALL remain implementation-dependent.
- Events SHALL remain infrastructure-independent.
- Events SHALL NOT form inheritance hierarchies.
- Event consumption SHALL NOT modify the event.
- Any component MAY consume any published event.

## Out of Scope

This document does not define:

- Payload schemas
- Serialization formats
- Transport protocols
- Messaging systems
- Event storage mechanisms
- Event replay strategies
- Infrastructure implementation details

These topics belong to separate specifications.

## Related Documents

- `concepts/mission_lifecycle.md` - Mission Lifecycle
- `concepts/workflow_lifecycle.md` - Workflow Lifecycle
- `concepts/task_lifecycle.md` - Task Lifecycle
- `eip/EIP-0001-architecture-first.md` - Architecture First principle
- `eip/EIP-0002-resource-first.md` - Resource First principle
