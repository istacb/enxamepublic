# Task Lifecycle

## Purpose

This document defines the lifecycle of a Task within the Enxame architecture.

A Task is the smallest immutable unit of domain work derived from a Workflow.

A Task exists only to perform a single logical responsibility required by a Workflow.

This document formalizes how a Task represents work without representing execution.

## Design Principles

The Task lifecycle follows these principles:

- **Workflow-Derived** - A Task exists solely because a Workflow requires it.
- **Immutability** - The Task never changes after creation.
- **Independence** - Every Task is independent and does not depend on other Tasks.
- **Ownership** - A Task belongs to the Workflow that derived it.
- **Single Responsibility** - A Task represents exactly one logical unit of work.

## Task Origin

Tasks SHALL be derived exclusively by the Workflow.

Runtime SHALL NEVER create Tasks.

Scheduler SHALL NEVER create Tasks.

Agents SHALL NEVER create Tasks.

Users SHALL NEVER create Tasks.

A Task is a deterministic architectural consequence of a Workflow.

Tasks never represent user intent.

## Task Ownership

A Task belongs exclusively to the Workflow that derived it.

Ownership never transfers to Runtime, Scheduler or Agents.

No component other than the Workflow may claim ownership of a Task.

The Workflow tracks Task progress and consolidates artifacts.

## Task Immutability

A Task is immutable.

After creation it SHALL NEVER be modified.

If a different logical work is required, a new Task SHALL be derived by the Workflow.

The original Task remains unchanged.

Task immutability preserves the integrity of the work definition.

## Task Independence

A Task SHALL NOT know:

- Runtime
- Scheduler
- Agents
- Nodes
- Heartbeat
- Discovery
- Infrastructure

A Task belongs exclusively to the domain layer.

Task definition remains independent from execution infrastructure.

## Task Responsibilities

A Task defines only:

- One logical unit of work

A Task SHALL NOT define:

- Execution order
- Scheduling
- Retries
- Infrastructure
- Node selection
- Agent selection
- Execution strategy
- Parallelization

Tasks represent what work should be done, not how or when it executes.

## Task Scheduling

Scheduling SHALL remain an exclusive responsibility of the Scheduler.

Tasks SHALL NEVER determine:

- Execution time
- Execution order
- Execution priority

The Scheduler analyzes Tasks and determines execution sequence based on Workflow dependencies and resource availability.

## Task Execution

Execution belongs exclusively to Runtime.

A Task represents the work.

Execution represents the attempt to perform that work.

Multiple execution attempts MAY occur without changing the Task.

Execution attempts SHALL NOT modify the Task.

Task execution is separate from Task definition.

## Task Retry

Task retries SHALL NOT create new Tasks.

If execution fails:

- Runtime reports the failure.
- Orchestrator decides the next action.
- Another execution attempt MAY be scheduled.
- The original Task remains unchanged.

Retry occurs through execution attempts, never through Task mutation.

## Task Result

Artifacts produced during execution belong to the Workflow.

Tasks do not own final results.

Tasks only contribute artifacts to the Workflow.

The Workflow consolidates all Task artifacts for Mission delivery.

## Task Dependencies

Task dependencies SHALL NOT exist.

Logical dependencies belong exclusively to the Workflow.

Tasks remain completely independent.

The Workflow defines which Tasks must complete before others may begin.

## Task Completion

Task completion SHALL be reported by Runtime.

Workflow SHALL consolidate Task completion.

Mission completion remains independent.

A Task completes when its single logical unit of work has been performed.

Workflow completion occurs when all derived Tasks have completed.

## Architectural Invariants

The following invariants MUST be maintained throughout the Task lifecycle:

- A Task SHALL always belong to exactly one Workflow.
- A Task SHALL remain immutable after creation.
- A Task SHALL represent exactly one logical unit of work.
- A Task SHALL never know infrastructure.
- A Task SHALL never know Agents.
- A Task SHALL never perform scheduling.
- A Task SHALL never create other Tasks.
- Execution attempts SHALL never modify a Task.
- Retry SHALL occur through execution attempts, never through Task mutation.
- Workflow SHALL remain responsible for logical coordination.

## Out of Scope

This document does not define:

- Workflow lifecycle
- Mission lifecycle
- Event catalog
- Runtime lifecycle
- Persistence mechanisms
- Recovery procedures
- Scheduler algorithms
- Resource allocation
- Infrastructure details

These topics belong to separate specifications.

## Related Documents

- `concepts/workflow.md` - Workflow concept definition
- `concepts/workflow_lifecycle.md` - Workflow Lifecycle
- `concepts/mission_lifecycle.md` - Mission Lifecycle
- `eip/EIP-0001-architecture-first.md` - Architecture First principle
- `eip/EIP-0002-resource-first.md` - Resource First principle
