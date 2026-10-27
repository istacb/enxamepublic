# EIP-0009: Identificador Hierárquico de Execução (HEI)

**Status:** Aceito  
**Tipo:** Standards Track  
**Sprint:** 4  
**PR:** 4.3

---

## Resumo

Toda execução no Enxame deve possuir uma identificação hierárquica legível por humanos.

O objetivo é fornecer rastreabilidade completa sem depender de identificadores aleatórios ou infraestrutura complexa de observabilidade.

---

## Motivação

Permitir:

- **Auditoria**: Linhagem clara de artefatos de execução.
- **Depuração**: Identificação rápida do contexto de execução.
- **Rastreamento**: Visibilidade end-to-end do fluxo da missão.
- **Correlação**: Link de eventos relacionados através de componentes distribuídos.
- **Compreensão Humana**: Baixa carga cognitiva ao analisar logs ou relatórios.

Tudo isso com custo computacional mínimo, aderindo à Resource First Architecture (EIP-0002).

---

## Princípios

### Hierarquia

O modelo de execução segue um relacionamento estrito pai-filho:

1. **Missão** gera **Workflows**.
2. **Workflow** gera **Tasks**.
3. **Task** gera **Execuções**.
4. **Execução** gera **Resultados**.

Todos os componentes filhos herdam o identificador de seu ancestral.

### Herança

Todo componente derivado deve herdar o caminho completo do identificador de seu pai. Isso permite reconstruir toda a árvore de execução a partir de qualquer nó único na hierarquia.

### Imutabilidade

Uma vez atribuído, um HEI nunca muda durante o tempo de vida da entidade que identifica.

---

## Especificação do Formato

O Identificador Hierárquico de Execução usa uma notação separada por pontos representando a profundidade da árvore de execução.

### Estrutura

| Nível | Formato | Exemplo | Descrição |
| :--- | :--- | :--- | :--- |
| **Missão** | `M{NNNNNN}` | `M000001` | Identificador raiz para uma Missão. |
| **Workflow** | `{Missão}.W{NN}` | `M000001.W01` | Workflow específico dentro de uma Missão. |
| **Task** | `{Workflow}.T{NN}` | `M000001.W01.T03` | Task específica dentro de um Workflow. |
| **Execução** | `{Task}.E{NN}` | `M000001.W01.T03.E01` | Tentativa de execução específica de uma Task. |
| **Resultado** | `{Task}.R{NN}` | `M000001.W01.T03.R01` | Artefato de resultado de uma execução de Task. |
| **Resposta Final** | `{Missão}.A` | `M000001.A` | Resposta final sintetizada da Missão. |

### Regras de Notação

- **Prefixos**: 
  - `M` = Missão (Mission)
  - `W` = Workflow
  - `T` = Task
  - `E` = Tentativa de Execução
  - `R` = Resultado
  - `A` = Resposta Final (Answer)
- **Preenchimento (Padding)**: Porções numéricas são preenchidas com zeros à esquerda para garantir correção na ordenação lexicográfica.
  - Missão: 6 dígitos (`000001`)
  - Workflow: 2 dígitos (`01`)
  - Task: 2 dígitos (`03`)
  - Execução/Resultado: 2 dígitos (`01`)

### Exemplos

```text
# Uma missão simples com um workflow e uma task
M000042
M000042.W01
M000042.W01.T01
M000042.W01.T01.E01
M000042.W01.T01.R01
M000042.A

# Uma missão complexa com retries
M000100
M000100.W01
M000100.W01.T05
M000100.W01.T05.E01  (Falhou)
M000100.W01.T05.E02  (Retry 1 - Falhou)
M000100.W01.T05.E03  (Retry 2 - Sucesso)
M000100.W01.T05.R03  (Resultado da execução bem-sucedida)
```

---

## Regras

### 1. Sem UUID como Identificador Primário

Nunca use UUIDs como identificador primário de execução visível para usuários ou logs.

- UUIDs podem existir internamente como detalhes técnicos (ex: chaves de banco de dados, IDs de mensagem).
- UUIDs **nunca** devem substituir o HEI para propósitos de rastreabilidade.

### 2. Herança Obrigatória

Todo componente filho deve herdar o caminho completo do identificador de seu pai.

- Uma Task não pode existir sem prefixo de Workflow.
- Um Workflow não pode existir sem prefixo de Missão.

### 3. Reconstrutabilidade da Árvore

O identificador deve permitir a reconstrução de toda a árvore de execução.

Dado qualquer HEI, deve-se ser capaz de determinar:
- A Missão pai.
- O Workflow específico.
- A Task específica.
- O número da tentativa de execução.

### 4. Escopo de Unicidade

- **ID da Missão**: Globalmente único em todo o Swarm.
- **ID do Workflow**: Único dentro do escopo de sua Missão.
- **ID da Task**: Único dentro do escopo de seu Workflow.
- **ID da Execução**: Único dentro do escopo de sua Task (incrementa em caso de retry).

---

## Benefícios

### Legibilidade

Operadores podem instantaneamente entender o contexto de uma execução olhando para o identificador.

```text
# Qual missão? Qual task? Qual tentativa?
M000001.W01.T03.E02
^       ^   ^   ^
|       |   |   └─ Tentativa 2
|       |   └───── Task 3
|       └───────── Workflow 1
└───────────────── Missão 1
```

### Auditoria

Simplifica conformidade e análise histórica. Todos os artefatos relacionados a uma missão compartilham um prefixo comum.

### Depuração

Isola rapidamente falhas. Se `M000001.W01.T03.E01` falha, o operador sabe exatamente onde procurar sem consultar tabelas join complexas.

### Correlação de Eventos

Logs, métricas e traces podem ser correlacionados usando um único campo de string sem requerer infraestrutura de distributed tracing.

### Troubleshooting

Reduz o tempo médio de resolução (MTTR) fornecendo contexto imediato.

### Baixa Complexidade

Nenhum serviço externo necessário para gerar ou resolver identificadores. Simples concatenação de strings.

---

## Consequências

### Positivas

- **Simplicidade**: Sem algoritmos complexos de geração de ID.
- **Performance**: Operações de string são baratas comparadas à geração/armazenamento de UUID.
- **Observabilidade**: Tracing embutido sem ferramentas externas.
- **Amigável a Legado**: Strings curtas e legíveis funcionam bem em terminais antigos e logs.

### Negativas

- **Comprimento**: Identificadores crescem com a profundidade da hierarquia (mitigado por padding fixo).
- **Rigidez**: Mudar a estrutura da hierarquia requer migrar IDs existentes.

### Neutras

- **Sequencialidade**: Requer mecanismo de contador (por node ou centralizado) para garantir unicidade.

---

## Justificativa

O design do HEI prioriza **legibilidade humana** e **simplicidade operacional** sobre aleatoriedade absoluta.

Em sistemas distribuídos, UUIDs fornecem unicidade mas destroem contexto. Um operador vendo `550e8400-e29b...` não aprende nada sobre o contexto de execução sem lookups em banco de dados.

A abordagem HEI embute contexto diretamente no identificador:
- Diz **o que** está executando (Missão/Task).
- Diz **onde** se encaixa (Workflow).
- Diz **quantas vezes** foi tentado (contagem de Execução).

Isso se alinha com a filosofia **Resource First** (EIP-0002) minimizando os recursos computacionais e cognitivos necessários para entender o estado do sistema.

---

## Compatibilidade

Esta EIP é considerada **experimental** inicialmente.

- Sprints futuras podem refinar o padding ou notação se limitações forem encontradas.
- Compatibilidade retroativa será mantida sempre que possível.
- O princípio central (herança hierárquica) é imutável.

---

## Referências

- **EIP-0001**: Architecture First
- **EIP-0002**: Resource First Architecture
- **PR 4.3**: Communication Protocol
- **Spec**: Communication Protocol (campo `mission_id` do Envelope)

---

## Histórico

| Data | Versão | Autor | Descrição |
| :--- | :--- | :--- | :--- |
| 2024-XX-XX | 1.0.0 | Architect | Proposta Inicial |
| 2024-XX-XX | 1.0.0 | Architect | Aceito para Sprint 4 |
