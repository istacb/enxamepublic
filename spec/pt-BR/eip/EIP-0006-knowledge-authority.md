# EIP-0006: Autoridade de Conhecimento

## Status

**Aceito**

## Resumo

Nenhum Agent é autoridade sobre conhecimento.

Toda consulta além do contexto imediato da Task deve passar pelo Orchestrator.

O Bibliotecário é a autoridade de conhecimento do Enxame.

## Ordem Obrigatória de Consulta

1. Base offline do usuário
2. Bases locais
3. Recursos locais
4. Internet (último recurso)

## Restrições

Agents nunca acessam diretamente:

- Internet
- Bibliotecário
- outros Nodes

## Princípios

- Agents não são autoridades de conhecimento.
- Todas as consultas de conhecimento fluem através do Orchestrator.
- O Bibliotecário é a autoridade central de conhecimento.
- A ordem de consulta deve ser respeitada para preservar Offline First.
- Acesso direto por Agents é proibido.

## Consequências

### Positivas

- Preserva o princípio Offline First
- Mantém a arquitetura Resource First
- Centraliza o gerenciamento de conhecimento
- Previne acesso externo descontrolado
- Garante padrões consistentes de recuperação de conhecimento
- Protege contra vazamento de informação

### Negativas

- Adiciona latência às consultas de conhecimento
- Requer coordenação do Orchestrator para todo acesso externo
- Limita autonomia do Agent para coleta de informações

### Neutras

- A ordem de consulta é fixa e não negociável
- Orchestrator atua como guardião para acesso ao conhecimento
- Bibliotecário mantém o estado autoritativo de conhecimento

## Justificativa

A arquitetura Enxame estabelece limites claros em torno do acesso ao conhecimento para preservar princípios arquiteturais centrais.

Agents são entidades de execução, não autoridades de conhecimento.

Seu papel é executar Tasks usando recursos disponíveis, não coletar ou verificar informações independentemente.

Quando um Agent requer informações além do contexto imediato da Task, deve solicitar estas informações através do Orchestrator.

O Orchestrator então coordena com o Bibliotecário para recuperar o conhecimento necessário.

Este design preserva várias propriedades importantes:

**Offline First**: Ao exigir que consultas sigam uma ordem específica (base offline → bases locais → recursos locais → Internet), a arquitetura garante que conectividade externa seja usada apenas quando absolutamente necessário.

**Resource First**: Recursos locais são priorizados sobre recursos externos, respeitando a suposição de escassez da arquitetura.

**Conhecimento Centralizado**: O Bibliotecário serve como fonte única de verdade para conhecimento, prevenindo fragmentação e inconsistência.

**Acesso Controlado**: Ao proibir acesso direto de Agents a recursos externos, a arquitetura mantém controle sobre quais informações são acessadas e quando.

A ordem obrigatória de consulta garante que:

1. Conhecimento offline do Usuário seja sempre consultado primeiro
2. Conhecimento local em cache seja usado antes de fontes externas
3. Recursos computacionais locais sejam aproveitados antes de recursos de rede
4. Acesso à Internet seja verdadeiramente um último recurso

Esta abordagem se alinha com a filosofia Enxame de adaptar-se ao hardware disponível e minimizar consumo desnecessário de recursos.

## Referências

- EIP-0001: Arquitetura First
- EIP-0002: Arquitetura Resource First
- PR 4.2: Runtime

## Histórico

- **2024** - EIP criado como parte da Sprint 4 architecture
