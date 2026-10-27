# Regras Arquiteturais

## Princípios Fundamentais

1. **Arquitetura First** - Especificação precede implementação
2. **Domínio Explícito** - Conceitos de domínio documentados em `spec/domain/`
3. **Dependências Controladas** - Regras definidas em `dependency_rules.md`
4. **Protocolos Estáveis** - APIs e protocolos não mudam sem EIP

## Estrutura de Decisão

- Mudanças arquiteturais requerem EIP (Enxame Improvement Proposal)
- EIPs são numerados sequencialmente em `spec/eip/`
- Cada EIP descreve: contexto, proposta, consequências

## Validação

- Implementação deve conformar com especificação
- Testes validam conformidade arquitetural
- Violações de dependência são erros de build

## Governança

- Arquiteto-Chefe define arquitetura
- Engenheiro de Implementação executa fielmente
- Nenhuma alteração sem autorização explícita
