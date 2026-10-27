# EIP-0004: Hybrid Task Dispatch

## Status

**Accepted**

## Summary

Enxame uses hybrid Task dispatch.

The preferred model is Pull.

Push exists only for exceptions.

## Models

### Pull

The Node informs its availability.

The Orchestrator sends compatible Tasks.

### Push

Used only for:

- emergency
- failover
- administration
- recovery
- architectural necessity

## Principles

- Pull is the default dispatch mechanism.
- Push is reserved for exceptional situations.
- The Orchestrator remains responsible for planning.
- The Runtime remains responsible only for execution.
- Task dispatch model does not change Task ownership.

## Consequences

### Positive

- Nodes control their own workload acceptance
- Better resource utilization through self-reporting
- Reduced unnecessary Task transfers
- Clear separation between planning and execution
- Failover and emergency scenarios are supported

### Negative

- Requires Nodes to continuously report availability
- Adds complexity to dispatch logic

### Neutral

- Both models coexist in the architecture
- Push does not replace Pull as the primary mechanism

## Rationale

The Enxame architecture adopts a hybrid Task dispatch model that balances efficiency with flexibility.

The Pull model is preferred because it allows Nodes to self-report their availability and capabilities.

This approach respects the Resource First principle by ensuring Tasks are only sent to Nodes that can execute them.

The Push model exists to handle exceptional situations where immediate Task assignment is necessary.

Examples of Push usage include:

- Emergency redistribution when a Node fails
- Failover scenarios requiring immediate Task migration
- Administrative Tasks that must be executed on specific Nodes
- Recovery operations after network partitions
- Architectural necessities that require direct assignment

The Orchestrator maintains responsibility for overall Task planning and distribution.

The Runtime maintains responsibility only for executing assigned Tasks.

This separation ensures clear boundaries between planning and execution concerns.

## References

- EIP-0002: Resource First Architecture
- PR 4.2: Runtime

## History

- **2024** - EIP created as part of Sprint 4 architecture
