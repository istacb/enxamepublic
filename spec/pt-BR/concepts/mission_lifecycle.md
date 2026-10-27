# Ciclo de Vida da Missão

## Propósito

Este documento define o ciclo de vida de uma Missão dentro da arquitetura do Enxame.

Uma Missão representa uma intenção imutável do usuário cujo objetivo é resolver um problema do usuário.

Este documento formaliza como uma Missão evolui através de transições de estado sem modificar sua intenção central.

## Princípios de Design

O ciclo de vida da Missão segue estes princípios:

- **Intenção do Usuário Primeiro** - Uma Missão existe unicamente para representar o que o Usuário deseja realizar.
- **Imutabilidade** - A intenção da Missão nunca muda após a criação.
- **Independência** - Toda Missão é independente e não depende de outras Missões.
- **Propriedade** - Uma Missão sempre pertence ao Usuário durante todo o seu ciclo de vida.
- **Transições Explícitas** - Uma Missão evolui apenas através de transições de estado bem definidas.

## Propriedade da Missão

Uma Missão sempre pertence ao Usuário.

Runtime, Workflow, Scheduler, Judge e todos os Agents agem em nome do Usuário.

A propriedade nunca muda durante o ciclo de vida da Missão.

Nenhum componente pode reivindicar propriedade de uma Missão.

## Imutabilidade da Missão

Uma Missão é imutável.

Sua intenção nunca muda.

O seguinte pode mudar durante a execução:
- Estado de execução
- Workflow
- Tasks
- Events

A Missão em si nunca muda.

Se o Usuário modificar a intenção original, uma nova Missão DEVERÁ ser criada.

## Independência da Missão

Toda Missão é independente.

Uma Missão nunca depende de outra Missão.

Artefatos produzidos por uma Missão podem ser usados por outra Missão.

Missões em si nunca formam árvores de dependência.

## Ciclo de Vida da Missão

Uma Missão evolui através dos seguintes estados conceituais:

### 1. Criada

A Missão é criada com uma intenção definida do usuário.

Neste estágio:
- A intenção do Usuário é capturada
- Critérios de sucesso são definidos
- Nenhuma execução começou

### 2. Planejada

A Missão é preparada para execução.

Neste estágio:
- Um Workflow pode ser gerado
- Tasks podem ser identificadas
- Recursos podem ser alocados

A intenção da Missão permanece inalterada.

### 3. Em Execução

A Missão está sendo ativamente executada.

Neste estágio:
- Tasks estão sendo realizadas
- Workflow está progredindo
- Transições de estado ocorrem baseadas no progresso da execução

A intenção da Missão permanece inalterada.

### 4. Validação

Artefatos de execução são avaliados antes da entrega final ao Usuário.

Neste estágio:
- Judge avalia resultados contra critérios de sucesso
- Revalidação pode ser solicitada
- Nenhuma decisão do usuário é tomada pelo Judge

### 5. Completa

O Usuário declara a Missão como completa.

Completação nunca é automática.

Completação é independente de:
- Completação do Workflow
- Completação da Task
- Aprovação do Judge

### 6. Cancelada

A Missão é cancelada por decisão explícita do Usuário ou liberação de recursos.

Neste estágio:
- Recursos alocados são liberados de acordo com as regras do Runtime
- Execução para
- A Missão permanece imutável como registro histórico

## Validação da Missão

Judge nunca possui a Missão.

Judge nunca completa a Missão.

Judge nunca decide pelo Usuário.

Judge apenas avalia resultados e pode solicitar revalidação.

Revalidação usa artefatos já produzidos durante a execução.

Revalidação nunca muda a Missão.

## Completação da Missão

Apenas o Usuário pode declarar uma Missão como completa.

Completação nunca é automática.

Completação é independente de:
- Completação do Workflow
- Completação da Task
- Aprovação do Judge

O sistema pode sugerir completamento, mas a declaração final pertence ao Usuário.

## Substituição da Missão

Se o Usuário muda a intenção original:

Uma nova Missão DEVERÁ ser criada.

A Missão anterior permanece imutável.

Se o Usuário explicitamente substitui a Missão anterior:

A Missão anterior DEVERÁ ser cancelada.

Recursos alocados DEVERÃO ser liberados de acordo com as regras do Runtime.

## Revalidação da Missão

Judge pode solicitar revalidação usando artefatos já produzidos durante a execução.

Revalidação nunca muda a Missão.

Se o Usuário muda a intenção após revalidação:

Uma nova Missão DEVERÁ ser criada.

## Invariantes Arquiteturais

Os seguintes invariantes DEVEM ser mantidos durante todo o ciclo de vida da Missão:

- Uma Missão DEVE sempre representar uma única intenção do usuário.
- Uma Missão DEVE permanecer imutável após a criação.
- Apenas o Usuário DEVE completar uma Missão.
- Judge NUNCA DEVE tomar decisões pelo usuário.
- Missões DEVEM permanecer independentes.
- Substituição de Missão DEVE sempre criar uma nova Missão.
- Runtime NUNCA DEVE alterar a intenção da Missão.
- Workflow DEVE executar uma Missão mas nunca redefini-la.
- Propriedade DEVE permanecer com o Usuário durante todo o ciclo de vida.
- Transições de estado NÃO DEVEM modificar a intenção da Missão.

## Fora do Escopo

Este documento não define:

- Ciclo de vida da Task
- Ciclo de vida do Agent
- Ciclo de vida do Runtime
- Catálogo de Events
- Mecanismos de persistência
- Procedimentos de recuperação
- Internos do Scheduler
- Protocolos de comunicação
- Algoritmos de alocação de recursos

Estes tópicos pertencem a especificações separadas.

## Documentos Relacionados

- `concepts/mission.md` - Definição do conceito de Missão
- `domain/mission.md` - Modelo de domínio da Missão
- `eip/EIP-0001-architecture-first.md` - Princípio Architecture First
- `eip/EIP-0002-resource-first.md` - Princípio Resource First
