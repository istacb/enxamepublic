# Catálogo de Eventos

## Propósito

Este documento define o Catálogo de Eventos dentro da arquitetura Enxame.

Um Evento representa um fato arquitetural imutável.

Eventos representam transições entre estados, não estados em si.

Este documento formaliza o modelo arquitetural de eventos utilizado em todo o Enxame.

## Princípios de Design

O modelo de Eventos segue estes princípios:

- **Imutabilidade** - Eventos nunca mudam após publicação.
- **Representação de Transição** - Eventos representam transições de estado, não estados.
- **Propriedade do Componente** - Cada componente publica apenas seus próprios eventos.
- **Independência** - Eventos permanecem independentes de infraestrutura e mecanismos de transporte.
- **Reuso de Identificadores** - Eventos reutilizam identificadores de domínio existentes sempre que suficiente.

## Propriedade de Eventos

Cada componente arquitetural DEVE publicar apenas seus próprios eventos.

Componentes NUNCA DEVEM publicar eventos em nome de outros componentes.

A propriedade de eventos é determinada pelo componente que origina o evento:

- Eventos de Missão são publicados pelo componente gerenciando transições de estado da Missão.
- Eventos de Workflow são publicados pelo Orchestrator.
- Eventos de Task são publicados pelo componente derivando Tasks de Workflows.
- Eventos de Execução são publicados pelo Runtime.

Propriedade determina responsabilidade de publicação, não direitos de consumo.

## Ciclo de Vida de Eventos

### Publicação

Um evento é publicado quando uma transição de estado ocorre.

Publicação torna o evento disponível para consumidores interessados.

O componente publicador determina quando um evento é publicado baseado em transições arquiteturais.

### Consumo

Qualquer componente PODE consumir qualquer evento publicado, incluindo os seus próprios.

Consumir um evento NUNCA DEVE modificar o próprio evento.

Consumo é independente da publicação.

Um componente pode consumir eventos sem ser o publicador.

### Imutabilidade

Eventos NUNCA DEVEM ser modificados após publicação.

Uma vez publicado, um evento se torna um fato arquitetural imutável.

Se informação adicional for necessária, um novo evento DEVE ser publicado.

## Persistência de Eventos

Persistência permanente de eventos NÃO é requerida pela arquitetura.

Retenção de eventos DEVE ser considerada uma política de implementação baseada em recursos disponíveis.

Decisões de persistência pertencem à implementação, não à arquitetura.

A arquitetura não manda duração ou estratégia de armazenamento de eventos.

## Identificação de Eventos

Eventos DEVEM reutilizar identificadores de domínio existentes sempre que suficiente.

A arquitetura NÃO DEVE introduzir identificadores adicionais quando identificadores de Missão, Workflow e Task já fornecem o contexto necessário.

Identificação de eventos depende de:

- Identificador de Missão para eventos relacionados a Missão
- Identificador de Workflow para eventos relacionados a Workflow
- Identificador de Task para eventos relacionados a Task
- Identificador de Execução para eventos relacionados a execução

Identificadores adicionais DEVEM apenas ser introduzidos quando identificadores de domínio forem insuficientes.

## Independência de Eventos

Eventos NÃO DEVEM conhecer:

- Publicadores
- Consumidores
- Mecanismos de transporte
- Protocolos de comunicação
- Infraestrutura

Eventos são fatos arquiteturais puros.

Definição de eventos permanece independente da distribuição de eventos.

## Hierarquia de Eventos

Eventos NÃO DEVEM formar hierarquias de herança.

Eventos são fatos arquiteturais independentes.

Cada tipo de evento existe isoladamente sem relacionamentos pai-filho.

Composição de eventos ocorre através de correlação via identificadores de domínio, não através de herança.

## Catálogo de Eventos

Os seguintes eventos constituem o vocabulário arquitetural mínimo.

Eventos específicos de implementação pertencem a documentação futura.

### Eventos de Missão

#### MissionCreated

Publicado quando uma Missão é criada com um intento de usuário definido.

Indica o início do ciclo de vida de uma Missão.

#### MissionCompleted

Publicado quando o Usuário declara uma Missão como completada.

Indica conclusão bem-sucedida da Missão por decisão do Usuário.

#### MissionCancelled

Publicado quando uma Missão é cancelada.

Indica terminação da Missão antes da conclusão.

### Eventos de Workflow

#### WorkflowDerived

Publicado quando um Workflow é derivado de uma Missão pelo Orchestrator.

Indica criação de um plano de execução imutável.

#### WorkflowCompleted

Publicado quando todas as Tasks derivadas de um Workflow foram executadas.

Indica conclusão do trabalho lógico do Workflow.

Não implica conclusão da Missão.

#### WorkflowCancelled

Publicado quando um Workflow é cancelado antes da conclusão.

Indica terminação do Workflow.

### Eventos de Task

#### TaskCreated

Publicado quando uma Task é derivada de um Workflow.

Indica criação de uma unidade de trabalho de domínio.

#### TaskCompleted

Publicado quando o trabalho lógico de uma Task foi realizado.

Indica execução bem-sucedida da Task.

#### TaskFailed

Publicado quando uma execução de Task falha.

Indica falha na execução da Task sem modificar a Task.

### Eventos de Execução

#### ExecutionStarted

Publicado quando o Runtime inicia a execução de uma Task.

Indica início de uma tentativa de execução.

#### ExecutionCompleted

Publicado quando o Runtime completa com sucesso uma tentativa de execução.

Indica execução bem-sucedida de uma Task.

#### ExecutionFailed

Publicado quando o Runtime falha em completar uma tentativa de execução.

Indica falha de execução, que pode acionar retry.

## Invariantes Arquiteturais

As seguintes invariantes DEVEM ser mantidas em todo o modelo de Eventos:

- Eventos DEVEM representar fatos arquiteturais.
- Eventos DEVEM representar transições ao invés de estados.
- Eventos DEVEM permanecer imutáveis após publicação.
- Componentes DEVEM publicar apenas seus próprios eventos.
- Identificadores de domínio existentes DEVEM ser reutilizados sempre que possível.
- Persistência de eventos DEVE permanecer dependente da implementação.
- Eventos DEVEM permanecer independentes de infraestrutura.
- Eventos NÃO DEVEM formar hierarquias de herança.
- Consumo de eventos NÃO DEVE modificar o evento.
- Qualquer componente PODE consumir qualquer evento publicado.

## Fora do Escopo

Este documento não define:

- Schemas de payload
- Formatos de serialização
- Protocolos de transporte
- Sistemas de mensageria
- Mecanismos de armazenamento de eventos
- Estratégias de replay de eventos
- Detalhes de implementação de infraestrutura

Estes tópicos pertencem a especificações separadas.

## Documentos Relacionados

- `concepts/mission_lifecycle.md` - Ciclo de Vida da Missão
- `concepts/workflow_lifecycle.md` - Ciclo de Vida do Workflow
- `concepts/task_lifecycle.md` - Ciclo de Vida da Task
- `eip/EIP-0001-architecture-first.md` - Princípio Architecture First
- `eip/EIP-0002-resource-first.md` - Princípio Resource First
