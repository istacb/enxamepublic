# Protocols

Diretório de especificação de protocolos do projeto Enxame.

## Protocolos em Especificação

| Protocolo | Status | Descrição |
|-----------|--------|-----------|
| Node Discovery | Pendente | Descoberta e registro de nodes |
| Task Assignment | Pendente | Atribuição de tasks a nodes |
| Consensus | Pendente | Protocolos de consenso distribuído |
| Message Transport | Pendente | Transporte de mensagens entre nodes |
| Health Check | Pendente | Verificação de saúde de nodes |
| Provider Registration | Pendente | Registro e descoberta de providers |

## Princípios de Design

1. **Stateless** - Protocolos devem ser stateless quando possível
2. **Idempotente** - Operações devem ser idempotentes
3. **Timeout** - Toda operação deve ter timeout definido
4. **Retry** - Política de retry deve ser explícita
5. **Versionado** - Protocolos devem suportar versionamento

## Formato de Especificação

Cada protocolo será documentado em arquivo separado com:
- Visão geral
- Mensagens trocadas
- Diagrama de sequência
- Estados e transições
- Tratamento de erros
- Exemplos
