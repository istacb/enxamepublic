# Specialization

## Definition

A Specialization represents a permanent responsibility inside Enxame.

It defines WHAT must be done.

It does not define HOW it is implemented.

A Specialization exists independently of Nodes, Agents, AI models or execution technologies.

## Responsibilities

- Define a permanent responsibility.
- Group related capabilities.
- Describe expected behavior.
- Remain stable across implementations.
- Allow different Agents to perform the same responsibility.

## It is NOT responsible for

- Executing work.
- Storing user knowledge.
- Managing Nodes.
- Making final decisions.
- Defining implementation details.

## Relationships

- A Specialization groups one or more Capabilities.
- A Specialization may be executed by one or more Agents.
- A Specialization may migrate between Nodes.
- Multiple Agents may implement the same Specialization.
- A Node may host Agents belonging to different Specializations.

## Invariants

- Every Specialization has one permanent purpose.
- A Specialization exists independently of execution.
- A Specialization survives Agent replacement.
- A Specialization survives Node replacement.
- A Specialization never owns user knowledge.

## Future Extensions

This concept may evolve through EIPs.

Changes to its invariants require architectural review.
