# Schemas

Diretório de schemas de validação do projeto Enxame.

## Schemas Planejados

| Schema | Formato | Status | Descrição |
|--------|---------|--------|-----------|
| Node | JSON Schema | Pendente | Validação de estrutura de Node |
| Capability | JSON Schema | Pendente | Validação de Capability |
| Task | JSON Schema | Pendente | Validação de Task |
| Mission | JSON Schema | Pendente | Validação de Mission |
| Workflow | JSON Schema | Pendente | Validação de Workflow |
| Message | JSON Schema | Pendente | Validação de Message |
| Protocol | JSON Schema | Pendente | Validação de mensagens de protocolo |

## Uso

Schemas são utilizados para:
- Validar entrada de APIs
- Validar saída de operações
- Validar persistência em banco de dados
- Gerar tipos TypeScript/Python automaticamente
- Documentar contratos de dados

## Ferramentas

- **ajv** - Validação JSON Schema em JavaScript/TypeScript
- **jsonschema** - Validação em Python
- **quicktype** - Geração de tipos a partir de schemas

## Versionamento

- Schemas são versionados semanticamente
- Mudanças breaking requerem nova versão major
- Implementação deve suportar múltiplas versões durante transição
