# Enxame Microkernel

O Kernel do Enxame é um microkernel extremamente mínimo cuja única função é manter o Node vivo. Ele não executa IA, não conhece Missions, Workflows, Tasks, ou qualquer conceito de domínio.

## Filosofia

- **Minimalismo**: O Kernel deve ser extremamente pequeno e permanecer praticamente imutável durante toda a vida do projeto.
- **Agnosticismo**: O Kernel não conhece IA, LLMs, Missions, Workflows, Judges, Orchestrators, etc.
- **Extensibilidade**: Novas funcionalidades são implementadas como Services, nunca dentro do Kernel.

## Princípios de Design

| Código | Descrição |
|--------|-----------|
| K-001 | O Kernel NÃO suporta atualização em tempo de execução. Qualquer alteração exige reinicialização do Node. |
| K-002 | O Kernel somente pode ser alterado por atualização oficial do software. |
| K-003 | O Kernel é completamente agnóstico. Não conhece conceitos de domínio. |
| K-004 | O Kernel conhece apenas o próprio Node. Não conhece outros Nodes. |
| K-005 | Caso o Kernel falhe, o Node é encerrado; os demais Nodes continuam funcionando. |
| K-006 | Node = Máquina. Cada máquina executa exatamente um Node. |

## Responsabilidades do Kernel

O Kernel deve apenas:

1. Inicializar o Node
2. Carregar configurações
3. Manter o ciclo de vida
4. Disponibilizar um Event Bus interno
5. Registrar Services
6. Registrar Capabilities
7. Iniciar e finalizar Services
8. Expor estado interno do Node

## Estrutura

```
kernel/
├── kernel.ts           # Implementação principal do Kernel
├── index.ts            # Ponto de entrada e exports públicos
├── config/             # Carregamento de configuração
├── lifecycle/          # Gerenciamento do ciclo de vida
├── registry/           # Service e Capability Registries
├── capability/         # (Reservado para futuras extensões)
├── events/             # Event Bus interno
├── interfaces/         # Definições de interfaces
├── types/              # Definições de tipos
└── errors/             # Classes de erro
```

## Lifecycle

O Node passa pelos seguintes estados durante seu ciclo de vida:

```
Booting → Initializing → Ready → Running → Stopping → Stopped
                                             ↓
                                          Faulted
```

### Estados

| Estado | Descrição |
|--------|-----------|
| `Booting` | Node está iniciando |
| `Initializing` | Componentes estão sendo inicializados |
| `Ready` | Node está pronto para aceitar trabalho |
| `Running` | Node está ativamente executando |
| `Stopping` | Node está sendo desligado |
| `Stopped` | Node foi desligado (estado terminal) |
| `Faulted` | Node encontrou um erro fatal (estado terminal) |

## Interfaces Principais

### IKernel

Interface principal do Kernel. Responsável por inicializar, iniciar, parar e expor o estado do Node.

### IService

Interface para todos os Services no Enxame. Services são componentes independentes que podem ser registrados com o Kernel.

Exemplos futuros: Runtime, Discovery, Heartbeat, Scheduler

### IServiceRegistry

Responsável por manter referências aos Services registrados. **Não executa Services.**

### ICapabilityRegistry

Responsável por registrar capacidades oferecidas pelo Node. Capacidades são dinâmicas e podem aparecer ou desaparecer durante a execução.

Exemplos: CPU, GPU, Storage, Ollama, Whisper, Internet

### IEventBus

Barramento de eventos interno ao Node. Exclusivamente interno - nenhum protocolo de comunicação é implementado nesta PR.

### ILifecycle

Gerencia o ciclo de vida do Node, incluindo transições de estado e notificações.

## Uso Básico

```typescript
import { Kernel, LifecycleState } from '@enxame/kernel';

// Criar instância do Kernel
const kernel = new Kernel();

// Inicializar com configuração
await kernel.initialize({
  nodeId: 'node-001',
  nodeName: 'My Node',
  logLevel: 'info'
});

// Registrar um service (exemplo futuro)
// await kernel.registerService(myService);

// Registrar uma capability
kernel.registerCapability({
  id: 'cpu-001',
  name: 'CPU Cores',
  type: 'cpu',
  available: true,
  metadata: { cores: 8 }
});

// Iniciar o Kernel
await kernel.start();

// Obter estado atual
const state = kernel.getState();
console.log(`Node ${state.nodeId} está ${state.lifecycle}`);

// Parar o Kernel
await kernel.stop();
```

## Regras Importantes

1. **Services são independentes dos Resources**: Services sempre podem existir. Resources podem aparecer e desaparecer durante a execução.

2. **Indisponibilidade de Resource não encerra Service**: A indisponibilidade de um Resource nunca encerra um Service. Ela apenas altera as Capabilities publicadas.

3. **Sem dependências de domínio**: O Kernel não contém nenhuma referência a:
   - IA, Ollama, LLM, Prompt
   - Mission, Workflow, Task
   - Judge, Orchestrator, Scheduler
   - Discovery, Heartbeat, Protocol
   - Failover, Runtime

## Próximas PRs

Esta PR é exclusivamente arquitetural. As próximas PRs da Sprint 4 implementarão:

- **PR 4.2**: Runtime Service
- **PR 4.3**: Discovery Service
- **PR 4.4**: Heartbeat Service
- **PR 4.5**: Scheduler Service
- **PR 4.6**: Protocol Implementation

## Critérios de Aceite

- [x] Kernel completamente desacoplado
- [x] Nenhuma referência a IA dentro do Kernel
- [x] Nenhuma referência ao Orchestrator dentro do Kernel
- [x] Nenhuma referência ao Judge dentro do Kernel
- [x] Registries separados (Service e Capability)
- [x] Lifecycle implementado
- [x] Event Bus interno definido
- [x] Todas as interfaces documentadas
- [x] Arquitetura preparada para PR 4.2 (Runtime)
