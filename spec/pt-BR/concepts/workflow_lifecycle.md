# Ciclo de Vida do Workflow

## Propósito

Este documento define o ciclo de vida de um Workflow dentro da arquitetura do Enxame.

Um Workflow é um plano de execução imutável derivado de uma Missão.

Um Workflow existe apenas para transformar uma Missão em trabalho executável.

Este documento formaliza como um Workflow serve como a ponte arquitetural entre uma Missão imutável e Tasks executáveis.

## Princípios de Design

O ciclo de vida do Workflow segue estes princípios:

- **Derivado da Missão** - Um Workflow existe unicamente porque uma Missão existe.
- **Imutabilidade** - O Workflow nunca muda após a criação.
- **Independência** - Um Workflow permanece independente de componentes de infraestrutura.
- **Propriedade** - Um Workflow pertence à Missão que o originou.
- **Apenas Lógico** - Um Workflow define apenas trabalho lógico, não comportamento de execução.

## Origem do Workflow

Um Workflow DEVERÁ ser derivado exclusivamente pelo Orchestrator.

Usuários nunca criam Workflows diretamente.

O Workflow é uma consequência arquitetural determinística de uma Missão.

Um Workflow nunca representa intenção do usuário.

## Propriedade do Workflow

O Workflow pertence à Missão que o originou.

O Orchestrator gerencia seu ciclo de vida.

A propriedade nunca é transferida para Runtime, Scheduler ou Agents.

Nenhum componente além do Orchestrator pode gerenciar o ciclo de vida do Workflow.

## Imutabilidade do Workflow

Um Workflow é imutável.

Após a criação, ele nunca deverá ser modificado.

Se a execução requer mudanças estruturais, um novo Workflow DEVERÁ ser derivado.

O Workflow original permanece inalterado.

A imutabilidade do Workflow preserva a integridade do plano de execução.

## Independência do Workflow

Um Workflow NÃO DEVERÁ conhecer:

- Runtime
- Scheduler
- Agents
- Nodes
- Heartbeat
- Discovery
- Infraestrutura

O Workflow pertence exclusivamente à camada de domínio.

A definição do Workflow permanece independente da infraestrutura de execução.

## Responsabilidades do Workflow

Um Workflow define apenas:

- Trabalho necessário
- Dependências lógicas
- Estrutura de execução

Um Workflow NÃO DEVERÁ definir:

- Ordem de execução
- Escalonamento
- Alocação de recursos
- Seleção de Agent
- Seleção de Node
- Comportamento de runtime

## Escalonamento do Workflow

Ordem de execução NÃO faz parte do Workflow.

O Scheduler é exclusivamente responsável por determinar:

- Sequência de execução
- Execução paralela
- Prioridades
- Distribuição de recursos

O Workflow define apenas dependências lógicas.

Decisões de escalonamento pertencem exclusivamente ao componente Scheduler.

## Ciclo de Vida do Workflow

Um Workflow evolui através dos seguintes estados conceituais:

### 1. Derivado

O Workflow é derivado de uma Missão pelo Orchestrator.

Neste estágio:
- A intenção da Missão é analisada
- Decomposição lógica do trabalho é realizada
- Dependências são identificadas
- Estrutura de execução é definida

O Workflow é criado como um artefato imutável.

### 2. Ativo

O Workflow está disponível para planejamento de execução.

Neste estágio:
- Scheduler pode analisar o Workflow
- Tasks podem ser identificadas para escalonamento
- Recursos podem ser alocados pelo Runtime

O Workflow permanece inalterado.

### 3. Em Execução

Tasks derivadas do Workflow estão sendo executadas.

Neste estágio:
- Tasks são escalonadas pelo Scheduler
- Runtime executa Tasks em Nodes disponíveis
- Progresso do Workflow é monitorado

A definição do Workflow permanece imutável.

### 4. Completo

Todas as Tasks derivadas do Workflow foram executadas.

Neste estágio:
- Completação do Workflow é gerenciada pelo Orchestrator
- Artefatos estão disponíveis para validação
- Completação do Workflow não implica completação da Missão

Completação da Missão permanece uma decisão exclusiva do usuário.

## Recriação do Workflow

Múltiplos Workflows podem existir durante o tempo de vida de uma Missão.

Cada novo Workflow DEVERÁ ser independentemente derivado.

Um novo Workflow nunca muda a Missão.

Recriação do Workflow ocorre quando:
- Usuário refina o objetivo dentro da mesma intenção da Missão
- Execução requer uma abordagem estrutural diferente
- Workflow anterior completou mas a Missão continua

Cada Workflow permanece como um artefato imutável independente.

## Completação do Workflow

Completação do Workflow é gerenciada pelo Orchestrator.

Completação do Workflow NÃO DEVERÁ implicar completação da Missão.

Completação da Missão permanece uma decisão exclusiva do usuário.

Um Workflow completa quando:
- Todas as Tasks derivadas foram executadas
- Todo trabalho lógico definido pelo Workflow está terminado

A Missão pode continuar com Workflows adicionais.

## Consciência de Recursos do Workflow

Criação de Workflow DEVE cumprir com EIP-0002.

Um Workflow DEVERIA existir apenas quando fornece valor arquitetural.

A arquitetura DEVE evitar instâncias desnecessárias de Workflow que consomem recursos sem benefício funcional.

Múltiplos Workflows para a mesma Missão devem ser justificados por necessidades distintas de execução.

## Invariantes Arquiteturais

Os seguintes invariantes DEVEM ser mantidos durante todo o ciclo de vida do Workflow:

- Um Workflow DEVE sempre ser derivado de exatamente uma Missão.
- Um Workflow DEVE permanecer imutável após a criação.
- Um Workflow NUNCA DEVE modificar a intenção da Missão.
- Um Workflow DEVE permanecer independente da infraestrutura.
- Um Workflow DEVE definir apenas trabalho lógico.
- Ordem de execução DEVE pertencer exclusivamente ao Scheduler.
- Seleção de Agent NUNCA DEVE fazer parte de um Workflow.
- Runtime NUNCA DEVE redefinir um Workflow.
- Um novo Workflow NUNCA DEVE alterar a Missão originadora.
- Orchestrator DEVE ser o único componente derivando Workflows.

## Fora do Escopo

Este documento não define:

- Ciclo de vida da Task
- Ciclo de vida do Agent
- Ciclo de vida do Runtime
- Catálogo de Events
- Mecanismos de persistência
- Procedimentos de recuperação
- Algoritmos do Scheduler
- Protocolos de comunicação
- Alocação de recursos
- Detalhes de infraestrutura

Estes tópicos pertencem a especificações separadas.

## Documentos Relacionados

- `concepts/workflow.md` - Definição do conceito de Workflow
- `concepts/mission_lifecycle.md` - Ciclo de Vida da Missão
- `eip/EIP-0001-architecture-first.md` - Princípio Architecture First
- `eip/EIP-0002-resource-first.md` - Princípio Resource First
