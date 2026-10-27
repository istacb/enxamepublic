# Service Loader

The Service Loader is responsible exclusively for the lifecycle management of Services within a Node.

## Responsibilities

- Starting Services
- Respecting declared dependencies
- Monitoring initialization failures
- Restarting Services when permitted
- Respecting the lifecycle of each Service

## What It Does NOT Do

- Execute business logic
- Interpret behaviors
- Perform Discovery
- Send Heartbeats
- Implement Scheduler or Failover

## Structure

```
service-loader/
├── index.ts              # Main ServiceLoader implementation
├── interfaces/           # Interface definitions
│   └── index.ts
├── types/                # Type definitions
│   └── index.ts
├── lifecycle/            # Lifecycle management
│   └── index.ts
├── manifest/             # Manifest handling
│   └── index.ts
├── policy/               # Restart policy
│   └── index.ts
└── README.md
```

## Usage

```typescript
import { ServiceLoader } from './service-loader';
import type { ServiceManifest } from './service-loader/types';

// Define manifest
const manifest: ServiceManifest = {
  services: [
    {
      id: 'runtime',
      name: 'Runtime',
      type: 'permanent',
      dependencies: [],
      requirements: [],
      restartPolicy: {
        enabled: true,
        maxAttempts: 5,
        delayMs: 1000
      },
      autoStart: true
    },
    {
      id: 'heartbeat',
      name: 'Heartbeat',
      type: 'permanent',
      dependencies: ['runtime'],
      requirements: [],
      restartPolicy: {
        enabled: true,
        maxAttempts: 5,
        delayMs: 1000
      },
      autoStart: true
    },
    {
      id: 'discovery',
      name: 'Discovery',
      type: 'ephemeral',
      dependencies: ['runtime'],
      requirements: [],
      restartPolicy: {
        enabled: false,
        maxAttempts: 0,
        delayMs: 0
      },
      autoStart: true
    }
  ]
};

// Create and initialize Service Loader
const loader = new ServiceLoader();
await loader.initialize(manifest);

// Register service instances
// loader.registerService(runtimeService, runtimeDescriptor);

// Start all services
await loader.start();

// Stop all services
await loader.stop();
```

## Service Types

### Permanent
Services that run continuously throughout the Node's lifecycle.
- Examples: Runtime, Heartbeat, Kernel Interface
- Automatically restarted on failure (up to maxAttempts)

### Ephemeral
Services with a defined execution cycle that terminate upon completion.
- Examples: Discovery
- Normal termination is not treated as a failure
- Not automatically restarted

## Restart Policy

Default configuration:
- **Max Attempts**: 5
- **Delay**: 1000ms between attempts

After reaching max attempts, a failure event is published to the Heartbeat.

## States

| State | Description |
|-------|-------------|
| `Initializing` | Service Loader is initializing |
| `Loading` | Loading Service definitions from Manifest |
| `Running` | Actively managing Services |
| `Waiting Dependency` | Waiting for a dependency |
| `Restarting` | Attempting to restart a failed Service |
| `Failed` | Fatal error encountered |
| `Finished` | All work completed |

## Interfaces

- `IServiceLoader` - Main Service Loader interface
- `IService` - Service interface
- `IServiceManifest` - Manifest management
- `IServiceDescriptor` - Service descriptor
- `IServiceLifecycle` - Lifecycle management
- `IRestartPolicy` - Restart policy
- `IServiceDependency` - Service dependency
- `ICapabilityChecker` - Capability checking

## References

- [Documentation (EN)](../spec/en/protocols/service-loader.md)
- [Documentation (PT-BR)](../spec/pt-BR/protocols/service-loader.md)
- [Communication Protocol](../spec/en/protocols/communication-protocol.md)
