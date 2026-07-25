# Provider

## Definição

Entidade que fornece recursos ou serviços ao enxame.

## Responsabilidades

- Fornecer recursos sob demanda
- Reportar disponibilidade de recursos
- Garantir qualidade de serviço (QoS)
- Notificar falhas ou indisponibilidade

## Atributos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | Identificador único do provider |
| `name` | string | Nome descritivo |
| `type` | enum | Computação, Armazenamento, Rede, API Externa |
| `capabilities` | Capability[] | Capabilities que este provider suporta |
| `endpoint` | string | Endpoint de acesso (URL, URI, etc.) |
| `auth_config` | object | Configuração de autenticação |
| `quota` | object | Limites de uso (requests/s, storage, etc.) |
| `health_check` | object | Configuração de verificação de saúde |
| `status` | enum | Disponível, Indisponível, Degradado |

## Relações

- **Fornece para:** `Node`, `Mission`
- **Suporta:** Múltiplas `Capability`
- **Utilizado por:** `Task` (indiretamente via Node)

## Tipos de Provider

1. **Computação** - CPU, GPU, memória
2. **Armazenamento** - Disco, banco de dados, cache
3. **Rede** - Bandwidth, conexões, load balancer
4. **API Externa** - Serviços de terceiros (LLM, visão, etc.)
5. **Humano** - Intervenção humana quando necessária

## Ciclo de Vida

1. **Registro** - Provider é registrado no enxame
2. **Descoberta** - Provider é descoberto por nodes/missions
3. **Alocação** - Recursos são alocados sob demanda
4. **Monitoramento** - Saúde e quota são acompanhados
5. **Liberação** - Recursos são liberados após uso
6. **Desregistro** - Provider é removido do enxame

## Restrições

- Provider deve implementar health_check
- Quota não pode ser excedida sem aprovação explícita
- Falha do provider deve propagar para tasks dependentes
- Provider externo requer configuração de auth válida
