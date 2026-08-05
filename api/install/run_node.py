#!/usr/bin/env python3
"""
ENXAME - Ponto de entrada único do node
========================================
[Não verificado] O repositório não contém um comando de start documentado
que de fato funcione: o README menciona `python -m kernel.main`, mas
`kernel/` é um pacote TypeScript (kernel.ts, index.ts) sem package.json no
repositório, então esse comando não executa nada em Python. Este script
substitui isso pelos serviços que realmente existem e rodam em Python:
juiz/app.py e bibliotecario/app.py (FastAPI, servidos via uvicorn) e
agentes/service.py (worker assíncrono, sem porta HTTP própria).

Uso:
    python3 run_node.py --env-file /caminho/para/.env

A função (ENXAME_NODE_ROLE) e a porta (ENXAME_NODE_PORT) são lidas do
arquivo .env criado pelo instalador / por node_role_setup.py.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def run_juiz(port: int) -> None:
    import uvicorn

    uvicorn.run("juiz.app:app", host="0.0.0.0", port=port, log_level="info")


def run_bibliotecario(port: int) -> None:
    import uvicorn

    uvicorn.run("bibliotecario.app:app", host="0.0.0.0", port=port, log_level="info")


def run_agente() -> None:
    from agentes.service import DynamicAgentService

    service = DynamicAgentService()
    asyncio.run(service.run_forever())


def main() -> int:
    parser = argparse.ArgumentParser(description="Inicia o node ENXAME de acordo com a função configurada")
    parser.add_argument("--env-file", required=True)
    args = parser.parse_args()

    env_path = Path(args.env_file)
    load_env_file(env_path)

    role = os.environ.get("ENXAME_NODE_ROLE", "agente")
    port = int(os.environ.get("ENXAME_NODE_PORT", "0") or 0)

    print(f"Iniciando node ENXAME com função: {role}")

    if role == "juiz":
        run_juiz(port or 7700)
    elif role == "bibliotecario":
        run_bibliotecario(port or 7701)
    elif role in {"agente", "auto"}:
        run_agente()
    else:
        print(f"[Erro] Função desconhecida: {role}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
