# Workflow

## Definição

Sequência coordenada de tasks com dependências definidas.

## Responsabilidades

- Definir ordem de execução das tasks
- Gerenciar dependências entre tasks
- Coordenar paralelismo quando possível
- Tratar falhas e recovery

## Atributos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | Identificador único do workflow |
| `name` | string | Nome descritivo |
| `description` | string | Descrição detalhada |
| `tasks` | Task[] | Lista ordenada de tasks |
| `dependencies` | object[] | Grafo de dependências (task_id → [dependency_ids]) |
| `parallel_groups` | Task[][] | Grupos de tasks que podem executar em paralelo |
| `on_failure` | enum | Abort, Continue, Retry |
| `timeout_ms` | number | Timeout total do workflow |

## Relações

- **Orquestra:** Múltiplas `Task`
- **Associado a:** `Mission`
- **Executado por:** Múltiplos `Node`

## Padrões de Workflow

1. **Sequencial** - Tasks executam uma após outra
2. **Paralelo** - Tasks independentes executam simultaneamente
3. **Fan-out/Fan-in** - Uma task divide em múltiplas, depois consolida
4. **Condicional** - Execução depende de resultados anteriores
5. **Loop** - Tasks repetem até condição ser satisfeita

## Ciclo de Vida

1. **Definição** - Tasks e dependências são especificadas
2. **Validação** - Grafo é validado (sem ciclos, dependências existem)
3. **Inicialização** - Tasks iniciais marcadas como prontas
4. **Execução** - Tasks são disparadas conforme dependências liberam
5. **Monitoramento** - Progresso acompanhado em tempo real
6. **Finalização** - Todas tasks completas ou falha tratada

## Restrições

- Workflow não pode conter ciclos de dependência
- Toda task deve ter caminho válido desde tasks iniciais
- On_failure deve ser definido para tratamento de erros
- Timeout total deve ser maior que soma dos timeouts individuais
