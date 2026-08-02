# Communication Protocol Specification

**Version:** 1.0.0  
**Status:** Draft  
**PR:** 4.3  
**Sprint:** 4

---

## 1. Objective

Define the communication language used by all components of the Enxame (Swarm).

This specification serves as the foundation for:

- Discovery
- Heartbeat
- Runtime
- Scheduler
- Failover
- Service Loader
- Librarian
- Judge
- Orchestrator

All components will utilize this protocol.

---

## 2. Philosophy

The protocol must be:

- **Simple**: Easy to understand and implement.
- **Immutable**: Messages never change once created.
- **Lightweight**: Minimal overhead for compatibility with legacy hardware.
- **Decoupled**: Independent of transport mechanisms.
- **Event-Oriented**: Driven by state changes and actions.
- **Legacy-Compatible**: Efficient enough for older hardware.

**Note:** The protocol does not implement transport. It only defines how messages are structured. The implementation may use any transport mechanism in the future (HTTP, TCP, gRPC, etc.).

---

## 3. Principles

### 3.1 Single Envelope
All communication utilizes a single, unified Envelope structure.

### 3.2 Immutability
All messages are immutable.
- A new requirement generates a new message.
- Messages are never altered during transit.
- Modifications result in the creation of a new message instance.

### 3.3 Agnosticism
The protocol is agnostic to:
- Transport layer (HTTP, TCP, UDP, etc.)
- Serialization format (JSON, Binary, etc.)
- Network topology

---

## 4. The Envelope

Every message must possess a common Envelope containing the following fields:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `message_id` | String | Yes | Unique identifier for this specific message. |
| `timestamp` | ISO8601 | Yes | UTC timestamp of message creation. |
| `sender` | String | Yes | Identifier of the Node or Service sending the message. |
| `receiver` | String | Yes | Identifier of the intended recipient (Node, Service, or Broadcast). |
| `message_type` | Enum | Yes | Categorizes the intent of the message (see Section 5). |
| `mission_id` | String | No | Hierarchical Execution Identifier (HEI) of the parent Mission. Required for operational messages. |
| `correlation_id` | String | No | Links related messages (e.g., Request/Response, Task/Result). |
| `payload` | Object | No | The actual data content of the message. Structure depends on `message_type`. |

### 4.1 Field Specifications

#### `message_id`
- Must be unique across the entire Swarm lifecycle.
- Used for deduplication and auditing.

#### `timestamp`
- Must be in UTC.
- Used for ordering and timeout calculations.

#### `sender` / `receiver`
- Identifiers must be consistent with the Node identity defined in the Kernel.
- `receiver` may be a broadcast address (e.g., `*` or `broadcast`) for discovery purposes.

#### `mission_id`
- Follows the Hierarchical Execution Identifier (HEI) standard (see EIP-0009).
- Mandatory for any message related to a Mission execution.

#### `correlation_id`
- Typically matches the `message_id` of the request being answered.
- Enables tracing of request/response cycles.

#### `payload`
- Schema varies by `message_type`.
- Must be self-contained; no external references required for basic processing.

---

## 5. Message Types

Messages are categorized into three distinct groups: Infrastructure, Operational, and Administrative.

### 5.1 Infrastructure Messages

Used for node management, discovery, and health monitoring.

| Type | Code | Description |
| :--- | :--- | :--- |
| `DISCOVERY_REQUEST` | `INFRA.01` | Request for available nodes in the swarm. |
| `DISCOVERY_RESPONSE` | `INFRA.02` | Response containing node capabilities and status. |
| `HEARTBEAT` | `INFRA.03` | Periodic signal indicating node liveness. |
| `CAPABILITY_UPDATE` | `INFRA.04` | Notification of changed local capabilities (Hot Plug/Remove). |
| `READY` | `INFRA.05` | Node is initialized and ready to accept tasks. |
| `BUSY` | `INFRA.06` | Node is temporarily unable to accept new tasks. |
| `SHUTDOWN` | `INFRA.07` | Node is gracefully stopping services. |

### 5.2 Operational Messages

Used for mission execution, task distribution, and result reporting.
**Authority:** Only the Orchestrator initiates operational flow; Nodes respond.

| Type | Code | Description |
| :--- | :--- | :--- |
| `TASK_ASSIGN` | `OPS.01` | Assignment of a specific Task to a Node. |
| `TASK_RESULT` | `OPS.02` | Successful completion report of a Task. |
| `TASK_FAILURE` | `OPS.03` | Report of a Task failure after retries. |
| `TASK_CANCEL` | `OPS.04` | Request to immediately stop a running Task. |
| `TASK_RETRY` | `OPS.05` | Instruction to retry a failed Task (local recovery). |
| `TASK_REPLAN` | `OPS.06` | Notification that the Mission workflow is being replanned. |
| `SERVICE_PROMOTION` | `OPS.07` | Notification of temporary service promotion (Failover). |

### 5.3 Administrative Messages

Used for configuration, diagnostics, and system health.

| Type | Code | Description |
| :--- | :--- | :--- |
| `CONFIG_UPDATE` | `ADM.01` | Push configuration updates to a Node. |
| `DIAGNOSTICS_REQUEST` | `ADM.02` | Request detailed diagnostic data from a Node. |
| `DIAGNOSTICS_REPORT` | `ADM.03` | Detailed system health and metrics report. |
| `HEALTH_CHECK` | `ADM.04` | Deep health check request (beyond heartbeat). |

---

## 6. Communication Rules

### 6.1 Initiation Authority

- **Infrastructure Messages:** Only **Nodes** can initiate infrastructure messages (e.g., Heartbeat, Capability Update).
- **Operational Messages:** Only the **Orchestrator** initiates operational messages (e.g., Task Assignment).
- **Responses:** Any component may send a response message correlated to a received message.

### 6.2 Topology Constraints

- **No Direct Node-to-Node Communication:** Nodes never send Tasks or Operational messages directly to other Nodes.
- **Centralized Coordination:** All distributed communication passes through the Orchestrator.
- **Flow:** `Node → Orchestrator → Node`.

### 6.3 Immutability Enforcement

- Once a message envelope is sealed (created), it cannot be modified.
- If a state change requires updating information, a **new message** must be generated with a new `message_id` and `timestamp`.
- The `correlation_id` should link the new message to the previous state if applicable.

---

## 7. Tracing and Observability

### 7.1 Traceability
Every message related to a Mission must possess complete traceability.
- Use `mission_id` to group all messages belonging to a specific Mission.
- Use `correlation_id` to link specific request/response pairs.

### 7.2 Hierarchy
The protocol supports the Hierarchical Execution Identifier (HEI) defined in EIP-0009.
- `mission_id` in the envelope allows reconstructing the execution tree:
  `Mission → Workflow → Task → Execution`.

### 7.3 Judge Visibility
The **Judge** component monitors specific message types for auditing and quality assurance:
- **Monitored:** `TASK_ASSIGN`, `TASK_RESULT`, `TASK_FAILURE`, `TASK_CANCEL`, `TASK_RETRY`, `TASK_REPLAN`.
- **Ignored:** `DISCOVERY`, `HEARTBEAT`, `CAPABILITY_UPDATE` (Infrastructure noise).

---

## 8. Logging and Transport

### 8.1 Logging
- The protocol **does not** implement logging.
- Logging is the responsibility of an independent Service.
- The protocol only transports messages; it does not dictate where or how they are stored.

### 8.2 Transport Agnosticism
This specification **does not define** the transport layer.
- Supported transports (future implementation): HTTP, TCP, UDP, gRPC, WebSocket, Shared Memory.
- The Envelope structure remains constant regardless of the transport mechanism.

---

## 9. Acceptance Criteria

This specification is considered complete when:

1. All future components (Discovery, Runtime, Scheduler, etc.) can utilize the same Envelope structure.
2. There are no different formats for each Service.
3. Every message utilizes the unified Envelope.
4. Immutability is enforced by design (new state = new message).
5. The protocol supports full traceability via `mission_id` and `correlation_id`.

---

## 10. References

- **EIP-0001**: Architecture First
- **EIP-0002**: Resource First Architecture
- **EIP-0009**: Hierarchical Execution Identifier
- **PR 4.1**: Kernel (Microkernel)
- **PR 4.2**: Runtime

---

## 11. History

| Date | Version | Author | Description |
| :--- | :--- | :--- | :--- |
| 2024-XX-XX | 1.0.0 | Architect | Initial Draft for PR 4.3 |
