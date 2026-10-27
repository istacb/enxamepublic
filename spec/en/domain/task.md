# Task

## Definição

Unidade atômica de trabalho dentro de uma mission.

## Responsabilidades

- Executar ação específica e bem definida
- Produzir resultado verificável
- Reportar status de execução
- Respeitar limites de tempo e recursos

## Atributos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | Identificador único da task |
| `name` | string | Nome descritivo |
| `description` | string | Descrição detalhada |
| `capability_required` | Capability | Capability necessária para execução |
| `input` | object | Dados de entrada |
| `output` | object | Dados de saída (após execução) |
| `status` | enum | Pendente, Em Execução, Completa, Falha |
| `assigned_to` | Node | Node responsável pela execução |
| `timeout_ms` | number | Timeout de execução |
| `retry_count` | number | Número máximo de retries |
| `dependencies` | Task[] | Tasks que devem completar antes desta |

## Relações

- **Requer:** Uma `Capability`
- **Contida em:** `Mission`
- **Orquestrada por:** `Workflow`
- **Executada por:** `Node`
- **Depende de:** Zero ou mais `Task`

## Estados

| Estado | Descrição | Transições Válidas |
|--------|-----------|-------------------|
| Pendente | Aguardando execução | → Em Execução, → Falha |
| Em Execução | Sendo processada | → Completa, → Falha |
| Completa | Executada com sucesso | (terminal) |
| Falha | Execução falhou | → Pendente (retry) |

## Restrições

- Task é atômica - não pode ser dividida
- Task deve ter capability_required definida
- Task não pode depender de si mesma (ciclos proibidos)
- Output deve conformar com output_schema da capability
