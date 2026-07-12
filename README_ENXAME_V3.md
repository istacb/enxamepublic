# ENXAME v3 — Arquitetura por Papéis Especializados

Evolução do v2: agora cada máquina tem uma **especialidade de conhecimento** fixa
(Juiz, Bibliotecário, Worker Engenharia, Worker Contábil, Artista Mídia), mas o
**papel de execução** (quem responde, quem audita, quem ajuda quem) continua
dinâmico, decidido pelo Juiz conforme disponibilidade.

---

## Os 5 papéis, como pedido

| Nó | Internet | Função | Onde está |
|---|---|---|---|
| **Juiz** | Sim | Hub de decisão, servidor de arquivos/rede, orquestrador de LLMs. Se auto-otimiza em ociosidade. | `core/juiz.py` |
| **Bibliotecário** | Sim | RAG, indexação, servidor de conhecimento geral, movimentação de arquivo autorizada, orquestra as bases. | `core/bibliotecario.py` |
| **Worker Engenharia** | Não | Engenharia civil, obras, BIM, CAD, normas. | `core/agente_universal.py` + `perfis/worker_engenharia.json` |
| **Worker Contábil** | Não | Contabilidade, administração, jurídico leve, direito do consumidor. | `core/agente_universal.py` + `perfis/worker_contabil.json` |
| **Artista Mídia** | Sim (hoje), preparado p/ offline | OCR, RAG de mídia, imagens/fotos/músicas/vídeos, armazenamento. | `core/agente_universal.py` + `perfis/artista_midia.json` |

O truque de engenharia: **agente_universal.py é o mesmo binário para os 3
papéis de conhecimento fechado** (engenharia, contábil, mídia) — só muda o
arquivo `perfis/<nome>.json` que ele carrega. Isso é o que torna o bootstrap
tão simples: 1 script, 5 perfis, sem duplicar lógica.

---

## Requisito → onde foi resolvido

| Você pediu | Onde está |
|---|---|
| Juiz com internet, servidor de arquivos/rede/LLMs | `core/juiz.py` — hub central, único ponto de entrada do chat, roteia e sintetiza |
| Juiz melhora a si mesmo na ociosidade | `loop_auto_otimizacao()` em `juiz.py`: quando não há pergunta há `OCIOSIDADE_SEGUNDOS` (padrão 300s), benchmarka todos os nós ativos e ajusta uma preferência leve de roteamento — **nunca muda peso/modelo de ninguém**, só prioridade de escolha, e tudo fica em `logs/juiz_otimizacoes.log` (reversível: apague o log e reinicie o Juiz). |
| Bibliotecário com internet, RAG, indexação, servidor de conhecimento geral | `core/bibliotecario.py`: embeddings via Ollama (`nomic-embed-text`) + busca por similaridade em SQLite/numpy, atualizado em loop contínuo. |
| Bibliotecário move arquivo só com autorização do admin | Endpoint `/api/v1/mover_arquivo` exige `admin_token` igual ao `ADMIN_TOKEN` gerado no `.env` de cada nó. Toda tentativa (aprovada ou negada) vai pro `logs/movimentacoes.log`. |
| Bibliotecário orquestra várias bases de conhecimento | `BASES_CONHECIMENTO` no `.env` lista as 4 bases (`kb_geral`, `kb_engenharia`, `kb_contabil`, `kb_midia`); o bibliotecário nunca mistura contexto de uma na resposta de outra, a não ser que o Juiz peça síntese geral explicitamente. |
| Worker 1 sem internet, base de engenharia/BIM/CAD/normas | `perfis/worker_engenharia.json`: `internet_permitida: false`, `keywords_dominio` cobrindo o domínio, escalando pro Juiz se não achar nada local. |
| Worker 2 sem internet, base contábil/jurídico leve | `perfis/worker_contabil.json`: mesma lógica + `aviso_padrao` obrigatório em respostas jurídicas/tributárias. |
| Artista com internet hoje, offline no futuro | `perfis/artista_midia.json` tem `internet_transitoria: true` e um campo `nota_transicao_offline` — todo fluxo que hoje depende de internet precisa ter plano B local documentado desde já (ex: OCR via Tesseract local, descrição de imagem via modelo de visão local pelo Ollama), não como retrofit depois. |
| Artista com OCR, RAG de mídia, criação/armazenamento de imagem/foto/música/vídeo | Bootstrap instala `tesseract-ocr` + `ffmpeg` + `pytesseract`/`pillow`; modelo de visão (`llava`/`moondream`) escolhido por hardware. Geração real de imagem/vídeo/música por IA generativa **não** foi implementada aqui — é stack pesada (Stable Diffusion/ComfyUI) que precisa de decisão sua sobre GPU dedicada; deixei o ponto de extensão documentado abaixo, não fingi que já está pronto. |
| Script automático de configuração via SSH | `scripts/ssh_provision_cluster.sh`: lê `inventory.yaml` (`ip;usuario;senha;perfil`) e roda o bootstrap remoto em cada máquina. |
| Verificação de capacidade da máquina + sugestão de modelo | `scripts/bootstrap_node.sh`: mede CPU/RAM/GPU/VRAM, calcula score, e escolhe automaticamente modelo de texto (0.5b→7b) e, para o Artista, modelo de visão (moondream→llava:13b) e, para o Bibliotecário, modelo de embeddings. Idempotente: rodar de novo só instala o que falta. |
| Acesso HTML por qualquer PC da rede | `enxame_chat.html`, agora mostrando perfil, se o nó tem internet, e se a pergunta foi escalada pro Bibliotecário. |
| Pesquisa offline primeiro | Camada dupla: Juiz busca `.zim` antes de rotear; agente busca catálogo local antes de gerar; só escala pro Bibliotecário (com internet) se o worker offline-only não achar nada. |

---

## Sobre a "auto-melhoria" do Juiz — o que ela é e o que não é

**Importante ser honesto aqui:** um LLM local não aprende de verdade só rodando
em ociosidade — não há re-treinamento nem ajuste de pesos acontecendo. O que
o Juiz realmente faz:

1. Manda um prompt de teste padrão pra cada nó ativo e mede latência/sucesso.
2. Ajusta um número interno de preferência de roteamento (entre -5 e +5) —
   usado só para desempate quando o score de hardware é parecido.
3. Registra cada mudança em log, com o motivo.

Isso é otimização operacional (roteamento), não otimização de modelo. Se no
futuro você quiser fine-tuning real, isso é outro projeto — envolve dataset,
GPU de treino e avaliação, e eu não implementaria isso escondido dentro de
"ociosidade" sem sua decisão explícita.

---

## Estrutura de arquivos

```
enxame_v3/
├── core/
│   ├── juiz.py                 # Hub central + auto-otimização
│   ├── bibliotecario.py        # RAG + indexação + movimentação autorizada
│   ├── agente_universal.py     # Worker Engenharia / Worker Contábil / Artista Mídia
│   ├── indexador.py            # Catalogação local (reaproveitado do v2)
│   └── perfis/
│       ├── juiz.json            (não usado por agente_universal.py, documental)
│       ├── bibliotecario.json
│       ├── worker_engenharia.json
│       ├── worker_contabil.json
│       └── artista_midia.json
├── scripts/
│   ├── bootstrap_node.sh        # Setup por perfil, hardware-aware, idempotente
│   ├── ssh_provision_cluster.sh # Provisiona todas as máquinas do inventory.yaml
│   ├── sync_arquivos.sh         # Distribui .zim/.pmtiles (reaproveitado do v2)
│   ├── copiar_acervo.sh         # Artista copia arquivos de interesse (sem instaladores)
│   └── windows_ollama_setup.ps1 # Ollama nativo no Windows do artista (GPU)
├── enxame_chat.html             # Cliente web, mostra perfil/internet/escalonamento
├── inventory.example.yaml       # ip;usuario;senha;perfil
└── README_ENXAME_V3.md
```

> Nota: não criei `perfis/juiz.json` com efeito de código — o Juiz não roda
> `agente_universal.py`, então um perfil ali seria só documentação. Se quiser,
> posso criar mesmo assim para manter o padrão de "5 arquivos de perfil, 5 papéis".

---

## Como usar do zero

**1. Juiz** (a máquina com internet e mais estável, ex: o Dell):
```bash
mkdir -p ~/enxame/perfis
cp core/*.py ~/enxame/
cp core/perfis/*.json ~/enxame/perfis/
cd ~/enxame && bash scripts/bootstrap_node.sh --perfil juiz
```

**2. Provisionar as demais máquinas** (rodando ainda no Juiz):
```bash
cp inventory.example.yaml inventory.yaml
# edite IPs/usuário/senha/perfil reais
bash scripts/ssh_provision_cluster.sh --inventory inventory.yaml
```

**3. Máquina nova depois:** adicione a linha no `inventory.yaml` (com o
perfil certo) e rode `ssh_provision_cluster.sh` de novo.

**4. Artista (Windows + WSL2, GPU):**
```powershell
.\scripts\windows_ollama_setup.ps1
```
```bash
bash bootstrap_node.sh --juiz <IP_JUIZ> --perfil artista_midia
bash scripts/copiar_acervo.sh "/mnt/c/Users/voce/Documents"
```

**5. Autorizar movimentação de arquivo pelo Bibliotecário:**
O token fica em `~/enxame/.env` (`ADMIN_TOKEN=...`) da máquina do Bibliotecário.
Só quem tiver esse token consegue mover arquivo via API — guarde-o como admin.

**6. Acessar de qualquer PC da rede:**
Abra `enxame_chat.html`, digite o IP do Juiz, pronto.

---

## O que ficou como ponto de extensão (não fingi que estava pronto)

- **Geração real de imagem/vídeo/música por IA** no Artista: precisa de
  Stable Diffusion/ComfyUI (ou similar) e decisão sobre alocação de GPU —
  não incluído no bootstrap automático por ser stack pesada e específica de
  driver; hoje o Artista faz OCR + descrição/organização de mídia via modelo
  de visão local, que é o que dava pra bootstrapar com segurança.
- **RAG vetorial em escala**: o SQLite+numpy do Bibliotecário é ótimo até
  alguns milhares de documentos; se crescer muito, trocar por Qdrant (que já
  está no seu `docker-compose.yml`) é o próximo passo natural.
- **Busca de internet do Bibliotecário**: propositalmente não fiz scraping
  direto de motores de busca de terceiros — `SEARCH_API_URL` no `.env` espera
  um endpoint de busca próprio/autorizado (ex: uma instância SearXNG sua).
