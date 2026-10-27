# Message

## Definição

Unidade de comunicação entre nodes.

## Responsabilidades

- Transportar dados entre nodes de forma confiável
- Identificar remetente e destinatário(s)
- Suportar diferentes padrões de entrega
- Prover metadados para roteamento e processamento

## Atributos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | Identificador único da message |
| `type` | enum | Request, Response, Event, Command, Query |
| `sender_id` | string | ID do node remetente |
| `recipient_id` | string | ID do node destinatário (ou broadcast) |
| `topic` | string | Tópico/canal da mensagem |
| `correlation_id` | string | ID para correlacionar request/response |
| `payload` | object | Dados da mensagem |
| `metadata` | object | Metadados adicionais (prioridade, TTL, etc.) |
| `timestamp` | number | Timestamp de criação (epoch ms) |
| `ttl_ms` | number | Time-to-live em milissegundos |
| `priority` | number | Prioridade de entrega (0-10) |
| `delivery_mode` | enum | At-Least-Once, At-Most-Once, Exactly-Once |

## Relações

- **Enviada por:** `Node`
- **Recebida por:** `Node`
- **Utilizada em:** `Consensus`, Comunicação geral do enxame

## Tipos de Message

| Tipo | Direção | Descrição | Exemplo |
|------|---------|-----------|---------|
| Request | Unidirecional | Solicitação de ação | Execute task X |
| Response | Bidirecional | Resposta a request | Task X completed |
| Event | Unidirecional | Notificação de ocorrência | Node joined swarm |
| Command | Unidirecional | Ordem para execução | Stop task Y |
| Query | Bidirecional | Consulta de informação | Get node status |

## Padrões de Entrega

| Padrão | Garantia | Caso de Uso |
|--------|----------|-------------|
| At-Least-Once | Mensagem entregue ≥1 vez | Comandos críticos |
| At-Most-Once | Mensagem entregue ≤1 vez | Events não-críticos |
| Exactly-Once | Mensagem entregue exatamente 1 vez | Transações financeiras |

## Restrições

- Message deve ter sender_id válido
- Payload deve ser serializável (JSON-compatible)
- TTL deve ser positivo e finito
- Correlation_id é obrigatório para tipo Request/Response
- Priority deve estar no intervalo 0-10
