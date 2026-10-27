# EIP-0001: Arquitetura First

## Status

**Ativo** - Aprovado e em implementação

## Resumo

Estabelecer a prática de "Arquitetura First" como princípio fundamental do projeto Enxame, onde toda mudança significativa deve ser precedida por especificação arquitetural documentada.

## Motivação

- Garantir consistência arquitetural ao longo do tempo
- Facilitar onboarding de novos contribuidores
- Reduzir retrabalho causado por decisões não documentadas
- Criar fonte única de verdade sobre o sistema

## Proposta

### Estrutura de Especificação

Criar diretório `spec/` com subdiretórios para:
- `constitution/` - Constituição e glossário
- `domain/` - Modelos de domínio
- `protocols/` - Protocolos de comunicação
- `diagrams/` - Diagramas arquiteturais
- `schemas/` - Schemas de validação
- `eip/` - Propostas de melhoria

### Processo de Mudança

1. Identificar necessidade de mudança
2. Criar EIP descrevendo proposta
3. Revisão pelo Arquiteto-Chefe
4. Aprovação e merge da especificação
5. Implementação segue especificação aprovada

### Regras

- Nenhuma mudança arquitetural sem EIP aprovado
- Implementação deve conformar com especificação
- Violações de dependência são bloqueadas
- Documentação é pré-requisito para merge de features

## Consequências

### Positivas

- Maior clareza sobre direção do projeto
- Decisões arquiteturais documentadas e acessíveis
- Redução de ambiguidade na implementação
- Melhor rastreabilidade de decisões

### Negativas

- Overhead inicial de documentação
- Processo pode parecer burocrático para mudanças pequenas
- Requer disciplina da equipe

### Neutras

- EIPs pequenos podem ser aprovados rapidamente
- Processo pode ser ajustado baseado em feedback

## Referências

- [Architecture Decision Records (ADR)](https://adr.github.io/)
- [C4 Model](https://c4model.com/)
- [Domain-Driven Design](https://domainlanguage.com/ddd/)

## Histórico

- **2024** - EIP criado como parte da fundação arquitetural
