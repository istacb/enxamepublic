# Runtime Service

## Visão Geral

O Runtime é um serviço permanente do Enxame responsável por transformar Tasks em resultados utilizando exclusivamente os recursos disponíveis no próprio Node.

**Importante:** O Runtime NÃO é um executor de IA. Ele é um ambiente de execução.

## Definição Oficial

> O Runtime é o ambiente responsável por receber uma Task, criar um Agent efêmero, executar a Task utilizando recursos locais, destruir completamente o Agent ao término e devolver o resultado ao Orchestrator.

## Filosofia

O Runtime deve ser:

- **Permanente**: Sempre disponível enquanto o Node estiver ativo
- **Leve**: Baixo consumo de recursos
- **Desacoplado**: Sem dependências de outros serviços
- **Orientado a eventos**: Comunicação via Event Bus
- **Sem estado persistente**: Zero estado residual entre Tasks
- **Otimizado para hardware antigo**: Compatível com máquinas limitadas

## Responsabilidades

O Runtime deve:

1. Receber Tasks do Orchestrator
2. Validar disponibilidade local
3. Verificar Capabilities necessárias
4. Verificar Capacity disponível
5. Criar Agents efêmeros
6. Executar Tasks
7. Monitorar execução
8. Tentar recuperação local (máx. 2 tentativas)
9. Cancelar execução quando solicitado
10. Destruir completamente o Agent
11. Liberar todos os Resources
12. Devolver resultado ao Orchestrator

## O que o Runtime NÃO faz

- ❌ Discovery
- ❌ Scheduler
- ❌ Protocol
- ❌ Heartbeat
- ❌ Failover
- ❌ Bibliotecário
- ❌ Mission
- ❌ Workflow

Esses conceitos pertencem a outras PRs.

## Arquitetura

### Fluxo Principal

```
Task → Runtime → Agent → Execution → Result → Destroy Agent
```

### Ciclo de Vida do Agent

Todo Agent é criado pelo Runtime. Nunca pelo Orchestrator ou outro Node.

1. **Created**: Agent instanciado
2. **Initializing**: Contexto configurado
3. **Executing**: Task em execução
4. **Completing**: Finalizando execução
5. **Destroying**: Limpando recursos
6. **Destroyed**: Zero estado residual

### Estados do Runtime

```
Idle → Receiving → Validating → CreatingAgent → Running → Completed
                                      ↓
                                      Canceled
                                      ↓
                                      Retrying
                                      ↓
                                      Failed
```

## Componentes

### Runtime (`runtime.ts`)

Serviço principal que gerencia todo o ciclo de vida das Tasks.

### Agent (`agent/agent.ts`)

Entidade efêmera criada para executar uma Task específica. Destruída completamente ao término.

### ExecutionContext (`executor/execution-context.ts`)

Mantém o estado durante a execução de uma Task.

### ExecutionResult (`executor/execution-result.ts`)

Representa o resultado final de uma Task.

### TaskExecutor (`executor/task-executor.ts`)

Responsável pela execução efetiva e recuperação de falhas.

### ResourceAllocator (`allocator/resource-allocator.ts`)

Gerencia alocação e liberação de recursos locais.

## Configuração

```typescript
interface RuntimeConfig {
  maxRetries: number;          // Máximo de tentativas (padrão: 2)
  defaultTimeoutMs: number;    // Timeout padrão (padrão: 30000ms)
  maxConcurrentTasks: number;  // Capacidade máxima (padrão: 4)
}
```

## Uso Básico

```typescript
import { Runtime } from './runtime';

// Cria Runtime com configuração customizada
const runtime = new Runtime({
  maxRetries: 2,
  defaultTimeoutMs: 30000,
  maxConcurrentTasks: 4,
});

// Inicializa
await runtime.initialize();

// Recebe uma Task
await runtime.receiveTask(
  'task-123',
  { prompt: 'Hello, world!' },
  [{ type: 'CPU', minimum: 1 }]
);

// Cancela uma Task
await runtime.cancelTask('task-123');

// Obtém status
const status = runtime.getStatus();

// Finaliza
await runtime.shutdown();
```

## Recuperação Local

O Runtime pode tentar recuperar falhas locais:

- Recriar Agent
- Reinicializar contexto
- Alterar estratégia de execução
- Utilizar outro Resource local compatível

**Valor padrão:** Máximo de 2 tentativas (configurável).

Após atingir o limite, reporta falha ao Orchestrator.

## Cancelamento

Quando o Orchestrator cancela uma Mission:

1. Runtime interrompe imediatamente a Task
2. Destrói o Agent
3. Libera Resources
4. Remove contexto
5. Retorna status: `Canceled`

## Zero Estado Residual

Ao término de cada Task:

- ✅ Memória zerada
- ✅ Contexto descartado
- ✅ Agent inexistente
- ✅ Runtime volta ao estado Idle
- ✅ Resources liberados

Nenhum estado temporário pode permanecer.

## Capacity

O Runtime utiliza toda a capacidade disponível do Node. Não existe limite fixo.

O limite é determinado pela Capacity anunciada pelo próprio Node.

**Exemplo:**
```
Capacity = 4 → até 4 Tasks simultâneas
```

## Regras Importantes

- ✅ Runtime nunca conhece Mission
- ✅ Runtime nunca conhece Workflow
- ✅ Runtime nunca cria Tasks
- ✅ Runtime nunca reorganiza Tasks
- ✅ Runtime nunca executa em outro Node
- ✅ Runtime nunca cria Agents remotos
- ✅ Runtime nunca mantém estado entre Tasks

## Interfaces

### IRuntime

Interface principal do serviço Runtime.

### IAgent

Interface de um Agent efêmero.

### ITaskExecutor

Interface do executor de Tasks.

### IExecutionContext

Interface do contexto de execução.

### IResourceAllocator

Interface do alocador de recursos.

### IExecutionResult

Interface do resultado de execução.

## Próximos Passos

Esta PR implementa a infraestrutura básica do Runtime. PRs futuras implementarão:

- **PR 4.3**: Discovery Service
- **PR 4.4**: Heartbeat Service
- **PR 4.5**: Scheduler Service
- **PR 4.6**: Protocol Implementation
- **PR 4.7**: Resources concretos (Ollama, CPU, GPU, etc.)

## Critérios de Aceite

- ✅ Runtime desacoplado do Kernel
- ✅ Runtime cria Agents efêmeros
- ✅ Agents destruídos ao término
- ✅ Zero estado residual
- ✅ Recuperação local implementada
- ✅ Cancelamento imediato implementado
- ✅ Interfaces documentadas
- ✅ Preparado para integração futura com Discovery e Scheduler
