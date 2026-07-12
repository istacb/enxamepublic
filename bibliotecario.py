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
import re
import time
import json
import sqlite3
import threading
import subprocess
import xml.etree.ElementTree as ET
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
    "IP_JUIZ": "192.168.1.30", "JUIZ_PORTA": "7700",
    "KIWIX_URL": "http://localhost:7001", "CADDY_URL": "http://localhost:7002",
    "SSH_USER": "user", "SSH_PASS": "123",  # usados só pra push autorizado de arquivo pros workers
}
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for linha in f:
            if "=" in linha and not linha.startswith("#"):
                k, v = linha.strip().split("=", 1)
                if k in CONFIG:
                    CONFIG[k] = v
os.makedirs(os.path.dirname(MOV_LOG), exist_ok=True)

# Mapeia perfil de worker -> subpasta de base de conhecimento (mesma
# convenção usada em BASES_CONHECIMENTO e nos perfis .json)
PASTA_POR_PERFIL = {
    "worker_engenharia": "data/kb_engenharia",
    "worker_contabil": "data/kb_contabil",
    "artista_midia": "data/kb_midia",
}

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


# ---------------------------------------------------------------------------
# INTEGRAÇÃO COM KIWIX-SERVE (catálogo + busca full-text real nos .zim)
# Isso é bem mais forte que indexar nome de arquivo: o kiwix-serve já faz
# busca de texto completo dentro dos ZIMs, ao vivo, sem duplicar conteúdo.
# ---------------------------------------------------------------------------
_NS_OPDS = {"atom": "http://www.w3.org/2005/Atom"}


async def listar_livros_kiwix():
    """Lista os .zim que o kiwix-serve está servindo, via catálogo OPDS.
    Devolve [{'nome':..., 'titulo':..., 'descricao':..., 'tags':...}, ...]
    Isso é o ponto de partida da curadoria: ver o que existe antes de decidir
    pra qual worker cada coisa pertence."""
    url = f"{CONFIG['KIWIX_URL']}/catalog/v2/entries"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url)
            raiz = ET.fromstring(resp.text)
            livros = []
            for entry in raiz.findall("atom:entry", _NS_OPDS):
                nome_el = entry.find("atom:name", _NS_OPDS)
                titulo_el = entry.find("atom:title", _NS_OPDS)
                resumo_el = entry.find("atom:summary", _NS_OPDS)
                tags_el = entry.find("atom:tags", _NS_OPDS)
                livros.append({
                    "nome": nome_el.text if nome_el is not None else "",
                    "titulo": titulo_el.text if titulo_el is not None else "",
                    "descricao": (resumo_el.text or "")[:300] if resumo_el is not None else "",
                    "tags": tags_el.text if tags_el is not None else "",
                })
            return livros
    except Exception as e:
        print(f"[Bibliotecário] Não consegui listar catálogo do Kiwix ({e}). Ele está rodando em {CONFIG['KIWIX_URL']}?")
        return []


_RE_RESULTADO = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*class="result-title"[^>]*>(.*?)</a>.*?'
    r'class="result-snippet"[^>]*>(.*?)</p>', re.DOTALL)


def _limpar_html(txt: str) -> str:
    return re.sub(r"<[^>]+>", "", txt or "").strip()


async def buscar_kiwix(query: str, livro: str = None, limite: int = 5):
    """Busca full-text real dentro dos .zim via kiwix-serve.
    Se 'livro' for passado, restringe a busca a esse ZIM específico."""
    params = {"pattern": query, "pageLength": limite}
    if livro:
        params["books.name"] = livro
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{CONFIG['KIWIX_URL']}/search", params=params)
            html = resp.text
            resultados = []
            for m in _RE_RESULTADO.finditer(html):
                link, titulo, trecho = m.groups()
                resultados.append({
                    "titulo": _limpar_html(titulo),
                    "trecho": _limpar_html(trecho),
                    "url": f"{CONFIG['KIWIX_URL']}{link}" if link.startswith("/") else link,
                })
            return resultados[:limite]
    except Exception as e:
        print(f"[Bibliotecário] Busca no Kiwix falhou: {e}")
        return []


@app.get("/api/v1/catalogo_kiwix")
async def catalogo_kiwix():
    """Endpoint pra curadoria: mostra o que existe no Kiwix, pra você decidir
    manualmente o que pertence a cada worker antes de mandar pra lá."""
    return {"livros": await listar_livros_kiwix()}


@app.get("/api/v1/buscar_kiwix")
async def buscar_kiwix_endpoint(query: str, livro: str = None):
    return {"resultados": await buscar_kiwix(query, livro)}


class PerguntaGeral(BaseModel):
    prompt: str


@app.post("/api/v1/pesquisar_geral")
async def pesquisar_geral(p: PerguntaGeral):
    """Chamado pelo Juiz quando um worker offline-only não achou nada na base
    local dele. Ordem de busca, do mais barato/confiável pro mais custoso:
    1) Kiwix (full-text real dentro dos .zim, offline)
    2) RAG local (embeddings sobre arquivos catalogados nas kb_*)
    3) Internet (só se SEARCH_API_URL estiver configurada) -- último recurso.
    """
    contexto = ""
    fonte = "nenhuma_fonte_local"

    resultados_kiwix = await buscar_kiwix(p.prompt, limite=4)
    if resultados_kiwix:
        contexto = "Trechos encontrados na biblioteca offline (Kiwix):\n" + \
            "\n".join(f"- {r['titulo']}: {r['trecho'][:250]}" for r in resultados_kiwix) + "\n\n"
        fonte = "kiwix"

    if not contexto:
        conn = init_rag_db()
        cur = conn.execute("SELECT base, caminho, trecho, vetor FROM embeddings")
        linhas = cur.fetchall()
        conn.close()

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
                fonte = "rag_local"

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


class PedidoMoverParaWorker(BaseModel):
    origem: str            # arquivo ou pasta dentro de ~/enxame/data/kb_* neste nó (Bibliotecário)
    perfil_destino: str    # worker_engenharia | worker_contabil | artista_midia
    admin_token: str
    solicitante: str = "desconhecido"
    reindexar_no_destino: bool = True


@app.post("/api/v1/mover_para_worker")
async def mover_para_worker(p: PedidoMoverParaWorker):
    """Curadoria de verdade: pega algo já organizado localmente pelo
    Bibliotecário (em data/kb_<tema>) e ENVIA (push via rsync/SSH) pra pasta
    correspondente no worker certo, disparando reindexação remota. Só roda
    com admin_token correto -- toda tentativa fica no log de auditoria."""
    if p.admin_token != CONFIG["ADMIN_TOKEN"]:
        log_movimentacao(f"NEGADO (mover_para_worker) - token inválido - solicitante={p.solicitante} "
                          f"origem={p.origem} destino_perfil={p.perfil_destino}")
        return {"ok": False, "erro": "Token de admin inválido. Movimentação recusada."}

    caminho_absoluto = p.origem if os.path.isabs(p.origem) else os.path.join(ENXAME_DIR, p.origem)
    if not os.path.exists(caminho_absoluto):
        return {"ok": False, "erro": f"Origem não existe: {caminho_absoluto}"}

    pasta_destino = PASTA_POR_PERFIL.get(p.perfil_destino)
    if not pasta_destino:
        return {"ok": False, "erro": f"perfil_destino inválido: {p.perfil_destino}"}

    # Descobre o worker ativo desse perfil consultando o Juiz
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"http://{CONFIG['IP_JUIZ']}:{CONFIG['JUIZ_PORTA']}/api/v1/workers")
            workers = resp.json().get("workers", {})
    except Exception as e:
        return {"ok": False, "erro": f"Não consegui consultar o Juiz: {e}"}

    candidatos = [(nid, w) for nid, w in workers.items() if w.get("perfil") == p.perfil_destino]
    if not candidatos:
        return {"ok": False, "erro": f"Nenhum nó ativo com perfil '{p.perfil_destino}' no momento."}
    node_id, w = candidatos[0]
    ip_destino = w["ip"]

    destino_remoto = f"{CONFIG['SSH_USER']}@{ip_destino}:~/enxame/{pasta_destino}/"
    comando_rsync = [
        "sshpass", "-p", CONFIG["SSH_PASS"], "rsync", "-avz",
        "-e", "ssh -o StrictHostKeyChecking=accept-new",
        caminho_absoluto, destino_remoto,
    ]
    try:
        resultado = subprocess.run(comando_rsync, capture_output=True, text=True, timeout=300)
        if resultado.returncode != 0:
            log_movimentacao(f"ERRO (mover_para_worker) - solicitante={p.solicitante} origem={caminho_absoluto} "
                              f"destino={node_id}:{pasta_destino} erro={resultado.stderr[:300]}")
            return {"ok": False, "erro": resultado.stderr[:500]}
    except Exception as e:
        log_movimentacao(f"ERRO (mover_para_worker) - solicitante={p.solicitante} origem={caminho_absoluto} erro={e}")
        return {"ok": False, "erro": str(e)}

    log_movimentacao(f"OK (mover_para_worker) - solicitante={p.solicitante} origem={caminho_absoluto} "
                      f"destino={node_id}:{pasta_destino}")

    reindexado = False
    if p.reindexar_no_destino:
        try:
            cmd_ssh = ["sshpass", "-p", CONFIG["SSH_PASS"], "ssh",
                       "-o", "StrictHostKeyChecking=accept-new",
                       f"{CONFIG['SSH_USER']}@{ip_destino}",
                       "~/enxame/venv/bin/python ~/enxame/indexador.py --once"]
            subprocess.run(cmd_ssh, capture_output=True, text=True, timeout=120)
            reindexado = True
        except Exception as e:
            print(f"[Bibliotecário] Push OK mas reindex remoto falhou: {e}")

    return {"ok": True, "enviado_para": node_id, "pasta": pasta_destino, "reindexado_remotamente": reindexado}


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
