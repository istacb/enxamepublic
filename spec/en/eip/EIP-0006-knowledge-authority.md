# EIP-0006: Knowledge Authority

## Status

**Accepted**

## Summary

No Agent is an authority on knowledge.

All queries beyond the immediate context of a Task must pass through the Orchestrator.

The Librarian is the knowledge authority of the Enxame.

## Mandatory Query Order

1. User's offline base
2. Local bases
3. Local resources
4. Internet (last resort)

## Restrictions

Agents never directly access:

- Internet
- Librarian
- other Nodes

## Principles

- Agents are not knowledge authorities.
- All knowledge queries flow through the Orchestrator.
- The Librarian is the central knowledge authority.
- Query order must be respected to preserve Offline First.
- Direct access by Agents is prohibited.

## Consequences

### Positive

- Preserves Offline First principle
- Maintains Resource First architecture
- Centralizes knowledge management
- Prevents uncontrolled external access
- Ensures consistent knowledge retrieval patterns
- Protects against information leakage

### Negative

- Adds latency to knowledge queries
- Requires Orchestrator coordination for all external access
- Limits Agent autonomy for information gathering

### Neutral

- Query order is fixed and non-negotiable
- Orchestrator acts as gatekeeper for knowledge access
- Librarian maintains authoritative knowledge state

## Rationale

The Enxame architecture establishes clear boundaries around knowledge access to preserve core architectural principles.

Agents are execution entities, not knowledge authorities.

Their role is to execute Tasks using available resources, not to independently gather or verify information.

When an Agent requires information beyond the immediate Task context, it must request this information through the Orchestrator.

The Orchestrator then coordinates with the Librarian to retrieve the necessary knowledge.

This design preserves several important properties:

**Offline First**: By requiring queries to follow a specific order (offline base → local bases → local resources → Internet), the architecture ensures that external connectivity is only used when absolutely necessary.

**Resource First**: Local resources are prioritized over external resources, respecting the scarcity assumption of the architecture.

**Centralized Knowledge**: The Librarian serves as the single source of truth for knowledge, preventing fragmentation and inconsistency.

**Controlled Access**: By prohibiting direct Agent access to external resources, the architecture maintains control over what information is accessed and when.

The mandatory query order ensures that:

1. User's offline knowledge is always consulted first
2. Local cached knowledge is used before external sources
3. Local computational resources are leveraged before network resources
4. Internet access is truly a last resort

This approach aligns with the Enxame philosophy of adapting to available hardware and minimizing unnecessary resource consumption.

## References

- EIP-0001: Architecture First
- EIP-0002: Resource First Architecture
- PR 4.2: Runtime

## History

- **2024** - EIP created as part of Sprint 4 architecture
