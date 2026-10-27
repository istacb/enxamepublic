# Workflow

## Definição

Um Workflow é a decomposição lógica de uma Missão.

Um Workflow existe apenas porque uma Missão existe.

Ele representa a organização lógica do trabalho necessário para realizar a Missão.

Uma Missão pode conter um ou mais Workflows.

Múltiplos Workflows podem existir sequencialmente dentro da mesma Missão à medida que o Usuário refina ou estende o objetivo solicitado.

## Responsabilidades

- Decompor uma Missão em estágios lógicos.
- Organizar o trabalho antes da execução.
- Agrupar Tasks relacionadas.
- Preservar a intenção da Missão.
- Fornecer uma estrutura lógica para execução.

## NÃO é responsável por

- Executar Tasks.
- Selecionar Nodes.
- Selecionar Agents.
- Gerenciar Knowledge.
- Coordenar execução.
- Tomar decisões pelo Usuário.

## Relacionamentos

- Um Workflow pertence exatamente a uma Missão.
- Um Workflow contém uma ou mais Tasks.
- Uma Missão pode gerar múltiplos Workflows.
- Um novo Workflow pode ser criado após interação com o Usuário enquanto preserva a mesma Missão.

## Invariantes

- Todo Workflow pertence a uma Missão.
- Um Workflow não pode existir sem uma Missão.
- Um Workflow termina quando todas as suas Tasks são completadas.
- Completar um Workflow não necessariamente completa a Missão.

## Racional de Design

Workflow representa organização lógica, não infraestrutura.

Dependendo da Missão, um Workflow pode descrever:

- o que deve ser feito;
- como um objetivo específico deve ser alcançado.

A interpretação depende da própria Missão ao invés da definição do Workflow.

## Extensões Futuras

EIPs futuros podem introduzir:

- Workflows Paralelos
- Workflows Condicionais
- Templates de Workflow Reutilizáveis

## Conceitos Relacionados

- Missão
- Task (Futuro)
