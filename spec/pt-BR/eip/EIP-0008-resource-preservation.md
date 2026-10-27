# EIP-0008: Preservação de Recursos

## Status

**Aceito**

## Resumo

Todo componente do Enxame deve preservar recursos computacionais.

Processamento desnecessário deve ser evitado.

CPU, memória, armazenamento e energia são considerados recursos escassos.

Este princípio complementa a EIP-0002.

A EIP-0002 define a filosofia arquitetural.

A EIP-0008 define o comportamento esperado dos componentes durante a execução.

## Exemplos

- cancelar imediatamente Tasks canceladas
- destruir Agents ao término
- evitar processamento sem utilidade
- evitar estado residual
- evitar serviços permanentes sem justificativa

## Princípios

- Todos os componentes devem ativamente preservar recursos.
- Processamento desnecessário é proibido.
- CPU, memória, armazenamento e energia são recursos escassos.
- Preservação de recursos é um requisito de runtime, não uma otimização.
- Este princípio complementa e estende a EIP-0002.

## Consequências

### Positivas

- Consumo geral reduzido de recursos
- Vida útil estendida do hardware
- Melhor desempenho em sistemas restritos
- Menores custos de energia
- Capacidade de rodar em hardware mais antigo
- Melhoria na responsividade do sistema

### Negativas

- Requer design cuidadoso de todos os componentes
- Pode limitar escopo de features em alguns casos
- Adiciona complexidade à lógica de gerenciamento de recursos

### Neutras

- Preservação de recursos é obrigatória, não opcional
- Todos os componentes estão sujeitos a este princípio
- Trade-offs devem favorecer eficiência de recursos

## Justificativa

A arquitetura Enxame trata recursos computacionais como fundamentalmente escassos.

Esta não é uma suposição que pode ser otimizada depois.

É uma restrição central de design que influencia toda decisão arquitetural.

EIP-0002 (Arquitetura Resource First) estabelece a fundação filosófica.

EIP-0008 (Preservação de Recursos) define os requisitos comportamentais concretos.

Preservação de recursos se aplica a todos os aspectos do sistema:

**Processamento**: Computação desnecessária deve ser evitada. Isto inclui:

- Cancelar Tasks imediatamente quando solicitado
- Pular cálculos redundantes
- Evitar polling quando abordagens event-driven são possíveis
- Terminar execução quando resultados não são mais necessários

**Memória**: Uso de memória deve ser minimizado. Isto inclui:

- Destruir Agents após conclusão da Task
- Liberar toda memória alocada
- Evitar caching desnecessário
- Limpar estruturas de dados temporárias

**Armazenamento**: Uso de armazenamento deve ser justificado. Isto inclui:

- Remover arquivos temporários prontamente
- Evitar logging desnecessário
- Comprimir dados quando apropriado
- Justificar requisitos de armazenamento persistente

**Energia**: Consumo de energia deve ser considerado. Isto inclui:

- Evitar loops de busy-waiting
- Usar algoritmos eficientes
- Minimizar tráfego de rede
- Reduzir utilização de CPU durante períodos idle

**Serviços**: Serviços permanentes devem ter justificativa clara. Isto inclui:

- Avaliar necessidade de cada serviço
- Considerar promoção temporária sobre deploy permanente
- Consolidar funcionalidade quando possível
- Remover serviços não utilizados

Este princípio garante que Enxame possa operar eficientemente na gama completa de hardware alvo, de sistemas modernos a computadores legados.

Preservação de recursos não é uma otimização realizada após desenvolvimento.

É um requisito fundamental que molda a arquitetura desde o início.

## Referências

- EIP-0001: Arquitetura First
- EIP-0002: Arquitetura Resource First
- EIP-0007: Zero Estado Residual
- PR 4.1: Kernel (Microkernel)
- PR 4.2: Runtime

## Histórico

- **2024** - EIP criado como parte da Sprint 4 architecture
