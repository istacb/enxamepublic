# ENXAME — Guia Completo de Instalação, Deploy e Operação (3 Nós)

## Novo modelo de operação (eleição automática + busca distribuída)

A arquitetura agora opera sem papéis fixos no plano de execução do cluster:

- todos os nós publicam benchmark de hardware (CPU/RAM/GPU/disco);
- o Juiz executa eleição automática via EXP (`ELECTION_PROPOSE`, `ELECTION_VOTE`, `ROLE_CHANGE`);
- melhor score assume papel lógico de **juiz de execução**;
- pior score assume papel lógico de **bibliotecária**;
- demais assumem papel lógico de **agentes**;
- **todos os nós** fazem busca local primeiro (`cache -> arquivos locais -> ZIM local`);
- internet é usada apenas como fallback pela bibliotecária quando o cluster não encontra localmente;
- arquivos `.zim` são particionados logicamente entre nós e distribuídos via plano de atribuição.

> Compatibilidade mantida: protocolo EXP, Docker Compose e CLI continuam suportados.

## Visão geral dos scripts novos

Todos ficam em `scripts/`:

- `bootstrap_ubuntu.sh` → prepara máquina Ubuntu/Xubuntu
- `setup_inicial.sh` → gera segredos, certificados e `.env` por nó
- `deploy_3nos.sh` → deploy automático do nó local (com detecção)
- `enxame.sh` → gerenciamento do cluster no nó local (`start|stop|restart|status|logs|health`)
- `pull_models.sh` → baixa modelos Ollama por perfil de nó
- `cluster_auto_init.py` → executa benchmark local e dispara eleição automática (quando no Juiz)

---

## 1) Pré-requisitos

- 3 máquinas Ubuntu/Xubuntu 22.04+
- Acesso `sudo` nas 3 máquinas
- Rede local funcional entre os nós
- Repositório ENXAME copiado para o mesmo caminho nas 3 máquinas (recomendado)

IPs de exemplo (ajuste conforme seu ambiente):

- Nó 1 (Juiz): `192.168.1.10`
- Nó 2 (Bibliotecário): `192.168.1.11`
- Nó 3 (Agentes): `192.168.1.12`

---

## 2) Bootstrap em cada máquina (Ubuntu/Xubuntu)

Em **cada um dos 3 nós**:

```bash
cd /caminho/para/enxame
chmod +x scripts/*.sh
./scripts/bootstrap_ubuntu.sh
```

O script instala automaticamente:

- Docker Engine + Docker Compose plugin
- Ollama
- Python 3.11+
- Redis (serviço local)
- Imagens Docker de Redis e Qdrant
- Modelos Ollama:
  - `llama3`
  - `gemma2:9b`
  - `gemma2:2b-it-qat`

> Se o usuário foi adicionado ao grupo `docker`, faça logout/login antes de continuar.

---

## 3) Configuração inicial centralizada (segredos + TLS + envs)

Execute **uma única vez** (normalmente no nó 1 ou em uma máquina de administração):

```bash
cd /caminho/para/enxame
./scripts/setup_inicial.sh \
  --node1-ip 192.168.1.10 \
  --node2-ip 192.168.1.11 \
  --node3-ip 192.168.1.12
```

Serão gerados:

- `deploy/secrets/exp_shared_secret`
- `deploy/certs/ca.crt`, `ca.key`, certificados `node*.crt/node*.key`
- `deploy/env/node1.env`, `node2.env`, `node3.env`

### Distribuição para os nós

- Copie `deploy/env/nodeX.env` para a máquina correspondente.
- Copie os certificados para `/etc/enxame/certs` em cada nó:
  - `ca.crt`
  - cert/chave do próprio nó (`node1-juiz.*`, `node2-bibliotecario.*`, `node3-agentes.*`)

Exemplo (em cada nó):

```bash
sudo mkdir -p /etc/enxame/certs
sudo cp ca.crt /etc/enxame/certs/
sudo cp nodeX-*.crt nodeX-*.key /etc/enxame/certs/
sudo chmod 600 /etc/enxame/certs/*.key
```

---

## 4) Deploy automático em cada nó

Em cada máquina, execute o deploy local.

### Opção A: auto detecção do nó por hostname

```bash
./scripts/deploy_3nos.sh
```

### Opção B: forçando o nó explicitamente

```bash
./scripts/deploy_3nos.sh --node 1 --env-file deploy/env/node1.env
./scripts/deploy_3nos.sh --node 2 --env-file deploy/env/node2.env
./scripts/deploy_3nos.sh --node 3 --env-file deploy/env/node3.env
```

Opções úteis:

- `--set-hostname` → ajusta hostname para padrão ENXAME
- `--skip-models` → pula pull de modelos Ollama

O script:

- Detecta/define papel do nó (1=Juiz, 2=Bibliotecário, 3=Agentes)
- Usa o compose correto (`node1-juiz/`, `node2-bibliotecario/`, `node3-agentes/`)
- Sobe serviços com `docker compose up -d --build`
- Executa pull de modelos do perfil do nó

---

## 5) Gerenciamento do cluster no nó local

Use `scripts/enxame.sh`:

```bash
./scripts/enxame.sh start [--node 1|2|3]
./scripts/enxame.sh stop [--node 1|2|3]
./scripts/enxame.sh restart [--node 1|2|3]
./scripts/enxame.sh status [--node 1|2|3]
./scripts/enxame.sh logs [--node 1|2|3] --lines 300
./scripts/enxame.sh health [--node 1|2|3]
```

### O que cada comando faz

- `start`: executa pipeline de deploy do nó
- `stop`: derruba os containers do nó
- `restart`: reinicia os serviços
- `status`: mostra estado dos containers (`docker compose ps`)
- `logs`: exibe logs centralizados do compose local
- `health`:
  - Nó 1: `GET http://127.0.0.1:7700/api/v1/health`
  - Nó 2: `GET http://127.0.0.1:7710/api/v1/health`
  - Nó 3: valida serviços em execução (agentes não expõem HTTP dedicado)

---

## 6) Verificação rápida pós-deploy

No nó 1 (Juiz):

```bash
curl -s http://127.0.0.1:7700/api/v1/health
```

No nó 2 (Bibliotecário):

```bash
curl -s http://127.0.0.1:7710/api/v1/health
```

Status dos serviços em cada nó:

```bash
./scripts/enxame.sh status --node 1
./scripts/enxame.sh status --node 2
./scripts/enxame.sh status --node 3
```

---

## 7) Uso da CLI ENXAME

Com ambiente Python ativo no nó que acessa o Juiz:

```bash
python -m cli.enxame ask "Explique a arquitetura do ENXAME"
python -m cli.enxame cluster
python -m cli.enxame agents
python -m cli.enxame status <task_id>
```

Variáveis relevantes:

- `EXP_SHARED_SECRET`
- `ENXAME_JUIZ_URL` (ex.: `http://192.168.1.10:7700`)

### Eleição automática (opcional/manual)

Para forçar nova eleição via API do Juiz:

```bash
curl -s -X POST http://127.0.0.1:7700/api/v1/election \
  -H "x-exp-timestamp: <timestamp>" \
  -H "x-exp-signature: <assinatura_hmac>"
```

> No fluxo padrão, `deploy_3nos.sh` já executa `scripts/cluster_auto_init.py` automaticamente.

---

## 8) Deploy local único (simulação em 1 máquina)

Para desenvolvimento local:

```bash
cp .env.example .env
# ajuste EXP_SHARED_SECRET

docker compose --env-file .env up -d --build
./scripts/pull_models.sh all
```

---

## 9) Troubleshooting

### Docker sem permissão

```bash
sudo usermod -aG docker $USER
# logout/login
```

### Ollama não responde

```bash
sudo systemctl status ollama
ollama list
```

### Nó 2 e Nó 3 não conectam ao Juiz

- Validar IP/porta no `deploy/env/node2.env` e `deploy/env/node3.env` (`JUIZ_WS_URL`)
- Validar conectividade de rede para `192.168.1.10:7700`

### Health check falhando

```bash
./scripts/enxame.sh logs --node 1 --lines 300
./scripts/enxame.sh logs --node 2 --lines 300
./scripts/enxame.sh logs --node 3 --lines 300
```

---

## 10) Segurança

- Comunicação autenticada com HMAC (`EXP_SHARED_SECRET`)
- Certificados TLS próprios para ambiente air-gapped
- Proteja:
  - `deploy/secrets/exp_shared_secret`
  - `deploy/certs/*.key`

Não versione segredos e chaves privadas em Git.

---

## Estrutura principal

```text
enxame/
├── agentes/
├── bibliotecario/
├── cli/
├── core/
├── juiz/
├── node1-juiz/
├── node2-bibliotecario/
├── node3-agentes/
├── scripts/
│   ├── bootstrap_ubuntu.sh
│   ├── setup_inicial.sh
│   ├── deploy_3nos.sh
│   ├── enxame.sh
│   └── pull_models.sh
├── deploy/                  # gerado por setup_inicial.sh
└── README.md
```
