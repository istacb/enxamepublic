# Workflow

## Definition

A Workflow is the logical decomposition of a Mission.

A Workflow exists only because a Mission exists.

It represents the logical organization of work required to accomplish the Mission.

A Mission may contain one or more Workflows.

Multiple Workflows may exist sequentially within the same Mission as the User refines or extends the requested objective.

## Responsibilities

- Decompose a Mission into logical stages.
- Organize work before execution.
- Group related Tasks.
- Preserve the intent of the Mission.
- Provide a logical structure for execution.

## It is NOT responsible for

- Executing Tasks.
- Selecting Nodes.
- Selecting Agents.
- Managing Knowledge.
- Coordinating execution.
- Making decisions for the User.

## Relationships

- A Workflow belongs to exactly one Mission.
- A Workflow contains one or more Tasks.
- A Mission may generate multiple Workflows.
- A new Workflow may be created after User interaction while preserving the same Mission.

## Invariants

- Every Workflow belongs to one Mission.
- A Workflow cannot exist without a Mission.
- A Workflow ends when all of its Tasks are completed.
- Completing a Workflow does not necessarily complete the Mission.

## Design Rationale

Workflow represents logical organization, not infrastructure.

Depending on the Mission, a Workflow may describe:

- what should be done;
- how a specific objective should be achieved.

The interpretation depends on the Mission itself rather than on the Workflow definition.

## Future Extensions

Future EIPs may introduce:

- Parallel Workflows
- Conditional Workflows
- Reusable Workflow Templates

## Related Concepts

- Mission
- Task (Future)
