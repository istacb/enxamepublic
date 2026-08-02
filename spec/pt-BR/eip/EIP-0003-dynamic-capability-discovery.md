# EIP-0003: Descoberta Dinâmica de Capacidades

## Status

**Aceito**

## Resumo

As capacidades de um Node representam seu estado atual.

Capabilities são dinâmicas.

Podem aparecer ou desaparecer durante a execução.

Não exigem reinicialização do Node.

O Capability Registry deve refletir sempre o estado atual.

O Orchestrator deve ser informado quando ocorrerem alterações.

## Motivação

Permitir adaptação dinâmica da infraestrutura sem reinicialização.

## Princípios

- Capabilities são dinâmicas, não estáticas.
- Recursos podem ser hot-plugged e hot-removed.
- O Capability Registry reflete o estado em tempo real.
- Mudanças nas capabilities devem ser comunicadas ao Orchestrator.
- Reinicialização do Node não é necessária para mudanças de capabilities.

## Consequências

### Positivas

- Hot Plug de recursos
- Hot Removal de recursos
- Maior resiliência
- Melhor distribuição de Tasks
- Infraestrutura se adapta a mudanças de hardware

### Negativas

- Requer monitoramento contínuo do estado dos recursos
- Adiciona complexidade ao rastreamento de capabilities

### Neutras

- Mudanças de capabilities são locais ao Node
- Orchestrator recebe atualizações de forma assíncrona

## Justificativa

A arquitetura Enxame trata capabilities como propriedades dinâmicas que refletem a disponibilidade atual de recursos em um Node.

Ao contrário de sistemas que assumem capabilities estáticas definidas na inicialização, o Enxame reconhece que recursos de hardware podem mudar durante a execução.

Este princípio permite que Nodes se adaptem a mudanças de hardware tais como:

- Dispositivos USB conectados ou desconectados
- Interfaces de rede tornando-se disponíveis ou indisponíveis
- Dispositivos de armazenamento montados ou desmontados
- Drivers de GPU carregados ou descarregados
- Dispositivos periféricos adicionados ou removidos

O Capability Registry mantém o estado atual de todas as capabilities.

Quando uma capability muda, o Registry é atualizado e o Orchestrator é notificado.

Isso permite que o Enxame tome decisões inteligentes de distribuição de Tasks baseadas na disponibilidade de recursos em tempo real.

## Referências

- EIP-0002: Arquitetura Resource First
- PR 4.1: Kernel (Microkernel)
- PR 4.2: Runtime

## Histórico

- **2024** - EIP criado como parte da Sprint 4 architecture
