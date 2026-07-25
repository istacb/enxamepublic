# Regras de Dependência

## Princípio

Módulos de nível inferior não podem depender de módulos de nível superior.

## Hierarquia de Camadas

```
Eixo: Domínio → Protocolos → Implementação
```

### Camada de Domínio (`spec/domain/`)
- **Depende de:** Nada (camada base)
- **Pode importar:** Apenas outros modelos de domínio
- **Não pode importar:** Protocolos, implementação, infraestrutura

### Camada de Protocolos (`spec/protocols/`)
- **Depende de:** Domínio
- **Pode importar:** Modelos de domínio
- **Não pode importar:** Implementação concreta

### Camada de Implementação
- **Depende de:** Domínio + Protocolos
- **Pode importar:** Especificações completas
- **Não pode importar:** Outras implementações do mesmo nível

## Regras Específicas

| Módulo | Pode Depender De | Não Pode Depender De |
|--------|------------------|----------------------|
| Node | Capability, Role | Mission, Task, Provider |
| Capability | - | Node, Mission |
| Role | Capability | Provider |
| Mission | Task, Workflow | Node |
| Task | - | Mission, Provider |
| Workflow | Task | Node |
| Provider | Capability | Mission |
| KnowledgeSource | - | Consensus |
| Consensus | Message | Provider |
| Message | - | Workflow |

## Validação

- Ferramentas de análise estática validam regras
- Violações bloqueiam merge
- Exceções requerem aprovação via EIP
