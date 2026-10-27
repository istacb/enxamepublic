# Node

## Definition

A Node is a computational participant of Enxame whose existence is justified by its ability to contribute to the system.

A computer only becomes a Node after joining Enxame and offering one or more contributions.

A Node is identified independently of its operational state.

## Responsibilities

- Participate in Enxame.
- Execute one or more capabilities.
- Contribute computational resources.
- Contribute specialized knowledge when applicable.
- Communicate with other Nodes through Enxame protocols.
- Execute its Primary Responsibility.
- Optionally assume Secondary Responsibilities.
- Optionally assume Temporary Responsibilities when requested by Enxame.

## It is NOT responsible for

- Making final decisions.
- Owning user knowledge.
- Replacing human judgment.
- Violating Kernel rules.
- Modifying user knowledge without authorization.

## Relationships

- A Node participates in one Enxame.
- A Node executes the Enxame Runtime.
- A Node hosts one or more Agents.
- A Node may contribute one or more Capabilities.
- A Node may access local Knowledge Assets.
- A Node communicates with other Nodes.
- A Node may temporarily assume responsibilities belonging to another Node.

## Identity

Every Node has its own identity.

The implementation of this identity is intentionally unspecified by the architecture.

Examples may include UUIDs, fingerprints or cryptographic identities.

Identity must survive temporary offline states whenever possible.

## Responsibilities Model

Every Node has exactly one Primary Responsibility.

A Node may have zero or more Secondary Responsibilities.

A Node may receive Temporary Responsibilities during execution in order to maintain Enxame operation.

Temporary Responsibilities never replace the Primary Responsibility.

## Operational States

Possible states include, but are not limited to:

- Available
- Busy
- Offline
- Maintenance
- Recovering

Operational state does not change Node identity.

## Invariants

- Every Node contributes to Enxame.
- Every Node has a unique identity.
- Every Node has one Primary Responsibility.
- A Node may execute Secondary Responsibilities.
- A Node may execute Temporary Responsibilities.
- A Node never owns user knowledge.
- A Node never replaces the user's final decision.
- A Node always respects Kernel rules.

## Future Extensions

This concept may evolve through EIPs.

Changes to its invariants require architectural review.
