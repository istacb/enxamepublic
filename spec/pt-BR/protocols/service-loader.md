# Especificação do Protocolo Service Loader

**Versão:** 1.0.0  
**Status:** Rascunho  
**PR:** 4.6  
**Sprint:** 4

---

## 1. Objetivo

Definir o Service Loader responsável exclusivamente pelo gerenciamento do ciclo de vida dos Services dentro de um Node.

O Service Loader é encarregado de:

- Iniciar Services;
- Respeitar dependências declaradas;
- Monitorar falhas de inicialização;
- Reiniciar Services quando permitido;
- Respeitar o ciclo de vida de cada Service.

O Service Loader não executa lógica de negócio.

O Service Loader não interpreta comportamentos.

O Service Loader administra apenas o ciclo de vida dos Services.

---

## 2. Filosofia

O Service Loader deve ser:

- **Simples**: Fácil de entender e implementar.
- **Leve**: Consumo mínimo de recursos.
- **Desacoplado**: Independente de outros componentes.
- **Previsível**: Comportamento determinístico.
- **Orientado ao Ciclo de Vida**: Focado no gerenciamento do ciclo de vida dos services.
- **Compatível com Legado**: Compatível com hardware antigo.

Seu consumo de recursos deve ser mínimo.

---

## 3. Responsabilidade Única

O Service Loader administra Services.

Nunca administra comportamentos.

Nunca interpreta regras de negócio.

Nunca toma decisões distribuídas.

---

## 4. Fluxo de Inicialização

Fluxo obrigatório:

```
Node Boot
    ↓
Kernel
    ↓
Service Loader
    ↓
Inicialização dos Services
    ↓
Runtime
    ↓
Discovery
    ↓
Heartbeat
    ↓
Node Ready
```

O Kernel inicia apenas o Service Loader.

Todo o restante é responsabilidade do Service Loader.

---

## 5. Dependências

Cada Service declara explicitamente suas dependências.

Exemplo:

```yaml
Heartbeat
requires:
  - Runtime
```

O Service Loader apenas garante a ordem correta.

Ele nunca interpreta o funcionamento interno dos Services.

---

## 6. Manifesto

Os Services disponíveis devem ser definidos através de um Manifesto do Node.

O Manifesto informa:

- Services disponíveis;
- Dependências;
- Requisitos mínimos;
- Tipo do Service;
- Política de reinício.

O Service Loader apenas interpreta o Manifesto.

Não utilizar listas fixas compiladas no código.

### 6.1 Estrutura do Manifesto

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

## 7. Tipos de Service

Existem dois tipos de Service.

### 7.1 Permanente

Exemplos:

- Runtime
- Heartbeat
- Kernel Interface

Services Permanentes são esperados para executar continuamente durante todo o ciclo de vida do Node.

### 7.2 Efêmero

Exemplos:

- Discovery

Services Efêmeros possuem um ciclo de execução definido e terminam ao completar sua tarefa.

O Service Loader deve respeitar o ciclo de vida declarado.

O término normal de um Service efêmero nunca deve ser tratado como falha.

---

## 8. Reinicialização

Caso um Service permanente falhe:

O Service Loader deve tentar reiniciá-lo.

Número padrão:

**5 tentativas**.

O número deve ser configurável.

Após atingir o limite:

Publicar um evento de falha.

### 8.1 Configuração de Reinício

```typescript
interface RestartConfig {
  defaultMaxAttempts: number; // Padrão: 5
  defaultDelayMs: number;     // Atraso entre tentativas
}
```

---

## 9. Falhas

Quando um Service não puder ser recuperado:

Publicar evento ao Heartbeat.

Heartbeat informa ao Orchestrator.

O Orchestrator informa ao Judge.

O Judge poderá recomendar verificação física do equipamento.

Exemplos:

- Fonte;
- Cabo;
- Armazenamento;
- Memória;
- Falha completa do Node.

O Service Loader nunca realiza diagnóstico.

Ele apenas informa a falha.

---

## 10. Discovery

Discovery é um Service efêmero.

Ao finalizar normalmente:

O Service Loader considera a execução concluída.

Não reiniciar Discovery automaticamente.

Discovery somente poderá ser executado novamente quando solicitado pelo Orchestrator ou durante um novo processo de inicialização do Node.

---

## 11. Requisitos

O Service Loader verifica apenas requisitos declarados.

Exemplo:

```yaml
Service
requires:
  - GPU
```

Caso o Node não possua GPU:

O Service não será iniciado.

O Service Loader não procura alternativas.

O Service Loader não adapta configurações.

---

## 12. Capabilities

O Service Loader apenas verifica se o Node atende aos requisitos necessários para carregar um Service.

Capabilities continuam sendo responsabilidade do Discovery e do Heartbeat.

---

## 13. Comunicação

Toda comunicação deve utilizar exclusivamente o Communication Protocol oficial.

Não criar novos formatos.

Não criar novos envelopes.

Referenciar a [Especificação do Communication Protocol](./communication-protocol.md).

---

## 14. Estados

Estados mínimos:

| Estado | Descrição |
| :--- | :--- |
| `Initializing` | Service Loader está inicializando |
| `Loading` | Carregando definições de Services do Manifesto |
| `Running` | Service Loader está gerenciando Services ativamente |
| `Waiting Dependency` | Aguardando uma dependência ser satisfeita |
| `Restarting` | Tentando reiniciar um Service falho |
| `Failed` | Service Loader encontrou um erro fatal |
| `Finished` | Service Loader completou seu trabalho (todos os Services finalizados) |

---

## 15. Interfaces

Criar interfaces desacopladas para:

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

## 16. O Que o Service Loader NÃO Faz

- Não executa Tasks.
- Não conhece Missions.
- Não conhece Workflows.
- Não conhece Agents.
- Não conhece IA.
- Não realiza Discovery.
- Não envia Heartbeats.
- Não realiza Scheduler.
- Não realiza Failover.
- Não interpreta comportamentos dos Services.
- Não implementa Logging.

---

## 17. Critérios de Aceite

Esta especificação é considerada completa quando:

1. O Service Loader possui responsabilidade única.
2. O Kernel inicia apenas o Service Loader.
3. O Service Loader inicia todos os demais Services.
4. As dependências declaradas forem respeitadas.
5. O ciclo de vida de cada Service for respeitado.
6. Services efêmeros não forem reiniciados automaticamente.
7. Services permanentes puderem ser reiniciados.
8. O número de tentativas for configurável.
9. O padrão for cinco tentativas.
10. Toda comunicação utilizar o protocolo oficial.
11. Toda documentação estiver disponível em inglês e português.

---

## 18. Referências

- **EIP-0001**: Architecture First
- **EIP-0002**: Resource First Architecture
- **Communication Protocol**: PR 4.3
- **Kernel**: PR 4.1
- **Runtime**: PR 4.2

---

## 19. Histórico

| Data | Versão | Autor | Descrição |
| :--- | :--- | :--- | :--- |
| 2024-XX-XX | 1.0.0 | Architect | Rascunho Inicial para PR 4.6 |
