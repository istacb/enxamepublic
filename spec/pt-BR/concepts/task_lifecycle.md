# Ciclo de Vida da Task

## Propósito

Este documento define o ciclo de vida de uma Task na arquitetura Enxame.

Uma Task é a menor unidade imutável de trabalho de domínio derivada de um Workflow.

Uma Task existe apenas para executar uma única responsabilidade lógica requerida por um Workflow.

Este documento formaliza como uma Task representa trabalho sem representar execução.

## Princípios de Design

O ciclo de vida da Task segue estes princípios:

- **Derivada do Workflow** - Uma Task existe somente porque um Workflow a requer.
- **Imutabilidade** - A Task nunca muda após sua criação.
- **Independência** - Toda Task é independente e não depende de outras Tasks.
- **Posse** - Uma Task pertence ao Workflow que a derivou.
- **Responsabilidade Única** - Uma Task representa exatamente uma unidade lógica de trabalho.

## Origem da Task

Tasks SHALL ser derivadas exclusivamente pelo Workflow.

Runtime NUNCA SHALL criar Tasks.

Scheduler NUNCA SHALL criar Tasks.

Agents NUNCA SHALL criar Tasks.

Users NUNCA SHALL criar Tasks.

Uma Task é uma consequência arquitetural determinística de um Workflow.

Tasks nunca representam intenção do usuário.

## Posse da Task

Uma Task pertence exclusivamente ao Workflow que a derivou.

A posse nunca transfere para Runtime, Scheduler ou Agents.

Nenhum componente além do Workflow pode reivindicar posse de uma Task.

O Workflow rastreia o progresso da Task e consolida artefatos.

## Imutabilidade da Task

Uma Task é imutável.

Após a criação, ela NUNCA SHALL ser modificada.

Se um trabalho lógico diferente for necessário, uma nova Task SHALL ser derivada pelo Workflow.

A Task original permanece inalterada.

A imutabilidade da Task preserva a integridade da definição do trabalho.

## Independência da Task

Uma Task NÃO SHALL conhecer:

- Runtime
- Scheduler
- Agents
- Nodes
- Heartbeat
- Discovery
- Infrastructure

Uma Task pertence exclusivamente à camada de domínio.

A definição da Task permanece independente da infraestrutura de execução.

## Responsabilidades da Task

Uma Task define apenas:

- Uma unidade lógica de trabalho

Uma Task NÃO SHALL definir:

- Ordem de execução
- Scheduling
- Retries
- Infraestrutura
- Seleção de Node
- Seleção de Agent
- Estratégia de execução
- Paralelização

Tasks representam qual trabalho deve ser feito, não como ou quando ele executa.

## Scheduling da Task

Scheduling SHALL permanecer uma responsabilidade exclusiva do Scheduler.

Tasks NUNCA SHALL determinar:

- Tempo de execução
- Ordem de execução
- Prioridade de execução

O Scheduler analisa Tasks e determina a sequência de execução com base nas dependências do Workflow e disponibilidade de recursos.

## Execução da Task

Execução pertence exclusivamente ao Runtime.

Uma Task representa o trabalho.

Execução representa a tentativa de realizar esse trabalho.

Múltiplas tentativas de execução PODEM ocorrer sem alterar a Task.

Tentativas de execução NÃO SHALL modificar a Task.

Execução da Task é separada da definição da Task.

## Retry da Task

Retries de Task NÃO SHALL criar novas Tasks.

Se a execução falhar:

- Runtime reporta a falha.
- Orchestrator decide a próxima ação.
- Outra tentativa de execução PODE ser agendada.
- A Task original permanece inalterada.

Retry ocorre através de tentativas de execução, nunca através de mutação da Task.

## Resultado da Task

Artefatos produzidos durante a execução pertencem ao Workflow.

Tasks não possuem resultados finais.

Tasks apenas contribuem com artefatos para o Workflow.

O Workflow consolida todos os artefatos das Tasks para entrega da Missão.

## Dependências da Task

Dependências de Task NÃO SHALL existir.

Dependências lógicas pertencem exclusivamente ao Workflow.

Tasks permanecem completamente independentes.

O Workflow define quais Tasks devem completar antes que outras possam começar.

## Completação da Task

Completação da Task SHALL ser reportada pelo Runtime.

Workflow SHALL consolidar completação de Task.

Completação da Missão permanece independente.

Uma Task completa quando sua única unidade lógica de trabalho foi realizada.

Completação do Workflow ocorre quando todas as Tasks derivadas completaram.

## Invariantes Arquiteturais

Os seguintes invariantes DEVEM ser mantidos durante todo o ciclo de vida da Task:

- Uma Task SHALL sempre pertencer a exatamente um Workflow.
- Uma Task SHALL permanecer imutável após criação.
- Uma Task SHALL representar exatamente uma unidade lógica de trabalho.
- Uma Task NUNCA SHALL conhecer infraestrutura.
- Uma Task NUNCA SHALL conhecer Agents.
- Uma Task NUNCA SHALL realizar scheduling.
- Uma Task NUNCA SHALL criar outras Tasks.
- Tentativas de execução NUNCA SHALL modificar uma Task.
- Retry SHALL ocorrer através de tentativas de execução, nunca através de mutação da Task.
- Workflow SHALL permanecer responsável pela coordenação lógica.

## Fora do Escopo

Este documento não define:

- Ciclo de vida do Workflow
- Ciclo de vida da Missão
- Catálogo de eventos
- Ciclo de vida do Runtime
- Mecanismos de persistência
- Procedimentos de recuperação
- Algoritmos do Scheduler
- Alocação de recursos
- Detalhes de infraestrutura

Estes tópicos pertencem a especificações separadas.

## Documentos Relacionados

- `concepts/workflow.md` - Definição do conceito de Workflow
- `concepts/workflow_lifecycle.md` - Ciclo de Vida do Workflow
- `concepts/mission_lifecycle.md` - Ciclo de Vida da Missão
- `eip/EIP-0001-architecture-first.md` - Princípio Architecture First
- `eip/EIP-0002-resource-first.md` - Princípio Resource First
