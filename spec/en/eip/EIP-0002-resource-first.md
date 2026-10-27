# EIP-0002: Resource First Architecture

## Status

**Accepted**

## Summary

Enxame assumes computational resources are limited.

Architecture must minimize memory usage, CPU consumption, storage requirements and unnecessary execution.

Every permanent architectural component must justify its computational cost.

## Motivation

Enxame is designed to reuse existing hardware before requiring new hardware.

Software must adapt to available hardware whenever possible.

Efficiency is an architectural requirement.

It is not an optimization step performed later.

## Principles

- Existing hardware comes first.
- Offline First remains a core principle.
- Human decision is always final.
- User knowledge belongs to the User.
- Components must justify their computational cost.
- Simplicity is preferred over unnecessary abstraction.
- New permanent services require architectural justification.

## Consequences

Future architectural decisions should always prefer simpler and lighter solutions whenever they provide equivalent functionality.

Architectural complexity must always have measurable value.

## Rationale

The Enxame architecture assumes scarce computational resources as a design premise.

Unlike systems designed for abundant cloud infrastructure, Enxame prioritizes efficient execution on existing user hardware, including legacy computers.

This principle influences all future architectural decisions.
