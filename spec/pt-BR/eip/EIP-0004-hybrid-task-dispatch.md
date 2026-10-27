# EIP-0004: Despacho Híbrido de Tasks

## Status

**Aceito**

## Resumo

O Enxame utiliza despacho híbrido de Tasks.

O modelo preferencial é Pull.

Push existe apenas para exceções.

## Modelos

### Pull

O Node informa sua disponibilidade.

O Orchestrator envia Tasks compatíveis.

### Push

Utilizado apenas para:

- emergência
- failover
- administração
- recuperação
- necessidade arquitetural

## Princípios

- Pull é o mecanismo de despacho padrão.
- Push é reservado para situações excepcionais.
- O Orchestrator permanece responsável pelo planejamento.
- O Runtime permanece responsável apenas pela execução.
- O modelo de despacho de Tasks não altera a propriedade da Task.

## Consequências

### Positivas

- Nodes controlam sua própria aceitação de carga de trabalho
- Melhor utilização de recursos através de auto-relato
- Transferências desnecessárias de Tasks são reduzidas
- Separação clara entre planejamento e execução
- Cenários de failover e emergência são suportados

### Negativas

- Requer que Nodes relatem continuamente sua disponibilidade
- Adiciona complexidade à lógica de despacho

### Neutras

- Ambos os modelos coexistem na arquitetura
- Push não substitui Pull como mecanismo principal

## Justificativa

A arquitetura Enxame adota um modelo híbrido de despacho de Tasks que equilibra eficiência com flexibilidade.

O modelo Pull é preferido porque permite que Nodes auto-relatem sua disponibilidade e capabilities.

Esta abordagem respeita o princípio Resource First ao garantir que Tasks sejam enviadas apenas para Nodes que podem executá-las.

O modelo Push existe para lidar com situações excepcionais onde atribuição imediata de Tasks é necessária.

Exemplos de uso do Push incluem:

- Redistribuição de emergência quando um Node falha
- Cenários de failover requerendo migração imediata de Tasks
- Tasks administrativas que devem ser executadas em Nodes específicos
- Operações de recuperação após partições de rede
- Necessidades arquiteturais que requerem atribuição direta

O Orchestrator mantém responsabilidade pelo planejamento geral e distribuição de Tasks.

O Runtime mantém responsabilidade apenas pela execução das Tasks atribuídas.

Esta separação garante limites claros entre preocupações de planejamento e execução.

## Referências

- EIP-0002: Arquitetura Resource First
- PR 4.2: Runtime

## Histórico

- **2024** - EIP criado como parte da Sprint 4 architecture
