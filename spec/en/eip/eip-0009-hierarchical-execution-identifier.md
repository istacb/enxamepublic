# EIP-0009: Hierarchical Execution Identifier (HEI)

**Status:** Accepted  
**Type:** Standards Track  
**Sprint:** 4  
**PR:** 4.3

---

## Summary

Every execution in the Enxame must possess a human-readable hierarchical identification.

The objective is to provide complete traceability without relying on random identifiers or complex observability infrastructure.

---

## Motivation

Enable:

- **Auditing**: Clear lineage of execution artifacts.
- **Debugging**: Rapid identification of execution context.
- **Tracing**: End-to-end visibility of mission flow.
- **Correlation**: Linking related events across distributed components.
- **Human Comprehension**: Low cognitive load when analyzing logs or reports.

All with minimal computational cost, adhering to the Resource First Architecture (EIP-0002).

---

## Principles

### Hierarchy

The execution model follows a strict parent-child relationship:

1. **Mission** generates **Workflows**.
2. **Workflow** generates **Tasks**.
3. **Task** generates **Executions**.
4. **Execution** generates **Results**.

All child components inherit the identifier of their ancestor.

### Inheritance

Every derived component must inherit the full path of its parent identifier. This allows reconstructing the entire execution tree from any single node in the hierarchy.

### Immutability

Once assigned, an HEI never changes for the lifetime of the entity it identifies.

---

## Format Specification

The Hierarchical Execution Identifier uses a dot-separated notation representing the execution tree depth.

### Structure

| Level | Format | Example | Description |
| :--- | :--- | :--- | :--- |
| **Mission** | `M{NNNNNN}` | `M000001` | Root identifier for a Mission. |
| **Workflow** | `{Mission}.W{NN}` | `M000001.W01` | Specific workflow within a Mission. |
| **Task** | `{Workflow}.T{NN}` | `M000001.W01.T03` | Specific task within a Workflow. |
| **Execution** | `{Task}.E{NN}` | `M000001.W01.T03.E01` | Specific execution attempt of a Task. |
| **Result** | `{Task}.R{NN}` | `M000001.W01.T03.R01` | Result artifact from a Task execution. |
| **Final Answer** | `{Mission}.A` | `M000001.A` | Final synthesized answer of the Mission. |

### Notation Rules

- **Prefixes**: 
  - `M` = Mission
  - `W` = Workflow
  - `T` = Task
  - `E` = Execution Attempt
  - `R` = Result
  - `A` = Final Answer
- **Padding**: Numeric portions are zero-padded to ensure lexicographical sorting correctness.
  - Mission: 6 digits (`000001`)
  - Workflow: 2 digits (`01`)
  - Task: 2 digits (`03`)
  - Execution/Result: 2 digits (`01`)

### Examples

```text
# A simple mission with one workflow and one task
M000042
M000042.W01
M000042.W01.T01
M000042.W01.T01.E01
M000042.W01.T01.R01
M000042.A

# A complex mission with retries
M000100
M000100.W01
M000100.W01.T05
M000100.W01.T05.E01  (Failed)
M000100.W01.T05.E02  (Retry 1 - Failed)
M000100.W01.T05.E03  (Retry 2 - Success)
M000100.W01.T05.R03  (Result from successful execution)
```

---

## Rules

### 1. No UUID as Primary Identifier

Never use UUIDs as the primary execution identifier visible to users or logs.

- UUIDs may exist internally as technical details (e.g., database keys, message IDs).
- UUIDs must **never** replace the HEI for traceability purposes.

### 2. Mandatory Inheritance

Every child component must inherit the full identifier path of its parent.

- A Task cannot exist without a Workflow prefix.
- A Workflow cannot exist without a Mission prefix.

### 3. Tree Reconstructability

The identifier must allow reconstruction of the entire execution tree.

Given any HEI, one must be able to determine:
- The parent Mission.
- The specific Workflow.
- The specific Task.
- The execution attempt number.

### 4. Uniqueness Scope

- **Mission ID**: Globally unique across the Swarm.
- **Workflow ID**: Unique within the scope of its Mission.
- **Task ID**: Unique within the scope of its Workflow.
- **Execution ID**: Unique within the scope of its Task (increments on retry).

---

## Benefits

### Readability

Operators can instantly understand the context of an execution by looking at the identifier.

```text
# Which mission? Which task? Which attempt?
M000001.W01.T03.E02
^       ^   ^   ^
|       |   |   └─ Attempt 2
|       |   └───── Task 3
|       └───────── Workflow 1
└───────────────── Mission 1
```

### Auditing

Simplifies compliance and historical analysis. All artifacts related to a mission share a common prefix.

### Debugging

Rapidly isolate failures. If `M000001.W01.T03.E01` fails, the operator knows exactly where to look without querying complex join tables.

### Event Correlation

Logs, metrics, and traces can be correlated using a single string field without requiring distributed tracing infrastructure.

### Troubleshooting

Reduces mean time to resolution (MTTR) by providing immediate context.

### Low Complexity

No external service required to generate or resolve identifiers. Simple string concatenation.

---

## Consequences

### Positive

- **Simplicity**: No complex ID generation algorithms.
- **Performance**: String operations are cheap compared to UUID generation/storage.
- **Observability**: Built-in tracing without external tools.
- **Legacy Friendly**: Short, readable strings work well in old terminals and logs.

### Negative

- **Length**: Identifiers grow with hierarchy depth (mitigated by fixed padding).
- **Rigidity**: Changing the hierarchy structure requires migrating existing IDs.

### Neutral

- **Sequentiality**: Requires a counter mechanism (per node or centralized) to ensure uniqueness.

---

## Rationale

The HEI design prioritizes **human readability** and **operational simplicity** over absolute randomness.

In distributed systems, UUIDs provide uniqueness but destroy context. An operator seeing `550e8400-e29b...` learns nothing about the execution context without database lookups.

The HEI approach embeds context directly into the identifier:
- It tells you **what** is executing (Mission/Task).
- It tells you **where** it fits (Workflow).
- It tells you **how many times** it has been tried (Execution count).

This aligns with the **Resource First** philosophy (EIP-0002) by minimizing the computational and cognitive resources required to understand system state.

---

## Compatibility

This EIP is considered **experimental** initially.

- Future Sprints may refine the padding or notation if limitations are encountered.
- Backward compatibility will be maintained whenever possible.
- The core principle (hierarchical inheritance) is immutable.

---

## References

- **EIP-0001**: Architecture First
- **EIP-0002**: Resource First Architecture
- **PR 4.3**: Communication Protocol
- **Spec**: Communication Protocol (Envelope `mission_id` field)

---

## History

| Date | Version | Author | Description |
| :--- | :--- | :--- | :--- |
| 2024-XX-XX | 1.0.0 | Architect | Initial Proposal |
| 2024-XX-XX | 1.0.0 | Architect | Accepted for Sprint 4 |
