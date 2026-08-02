# EIP-0005: Promoção Temporária de Serviços

## Status

**Aceito**

## Resumo

Um Node pode iniciar temporariamente serviços adicionais para manter o Enxame operacional.

Exemplo:

O Node que hospeda o Judge pode iniciar temporariamente o serviço Orchestrator caso este fique indisponível.

O Judge NÃO se transforma em Orchestrator.

O Node apenas hospeda temporariamente um novo Service.

Quando o Orchestrator retornar, o serviço temporário deve ser encerrado.

## Objetivo

Alta disponibilidade com simplicidade.

## Princípios

- Serviços podem ser promovidos temporariamente durante falhas.
- O Node hospeda o serviço, não se transforma nele.
- Serviços temporários devem ser encerrados quando o serviço original retornar.
- Promoção é automática e transparente para o Enxame.
- Nenhuma mudança de estado permanente ocorre durante a promoção.

## Consequências

### Positivas

- Alta disponibilidade sem infraestrutura complexa de failover
- Mecanismo simples de recuperação para serviços críticos
- Overhead mínimo durante operação normal
- Separação clara entre identidade do serviço e do Node
- Recuperação automática quando o serviço original retorna

### Negativas

- Requer monitoramento da disponibilidade do serviço
- Duplicação temporária de estado do serviço pode ocorrer
- Adiciona complexidade ao gerenciamento de lifecycle de serviços

### Neutras

- Promoção é temporária por design
- Apenas serviços críticos são elegíveis para promoção
- Identidade do serviço original é preservada

## Justificativa

A arquitetura Enxame requer alta disponibilidade enquanto mantém simplicidade arquitetural.

Promoção Temporária de Serviços fornece um mecanismo para manter serviços críticos durante falhas sem introduzir infraestrutura complexa de failover.

Quando um serviço crítico se torna indisponível, um Node pode hospedar temporariamente aquele serviço para manter as operações do Enxame.

Esta abordagem difere do failover tradicional de várias maneiras:

- O Node não se torna permanentemente o serviço.
- A identidade do serviço permanece inalterada.
- A promoção é temporária e automática.
- O serviço original pode retomar quando disponível.

Por exemplo, se o Orchestrator se tornar indisponível:

1. O Node que hospeda o Judge detecta a ausência.
2. O Node inicia um serviço Orchestrator temporário.
3. O Orchestrator temporário lida com operações essenciais.
4. Quando o Orchestrator original retorna, a instância temporária termina.
5. O Node retorna à sua configuração original de serviços.

Este mecanismo garante continuidade sem exigir redundância permanente ou protocolos complexos de coordenação.

## Referências

- EIP-0001: Arquitetura First
- EIP-0002: Arquitetura Resource First
- PR 4.1: Kernel (Microkernel)

## Histórico

- **2024** - EIP criado como parte da Sprint 4 architecture
