# Glossário

## Termos Fundamentais

| Termo | Definição |
|-------|-----------|
| **Enxame** | Sistema distribuído completo de agentes coordenados |
| **Node** | Unidade computacional autônoma no enxame |
| **Capability** | Habilidade funcional que um node pode executar |
| **Role** | Função atribuída a um node baseada em suas capabilities |
| **Mission** | Objetivo de alto nível a ser alcançado pelo enxame |
| **Task** | Unidade atômica de trabalho dentro de uma mission |
| **Workflow** | Sequência coordenada de tasks com dependências definidas |
| **Provider** | Entidade que fornece recursos ou serviços ao enxame |
| **KnowledgeSource** | Fonte de informação consultável pelo enxame |
| **Consensus** | Mecanismo de acordo entre nodes sobre estado ou decisões |
| **Message** | Unidade de comunicação entre nodes |
| **Protocol** | Conjunto de regras para comunicação e coordenação |
| **EIP** | Enxame Improvement Proposal - mecanismo de mudança arquitetural |

## Relações

- Um **Node** possui múltiplas **Capabilities**
- Uma **Role** requer múltiplas **Capabilities**
- Uma **Mission** contém múltiplas **Tasks**
- Um **Workflow** orquestra múltiplas **Tasks**
- **Messages** transportam dados entre **Nodes**
- **Consensus** coordena decisões entre **Nodes**

## Estados

- **Node:** Ativo, Inativo, Degradado
- **Task:** Pendente, Em Execução, Completa, Falha
- **Mission:** Planejada, Em Andamento, Completa, Cancelada
