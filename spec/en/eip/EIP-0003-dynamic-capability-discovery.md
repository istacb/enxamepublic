# EIP-0003: Dynamic Capability Discovery

## Status

**Accepted**

## Summary

Node capabilities represent the current state of a Node.

Capabilities are dynamic.

They can appear or disappear during execution.

They do not require Node restart.

The Capability Registry must always reflect the current state.

The Orchestrator must be informed when changes occur.

## Motivation

Enable dynamic infrastructure adaptation without restart.

## Principles

- Capabilities are dynamic, not static.
- Resources can be hot-plugged and hot-removed.
- The Capability Registry reflects real-time state.
- Changes in capabilities must be communicated to the Orchestrator.
- Node restart is not required for capability changes.

## Consequences

### Positive

- Hot Plug of resources
- Hot Removal of resources
- Greater resilience
- Better Task distribution
- Infrastructure adapts to hardware changes

### Negative

- Requires continuous monitoring of resource state
- Adds complexity to capability tracking

### Neutral

- Capability changes are local to the Node
- Orchestrator receives updates asynchronously

## Rationale

The Enxame architecture treats capabilities as dynamic properties that reflect the current availability of resources on a Node.

Unlike systems that assume static capabilities defined at startup, Enxame recognizes that hardware resources can change during execution.

This principle enables Nodes to adapt to hardware changes such as:

- USB devices connected or disconnected
- Network interfaces becoming available or unavailable
- Storage devices mounted or unmounted
- GPU drivers loaded or unloaded
- Peripheral devices added or removed

The Capability Registry maintains the current state of all capabilities.

When a capability changes, the Registry is updated and the Orchestrator is notified.

This allows the Enxame to make intelligent Task distribution decisions based on real-time resource availability.

## References

- EIP-0002: Resource First Architecture
- PR 4.1: Kernel (Microkernel)
- PR 4.2: Runtime

## History

- **2024** - EIP created as part of Sprint 4 architecture
