# EIP-0002: Arquitetura Resource First

## Status

**Aceito**

## Resumo

Enxame assume que recursos computacionais são limitados.

A arquitetura deve minimizar uso de memória, consumo de CPU, requisitos de armazenamento e execução desnecessária.

Cada componente arquitetural permanente deve justificar seu custo computacional.

## Motivação

Enxame é projetado para reutilizar hardware existente antes de requerer novo hardware.

Software deve se adaptar ao hardware disponível sempre que possível.

Eficiência é um requisito arquitetural.

Não é um passo de otimização realizado depois.

## Princípios

- Hardware existente vem primeiro.
- Offline First permanece como princípio central.
- Decisão humana é sempre final.
- Conhecimento do Usuário pertence ao Usuário.
- Componentes devem justificar seu custo computacional.
- Simplicidade é preferida sobre abstração desnecessária.
- Novos serviços permanentes requerem justificativa arquitetural.

## Consequências

Decisões arquiteturais futuras devem sempre preferir soluções mais simples e leves sempre que fornecerem funcionalidade equivalente.

Complexidade arquitetural deve sempre ter valor mensurável.

## Justificativa

A arquitetura Enxame assume recursos computacionais escassos como premissa de design.

Ao contrário de sistemas projetados para infraestrutura de cloud abundante, Enxame prioriza execução eficiente em hardware existente do usuário, incluindo computadores legados.

Este princípio influencia todas as decisões arquiteturais futuras.
