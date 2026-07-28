# Mission

## Definition

A Mission represents the user's objective inside Enxame.

A Mission is always created by the User.

It defines WHAT the User wants to accomplish.

A Mission is independent of implementation details.

A Mission may outlive a user session.

## Responsibilities

- Represent the User's objective.
- Preserve the User's intent.
- Define the desired outcome.
- Serve as the starting point for execution.
- Allow execution to pause and resume later.

## It is NOT responsible for

- Executing work.
- Planning execution.
- Selecting Nodes.
- Selecting Agents.
- Managing Capabilities.
- Storing knowledge.
- Making decisions for the User.

## Relationships

- Created by the User.
- Planned by the Orchestrator.
- May generate one or more Workflows.
- May generate one or more Tasks.
- Consumes Capabilities through execution.
- Is evaluated by the Judge before the final response is presented to the User.

## Invariants

- Every Mission originates from the User.
- A Mission preserves the User's original intent.
- A Mission may be paused.
- A Mission may be resumed later.
- A Mission never replaces the User's decision.

## Future Extensions

Future EIPs may introduce:

- Priorities
- Scheduling
- Dependencies between Missions

## Related Concepts

- Capability
- Workflow (Future)
- Task (Future)
- Orchestrator (Future)
