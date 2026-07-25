# Glossary

## Fundamental Terms

| Term | Definition |
|------|------------|
| **Enxame** | Complete distributed system of coordinated agents |
| **Node** | Autonomous computational unit in the swarm |
| **Capability** | Functional skill that a node can execute |
| **Role** | Function assigned to a node based on its capabilities |
| **Mission** | High-level objective to be achieved by the swarm |
| **Task** | Atomic unit of work within a mission |
| **Workflow** | Coordinated sequence of tasks with defined dependencies |
| **Provider** | Entity that provides resources or services to the swarm |
| **KnowledgeSource** | Source of information consultable by the swarm |
| **Consensus** | Mechanism of agreement between nodes on state or decisions |
| **Message** | Unit of communication between nodes |
| **Protocol** | Set of rules for communication and coordination |
| **EIP** | Enxame Improvement Proposal - mechanism for architectural change |

## Relations

- A **Node** has multiple **Capabilities**
- A **Role** requires multiple **Capabilities**
- A **Mission** contains multiple **Tasks**
- A **Workflow** orchestrates multiple **Tasks**
- **Messages** transport data between **Nodes**
- **Consensus** coordinates decisions between **Nodes**

## States

- **Node:** Active, Inactive, Degraded
- **Task:** Pending, In Progress, Complete, Failed
- **Mission:** Planned, In Progress, Complete, Cancelled
