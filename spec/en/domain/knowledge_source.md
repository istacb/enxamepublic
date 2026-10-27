# KnowledgeSource

## Definição

Fonte de informação consultável pelo enxame.

## Responsabilidades

- Armazenar conhecimento estruturado ou não estruturado
- Responder a consultas de forma eficiente
- Manter consistência e atualidade dos dados
- Prover mecanismos de busca e recuperação

## Atributos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | string | Identificador único da knowledge source |
| `name` | string | Nome descritivo |
| `type` | enum | Documento, Banco de Dados, API, Vetorial, Grafo |
| `schema` | object | Schema dos dados armazenados |
| `endpoint` | string | Endpoint de acesso |
| `query_language` | string | Linguagem de consulta suportada (SQL, SPARQL, etc.) |
| `indexes` | object[] | Índices disponíveis para otimização |
| `refresh_policy` | object | Política de atualização dos dados |
| `access_control` | object | Configuração de controle de acesso |

## Relações

- **Consultada por:** `Node`, `Task`
- **Contém:** Dados estruturados ou não estruturados
- **Integrada com:** `Provider` (quando externo)

## Tipos de KnowledgeSource

1. **Documento** - Textos, PDFs, markdown
2. **Banco de Dados** - Dados estruturados relacionais
3. **API** - Dados acessíveis via endpoint REST/GraphQL
4. **Vetorial** - Embeddings para busca semântica
5. **Grafo** - Conhecimento em formato de grafo (RDF, etc.)
6. **Cache** - Dados temporários de alta velocidade

## Operações Suportadas

| Operação | Descrição | Exemplo |
|----------|-----------|---------|
| `query` | Consulta estruturada | SELECT, GraphQL query |
| `search` | Busca textual/semântica | Full-text search |
| `retrieve` | Recuperação por ID | Get document by ID |
| `insert` | Inserção de dados | Add new document |
| `update` | Atualização de dados | Modify existing record |
| `delete` | Remoção de dados | Remove document |

## Restrições

- KnowledgeSource deve definir schema ou formato esperado
- Query deve respeitar access_control configurado
- Refresh policy deve ser executada conforme agendamento
- Indexes devem ser mantidos atualizados após write operations
