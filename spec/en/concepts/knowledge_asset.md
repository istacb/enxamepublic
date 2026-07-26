# Knowledge Asset

## Definition

A Knowledge Asset is the smallest managed unit representing user knowledge inside Enxame.

It may represent a document, image, conversation, audio, video, note, database record or any other information source.

## Responsibilities

- Store references.
- Preserve provenance.
- Preserve metadata.
- Enable indexing.
- Enable relationships.
- Support versioning.

## It is NOT responsible for

- Deciding truth.
- Replacing user knowledge.
- Making autonomous decisions.

## Relationships

- Every Knowledge Asset represents Knowledge.
- A Knowledge Asset may relate to other Knowledge Assets.
- A Knowledge Asset may have one or more sources.
- A Knowledge Asset belongs to one user.
- A Knowledge Asset may be superseded but never silently replaced.

## Invariants

- Every Knowledge Asset has an identifier.
- Every Knowledge Asset preserves provenance whenever possible.
- Every Knowledge Asset keeps timestamps.
- Every Knowledge Asset may carry validity information.
- Every Knowledge Asset is traceable.

## Future Extensions

This concept may evolve through EIPs.

Changes to its invariants require architectural review.
