# REVISÃO DE CONSISTÊNCIA ARQUITETURAL
## BEE-0001 vs EIPs Existentes

**Data:** 2025  
**Revisor:** Auditoria Arquitetural  
**EIPs Verificadas:** EIP-0001, EIP-0002

---

## 1. VERIFICAÇÃO CONTRA EIP-0001 (Architecture First)

### Princípio EIP-0001
> "Toda mudança significativa deve ser precedida por especificação arquitetural documentada."

### Conformidade BEE-0001

| Requisito | Status | Evidência |
|-----------|--------|-----------|
| Especificação antes da implementação | ✅ | BEE-0001 criado ANTES de qualquer código em `bees/` |
| Documentação em `spec/` | ✅ | Arquivo em `bees/spec/BEE-0001-ABELHA.md` |
| Fonte única de verdade | ✅ | Especificação define todos os aspectos da Abelha |
| Rastreabilidade de decisões | ✅ | Seção 20 lista explicitamente o que está incluído/excluído |
| Glossário | ✅ | Anexo B define todos os termos |

### Avaliação
**CONFORME.** BEE-0001 segue exatamente o processo estabelecido por EIP-0001:
- Especificação completa antes da implementação
- Estrutura documentada com status, versão, autoria
- Definições normativas claras
- Referências a componentes existentes (Anexo A)

---

## 2. VERIFICAÇÃO CONTRA EIP-0002 (Resource First)

### Princípios EIP-0002

#### 2.1 "Existing hardware comes first"

**BEE-0001 Seção 9 (Modelo(s) Locais):**
> "Cada máquina utiliza o melhor modelo que consegue sustentar conforme RAM/CPU/GPU"
> "Modelos de 1B a 10B parâmetros conforme hardware disponível"

**Avaliação:** ✅ **CONFORME**
- Algoritmo de seleção de modelo baseado em hardware
- Tabela de referência RAM vs Modelo recomendado
- Não requer hardware novo, adapta-se ao existente

---

#### 2.2 "Offline First remains a core principle"

**BEE-0001 Seção 13 (Política Offline First):**
> "A Abelha opera primariamente offline. Internet é recurso de último recurso, não dependência."

**BEE-0001 Seção 14 (LOCAL → ENXAME → WEB):**
> Hierarquia obrigatória: Memória local → RAG local → Outras Abelhas → Internet

**Avaliação:** ✅ **CONFORME**
- Offline-first explícito como princípio normativo
- Default `allow_web = false`
- Funciona completamente sem internet
- Internet apenas como fallback configurável

---

#### 2.3 "Components must justify their computational cost"

**BEE-0001 Seção 10 (Bibliotecário Local):**
- Reutiliza componentes existentes do `bibliotecario/`
- Remove Redis (cache em memória apenas)
- Remove tradução automática (opcional)

**BEE-0001 Seção 20 (O que NÃO faz parte):**
- ❌ Inferência distribuída de modelos grandes (complexidade injustificada)
- ❌ Redis como dependência (custo computacional)
- ❌ Múltiplos modelos automáticos (desperdício de recursos)

**Avaliação:** ✅ **CONFORME**
- Cada componente tem justificativa clara
- Componentes pesados (Redis) removidos
- Simplicidade preferida (cache em memória)
- Novo serviço justificado por autonomia local

---

#### 2.4 "Simplicity is preferred over unnecessary abstraction"

**BEE-0001 Seção 6 (Generalismo Inicial):**
> "Todas as Abelhas são generalistas na instalação inicial."
> "Não existe papel primário obrigatório, especialização forçada, hierarquia de funções"

**BEE-0001 Seção 17 (Independência de Provider/Modelo):**
> "A Abelha não assume nenhum modelo específico"
> "Não hardcode llama3 ou gemma2 como únicos"

**Avaliação:** ✅ **CONFORME**
- Sem abstrações desnecessárias (papéis fixos removidos)
- Sem especialização prematura
- Provider abstrato mas implementação simples (Ollama HTTP API)
- Generalismo reduz complexidade inicial

---

#### 2.5 "New permanent services require architectural justification"

**BEE-0001 Seção 2 (Relação Abelha × Enxame):**
> "Uma Abelha deve conseguir existir e trabalhar sem qualquer outra Abelha."
> "O Enxame é uma propriedade emergente da comunicação entre duas ou mais Abelhas"

**Justificativa para nova arquitetura:**
1. Papel fixo cria ponto único de falha (Juiz)
2. Topologia estrela não escala
3. Autonomia local melhora resiliência
4. Mesh peer-to-peer é mais eficiente que orquestração central

**Avaliação:** ✅ **CONFORME**
- Nova arquitetura (Abelha) tem justificativa clara
- Resolve problemas da arquitetura anterior (papéis fixos)
- Benefícios mensuráveis: resiliência, escalabilidade, autonomia

---

## 3. CONFLITOS IDENTIFICADOS

### Conflito Potencial 1: Campo `role` no Discovery

**Descrição:** 
- Core atual (`core/discovery/mdns_discovery.py`) usa campo `role`
- BEE-0001 especifica `capabilities` no lugar de `role`

**Severidade:** Alto

**Resolução Proposta:**
- Manter `role` no core para backward compatibility
- Adicionar `capabilities` como campo novo
- Abelhas usam `capabilities`, nós antigos usam `role`
- Deprecar `role` gradualmente

**Status:** ⚠️ **REQUER MITIGAÇÃO**

---

### Conflito Potencial 2: Tipos ROLE_* e ELECTION_* no EXP

**Descrição:**
- `core/exp/types.py` define tipos específicos de papéis fixos
- BEE-0001 não usa estes tipos

**Severidade:** Alto

**Resolução Proposta:**
- Criar subconjunto `EXP-BEE` com tipos necessários
- Ou versionar protocolo: `protocol_version: "BEE-0001"`
- Abelhas ignoram tipos ROLE_* e ELECTION_*

**Status:** ⚠️ **REQUER MITIGAÇÃO**

---

### Conflito Potencial 3: Coexistência de Arquiteturas

**Descrição:**
- Nós tradicionais (Juiz/Bibliotecário/Agente) podem estar rodando
- Abelhas novas podem rodar simultaneamente

**Severidade:** Médio

**Resolução Proposta:**
- Portas diferentes (Juiz: 8000, Abelha: 8765)
- Serviços mDNS diferentes (`_enxame-node._tcp` vs `_enxame-bee._tcp`)
- Permitir coexistência até migração completa

**Status:** ✅ **MITIGADO POR DESIGN** (namespace separado)

---

## 4. ALINHAMENTO COM OUTROS EIPs

### EIP-0003 (Dynamic Capability Discovery)

**BEE-0001 Seção 7 (Capabilities):**
- Anúncio dinâmico de capacidades via mDNS
- Atualização em tempo real de `load_score`
- Consulta de capabilities peer-to-peer

**Avaliação:** ✅ **ALINHADO**

---

### EIP-0005 (Temporary Service Promotion)

**BEE-0001 Seção 6 (Generalismo Inicial):**
- Todas as Abelhas são generalistas inicialmente
- Especialização pode surgir posteriormente por capacidade/experiência

**Nota:** BEE-0001 não implementa especialização nesta fase, mas deixa arquitetura extensível.

**Avaliação:** ✅ **ALINHADO** (especialização futura possível)

---

### EIP-0006 (Knowledge Authority)

**BEE-0001 Seção 14 (LOCAL → ENXAME → WEB):**
- Hierarquia de fontes de conhecimento
- Rastreabilidade de origem (`source` metadado)
- Confiança mensurável (`confidence` score)

**Avaliação:** ✅ **ALINHADO**

---

### EIP-0007 (Zero Residual State)

**BEE-0001 Seção 4.3 (Persistência de Estado):**
- Persiste: identidade, configuração, memória, índice
- **NÃO persiste:** estado de peers, cache volátil, contexto de sessão

**Avaliação:** ✅ **ALINHADO**
- Estado efêmero é realmente efêmero
- Estado persistente tem justificativa

---

### EIP-0008 (Resource Preservation)

**BEE-0001 Seção 13 (Offline First):**
- Minimiza uso de internet
- Reutiliza conhecimento local
- Compartilha carga entre peers (futuro)

**Avaliação:** ✅ **ALINHADO**

---

## 5. RESUMO DA REVISÃO

### Conformidade Geral

| EIP | Conformidade | Observações |
|-----|--------------|-------------|
| EIP-0001 | ✅ 100% | Processo de especificação seguido corretamente |
| EIP-0002 | ✅ 100% | Resource First aplicado em todas as decisões |
| EIP-0003 | ✅ 100% | Capabilities dinâmicas implementadas |
| EIP-0005 | ✅ 100% | Generalismo inicial, especialização futura |
| EIP-0006 | ✅ 100% | Autoridade de conhecimento rastreável |
| EIP-0007 | ✅ 100% | Estado residual minimizado |
| EIP-0008 | ✅ 100% | Preservação de recursos (offline-first) |

### Conflitos Críticos

| # | Conflito | Severidade | Mitigação |
|---|----------|------------|-----------|
| 1 | Campo `role` no mDNS | Alto | Adicionar `capabilities`, manter `role` temporariamente |
| 2 | Tipos ROLE_* no EXP | Alto | Criar subconjunto EXP-Bee ou versionar protocolo |
| 3 | Coexistência | Médio | Namespaces e portas separadas |

### Recomendações

1. **PR de Mitigação #1:** Atualizar `core/discovery/mdns_discovery.py` para suportar `capabilities` opcional
2. **PR de Mitigação #2:** Criar `core/exp/bee_types.py` com subconjunto de tipos para Abelhas
3. **Documentação:** Adicionar nota de coexistência em `README.md` explicando que Abelhas e nós tradicionais podem rodar simultaneamente

---

## 6. PARECER FINAL

**BEE-0001 — ABELHA está ARQUITETURALMENTE CONSISTENTE** com:

✅ EIP-0001 (Architecture First)  
✅ EIP-0002 (Resource First)  
✅ EIPs complementares (0003-0008)  

**Condições para implementação:**
1. Mitigar conflito do campo `role` no discovery (backward compatible)
2. Mitigar conflito dos tipos ROLE_* no protocolo EXP
3. Manter namespace `bees/` isolado até maturidade

**Risco arquitetural:** BAIXO  
**Impacto na arquitetura existente:** NULO (namespace isolado)  
**Recomendação:** **APROVADO PARA IMPLEMENTAÇÃO**

---

*Revisão concluída em: 2025*  
*Próxima etapa: Implementar PRs de mitigação, depois iniciar PR 1 (Fundação da Abelha)*
