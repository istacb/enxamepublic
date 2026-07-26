# Ativo de Conhecimento

## Definição

Um Ativo de Conhecimento é a menor unidade gerenciada representando conhecimento do usuário dentro do Enxame.

Pode representar um documento, imagem, conversação, áudio, vídeo, nota, registro de banco de dados ou qualquer outra fonte de informação.

## Responsabilidades

- Armazenar referências.
- Preservar proveniência.
- Preservar metadados.
- Permitir indexação.
- Permitir relacionamentos.
- Suportar versionamento.

## NÃO é responsável por

- Decidir a verdade.
- Substituir conhecimento do usuário.
- Tomar decisões autônomas.

## Relacionamentos

- Todo Ativo de Conhecimento representa Conhecimento.
- Um Ativo de Conhecimento pode relacionar-se com outros Ativos de Conhecimento.
- Um Ativo de Conhecimento pode ter uma ou mais fontes.
- Um Ativo de Conhecimento pertence a um usuário.
- Um Ativo de Conhecimento pode ser substituído mas nunca silenciosamente substituído.

## Invariantes

- Todo Ativo de Conhecimento possui um identificador.
- Todo Ativo de Conhecimento preserva proveniência sempre que possível.
- Todo Ativo de Conhecimento mantém timestamps.
- Todo Ativo de Conhecimento pode carregar informações de validade.
- Todo Ativo de Conhecimento é rastreável.

## Extensões Futuras

Este conceito pode evoluir através de EIPs.

Mudanças em seus invariantes requerem revisão arquitetural.
