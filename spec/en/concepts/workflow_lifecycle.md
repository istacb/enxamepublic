# Workflow Lifecycle

## Purpose

This document defines the lifecycle of a Workflow within the Enxame architecture.

A Workflow is an immutable execution plan derived from a Mission.

A Workflow exists only to transform a Mission into executable work.

This document formalizes how a Workflow serves as the architectural bridge between an immutable Mission and executable Tasks.

## Design Principles

The Workflow lifecycle follows these principles:

- **Mission-Derived** - A Workflow exists solely because a Mission exists.
- **Immutability** - The Workflow never changes after creation.
- **Independence** - A Workflow remains independent from infrastructure components.
- **Ownership** - A Workflow belongs to the Mission that originated it.
- **Logical Only** - A Workflow defines logical work only, not execution behavior.

## Workflow Origin

A Workflow SHALL be derived exclusively by the Orchestrator.

Users never create Workflows directly.

The Workflow is a deterministic architectural consequence of a Mission.

A Workflow never represents user intent.

## Workflow Ownership

The Workflow belongs to the Mission that originated it.

The Orchestrator manages its lifecycle.

Ownership never transfers to Runtime, Scheduler or Agents.

No component other than the Orchestrator may manage Workflow lifecycle.

## Workflow Immutability

A Workflow is immutable.

After creation, it shall never be modified.

If execution requires structural changes, a new Workflow SHALL be derived.

The original Workflow remains unchanged.

Workflow immutability preserves the integrity of the execution plan.

## Workflow Independence

A Workflow SHALL NOT know:

- Runtime
- Scheduler
- Agents
- Nodes
- Heartbeat
- Discovery
- Infrastructure

The Workflow belongs exclusively to the domain layer.

Workflow definition remains independent from execution infrastructure.

## Workflow Responsibilities

A Workflow defines only:

- Required work
- Logical dependencies
- Execution structure

A Workflow SHALL NOT define:

- Execution order
- Scheduling
- Resource allocation
- Agent selection
- Node selection
- Runtime behavior

## Workflow Scheduling

Execution order is NOT part of the Workflow.

The Scheduler is solely responsible for determining:

- Execution sequence
- Parallel execution
- Priorities
- Resource distribution

The Workflow defines logical dependencies only.

Scheduling decisions belong exclusively to the Scheduler component.

## Workflow Lifecycle

A Workflow evolves through the following conceptual states:

### 1. Derived

The Workflow is derived from a Mission by the Orchestrator.

At this stage:
- Mission intent is analyzed
- Logical work decomposition is performed
- Dependencies are identified
- Execution structure is defined

The Workflow is created as an immutable artifact.

### 2. Active

The Workflow is available for execution planning.

At this stage:
- Scheduler may analyze the Workflow
- Tasks may be identified for scheduling
- Resources may be allocated by Runtime

The Workflow remains unchanged.

### 3. Executing

Tasks derived from the Workflow are being executed.

At this stage:
- Tasks are scheduled by the Scheduler
- Runtime executes Tasks on available Nodes
- Workflow progress is tracked

The Workflow definition remains immutable.

### 4. Completed

All Tasks derived from the Workflow have been executed.

At this stage:
- Workflow completion is managed by the Orchestrator
- Artifacts are available for validation
- Workflow completion does not imply Mission completion

Mission completion remains an exclusive user decision.

## Workflow Recreation

Multiple Workflows may exist during the lifetime of a Mission.

Each new Workflow SHALL be independently derived.

A new Workflow never changes the Mission.

Workflow recreation occurs when:
- User refines the objective within the same Mission intent
- Execution requires a different structural approach
- Previous Workflow completed but Mission continues

Each Workflow remains an independent immutable artifact.

## Workflow Completion

Workflow completion is managed by the Orchestrator.

Workflow completion SHALL NOT imply Mission completion.

Mission completion remains an exclusive user decision.

A Workflow completes when:
- All derived Tasks have been executed
- All logical work defined by the Workflow is finished

The Mission may continue with additional Workflows.

## Workflow Resource Awareness

Workflow creation shall comply with EIP-0002.

A Workflow SHOULD only exist when it provides architectural value.

The architecture SHALL avoid unnecessary Workflow instances that consume resources without functional benefit.

Multiple Workflows for the same Mission must be justified by distinct execution needs.

## Architectural Invariants

The following invariants MUST be maintained throughout the Workflow lifecycle:

- A Workflow SHALL always be derived from exactly one Mission.
- A Workflow SHALL remain immutable after creation.
- A Workflow SHALL never modify Mission intent.
- A Workflow SHALL remain independent from infrastructure.
- A Workflow SHALL define logical work only.
- Execution order SHALL belong exclusively to the Scheduler.
- Agent selection SHALL never be part of a Workflow.
- Runtime SHALL never redefine a Workflow.
- A new Workflow SHALL never alter the originating Mission.
- Orchestrator SHALL be the sole component deriving Workflows.

## Out of Scope

This document does not define:

- Task lifecycle
- Agent lifecycle
- Runtime lifecycle
- Event catalog
- Persistence mechanisms
- Recovery procedures
- Scheduler algorithms
- Communication protocols
- Resource allocation
- Infrastructure details

These topics belong to separate specifications.

## Related Documents

- `concepts/workflow.md` - Workflow concept definition
- `concepts/mission_lifecycle.md` - Mission Lifecycle
- `eip/EIP-0001-architecture-first.md` - Architecture First principle
- `eip/EIP-0002-resource-first.md` - Resource First principle
