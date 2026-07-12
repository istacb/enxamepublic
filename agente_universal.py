#!/usr/bin/env python3
"""
ENXAME v3 - agente_universal.py
Roda em Worker Engenharia, Worker Contábil e Artista Mídia (o Juiz e o
Bibliotecário têm serviços próprios: juiz.py e bibliotecario.py).

O comportamento (base de conhecimento, permissão de internet, aviso padrão,
palavras-chave de domínio) vem de core/perfis/<PERFIL>.json -- mesmo binário,
N perfis. Isso é o que mantém o bootstrap simples.
"""

import os
import sys
import json
import time
import threading
import subprocess
import httpx
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

sys.path.insert(0, os.path.dirname(__file__))
from indexador import init_db as init_catalogo, buscar_local

ENXAME_DIR = os.path.expanduser("~/enxame")
ENV_PATH = os.path.join(ENXAME_DIR, ".env")

CONFIG = {
    "IP_JUIZ": "192.168.1.30", "JUIZ_PORTA": "7700",
    "NODE_ID": os.uname().nodename, "PERFIL": "worker_engenharia",
    "MODELO": "qwen2.5:1.5b", "OLLAMA_URL": "http://localhost:11434",
    "PORTA": "9000", "SCORE_HARDWARE": "0", "TEM_GPU": "0",
}
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for linha in f:
            if "=" in linha and not linha.startswith("#"):
                k, v = linha.strip().split("=", 1)
                if k in CONFIG:
                    CONFIG[k] = v

PERFIL_PATH = os.path.join(os.path.dirname(__file__), "perfis", f"{CONFIG['PERFIL']}.json")
with open(PERFIL_PATH, encoding="utf-8") as f:
    PERFIL = json.load(f)

PAPEL_ATUAL = PERFIL.get("papel_base", "agente")
INTERNET_PERMITIDA = bool(PERFIL.get("internet_permitida", False))

app = FastAPI(title=f"ENXAME v3 - {CONFIG['NODE_ID']} ({PERFIL['perfil']})")


class PedidoGeracao(BaseModel):
    prompt: str
    modelo: str | None = None
    ollama_url: str | None = None


@app.get("/")
def raiz():
    return {
        "node_id": CONFIG["NODE_ID"], "perfil": PERFIL["perfil"], "papel": PAPEL_ATUAL,
        "modelo": CONFIG["MODELO"], "internet_permitida": INTERNET_PERMITIDA,
        "descricao": PERFIL.get("descricao", ""),
    }


@app.post("/gerar")
async def gerar(p: PedidoGeracao):
    modelo = p.modelo or CONFIG["MODELO"]
    ollama_url = p.ollama_url or CONFIG["OLLAMA_URL"]

    # 1) OFFLINE-FIRST: catálogo local (já restrito à base_conhecimento_dir do perfil)
    conn = init_catalogo()
    achados = buscar_local(conn, p.prompt[:40])
    conn.close()

    if not achados and not INTERNET_PERMITIDA:
        # Nada local e este perfil não pode buscar na internet -> escala pro Juiz
        return {
            "response": "NAO_ENCONTRADO_LOCAL",
            "node_id": CONFIG["NODE_ID"], "perfil": PERFIL["perfil"],
            "usou_contexto_local": False,
        }

    contexto_local = ""
    if achados:
        contexto_local = ("Arquivos locais relevantes encontrados:\n" +
                           "\n".join(f"- {a['titulo']} ({a['tipo']})" for a in achados[:3]) + "\n\n")

    prompt_completo = f"Você é um especialista em: {PERFIL.get('descricao', '')}\n\n{contexto_local}{p.prompt}"

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(f"{ollama_url}/api/generate",
                                      json={"model": modelo, "prompt": prompt_completo, "stream": False})
            dados = resp.json()
            texto = dados.get("response", "").strip()

            aviso = PERFIL.get("aviso_padrao")
            if aviso:
                texto = f"{texto}\n\n[Aviso] {aviso}"

            return {"response": texto, "node_id": CONFIG["NODE_ID"], "perfil": PERFIL["perfil"],
                    "papel": PAPEL_ATUAL, "usou_contexto_local": bool(achados)}
    except Exception as e:
        return {"response": "", "erro": str(e), "node_id": CONFIG["NODE_ID"]}


@app.post("/papel")
def definir_papel(novo_papel: dict):
    global PAPEL_ATUAL
    PAPEL_ATUAL = novo_papel.get("papel", PAPEL_ATUAL)
    print(f"[Agente {PERFIL['perfil']}] Papel atualizado pelo Juiz: {PAPEL_ATUAL}")
    return {"ok": True, "papel": PAPEL_ATUAL}


# ---------------------------------------------------------------------------
# HEARTBEAT + INDEXAÇÃO EM BACKGROUND
# ---------------------------------------------------------------------------
def loop_heartbeat():
    global PAPEL_ATUAL
    url = f"http://{CONFIG['IP_JUIZ']}:{CONFIG['JUIZ_PORTA']}/api/v1/workers/registrar"
    while True:
        try:
            resp = httpx.post(url, json={
                "node_id": CONFIG["NODE_ID"], "ip": _meu_ip(), "porta": int(CONFIG["PORTA"]),
                "modelo": CONFIG["MODELO"], "papel": PAPEL_ATUAL, "perfil": PERFIL["perfil"],
                "score": int(CONFIG["SCORE_HARDWARE"]), "tem_gpu": int(CONFIG["TEM_GPU"]),
                "ollama_url": CONFIG["OLLAMA_URL"], "internet_permitida": INTERNET_PERMITIDA,
                "keywords_dominio": PERFIL.get("keywords_dominio", []),
            }, timeout=10)
            dados = resp.json()
            papel_do_juiz = dados.get("papel_atribuido")
            if papel_do_juiz and papel_do_juiz != PAPEL_ATUAL:
                PAPEL_ATUAL = papel_do_juiz
                print(f"[Agente {PERFIL['perfil']}] Juiz reatribuiu papel: {PAPEL_ATUAL}")
        except Exception as e:
            print(f"[Agente {PERFIL['perfil']}] Heartbeat falhou: {e}")
        time.sleep(15)


def loop_indexacao():
    while True:
        try:
            subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "indexador.py"), "--once"],
                            timeout=120)
        except Exception as e:
            print(f"[Agente {PERFIL['perfil']}] Indexação falhou: {e}")
        script_sync = os.path.join(ENXAME_DIR, "sync_arquivos.sh")
        if os.path.exists(script_sync):
            try:
                subprocess.run(["bash", script_sync], timeout=600)
            except Exception as e:
                print(f"[Agente {PERFIL['perfil']}] Sync falhou: {e}")
        time.sleep(1800)


def _meu_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((CONFIG["IP_JUIZ"], 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    threading.Thread(target=loop_heartbeat, daemon=True).start()
    threading.Thread(target=loop_indexacao, daemon=True).start()
    print(f"[Agente] {CONFIG['NODE_ID']} online. Perfil: {PERFIL['perfil']}. "
          f"Internet: {INTERNET_PERMITIDA}. Modelo: {CONFIG['MODELO']}")
    uvicorn.run(app, host="0.0.0.0", port=int(CONFIG["PORTA"]))
