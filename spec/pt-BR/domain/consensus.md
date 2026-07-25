# Consensus

## Definição

Mecanismo de acordo distribuído entre nodes sobre estado ou decisões.

## Responsabilidades

- Coordenar votação entre nodes participantes
- Garantir propriedades de consenso (segurança, liveness)
- Tratar falhas bizantinas ou não-bizantinas
- Produzir resultado verificável e auditável

## Atributos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | Identificador único do consensus |
| `type` | enum | Maioria Simples, Quórum, PBFT, Raft, Prova de Trabalho |
| `participants` | Node[] | Nodes participantes do consenso |
| `proposal` | object | Proposta sendo votada |
| `votes` | object[] | Votos recebidos (node_id → vote) |
| `threshold` | number | Limiar necessário para aprovação (0.0-1.0) |
| `timeout_ms` | number | Timeout para coleta de votos |
| `result` | enum | Aprovado, Rejeitado, Timeout, Indeterminado |
| `round` | number | Número da rodada (para consenso multi-round) |

## Relações

- **Participam:** Múltiplos `Node`
- **Comunica-se via:** `Message`
- **Decide sobre:** Propostas de `Mission`, `Task`, `Workflow`

## Tipos de Consenso

| Tipo | Descrição | Caso de Uso |
|------|-----------|-------------|
| Maioria Simples | >50% dos votos | Decisões rotineiras |
| Quórum | % configurável | Decisões importantes |
| PBFT | Tolerância a falhas bizantinas | Sistemas críticos |
| Raft | Leader-based consensus | Coordenação de estado |
| Prova de Trabalho | Proof-of-work | Sistemas abertos/descentralizados |

## Ciclo de Vida

1. **Iniciação** - Proposta é submetida ao consenso
2. **Distribuição** - Proposta é enviada a todos participantes
3. **Votação** - Nodes enviam seus votos
4. **Contagem** - Votos são agregados e validados
5. **Resultado** - Decisão é anunciada quando threshold atingido
6. **Finalização** - Resultado é registrado e propagado

## Restrições

- Participantes devem ser nodes válidos e ativos
- Voto deve ser assinado/autenticado para prevenção de fraude
- Timeout deve ser suficiente para propagação de rede
- Resultado só é válido se threshold for atingido dentro do timeout
