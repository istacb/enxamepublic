#!/usr/bin/env python3
"""
ENXAME v3 - Juiz (hub central de comunicação e decisão)

Responsabilidades fixas do Juiz (não mudam com carga/disponibilidade):
  - Único ponto de entrada: chat HTML e qualquer cliente falam só com ele.
  - Servidor de arquivos/dados de gerenciamento e orquestrador de LLMs/rede.
  - Decide QUEM responde (por perfil/domínio), SINTETIZA múltiplas respostas,
    aciona AUDITOR quando só 1 nó respondeu, e ESCALA ao Bibliotecário quando
    um worker offline-only não encontra nada na base local.
  - Em ociosidade (sem pergunta de usuário há um tempo), roda auto-otimização:
    benchmarka os nós ativos, registra em log, e ajusta uma preferência de
    roteamento (não muda modelo/peso de ninguém, só prioridade de escolha) --
    toda mudança é logada e reversível, nunca silenciosa.
"""

import os
import time
import sqlite3
import asyncio
import threading
import httpx
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

ENXAME_DIR = os.path.expanduser("~/enxame")
ENV_PATH = os.path.join(ENXAME_DIR, ".env")
LOG_OTIMIZACOES = os.path.join(ENXAME_DIR, "logs", "juiz_otimizacoes.log")

CONFIG = {
    "IP_DELL": "192.168.1.30", "PORTA": 7700,
    "DB_PATH": os.path.join(ENXAME_DIR, "biblio.db"),
    "IP_BIBLIOTECARIO": "", "BIBLIOTECARIO_PORTA": "7710",
    "OCIOSIDADE_SEGUNDOS": "300",
}
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for linha in f:
            if "=" in linha and not linha.startswith("#"):
                k, v = linha.strip().split("=", 1)
                if k in CONFIG:
                    CONFIG[k] = v
CONFIG["PORTA"] = int(CONFIG["PORTA"])
os.makedirs(os.path.dirname(LOG_OTIMIZACOES), exist_ok=True)

TEMPO_HEARTBEAT_LIMITE = 30  # segundos sem heartbeat = nó considerado offline

# workers[node_id] = {ip, porta, modelo, papel, perfil, score, tem_gpu,
#                      ollama_url, internet_permitida, keywords_dominio,
#                      ultima_vez, catalogo}
workers = {}
ultima_pergunta_em = time.time()
preferencia_roteamento = {}  # node_id -> peso extra aprendido em ociosidade (log tudo)


def log_otimizacao(msg):
    linha = f"{datetime.now().isoformat()} - {msg}"
    print(f"[Juiz][auto-otimização] {msg}")
    with open(LOG_OTIMIZACOES, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def init_db():
    conn = sqlite3.connect(CONFIG["DB_PATH"])
    conn.execute("""CREATE TABLE IF NOT EXISTS zim_docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT,
        source TEXT DEFAULT 'zim', url TEXT, node_location TEXT, zim_file TEXT)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_zim_content ON zim_docs(content)")
    conn.commit()
    conn.close()


def buscar_zim(query, limit=5):
    conn = sqlite3.connect(CONFIG["DB_PATH"])
    cur = conn.execute(
        "SELECT title, content, source, url, node_location FROM zim_docs WHERE content LIKE ? LIMIT ?",
        (f"%{query}%", limit))
    res = [{"title": r[0] or "Sem título", "text": (r[1] or "")[:500],
            "source": r[2], "url": r[3], "node": r[4]} for r in cur.fetchall()]
    conn.close()
    return res


app = FastAPI(title="ENXAME v3 - Juiz")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                    allow_methods=["*"], allow_headers=["*"])


class Pergunta(BaseModel):
    prompt: str


class RegistroWorker(BaseModel):
    node_id: str
    ip: str
    porta: int = 9000
    modelo: str = "?"
    papel: str = "agente"
    perfil: str = "generico"
    score: int = 0
    tem_gpu: int = 0
    ollama_url: str | None = None
    internet_permitida: bool = False
    keywords_dominio: list[str] = []


class CatalogoReport(BaseModel):
    node_id: str
    resumo: dict
    hora: str


# ---------------------------------------------------------------------------
# REGISTRO E ELEIÇÃO DE PAPÉIS
# ---------------------------------------------------------------------------
@app.post("/api/v1/workers/registrar")
def registrar(r: RegistroWorker):
    novo = r.node_id not in workers
    workers[r.node_id] = {
        "ip": r.ip, "porta": r.porta, "modelo": r.modelo, "papel": r.papel,
        "perfil": r.perfil, "score": r.score, "tem_gpu": r.tem_gpu,
        "ollama_url": r.ollama_url, "internet_permitida": r.internet_permitida,
        "keywords_dominio": r.keywords_dominio, "ultima_vez": time.time(),
        "catalogo": workers.get(r.node_id, {}).get("catalogo", {}),
    }
    if novo:
        print(f"[Juiz] Novo nó registrado: {r.node_id} (perfil={r.perfil}, papel={r.papel}, score={r.score})")
    return {"ok": True, "papel_atribuido": workers[r.node_id]["papel"], "total_workers": len(workers)}


def nodos_ativos():
    agora = time.time()
    return {nid: w for nid, w in workers.items() if agora - w["ultima_vez"] < TEMPO_HEARTBEAT_LIMITE}


@app.get("/api/v1/workers")
def listar():
    return {"workers": nodos_ativos(), "total": len(nodos_ativos())}


@app.post("/api/v1/catalogo")
def receber_catalogo(c: CatalogoReport):
    if c.node_id in workers:
        workers[c.node_id]["catalogo"] = c.resumo
    print(f"[Juiz] Catálogo atualizado de {c.node_id}: {c.resumo}")
    return {"ok": True}


# ---------------------------------------------------------------------------
# ROTEAMENTO POR DOMÍNIO (perfil), SÍNTESE, AUDITORIA, ESCALADA
# ---------------------------------------------------------------------------
def escolher_por_dominio(prompt, ativos):
    """Usa as keywords_dominio que cada nó reportou (vindas do perfil .json)
    para decidir se a pergunta bate com algum worker especializado."""
    p = prompt.lower()
    candidatos_por_match = []
    for nid, w in ativos.items():
        kws = w.get("keywords_dominio") or []
        acertos = sum(1 for k in kws if k in p)
        if acertos > 0:
            candidatos_por_match.append((acertos, nid, w))
    if not candidatos_por_match:
        return None
    candidatos_por_match.sort(key=lambda t: t[0], reverse=True)
    _, nid, w = candidatos_por_match[0]
    return nid, w


async def chamar_worker(prompt, node_id, w, timeout=150):
    ip, porta = w["ip"], w["porta"]
    modelo = w.get("modelo", "qwen2.5:1.5b")
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(f"http://{ip}:{porta}/gerar",
                                      json={"prompt": prompt, "modelo": modelo, "ollama_url": w.get("ollama_url")})
            dados = resp.json()
            return {"node": node_id, "resposta": dados.get("response", ""), "ok": True}
        except Exception as e:
            return {"node": node_id, "erro": str(e), "ok": False}


async def escalar_para_bibliotecario(prompt):
    """Chamado quando um worker offline-only responde NAO_ENCONTRADO_LOCAL.
    Só o Bibliotecário tem internet liberada pra este tipo de fallback."""
    ip = CONFIG["IP_BIBLIOTECARIO"]
    if not ip:
        biblios = [w for w in nodos_ativos().values() if w["papel"] == "bibliotecario"]
        if not biblios:
            return None
        ip, porta = biblios[0]["ip"], biblios[0]["porta"]
    else:
        porta = CONFIG["BIBLIOTECARIO_PORTA"]
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"http://{ip}:{porta}/api/v1/pesquisar_geral", json={"prompt": prompt})
            return resp.json().get("resposta")
    except Exception as e:
        print(f"[Juiz] Escalada ao Bibliotecário falhou: {e}")
        return None


async def auditar_resposta(resposta, prompt, node_auditor, w_auditor):
    pedido = (f"Revise a resposta abaixo para a pergunta do usuário. "
              f"Se estiver correta e completa, responda exatamente a mesma resposta. "
              f"Se tiver erro óbvio, corrija de forma breve.\n\n"
              f"Pergunta: {prompt}\nResposta a revisar: {resposta}")
    resultado = await chamar_worker(pedido, node_auditor, w_auditor)
    if resultado["ok"] and resultado["resposta"].strip():
        return resultado["resposta"], True
    return resposta, False


def sintetizar(respostas_ok):
    if len(respostas_ok) == 1:
        return respostas_ok[0]["resposta"], [respostas_ok[0]["node"]]
    respostas_ok.sort(key=lambda r: len(r["resposta"]), reverse=True)
    melhor = respostas_ok[0]
    fontes = [r["node"] for r in respostas_ok]
    return melhor["resposta"], fontes


@app.post("/api/v1/perguntar")
async def perguntar(p: Pergunta):
    global ultima_pergunta_em
    ultima_pergunta_em = time.time()

    prompt = p.prompt
    ativos = nodos_ativos()
    if not ativos:
        return {"erro": "Nenhum nó online no enxame."}

    print(f"[Juiz] Pergunta: {prompt[:80]}...")

    ctx = buscar_zim(prompt)
    prompt_final = prompt
    if ctx:
        ctx_txt = "\n".join(f"- {c['title']}: {c['text'][:200]}" for c in ctx[:3])
        prompt_final = f"Contexto da biblioteca offline:\n{ctx_txt}\n\nPergunta: {prompt}\nResponda em português do Brasil."
    else:
        prompt_final = f"{prompt}\nResponda em português do Brasil."

    # 1) Tenta achar um especialista por domínio (perfil.keywords_dominio)
    escolhido = escolher_por_dominio(prompt, ativos)
    if escolhido:
        nid, w = escolhido
        resultado = await chamar_worker(prompt_final, nid, w)
        resposta = resultado.get("resposta", "") if resultado["ok"] else ""

        if resposta == "NAO_ENCONTRADO_LOCAL":
            resposta_biblio = await escalar_para_bibliotecario(prompt)
            if resposta_biblio:
                return {"resposta": resposta_biblio, "worker": nid, "escalado_para": "bibliotecario",
                        "fonte_zim": bool(ctx)}
            return {"erro": f"{nid} não encontrou na base local e o Bibliotecário não respondeu."}

        if resultado["ok"] and resposta.strip():
            restantes = [(n, w2) for n, w2 in ativos.items() if n != nid]
            if restantes:
                nid_aud, w_aud = restantes[0]
                resposta, revisado = await auditar_resposta(resposta, prompt, nid_aud, w_aud)
                return {"resposta": resposta, "worker": nid, "auditado_por": nid_aud if revisado else None,
                        "fonte_zim": bool(ctx)}
            return {"resposta": resposta, "worker": nid, "fonte_zim": bool(ctx)}
        # falhou -> cai para o fluxo genérico abaixo

    # 2) Sem domínio claro: pool genérico (agente + artista_ajudante), com
    #    leve preferência aprendida em ociosidade (preferencia_roteamento)
    candidatos = [(nid, w) for nid, w in ativos.items() if w["papel"] in ("agente", "artista_ajudante")]
    if not candidatos:
        candidatos = list(ativos.items())

    def score_efetivo(item):
        nid, w = item
        return w["score"] + preferencia_roteamento.get(nid, 0)

    if len(prompt) < 80 and len(candidatos) > 1:
        candidatos.sort(key=score_efetivo, reverse=True)
        tarefas = [chamar_worker(prompt_final, nid, w) for nid, w in candidatos[:3]]
        resultados = await asyncio.gather(*tarefas)
        respostas_ok = [r for r in resultados if r["ok"] and r["resposta"].strip() and r["resposta"] != "NAO_ENCONTRADO_LOCAL"]

        if len(respostas_ok) >= 2:
            resposta_final, fontes = sintetizar(respostas_ok)
            return {"resposta": resposta_final, "sintetizado_de": fontes, "fonte_zim": bool(ctx)}
        elif len(respostas_ok) == 1:
            resposta_final = respostas_ok[0]["resposta"]
            node_usado = respostas_ok[0]["node"]
            restantes = [(nid, w) for nid, w in ativos.items() if nid != node_usado]
            if restantes:
                nid_aud, w_aud = restantes[0]
                resposta_final, revisado = await auditar_resposta(resposta_final, prompt, nid_aud, w_aud)
                return {"resposta": resposta_final, "worker": node_usado,
                        "auditado_por": nid_aud if revisado else None, "fonte_zim": bool(ctx)}
            return {"resposta": resposta_final, "worker": node_usado, "fonte_zim": bool(ctx)}
        else:
            return {"erro": "Todos os nós falharam ao responder."}
    else:
        nid, w = max(candidatos, key=score_efetivo)
        resultado = await chamar_worker(prompt_final, nid, w)
        if not resultado["ok"]:
            return {"erro": f"Falha com {nid}: {resultado.get('erro')}"}
        resposta_final = resultado["resposta"]
        restantes = [(n, w2) for n, w2 in ativos.items() if n != nid]
        if restantes:
            nid_aud, w_aud = restantes[0]
            resposta_final, revisado = await auditar_resposta(resposta_final, prompt, nid_aud, w_aud)
            return {"resposta": resposta_final, "worker": nid, "auditado_por": nid_aud if revisado else None,
                    "fonte_zim": bool(ctx)}
        return {"resposta": resposta_final, "worker": nid, "fonte_zim": bool(ctx)}


@app.get("/api/v1/buscar")
def buscar(query: str = ""):
    if not query:
        return {"erro": "Use ?query=seu+texto"}
    return {"resultados": buscar_zim(query)}


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "workers_ativos": len(nodos_ativos()), "hora": datetime.now().isoformat()}


@app.get("/api/v1/log_otimizacoes")
def ver_log_otimizacoes(linhas: int = 50):
    if not os.path.exists(LOG_OTIMIZACOES):
        return {"log": []}
    with open(LOG_OTIMIZACOES, encoding="utf-8") as f:
        todas = f.readlines()
    return {"log": [l.strip() for l in todas[-linhas:]]}


@app.get("/")
def raiz():
    return {"status": "ENXAME v3 - Juiz online", "hora": datetime.now().isoformat(),
            "workers": len(nodos_ativos()), "ip": CONFIG["IP_DELL"]}


# ---------------------------------------------------------------------------
# AUTO-OTIMIZAÇÃO EM OCIOSIDADE
# Regra de honestidade: isso NÃO treina nem muda pesos de nenhum modelo.
# É só benchmark contínuo (latência/sucesso) virando uma preferência leve de
# roteamento (empate é resolvido a favor de quem historicamente respondeu
# mais rápido/mais estável) -- toda mudança fica no log, é sempre revertível
# apagando o log e reiniciando o Juiz.
# ---------------------------------------------------------------------------
PROMPT_BENCHMARK = "Responda apenas 'ok' para confirmar que está funcionando."


def loop_auto_otimizacao():
    limite_ociosidade = int(CONFIG["OCIOSIDADE_SEGUNDOS"])
    while True:
        time.sleep(60)
        ocioso_ha = time.time() - ultima_pergunta_em
        if ocioso_ha < limite_ociosidade:
            continue
        ativos = nodos_ativos()
        if len(ativos) < 2:
            continue
        try:
            asyncio.run(_rodar_benchmark(ativos))
        except Exception as e:
            log_otimizacao(f"Benchmark falhou: {e}")


async def _rodar_benchmark(ativos):
    resultados = {}
    for nid, w in ativos.items():
        inicio = time.time()
        r = await chamar_worker(PROMPT_BENCHMARK, nid, w, timeout=30)
        duracao = time.time() - inicio
        resultados[nid] = {"ok": r["ok"], "duracao_s": round(duracao, 2)}

    # Ajuste leve: quem respondeu rápido e com sucesso ganha +1 de preferência,
    # quem falhou ou foi muito lento perde 1 (limitado a +-5 pra não dominar
    # o score real de hardware)
    mudou = False
    for nid, r in resultados.items():
        atual = preferencia_roteamento.get(nid, 0)
        if r["ok"] and r["duracao_s"] < 5:
            novo = min(5, atual + 1)
        elif not r["ok"] or r["duracao_s"] > 20:
            novo = max(-5, atual - 1)
        else:
            novo = atual
        if novo != atual:
            preferencia_roteamento[nid] = novo
            mudou = True

    if mudou:
        log_otimizacao(f"Preferência de roteamento ajustada: {preferencia_roteamento} "
                        f"(benchmark: {resultados})")
    else:
        log_otimizacao(f"Benchmark de ociosidade rodado, sem mudança de preferência. ({resultados})")


if __name__ == "__main__":
    print("=" * 60)
    print("  ENXAME v3 - Juiz (hub central)")
    print(f"  Acesse: http://{CONFIG['IP_DELL']}:{CONFIG['PORTA']}")
    print(f"  Chat HTML: abra enxame_chat.html de qualquer PC da rede")
    print("=" * 60)
    init_db()
    threading.Thread(target=loop_auto_otimizacao, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=CONFIG["PORTA"])
