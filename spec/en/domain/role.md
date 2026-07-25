# Role

## Definição

Função atribuída a um node baseada em suas capabilities.

## Responsabilidades

- Agrupar capabilities relacionadas
- Definir responsabilidades de alto nível
- Estabelecer expectativas de comportamento
- Servir como unidade de atribuição pelo enxame

## Atributos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | Identificador único da role |
| `name` | string | Nome descritivo |
| `description` | string | Descrição detalhada |
| `required_capabilities` | Capability[] | Capabilities mínimas necessárias |
| `optional_capabilities` | Capability[] | Capabilities desejáveis |
| `priority` | number | Prioridade de atribuição |
| `max_nodes` | number | Máximo de nodes com esta role (opcional) |

## Relações

- **Requer:** Múltiplas `Capability`
- **Atribuída a:** `Node`
- **Executa:** `Task` dentro de `Mission`

## Exemplos de Roles

1. **Coordinator** - Coordena tasks entre nodes
2. **Worker** - Executa tasks computacionais
3. **Observer** - Monitora estado do enxame
4. **Gateway** - Interface com sistemas externos
5. **Validator** - Valida resultados de consensus

## Ciclo de Vida

1. **Definição** - Role é definida com capabilities requeridas
2. **Elegibilidade** - Nodes com capabilities são elegíveis
3. **Atribuição** - Role é atribuída a node específico
4. **Ativação** - Node assume responsabilidades da role
5. **Revogação** - Role é removida do node

## Restrições

- Node só pode receber role se possuir todas required_capabilities
- Role não pode ser modificada enquanto estiver atribuída
- Atribuição de role deve respeitar max_nodes se definido
