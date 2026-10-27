# EIP-0005: Temporary Service Promotion

## Status

**Accepted**

## Summary

A Node can temporarily start additional services to maintain Enxame operational.

Example:

The Node hosting the Judge can temporarily start the Orchestrator service if it becomes unavailable.

The Judge does NOT transform into an Orchestrator.

The Node only temporarily hosts a new Service.

When the Orchestrator returns, the temporary service must be terminated.

## Objective

High availability with simplicity.

## Principles

- Services can be promoted temporarily during failures.
- The Node hosts the service, not transforms into it.
- Temporary services must be terminated when the original service returns.
- Promotion is automatic and transparent to the Enxame.
- No permanent state changes occur during promotion.

## Consequences

### Positive

- High availability without complex failover infrastructure
- Simple recovery mechanism for critical services
- Minimal overhead during normal operation
- Clear separation between service and Node identity
- Automatic recovery when original service returns

### Negative

- Requires monitoring of service availability
- Temporary duplication of service state may occur
- Adds complexity to service lifecycle management

### Neutral

- Promotion is temporary by design
- Only critical services are eligible for promotion
- Original service identity is preserved

## Rationale

The Enxame architecture requires high availability while maintaining architectural simplicity.

Temporary Service Promotion provides a mechanism for maintaining critical services during failures without introducing complex failover infrastructure.

When a critical service becomes unavailable, a Node can temporarily host that service to maintain Enxame operations.

This approach differs from traditional failover in several ways:

- The Node does not permanently become the service.
- The service identity remains unchanged.
- The promotion is temporary and automatic.
- The original service can resume when available.

For example, if the Orchestrator becomes unavailable:

1. The Node hosting the Judge detects the absence.
2. The Node starts a temporary Orchestrator service.
3. The temporary Orchestrator handles essential operations.
4. When the original Orchestrator returns, the temporary instance terminates.
5. The Node returns to its original service configuration.

This mechanism ensures continuity without requiring permanent redundancy or complex coordination protocols.

## References

- EIP-0001: Architecture First
- EIP-0002: Resource First Architecture
- PR 4.1: Kernel (Microkernel)

## History

- **2024** - EIP created as part of Sprint 4 architecture
