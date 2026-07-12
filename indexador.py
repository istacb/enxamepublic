#!/usr/bin/env python3
"""
ENXAME v2 - indexador.py
Roda em TODAS as máquinas do enxame (worker ou artista).

O que faz:
  1. Varre DOCS_DIR, ZIM_DIR, PMTILES_DIR, ACERVO_DIR (definidos no .env)
  2. Cataloga cada arquivo (título, tamanho, hash, tipo, caminho local)
  3. Guarda o catálogo em SQLite local (catalogo.db) -> busca offline instantânea
  4. Envia um RESUMO do catálogo (não o conteúdo) para o Juiz, que usa isso
     para saber "quem tem o quê" e decidir particionamento / roteamento.

Formatos entendidos: .zim, .pmtiles, .pdf, .txt, .md, .epub, .csv, .xlsx, .docx
Não indexa instaladores (.exe, .msi, .apk, .AppImage, .dmg) -- esses nunca
devem ocupar espaço de acervo compartilhado.
"""

import os
import sqlite3
import hashlib
import json
import time
import sys
import httpx

ENXAME_DIR = os.path.expanduser("~/enxame")
ENV_PATH = os.path.join(ENXAME_DIR, ".env")

CONFIG = {
    "IP_JUIZ": "192.168.1.30",
    "JUIZ_PORTA": "7700",
    "NODE_ID": os.uname().nodename,
    "DOCS_DIR": os.path.join(ENXAME_DIR, "data/docs"),
    "ZIM_DIR": os.path.join(ENXAME_DIR, "data/zim"),
    "PMTILES_DIR": os.path.join(ENXAME_DIR, "data/pmtiles"),
    "ACERVO_DIR": os.path.join(ENXAME_DIR, "data/acervo"),
}
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for linha in f:
            if "=" in linha and not linha.startswith("#"):
                k, v = linha.strip().split("=", 1)
                if k in CONFIG:
                    CONFIG[k] = v

DB_PATH = os.path.join(ENXAME_DIR, "catalogo.db")

EXTENSOES_VALIDAS = {".zim", ".pmtiles", ".pdf", ".txt", ".md", ".epub",
                     ".csv", ".xlsx", ".docx", ".jpg", ".jpeg", ".png", ".mp3", ".flac"}
EXTENSOES_BLOQUEADAS = {".exe", ".msi", ".apk", ".appimage", ".dmg", ".deb", ".rpm", ".iso"}


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS catalogo (
            caminho TEXT PRIMARY KEY,
            titulo TEXT,
            tipo TEXT,
            tamanho INTEGER,
            hash TEXT,
            node_id TEXT,
            indexado_em TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_titulo ON catalogo(titulo)")
    conn.commit()
    return conn


def hash_rapido(caminho, tamanho):
    """Hash barato: nome + tamanho + mtime (evita reler arquivos gigantes de zim/pmtiles)."""
    stat = os.stat(caminho)
    base = f"{caminho}:{tamanho}:{stat.st_mtime}"
    return hashlib.sha1(base.encode()).hexdigest()[:16]


def classificar(ext):
    if ext == ".zim":
        return "zim"
    if ext == ".pmtiles":
        return "pmtiles"
    if ext in {".jpg", ".jpeg", ".png"}:
        return "imagem"
    if ext in {".mp3", ".flac"}:
        return "musica"
    return "documento"


def varrer_diretorio(conn, diretorio, node_id):
    if not os.path.isdir(diretorio):
        return 0
    novos = 0
    for raiz, _, arquivos in os.walk(diretorio):
        for nome in arquivos:
            ext = os.path.splitext(nome)[1].lower()
            if ext in EXTENSOES_BLOQUEADAS:
                continue  # nunca indexa instaladores
            if ext not in EXTENSOES_VALIDAS:
                continue
            caminho = os.path.join(raiz, nome)
            try:
                tamanho = os.path.getsize(caminho)
            except OSError:
                continue
            h = hash_rapido(caminho, tamanho)
            titulo = os.path.splitext(nome)[0].replace("_", " ").replace("-", " ")
            conn.execute("""
                INSERT INTO catalogo (caminho, titulo, tipo, tamanho, hash, node_id, indexado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(caminho) DO UPDATE SET hash=excluded.hash, indexado_em=excluded.indexado_em
            """, (caminho, titulo, classificar(ext), tamanho, h, node_id, time.strftime("%Y-%m-%dT%H:%M:%S")))
            novos += 1
    conn.commit()
    return novos


def buscar_local(conn, termo, limite=10):
    """Busca offline instantânea no catálogo local (usada pelo agente antes de qualquer rede)."""
    cur = conn.execute(
        "SELECT titulo, tipo, caminho, tamanho FROM catalogo WHERE titulo LIKE ? LIMIT ?",
        (f"%{termo}%", limite)
    )
    return [{"titulo": r[0], "tipo": r[1], "caminho": r[2], "tamanho": r[3]} for r in cur.fetchall()]


def reportar_ao_juiz(conn, node_id):
    """Envia só o RESUMO (contagens por tipo) ao Juiz -- não o conteúdo."""
    cur = conn.execute("SELECT tipo, COUNT(*), SUM(tamanho) FROM catalogo GROUP BY tipo")
    resumo = {tipo: {"qtd": qtd, "bytes": total or 0} for tipo, qtd, total in cur.fetchall()}
    payload = {"node_id": node_id, "resumo": resumo, "hora": time.strftime("%Y-%m-%dT%H:%M:%S")}
    url = f"http://{CONFIG['IP_JUIZ']}:{CONFIG['JUIZ_PORTA']}/api/v1/catalogo"
    try:
        httpx.post(url, json=payload, timeout=10)
        print(f"[Indexador] Catálogo reportado ao Juiz: {resumo}")
    except Exception as e:
        print(f"[Indexador] Não consegui reportar ao Juiz ({e}). Catálogo local segue válido.")


def rodar_uma_vez():
    conn = init_db()
    node_id = CONFIG["NODE_ID"]
    total = 0
    for chave in ("DOCS_DIR", "ZIM_DIR", "PMTILES_DIR", "ACERVO_DIR"):
        total += varrer_diretorio(conn, CONFIG[chave], node_id)
    print(f"[Indexador] {total} arquivos catalogados/atualizados em {node_id}.")
    reportar_ao_juiz(conn, node_id)
    conn.close()


if __name__ == "__main__":
    if "--once" in sys.argv:
        rodar_uma_vez()
    elif "--buscar" in sys.argv:
        termo = sys.argv[sys.argv.index("--buscar") + 1]
        conn = init_db()
        for r in buscar_local(conn, termo):
            print(r)
    else:
        print("Uso: indexador.py --once | --buscar <termo>")
        print("Rodando indexação contínua a cada 10 minutos...")
        while True:
            rodar_uma_vez()
            time.sleep(600)
