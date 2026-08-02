# Service Loader Protocol Specification

**Version:** 1.0.0  
**Status:** Draft  
**PR:** 4.6  
**Sprint:** 4

---

## 1. Objective

Define the Service Loader responsible exclusively for the lifecycle management of Services within a Node.

The Service Loader is tasked with:

- Starting Services;
- Respecting declared dependencies;
- Monitoring initialization failures;
- Restarting Services when permitted;
- Respecting the lifecycle of each Service.

The Service Loader does not execute business logic.

The Service Loader does not interpret behaviors.

The Service Loader administers only the lifecycle of Services.

---

## 2. Philosophy

The Service Loader must be:

- **Simple**: Easy to understand and implement.
- **Lightweight**: Minimal resource consumption.
- **Decoupled**: Independent from other components.
- **Predictable**: Deterministic behavior.
- **Lifecycle-Oriented**: Focused on service lifecycle management.
- **Legacy-Compatible**: Compatible with old hardware.

Its resource consumption must be minimal.

---

## 3. Single Responsibility

The Service Loader administers Services.

It never administers behaviors.

It never interprets business rules.

It never makes distributed decisions.

---

## 4. Initialization Flow

Mandatory flow:

```
Node Boot
    ↓
Kernel
    ↓
Service Loader
    ↓
Services Initialization
    ↓
Runtime
    ↓
Discovery
    ↓
Heartbeat
    ↓
Node Ready
```

The Kernel initiates only the Service Loader.

Everything else is the responsibility of the Service Loader.

---

## 5. Dependencies

Each Service explicitly declares its dependencies.

Example:

```yaml
Heartbeat
requires:
  - Runtime
```

The Service Loader only guarantees the correct order.

It never interprets the internal functioning of Services.

---

## 6. Manifest

Available Services must be defined through a Node Manifest.

The Manifest informs:

- Available Services;
- Dependencies;
- Minimum requirements;
- Service type;
- Restart policy.

The Service Loader only interprets the Manifest.

Do not use fixed lists compiled into the code.

### 6.1 Manifest Structure

```typescript
interface ServiceManifest {
  services: ServiceDescriptor[];
}

interface ServiceDescriptor {
  id: string;
  name: string;
  type: 'permanent' | 'ephemeral';
  dependencies?: string[];
  requirements?: string[];
  restartPolicy: RestartPolicy;
  autoStart: boolean;
}

interface RestartPolicy {
  enabled: boolean;
  maxAttempts: number;
  delayMs: number;
}
```

---

## 7. Service Types

There are two types of Services.

### 7.1 Permanent

Examples:

- Runtime
- Heartbeat
- Kernel Interface

Permanent Services are expected to run continuously throughout the Node's lifecycle.

### 7.2 Ephemeral

Examples:

- Discovery

Ephemeral Services have a defined execution cycle and terminate upon completing their task.

The Service Loader must respect the declared lifecycle.

The normal termination of an ephemeral Service must never be treated as a failure.

---

## 8. Reinitialization

If a permanent Service fails:

The Service Loader must attempt to restart it.

Default number:

**5 attempts**.

The number must be configurable.

After reaching the limit:

Publish a failure event.

### 8.1 Restart Configuration

```typescript
interface RestartConfig {
  defaultMaxAttempts: number; // Default: 5
  defaultDelayMs: number;     // Delay between attempts
}
```

---

## 9. Failures

When a Service cannot be recovered:

Publish an event to the Heartbeat.

Heartbeat informs the Orchestrator.

The Orchestrator informs the Judge.

The Judge may recommend physical equipment verification.

Examples:

- Power supply;
- Cable;
- Storage;
- Memory;
- Complete Node failure.

The Service Loader never performs diagnostics.

It only reports the failure.

---

## 10. Discovery

Discovery is an ephemeral Service.

Upon normal completion:

The Service Loader considers the execution concluded.

Do not restart Discovery automatically.

Discovery may only be executed again when requested by the Orchestrator or during a new Node initialization process.

---

## 11. Requirements

The Service Loader verifies only declared requirements.

Example:

```yaml
Service
requires:
  - GPU
```

If the Node does not possess a GPU:

The Service will not be started.

The Service Loader does not search for alternatives.

The Service Loader does not adapt configurations.

---

## 12. Capabilities

The Service Loader only verifies whether the Node meets the necessary requirements to load a Service.

Capabilities remain the responsibility of Discovery and Heartbeat.

---

## 13. Communication

All communication must utilize exclusively the official Communication Protocol.

Do not create new formats.

Do not create new envelopes.

Refer to the [Communication Protocol Specification](./communication-protocol.md).

---

## 14. States

Minimum states:

| State | Description |
| :--- | :--- |
| `Initializing` | Service Loader is initializing |
| `Loading` | Loading Service definitions from Manifest |
| `Running` | Service Loader is actively managing Services |
| `Waiting Dependency` | Waiting for a dependency to be satisfied |
| `Restarting` | Attempting to restart a failed Service |
| `Failed` | Service Loader encountered a fatal error |
| `Finished` | Service Loader completed its work (all Services finished) |

---

## 15. Interfaces

Create decoupled interfaces for:

- `IServiceLoader`
- `IService`
- `IServiceManifest`
- `IServiceDescriptor`
- `IServiceLifecycle`
- `IRestartPolicy`
- `IServiceDependency`

### 15.1 IServiceLoader

```typescript
interface IServiceLoader {
  initialize(manifest: ServiceManifest): Promise<void>;
  start(): Promise<void>;
  stop(): Promise<void>;
  getState(): ServiceLoaderState;
}
```

### 15.2 IService

```typescript
interface IService {
  readonly id: string;
  readonly name: string;
  initialize(): Promise<void>;
  start(): Promise<void>;
  stop(): Promise<void>;
  isHealthy(): boolean;
}
```

### 15.3 IServiceManifest

```typescript
interface IServiceManifest {
  services: IServiceDescriptor[];
  validate(): boolean;
}
```

### 15.4 IServiceDescriptor

```typescript
interface IServiceDescriptor {
  id: string;
  name: string;
  type: ServiceType;
  dependencies: IServiceDependency[];
  requirements: string[];
  restartPolicy: IRestartPolicy;
  autoStart: boolean;
}
```

### 15.5 IServiceLifecycle

```typescript
interface IServiceLifecycle {
  currentState: ServiceState;
  transition(to: ServiceState): boolean;
  is(state: ServiceState): boolean;
}
```

### 15.6 IRestartPolicy

```typescript
interface IRestartPolicy {
  enabled: boolean;
  maxAttempts: number;
  currentAttempt: number;
  delayMs: number;
  canRetry(): boolean;
  reset(): void;
}
```

### 15.7 IServiceDependency

```typescript
interface IServiceDependency {
  serviceId: string;
  required: boolean;
  isSatisfied(): boolean;
}
```

---

## 16. What the Service Loader Does NOT Do

- Does not execute Tasks.
- Does not know Missions.
- Does not know Workflows.
- Does not know Agents.
- Does not know AI.
- Does not perform Discovery.
- Does not send Heartbeats.
- Does not perform Scheduler.
- Does not perform Failover.
- Does not interpret Service behaviors.
- Does not implement Logging.

---

## 17. Acceptance Criteria

This specification is considered complete when:

1. The Service Loader has single responsibility.
2. The Kernel initiates only the Service Loader.
3. The Service Loader starts all other Services.
4. Declared dependencies are respected.
5. The lifecycle of each Service is respected.
6. Ephemeral Services are not automatically restarted.
7. Permanent Services can be restarted.
8. The number of attempts is configurable.
9. The default is five attempts.
10. All communication utilizes the official protocol.
11. All documentation is available in English and Portuguese.

---

## 18. References

- **EIP-0001**: Architecture First
- **EIP-0002**: Resource First Architecture
- **Communication Protocol**: PR 4.3
- **Kernel**: PR 4.1
- **Runtime**: PR 4.2

---

## 19. History

| Date | Version | Author | Description |
| :--- | :--- | :--- | :--- |
| 2024-XX-XX | 1.0.0 | Architect | Initial Draft for PR 4.6 |
