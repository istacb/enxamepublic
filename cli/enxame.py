from __future__ import annotations

import json
import os

import httpx
import typer
from rich import print

from core.exp.http import build_auth_headers
from core.exp.security import EXPSecurity

app = typer.Typer(help="CLI do ENXAME (interage somente com o Juiz)")

JUIZ_URL = os.getenv("ENXAME_JUIZ_URL", "http://localhost:7700")
EXP_SHARED_SECRET = os.getenv("EXP_SHARED_SECRET", "enxame-dev-secret")
security = EXPSecurity(EXP_SHARED_SECRET)


def signed_request(method: str, path: str, payload: dict | None = None) -> httpx.Response:
    if payload is None:
        body = b""
    else:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    headers = build_auth_headers(security, body)
    if payload is not None:
        headers["content-type"] = "application/json"

    with httpx.Client(timeout=120.0) as client:
        return client.request(method, f"{JUIZ_URL}{path}", content=body if payload is not None else None, headers=headers)


@app.command()
def ask(prompt: str = typer.Argument(..., help="Pergunta para o cluster ENXAME")) -> None:
    """Submete uma tarefa ao Juiz."""
    resp = signed_request("POST", "/api/v1/task", {"prompt": prompt})
    if resp.status_code >= 400:
        print(f"[red]Erro[/red]: {resp.status_code} - {resp.text}")
        raise typer.Exit(code=1)
    data = resp.json()
    print(f"[bold green]Task ID:[/bold green] {data['task_id']}")
    print(f"[bold blue]Status:[/bold blue] {data['status']}")
    if data.get("result"):
        print("\n[bold]Resposta final:[/bold]\n")
        print(data["result"])


@app.command()
def status(task_id: str = typer.Argument(..., help="ID da tarefa")) -> None:
    """Consulta status de uma tarefa."""
    resp = signed_request("GET", f"/api/v1/task/{task_id}")
    if resp.status_code >= 400:
        print(f"[red]Erro[/red]: {resp.status_code} - {resp.text}")
        raise typer.Exit(code=1)
    print_json(resp.json())


@app.command()
def cluster() -> None:
    """Mostra estado atual do cluster."""
    resp = signed_request("GET", "/api/v1/cluster")
    if resp.status_code >= 400:
        print(f"[red]Erro[/red]: {resp.status_code} - {resp.text}")
        raise typer.Exit(code=1)
    print_json(resp.json())


@app.command("agents")
def agents_cmd() -> None:
    """Lista agentes registrados no Juiz."""
    resp = signed_request("GET", "/api/v1/agents")
    if resp.status_code >= 400:
        print(f"[red]Erro[/red]: {resp.status_code} - {resp.text}")
        raise typer.Exit(code=1)
    print_json(resp.json())


def print_json(data: dict | list) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
