# Capability

## Definição

Habilidade funcional que um node pode executar.

## Responsabilidades

- Definir interface de execução clara
- Declarar pré-condições e pós-condições
- Especificar recursos necessários
- Reportar resultado da execução

## Atributos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | Identificador único da capability |
| `name` | string | Nome descritivo |
| `description` | string | Descrição detalhada |
| `input_schema` | object | Schema de entrada (JSON Schema) |
| `output_schema` | object | Schema de saída (JSON Schema) |
| `resources` | object[] | Recursos necessários (CPU, memória, etc.) |
| `timeout_ms` | number | Timeout máximo de execução |
| `retry_policy` | object | Política de retry em caso de falha |

## Relações

- **Possuída por:** `Node`
- **Requerida por:** `Role`
- **Executa:** `Task`

## Tipos de Capability

1. **Computacional** - Processamento de dados
2. **IO** - Leitura/escrita de recursos externos
3. **Comunicação** - Envio/recebimento de messages
4. **Coordenação** - Participação em consensus

## Restrições

- Capability é imutável após registro
- Capability não possui estado interno persistente
- Capability deve ser idempotente quando possível
- Capability deve validar input contra input_schema
