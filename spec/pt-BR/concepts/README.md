# Conceitos

Este diretório contém especificações conceituais para o Modelo de Domínio Enxame.

## Conceitos

| Arquivo | Conceito |
|---------|----------|
| `knowledge.md` | Conhecimento |
| `knowledge_asset.md` | Ativo de Conhecimento |
| `node.md` | Node |
| `specialization.md` | Especialização |
| `mission.md` | Missão |
| `mission_lifecycle.md` | Ciclo de Vida da Missão |
| `workflow.md` | Workflow |
| `workflow_lifecycle.md` | Ciclo de Vida do Workflow |
| `task_lifecycle.md` | Ciclo de Vida da Task |
| `event_catalog.md` | Catálogo de Eventos |

## Princípios

- Cada conceito é independente e auto-contido
- Relacionamentos entre conceitos são explícitos
- Conceitos não contêm detalhes de implementação
- Conceitos podem evoluir através de EIPs

## Diagrama de Dependência

```mermaid
graph TD

Knowledge --> KnowledgeAsset
KnowledgeAsset --> Node
Node --> Specialization
Specialization --> Capability

Mission --> Workflow
Workflow --> Task

Task --> Capability

Task -.Future.-> Agent
```
