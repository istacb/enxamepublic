# Node

## Definition

Um Node é um participante computacional do Enxame cuja existência é justificada por sua capacidade de contribuir para o sistema.

Um computador só se torna um Node após ingressar no Enxame e oferecer uma ou mais contribuições.

Um Node é identificado independentemente de seu estado operacional.

## Responsibilities

- Participar do Enxame.
- Executar uma ou mais capacidades.
- Contribuir com recursos computacionais.
- Contribuir com conhecimento especializado quando aplicável.
- Comunicar-se com outros Nodes através dos protocolos do Enxame.
- Executar sua Responsabilidade Primária.
- Opcionalmente assumir Responsabilidades Secundárias.
- Opcionalmente assumir Responsabilidades Temporárias quando solicitado pelo Enxame.

## It is NOT responsible for

- Tomar decisões finais.
- Possuir conhecimento do usuário.
- Substituir o julgamento humano.
- Violar as regras do Kernel.
- Modificar conhecimento do usuário sem autorização.

## Relationships

- Um Node participa de um Enxame.
- Um Node executa o Runtime do Enxame.
- Um Node hospeda um ou mais Agents.
- Um Node pode contribuir com uma ou mais Capabilities.
- Um Node pode acessar Knowledge Assets locais.
- Um Node comunica-se com outros Nodes.
- Um Node pode assumir temporariamente responsabilidades pertencentes a outro Node.

## Identity

Todo Node possui sua própria identidade.

A implementação desta identidade é intencionalmente não especificada pela arquitetura.

Exemplos podem incluir UUIDs, fingerprints ou identidades criptográficas.

A identidade deve sobreviver a estados offline temporários sempre que possível.

## Responsibilities Model

Todo Node tem exatamente uma Responsabilidade Primária.

Um Node pode ter zero ou mais Responsabilidades Secundárias.

Um Node pode receber Responsabilidades Temporárias durante a execução para manter a operação do Enxame.

Responsabilidades Temporárias nunca substituem a Responsabilidade Primária.

## Operational States

Os estados possíveis incluem, mas não se limitam a:

- Available
- Busy
- Offline
- Maintenance
- Recovering

O estado operacional não altera a identidade do Node.

## Invariants

- Todo Node contribui para o Enxame.
- Todo Node possui uma identidade única.
- Todo Node tem uma Responsabilidade Primária.
- Um Node pode executar Responsabilidades Secundárias.
- Um Node pode executar Responsabilidades Temporárias.
- Um Node nunca possui conhecimento do usuário.
- Um Node nunca substitui a decisão final do usuário.
- Um Node sempre respeita as regras do Kernel.

## Future Extensions

Este conceito pode evoluir através de EIPs.

Mudanças em seus invariantes requerem revisão arquitetural.
