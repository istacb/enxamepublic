# Mission

## Definição

Objetivo de alto nível a ser alcançado pelo enxame.

## Responsabilidades

- Definir objetivo claro e mensurável
- Especificar critérios de sucesso
- Agrupar tasks relacionadas
- Coordenar execução através de workflow

## Atributos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | Identificador único da mission |
| `name` | string | Nome descritivo |
| `description` | string | Descrição detalhada |
| `objective` | string | Objetivo claro e mensurável |
| `success_criteria` | string[] | Critérios para considerar missão completa |
| `tasks` | Task[] | Tasks que compõem a mission |
| `workflow` | Workflow | Workflow que orquestra as tasks |
| `status` | enum | Planejada, Em Andamento, Completa, Cancelada |
| `priority` | number | Prioridade de execução |
| `timeout_ms` | number | Timeout total da mission |

## Relações

- **Contém:** Múltiplas `Task`
- **Orquestrada por:** `Workflow`
- **Executada por:** `Node` com `Role` apropriada
- **Utiliza:** `Provider` (opcional)

## Ciclo de Vida

1. **Criação** - Mission é definida com objetivo e critérios
2. **Planejamento** - Tasks são identificadas e workflow definido
3. **Atribuição** - Nodes e roles são atribuídos às tasks
4. **Execução** - Tasks são executadas conforme workflow
5. **Monitoramento** - Progresso é acompanhado
6. **Conclusão** - Critérios de sucesso são validados

## Restrições

- Mission deve ter pelo menos uma task
- Workflow deve cobrir todas as tasks da mission
- Mission não pode ser modificada durante execução
- Cancelamento deve liberar todos os recursos alocados
