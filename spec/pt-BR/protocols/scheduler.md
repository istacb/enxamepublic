# Especificação do Protocolo Scheduler

**Versão:** 1.0.0  
**Status:** Rascunho  
**PR:** 4.7  
**Sprint:** 4

---

## 1. Objetivo

Definir o Scheduler como um componente interno do Orchestrator responsável por decidir qual Node deverá executar uma Task.

O Scheduler nunca executa Tasks.

O Scheduler nunca comunica diretamente com Nodes.

O Scheduler apenas analisa o estado atual do Enxame e devolve ao Orchestrator a melhor decisão de escalonamento.

---

## 2. Filosofia

O Scheduler deve ser:

- **Simples**: Fácil de entender e implementar.
- **Determinístico**: Decisões previsíveis baseadas em dados disponíveis.
- **Orientado a Eventos**: Acionado por eventos, não polling.
- **Desacoplado**: Independente de outros componentes.
- **Eficiente**: Consumo mínimo de recursos.
- **Compatível com Legado**: Compatível com hardware antigo.

Toda decisão deve ser baseada exclusivamente nas informações disponíveis.

Nenhuma decisão deve utilizar heurísticas complexas ou IA.

---

## 3. Responsabilidade Única

O Scheduler possui apenas uma responsabilidade:

**Selecionar o melhor Node para executar uma Task.**

Todo o restante pertence ao Orchestrator.

---

## 4. Fonte das Informações

O Scheduler utiliza exclusivamente informações mantidas pelo Orchestrator.

Exemplos:

- Registry de Nodes;
- Discovery;
- Heartbeat;
- Queue de Tasks.

O Scheduler nunca consulta diretamente um Node.

---

## 5. Eventos

O Scheduler é orientado a eventos.

Ele é executado quando ocorrer qualquer evento que possa alterar o escalonamento.

Exemplos:

- Nova Task chega.
- Runtime Available.
- Novo Node registrado.
- Node removido.
- Capability alterada.
- Retorno de Failover.

O Scheduler nunca executa polling.

---

## 6. Fila

O Scheduler administra a fila de Tasks.

Quando uma nova Task chega:

- Verifica imediatamente a disponibilidade da rede;
- Caso exista um Node compatível disponível, agenda imediatamente;
- Caso contrário, coloca a Task na fila.

Quando um Runtime fica disponível:

- Verifica imediatamente a fila;
- Seleciona a próxima Task compatível;
- Agenda a execução.

### 6.1 Ordem da Fila

A política inicial será **FIFO (First In, First Out)**.

A primeira Task que entrar na fila será a primeira a ser escalonada.

Não implementar prioridades nesta PR.

A arquitetura deve permitir políticas futuras sem alterar o núcleo do Scheduler.

---

## 7. Processo de Escalonamento

Fluxo obrigatório:

```
Receber Task
    ↓
Filtrar Nodes compatíveis
    ↓
Remover Nodes indisponíveis
    ↓
Existe Node disponível?
    ↓
Não
    ↓
Fila
    ↓
Sim
    ↓
Selecionar Node
    ↓
Retornar decisão ao Orchestrator
```

---

## 8. Critérios de Seleção

A seleção deve seguir a seguinte ordem:

1. **Capability compatível**.
2. **Capacity disponível**.
3. **Primeiro Node disponível**.

Caso existam múltiplos Nodes equivalentes:

Selecionar o primeiro disponível.

A arquitetura deve permitir futuros algoritmos de balanceamento sem alterar a interface pública.

### 8.1 Correspondência de Capabilities

Uma Task somente poderá ser enviada para um Node que possua todas as Capabilities necessárias.

Caso nenhum Node possua as Capabilities exigidas:

A Task permanece na fila.

### 8.2 Capacity

Capacity representa a capacidade disponível para receber novas Tasks.

Caso o Node esteja ocupado:

Ele não participa do escalonamento.

### 8.3 GPU e Recursos Exclusivos

Caso uma Task exija um recurso exclusivo atualmente ocupado:

O Scheduler não divide a Task.

O Scheduler não procura alternativas artificiais.

A Task permanece na fila até existir disponibilidade.

---

## 9. Tasks

O Scheduler trabalha exclusivamente com Tasks.

Mission pertence ao Orchestrator.

Workflow pertence ao Orchestrator.

O Scheduler nunca interpreta Missões.

O Scheduler nunca modifica Workflows.

---

## 10. Comunicação

O Scheduler nunca comunica diretamente com Nodes.

Toda comunicação ocorre exclusivamente através do Orchestrator utilizando o Communication Protocol oficial.

Consulte a [Especificação do Communication Protocol](./communication-protocol.md).

---

## 11. Interfaces

Criar interfaces desacopladas para:

- `IScheduler`
- `ISchedulingPolicy`
- `ITaskQueue`
- `ISchedulingDecision`
- `INodeSelection`
- `ICapabilityMatcher`

### 11.1 IScheduler

```typescript
interface IScheduler {
  scheduleTask(task: Task): Promise<ISchedulingDecision>;
  onNodeRegistered(node: NodeInfo): void;
  onNodeRemoved(nodeId: string): void;
  onRuntimeAvailable(nodeId: string): void;
  onCapabilityChanged(nodeId: string, capabilities: Capability[]): void;
  getQueueStatus(): QueueStatus;
}
```

### 11.2 ISchedulingPolicy

```typescript
interface ISchedulingPolicy {
  name: string;
  selectNode(candidates: NodeInfo[], task: Task): NodeInfo | null;
  reorderQueue(queue: Task[]): Task[];
}
```

### 11.3 ITaskQueue

```typescript
interface ITaskQueue {
  enqueue(task: Task): void;
  dequeue(): Task | null;
  peek(): Task | null;
  size(): number;
  isEmpty(): boolean;
  filterByCapability(capabilities: Capability[]): Task[];
}
```

### 11.4 ISchedulingDecision

```typescript
interface ISchedulingDecision {
  taskId: string;
  nodeId: string | null;
  status: 'scheduled' | 'queued' | 'rejected';
  reason?: string;
  timestamp: number;
}
```

### 11.5 INodeSelection

```typescript
interface INodeSelection {
  filterByCapability(nodes: NodeInfo[], required: Capability[]): NodeInfo[];
  filterByCapacity(nodes: NodeInfo[]): NodeInfo[];
  selectFirst(nodes: NodeInfo[]): NodeInfo | null;
}
```

### 11.6 ICapabilityMatcher

```typescript
interface ICapabilityMatcher {
  matches(nodeCapabilities: Capability[], taskRequirements: Capability[]): boolean;
  missingCapabilities(nodeCapabilities: Capability[], taskRequirements: Capability[]): Capability[];
}
```

---

## 12. O Que o Scheduler NÃO Faz

- Não executa Tasks.
- Não cria Agents.
- Não conhece IA.
- Não realiza Discovery.
- Não envia Heartbeats.
- Não realiza Failover.
- Não comunica diretamente com Nodes.
- Não consulta Runtime diretamente.
- Não implementa polling.
- Não implementa Logging.

---

## 13. Critérios de Aceite

Esta especificação é considerada completa quando:

1. O Scheduler possuir responsabilidade única.
2. Trabalhar exclusivamente sobre Tasks.
3. Utilizar apenas informações do Orchestrator.
4. Administrar corretamente a fila.
5. Ser orientado a eventos.
6. Não utilizar polling.
7. Não comunicar diretamente com Nodes.
8. Utilizar exclusivamente o protocolo oficial.
9. Possuir documentação em inglês e português.

---

## 14. Referências

- **EIP-0001**: Architecture First
- **EIP-0002**: Resource First Architecture
- **Communication Protocol**: PR 4.3
- **Orchestrator**: Componente Interno
- **Service Loader**: PR 4.6

---

## 15. Histórico

| Data | Versão | Autor | Descrição |
| :--- | :--- | :--- | :--- |
| 2024-XX-XX | 1.0.0 | Architect | Rascunho Inicial para PR 4.7 |

