# Mission Lifecycle

## Purpose

This document defines the lifecycle of a Mission within the Enxame architecture.

A Mission represents an immutable user intent whose objective is to solve a user problem.

This document formalizes how a Mission evolves through state transitions without modifying its core intent.

## Design Principles

The Mission lifecycle follows these principles:

- **User Intent First** - A Mission exists solely to represent what the User wants to accomplish.
- **Immutability** - The Mission's intent never changes after creation.
- **Independence** - Every Mission is independent and does not depend on other Missions.
- **Ownership** - A Mission always belongs to the User throughout its lifecycle.
- **Explicit Transitions** - A Mission evolves only through well-defined state transitions.

## Mission Ownership

A Mission always belongs to the User.

Runtime, Workflow, Scheduler, Judge and all Agents act on behalf of the User.

Ownership never changes during the Mission lifecycle.

No component may claim ownership of a Mission.

## Mission Immutability

A Mission is immutable.

Its intent never changes.

The following may change during execution:
- Execution state
- Workflow
- Tasks
- Events

The Mission itself never changes.

If the User modifies the original intent, a new Mission SHALL be created.

## Mission Independence

Every Mission is independent.

A Mission never depends on another Mission.

Artifacts produced by one Mission may be used by another Mission.

Missions themselves never form dependency trees.

## Mission Lifecycle

A Mission evolves through the following conceptual states:

### 1. Created

The Mission is created with a defined user intent.

At this stage:
- The User intent is captured
- Success criteria are defined
- No execution has begun

### 2. Planned

The Mission is prepared for execution.

At this stage:
- A Workflow may be generated
- Tasks may be identified
- Resources may be allocated

The Mission intent remains unchanged.

### 3. Executing

The Mission is actively being executed.

At this stage:
- Tasks are being performed
- Workflow is progressing
- State transitions occur based on execution progress

The Mission intent remains unchanged.

### 4. Validating

Execution artifacts are evaluated before final delivery to the User.

At this stage:
- Judge evaluates results against success criteria
- Revalidation may be requested
- No user decision is made by the Judge

### 5. Completed

The User declares the Mission completed.

Completion is never automatic.

Completion is independent from:
- Workflow completion
- Task completion
- Judge approval

### 6. Cancelled

The Mission is cancelled by explicit User decision or resource release.

At this stage:
- Allocated resources are released according to Runtime rules
- Execution stops
- The Mission remains immutable as a historical record

## Mission Validation

Judge never owns the Mission.

Judge never completes the Mission.

Judge never decides for the User.

Judge only evaluates results and may request revalidation.

Revalidation uses artifacts already produced during execution.

Revalidation never changes the Mission.

## Mission Completion

Only the User can declare a Mission completed.

Completion is never automatic.

Completion is independent from:
- Workflow completion
- Task completion
- Judge approval

The system may suggest completion, but final declaration belongs to the User.

## Mission Replacement

If the User changes the original intent:

A new Mission SHALL be created.

The previous Mission remains immutable.

If the User explicitly replaces the previous Mission:

The previous Mission SHALL be cancelled.

Allocated resources SHALL be released according to Runtime rules.

## Mission Revalidation

Judge may request revalidation using artifacts already produced during execution.

Revalidation never changes the Mission.

If User changes the intent after revalidation:

A new Mission SHALL be created.

## Architectural Invariants

The following invariants MUST be maintained throughout the Mission lifecycle:

- A Mission SHALL always represent a single user intent.
- A Mission SHALL remain immutable after creation.
- Only the User SHALL complete a Mission.
- Judge SHALL never make user decisions.
- Missions SHALL remain independent.
- Mission replacement SHALL always create a new Mission.
- Runtime SHALL never alter Mission intent.
- Workflow SHALL execute a Mission but never redefine it.
- Ownership SHALL remain with the User throughout the lifecycle.
- State transitions SHALL not modify the Mission intent.

## Out of Scope

This document does not define:

- Task lifecycle
- Agent lifecycle
- Runtime lifecycle
- Event catalog
- Persistence mechanisms
- Recovery procedures
- Scheduler internals
- Communication protocols
- Resource allocation algorithms

These topics belong to separate specifications.

## Related Documents

- `concepts/mission.md` - Mission concept definition
- `domain/mission.md` - Mission domain model
- `eip/EIP-0001-architecture-first.md` - Architecture First principle
- `eip/EIP-0002-resource-first.md` - Resource First principle
