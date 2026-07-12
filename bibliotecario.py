#!/usr/bin/env python3
"""
ENXAME v3 - bibliotecario.py
Serviço próprio do nó Bibliotecário (não usa agente_universal.py porque as
responsabilidades são diferentes: RAG com embeddings, orquestração de várias
bases de conhecimento e movimentação de arquivo autorizada).

Vetor store: SQLite + numpy (busca por similaridade de cosseno em memória).
Evita depender de stack pesada (chromadb/qdrant) pra manter o bootstrap leve;
se o volume de documentos crescer muito, trocar por Qdrant (já existe no
docker-compose.yml do projeto) é o próximo passo natural -- ver README.
"""

import os
import sys
import time
import json
import sqlite3
import threading
import numpy as np
import httpx
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

sys.path.insert(0, os.path.dirname(__file__))
from indexador import init_db as init_catalogo, varrer_diretorio

ENXAME_DIR = os.path.expanduser("~/enxame")
ENV_PATH = os.path.join(ENXAME_DIR, ".env")
MOV_LOG = os.path.join(ENXAME_DIR, "logs", "movimentacoes.log")
RAG_DB = os.path.join(ENXAME_DIR, "rag_embeddings.db")

CONFIG = {
    "NODE_ID": os.uname().nodename, "PORTA": "7710",
    "OLLAMA_URL": "http://localhost:11434", "MODELO_EMBEDDING": "nomic-embed-text",
    "MODELO_GERACAO": "qwen2.5:3b", "ADMIN_TOKEN": "troque-este-token",
    "BASES_CONHECIMENTO": "data/kb_geral,data/kb_engenharia,data/kb_contabil,data/kb_midia",
    "SEARCH_API_URL": "",  # opcional: ex. instância própria de SearXNG. Vazio = sem busca externa automática.
}
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for linha in f:
            if "=" in linha and not linha.startswith("#"):
                k, v = linha.strip().split("=", 1)
                if k in CONFIG:
                    CONFIG[k] = v
os.makedirs(os.path.dirname(MOV_LOG), exist_ok=True)

app = FastAPI(title="ENXAME v3 - Bibliotecário")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                    allow_methods=["*"], allow_headers=["*"])


def log_movimentacao(msg):
    with open(MOV_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")


def init_rag_db():
    conn = sqlite3.connect(RAG_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS embeddings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, base TEXT, caminho TEXT,
        trecho TEXT, vetor BLOB, atualizado_em TEXT)""")
    conn.commit()
    return conn


async def gerar_embedding(texto: str):
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{CONFIG['OLLAMA_URL']}/api/embeddings",
                                  json={"model": CONFIG["MODELO_EMBEDDING"], "prompt": texto})
        dados = resp.json()
        return dados.get("embedding")


def cosine(a, b):
    a, b = np.array(a), np.array(b)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-9
    return float(np.dot(a, b) / denom)


class PerguntaGeral(BaseModel):
    prompt: str


@app.post("/api/v1/pesquisar_geral")
async def pesquisar_geral(p: PerguntaGeral):
    """Chamado pelo Juiz quando um worker offline-only não achou nada na base
    local dele. Aqui SIM podemos ir pra internet (é o papel do Bibliotecário),
    mas primeiro tentamos RAG local combinando todas as bases."""
    conn = init_rag_db()
    cur = conn.execute("SELECT base, caminho, trecho, vetor FROM embeddings")
    linhas = cur.fetchall()
    conn.close()

    contexto = ""
    if linhas:
        emb_pergunta = await gerar_embedding(p.prompt)
        pontuados = []
        for base, caminho, trecho, vetor_blob in linhas:
            vetor = json.loads(vetor_blob)
            pontuados.append((cosine(emb_pergunta, vetor), base, caminho, trecho))
        pontuados.sort(key=lambda t: t[0], reverse=True)
        top = [t for t in pontuados[:4] if t[0] > 0.5]
        if top:
            contexto = "Contexto encontrado nas bases de conhecimento:\n" + \
                "\n".join(f"- ({b}) {c[:200]}" for _, b, _, c in top) + "\n\n"

    fonte = "rag_local" if contexto else "nenhuma_fonte_local"
    if not contexto and CONFIG["SEARCH_API_URL"]:
        contexto, fonte = await _buscar_internet(p.prompt), "internet"

    prompt_final = f"{contexto}Pergunta: {p.prompt}\nResponda em português do Brasil, citando se usou fonte local ou internet."
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{CONFIG['OLLAMA_URL']}/api/generate",
                                      json={"model": CONFIG["MODELO_GERACAO"], "prompt": prompt_final, "stream": False})
            resposta = resp.json().get("response", "").strip()
            return {"resposta": resposta, "fonte": fonte}
    except Exception as e:
        return {"resposta": "", "erro": str(e)}


async def _buscar_internet(prompt: str) -> str:
    """Só roda se SEARCH_API_URL estiver configurada (ex: sua própria instância
    de SearXNG). Não fazemos scraping direto de motores de busca de terceiros
    aqui -- configure um endpoint de busca próprio/autorizado."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(CONFIG["SEARCH_API_URL"], params={"q": prompt})
            return resp.text[:1500]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# ATUALIZAÇÃO CONTÍNUA DO RAG (indexação + embeddings)
# ---------------------------------------------------------------------------
def atualizar_rag_uma_vez():
    conn_cat = init_catalogo()
    conn_rag = init_rag_db()
    bases = [b.strip() for b in CONFIG["BASES_CONHECIMENTO"].split(",")]
    for base in bases:
        caminho_base = os.path.join(ENXAME_DIR, base)
        varrer_diretorio(conn_cat, caminho_base, CONFIG["NODE_ID"])
        if not os.path.isdir(caminho_base):
            continue
        for raiz, _, arquivos in os.walk(caminho_base):
            for nome in arquivos:
                caminho = os.path.join(raiz, nome)
                ja_existe = conn_rag.execute(
                    "SELECT 1 FROM embeddings WHERE caminho=?", (caminho,)).fetchone()
                if ja_existe:
                    continue
                try:
                    with open(caminho, "r", errors="ignore") as f:
                        trecho = f.read(2000)
                except Exception:
                    trecho = nome  # binário (pdf/zim/etc): indexa só o nome por ora
                try:
                    import asyncio
                    vetor = asyncio.run(gerar_embedding(trecho))
                    if vetor:
                        conn_rag.execute(
                            "INSERT INTO embeddings (base, caminho, trecho, vetor, atualizado_em) VALUES (?,?,?,?,?)",
                            (base, caminho, trecho, json.dumps(vetor), time.strftime("%Y-%m-%dT%H:%M:%S")))
                except Exception as e:
                    print(f"[Bibliotecário] Falha ao gerar embedding de {caminho}: {e}")
    conn_rag.commit()
    conn_cat.close()
    conn_rag.close()
    print("[Bibliotecário] RAG atualizado.")


def loop_rag():
    while True:
        try:
            atualizar_rag_uma_vez()
        except Exception as e:
            print(f"[Bibliotecário] Atualização de RAG falhou: {e}")
        time.sleep(1800)


# ---------------------------------------------------------------------------
# MOVIMENTAÇÃO DE ARQUIVO -- SÓ COM AUTORIZAÇÃO DO ADMIN
# ---------------------------------------------------------------------------
class PedidoMovimentacao(BaseModel):
    origem: str
    destino: str
    admin_token: str
    solicitante: str = "desconhecido"


@app.post("/api/v1/mover_arquivo")
def mover_arquivo(p: PedidoMovimentacao):
    if p.admin_token != CONFIG["ADMIN_TOKEN"]:
        log_movimentacao(f"NEGADO - token inválido - solicitante={p.solicitante} origem={p.origem} destino={p.destino}")
        return {"ok": False, "erro": "Token de admin inválido. Movimentação recusada."}

    if not os.path.exists(p.origem):
        return {"ok": False, "erro": f"Origem não existe: {p.origem}"}

    os.makedirs(os.path.dirname(p.destino), exist_ok=True)
    try:
        os.replace(p.origem, p.destino)
        log_movimentacao(f"OK - solicitante={p.solicitante} origem={p.origem} destino={p.destino}")
        return {"ok": True}
    except Exception as e:
        log_movimentacao(f"ERRO - solicitante={p.solicitante} origem={p.origem} destino={p.destino} erro={e}")
        return {"ok": False, "erro": str(e)}


@app.get("/api/v1/movimentacoes")
def ver_movimentacoes(linhas: int = 50):
    if not os.path.exists(MOV_LOG):
        return {"log": []}
    with open(MOV_LOG, encoding="utf-8") as f:
        todas = f.readlines()
    return {"log": [l.strip() for l in todas[-linhas:]]}


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "hora": datetime.now().isoformat()}


@app.get("/")
def raiz():
    return {"status": "ENXAME v3 - Bibliotecário online", "node_id": CONFIG["NODE_ID"]}


if __name__ == "__main__":
    threading.Thread(target=loop_rag, daemon=True).start()
    print(f"[Bibliotecário] {CONFIG['NODE_ID']} online na porta {CONFIG['PORTA']}")
    uvicorn.run(app, host="0.0.0.0", port=int(CONFIG["PORTA"]))
