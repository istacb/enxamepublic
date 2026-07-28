# Missão

## Definição

Uma Missão representa o objetivo do usuário dentro do Enxame.

Uma Missão é sempre criada pelo Usuário.

Ela define O QUE o Usuário deseja realizar.

Uma Missão é independente de detalhes de implementação.

Uma Missão pode sobreviver a uma sessão do usuário.

## Responsabilidades

- Representar o objetivo do Usuário.
- Preservar a intenção do Usuário.
- Definir o resultado desejado.
- Servir como ponto de partida para execução.
- Permitir que a execução pause e retome depois.

## NÃO é responsável por

- Executar trabalho.
- Planejar execução.
- Selecionar Nodes.
- Selecionar Agents.
- Gerenciar Capabilities.
- Armazenar conhecimento.
- Tomar decisões pelo Usuário.

## Relacionamentos

- Criada pelo Usuário.
- Planejada pelo Orchestrator.
- Pode gerar um ou mais Workflows.
- Pode gerar uma ou mais Tasks.
- Consome Capabilities através da execução.
- É avaliada pelo Judge antes da resposta final ser apresentada ao Usuário.

## Invariantes

- Toda Missão se origina do Usuário.
- Uma Missão preserva a intenção original do Usuário.
- Uma Missão pode ser pausada.
- Uma Missão pode ser retomada depois.
- Uma Missão nunca substitui a decisão do Usuário.

## Extensões Futuras

EIPs futuros podem introduzir:

- Prioridades
- Agendamento
- Dependências entre Missões

## Conceitos Relacionados

- Capability
- Workflow (Futuro)
- Task (Futuro)
- Orchestrator (Futuro)
