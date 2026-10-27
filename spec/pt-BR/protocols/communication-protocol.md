# Especificação do Protocolo de Comunicação

**Versão:** 1.0.0  
**Status:** Rascunho  
**PR:** 4.3  
**Sprint:** 4

---

## 1. Objetivo

Definir a linguagem de comunicação utilizada por todos os componentes do Enxame.

Esta especificação serve como base para:

- Discovery
- Heartbeat
- Runtime
- Scheduler
- Failover
- Service Loader
- Bibliotecário
- Judge
- Orchestrator

Todos os componentes utilizarão este protocolo.

---

## 2. Filosofia

O protocolo deve ser:

- **Simples**: Fácil de entender e implementar.
- **Imutável**: Mensagens nunca mudam após serem criadas.
- **Leve**: Sobrecarga mínima para compatibilidade com hardware legado.
- **Desacoplado**: Independente de mecanismos de transporte.
- **Orientado a Eventos**: Acionado por mudanças de estado e ações.
- **Compatível com Legado**: Eficiente o suficiente para hardware antigo.

**Nota:** O protocolo não implementa transporte. Ele apenas define como as mensagens são estruturadas. A implementação poderá utilizar qualquer mecanismo de transporte no futuro (HTTP, TCP, gRPC, etc.).

---

## 3. Princípios

### 3.1 Envelope Único
Toda comunicação utiliza uma estrutura de Envelope única e unificada.

### 3.2 Imutabilidade
Todas as mensagens são imutáveis.
- Uma nova necessidade gera uma nova mensagem.
- Mensagens nunca são alteradas durante o trânsito.
- Modificações resultam na criação de uma nova instância de mensagem.

### 3.3 Agnosticismo
O protocolo é agnóstico a:
- Camada de transporte (HTTP, TCP, UDP, etc.)
- Formato de serialização (JSON, Binário, etc.)
- Topologia de rede

---

## 4. O Envelope

Toda mensagem deve possuir um Envelope comum contendo os seguintes campos:

| Campo | Tipo | Obrigatório | Descrição |
| :--- | :--- | :--- | :--- |
| `message_id` | String | Sim | Identificador único para esta mensagem específica. |
| `timestamp` | ISO8601 | Sim | Timestamp UTC da criação da mensagem. |
| `sender` | String | Sim | Identificador do Node ou Service enviando a mensagem. |
| `receiver` | String | Sim | Identificador do destinatário pretendido (Node, Service ou Broadcast). |
| `message_type` | Enum | Sim | Categoriza a intenção da mensagem (ver Seção 5). |
| `mission_id` | String | Não | Identificador Hierárquico de Execução (HEI) da Missão pai. Obrigatório para mensagens operacionais. |
| `correlation_id` | String | Não | Liga mensagens relacionadas (ex: Requisição/Resposta, Task/Resultado). |
| `payload` | Object | Não | Conteúdo real de dados da mensagem. Estrutura depende do `message_type`. |

### 4.1 Especificações dos Campos

#### `message_id`
- Deve ser único em todo o ciclo de vida do Swarm.
- Usado para deduplicação e auditoria.

#### `timestamp`
- Deve estar em UTC.
- Usado para ordenação e cálculos de timeout.

#### `sender` / `receiver`
- Identificadores devem ser consistentes com a identidade do Node definida no Kernel.
- `receiver` pode ser um endereço de broadcast (ex: `*` ou `broadcast`) para propósitos de descoberta.

#### `mission_id`
- Segue o padrão Hierarchical Execution Identifier (HEI) definido na EIP-0009.
- Obrigatório para qualquer mensagem relacionada à execução de uma Missão.

#### `correlation_id`
- Tipicamente corresponde ao `message_id` da requisição sendo respondida.
- Permite rastrear ciclos de requisição/resposta.

#### `payload`
- Schema varia conforme o `message_type`.
- Deve ser autocontido; nenhuma referência externa é necessária para processamento básico.

---

## 5. Tipos de Mensagem

Mensagens são categorizadas em três grupos distintos: Infraestrutura, Operacionais e Administrativas.

### 5.1 Mensagens de Infraestrutura

Usadas para gerenciamento de nodes, descoberta e monitoramento de saúde.

| Tipo | Código | Descrição |
| :--- | :--- | :--- |
| `DISCOVERY_REQUEST` | `INFRA.01` | Requisição por nodes disponíveis no swarm. |
| `DISCOVERY_RESPONSE` | `INFRA.02` | Resposta contendo capacidades e status do node. |
| `HEARTBEAT` | `INFRA.03` | Sinal periódico indicando vitalidade do node. |
| `CAPABILITY_UPDATE` | `INFRA.04` | Notificação de mudança nas capacidades locais (Hot Plug/Remove). |
| `READY` | `INFRA.05` | Node está inicializado e pronto para aceitar tasks. |
| `BUSY` | `INFRA.06` | Node está temporariamente incapaz de aceitar novas tasks. |
| `SHUTDOWN` | `INFRA.07` | Node está parando serviços graciosamente. |

### 5.2 Mensagens Operacionais

Usadas para execução de missões, distribuição de tasks e reporte de resultados.
**Autoridade:** Apenas o Orchestrator inicia fluxo operacional; Nodes respondem.

| Tipo | Código | Descrição |
| :--- | :--- | :--- |
| `TASK_ASSIGN` | `OPS.01` | Atribuição de uma Task específica a um Node. |
| `TASK_RESULT` | `OPS.02` | Reporte de conclusão bem-sucedida de uma Task. |
| `TASK_FAILURE` | `OPS.03` | Reporte de falha de uma Task após retries. |
| `TASK_CANCEL` | `OPS.04` | Requisição para parar imediatamente uma Task em execução. |
| `TASK_RETRY` | `OPS.05` | Instrução para retry de uma Task falhada (recuperação local). |
| `TASK_REPLAN` | `OPS.06` | Notificação de que o workflow da Missão está sendo replanejado. |
| `SERVICE_PROMOTION` | `OPS.07` | Notificação de promoção temporária de serviço (Failover). |

### 5.3 Mensagens Administrativas

Usadas para configuração, diagnósticos e saúde do sistema.

| Tipo | Código | Descrição |
| :--- | :--- | :--- |
| `CONFIG_UPDATE` | `ADM.01` | Push de atualizações de configuração para um Node. |
| `DIAGNOSTICS_REQUEST` | `ADM.02` | Requisição de dados detalhados de diagnóstico de um Node. |
| `DIAGNOSTICS_REPORT` | `ADM.03` | Reporte detalhado de saúde do sistema e métricas. |
| `HEALTH_CHECK` | `ADM.04` | Requisição de health check profundo (além do heartbeat). |

---

## 6. Regras de Comunicação

### 6.1 Autoridade de Iniciação

- **Mensagens de Infraestrutura:** Apenas **Nodes** podem iniciar mensagens de infraestrutura (ex: Heartbeat, Capability Update).
- **Mensagens Operacionais:** Apenas o **Orchestrator** inicia mensagens operacionais (ex: Task Assignment).
- **Respostas:** Qualquer componente pode enviar uma mensagem de resposta correlacionada a uma mensagem recebida.

### 6.2 Restrições de Topologia

- **Sem Comunicação Direta Node-a-Node:** Nodes nunca enviam Tasks ou mensagens Operacionais diretamente para outros Nodes.
- **Coordenação Centralizada:** Toda comunicação distribuída passa pelo Orchestrator.
- **Fluxo:** `Node → Orchestrator → Node`.

### 6.3 Aplicação da Imutabilidade

- Uma vez que um envelope de mensagem é selado (criado), ele não pode ser modificado.
- Se uma mudança de estado requer atualização de informação, uma **nova mensagem** deve ser gerada com um novo `message_id` e `timestamp`.
- O `correlation_id` deve ligar a nova mensagem ao estado anterior se aplicável.

---

## 7. Rastreamento e Observabilidade

### 7.1 Rastreabilidade
Toda mensagem relacionada a uma Missão deve possuir rastreabilidade completa.
- Use `mission_id` para agrupar todas as mensagens pertencentes a uma Missão específica.
- Use `correlation_id` para ligar pares específicos de requisição/resposta.

### 7.2 Hierarquia
O protocolo suporta o Identificador Hierárquico de Execução (HEI) definido na EIP-0009.
- O `mission_id` no envelope permite reconstruir a árvore de execução:
  `Missão → Workflow → Task → Execução`.

### 7.3 Visibilidade do Judge
O componente **Judge** monitora tipos específicos de mensagem para auditoria e garantia de qualidade:
- **Monitorados:** `TASK_ASSIGN`, `TASK_RESULT`, `TASK_FAILURE`, `TASK_CANCEL`, `TASK_RETRY`, `TASK_REPLAN`.
- **Ignorados:** `DISCOVERY`, `HEARTBEAT`, `CAPABILITY_UPDATE` (ruído de infraestrutura).

---

## 8. Logging e Transporte

### 8.1 Logging
- O protocolo **não** implementa logging.
- Logging é responsabilidade de um Service independente.
- O protocolo apenas transporta mensagens; não dita onde ou como são armazenadas.

### 8.2 Agnosticismo de Transporte
Esta especificação **não define** a camada de transporte.
- Transportes suportados (implementação futura): HTTP, TCP, UDP, gRPC, WebSocket, Memória Compartilhada.
- A estrutura do Envelope permanece constante independentemente do mecanismo de transporte.

---

## 9. Critérios de Aceite

Esta especificação é considerada completa quando:

1. Todos os componentes futuros (Discovery, Runtime, Scheduler, etc.) conseguem utilizar a mesma estrutura de Envelope.
2. Não existem formatos diferentes para cada Service.
3. Toda mensagem utiliza o Envelope unificado.
4. A imutabilidade é aplicada por design (novo estado = nova mensagem).
5. O protocolo suporta rastreabilidade completa via `mission_id` e `correlation_id`.

---

## 10. Referências

- **EIP-0001**: Architecture First
- **EIP-0002**: Resource First Architecture
- **EIP-0009**: Hierarchical Execution Identifier
- **PR 4.1**: Kernel (Microkernel)
- **PR 4.2**: Runtime

---

## 11. Histórico

| Data | Versão | Autor | Descrição |
| :--- | :--- | :--- | :--- |
| 2024-XX-XX | 1.0.0 | Architect | Rascunho Inicial para PR 4.3 |
