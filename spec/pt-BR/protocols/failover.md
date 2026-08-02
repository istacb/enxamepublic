# Protocolo de Failover

## Definição

Failover é o serviço responsável por detectar indisponibilidades e informar o Orchestrator sobre falhas que possam comprometer a execução de Tasks, Services ou Nodes.

Failover não executa recuperação.

Failover não reinicia Services.

Failover não redistribui Tasks.

Failover apenas publica eventos de falha.

Toda decisão pertence ao Orchestrator.

## Filosofia

Failover deve ser:

- simples;
- leve;
- orientado a eventos;
- desacoplado;
- determinístico.

Falhas são eventos esperados da arquitetura.

## Responsabilidade Única

O Failover possui apenas uma responsabilidade:

Informar indisponibilidades.

Toda recuperação pertence aos demais componentes da arquitetura.

## Fontes das Falhas

Failover pode receber eventos provenientes de:

- Orchestrator;
- Heartbeat;
- Service Loader.

Não realiza monitoramento próprio.

Não executa polling.

## Tipos de Falha

No mínimo:

- Service Failure
- Node Failure
- Communication Failure
- Capability Loss
- Task Failure

Cada evento deve possuir identificação clara.

## Node Failure

Quando o Orchestrator deixar de receber Heartbeats dentro do limite configurado:

O Node será considerado indisponível.

O Failover publica o evento correspondente.

O Scheduler e o Orchestrator decidirão como prosseguir.

## Service Failure

Quando o Service Loader esgotar todas as tentativas de reinicialização:

Publicar evento de falha.

Não tentar recuperação adicional.

## Task Failure

Cada Task define sua própria política de recuperação.

Exemplos:

- Never Retry
- Safe Retry
- Checkpoint

O Failover apenas informa que a Task foi interrompida.

A decisão pertence ao Orchestrator.

## Mission

A perda de um Node nunca implica cancelamento automático da Mission.

Enquanto existirem recursos suficientes, a Mission deverá continuar.

O Judge poderá avaliar o impacto da perda sobre a qualidade da Mission.

## Redistribuição

O Failover nunca redistribui Tasks.

Quando necessário:

As Tasks retornam para a fila.

Mantêm sua posição original.

O Scheduler decidirá novo destino.

## Retorno de Nodes

Quando um Node retornar após uma falha:

Executará novamente o processo oficial de Discovery.

Será tratado como disponível apenas após novo registro no Orchestrator.

Nenhuma Task anterior será automaticamente reassociada.

## Comunicação

Toda comunicação deve utilizar exclusivamente o Communication Protocol oficial.

Não criar novos protocolos.

Não criar novos envelopes.

## Interfaces

Criar interfaces desacopladas para:

- IFailover
- IFailureEvent
- IFailureType
- IFailureNotifier
- INodeFailure
- IServiceFailure
- ITaskFailure

## O Que o Failover Não Faz

- Não executa Tasks.
- Não realiza Discovery.
- Não envia Heartbeats.
- Não reinicia Services.
- Não reinicia Nodes.
- Não agenda Tasks.
- Não altera Missões.
- Não interpreta qualidade.
- Não implementa Logging.
- Não realiza diagnóstico físico.

## Eventos

Exemplos mínimos:

- Node Lost
- Node Recovered
- Service Failed
- Task Interrupted
- Capability Lost
- Communication Lost

Cada evento deve possuir identificação única e timestamp.

## Critérios de Aceite

A PR será considerada concluída quando:

- Failover possuir responsabilidade única.
- Utilizar exclusivamente eventos.
- Não realizar polling.
- Não executar recuperação.
- Não redistribuir Tasks.
- Trabalhar exclusivamente através do Orchestrator.
- Utilizar o protocolo oficial.
- Possuir documentação em inglês e português.

## Restrições

- Não modificar Runtime.
- Não modificar Scheduler.
- Não modificar Heartbeat.
- Não modificar Discovery.
- Não alterar EIPs existentes.
- Não criar novos protocolos.
- Não modificar documentos existentes.
- Adicionar apenas os documentos e implementação referentes ao Failover.

Priorizar simplicidade, desacoplamento e compatibilidade com hardware legado.
