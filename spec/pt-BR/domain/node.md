# Node

## Definição

Unidade computacional autônoma no enxame.

## Responsabilidades

- Executar capabilities atribuídas
- Participar em protocolos de consenso
- Comunicar-se com outros nodes via messages
- Reportar estado e saúde ao enxame

## Atributos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | Identificador único do node |
| `capabilities` | Capability[] | Lista de capacidades possuídas |
| `roles` | Role[] | Funções atualmente atribuídas |
| `status` | enum | Ativo, Inativo, Degradado |
| `metadata` | object | Dados adicionais específicos |

## Relações

- **Possui:** Múltiplas `Capability`
- **Atribuído a:** Múltiplas `Role`
- **Comunica-se via:** `Message`
- **Participa em:** `Consensus`

## Ciclo de Vida

1. **Inicialização** - Node registra capabilities disponíveis
2. **Descoberta** - Node é descoberto pelo enxame
3. **Atribuição** - Roles são atribuídas baseadas em capabilities
4. **Operação** - Node executa tasks conforme roles
5. **Monitoramento** - Estado reportado continuamente
6. **Desregistro** - Node sai do enxame (graceful ou falha)

## Restrições

- Node não pode modificar suas próprias capabilities em runtime
- Node deve reportar falhas dentro de timeout definido
- Node não pode assumir roles sem capabilities requeridas
