#!/usr/bin/env python3
"""
bee CLI — Interface de Linha de Comando da Abelha
=================================================
Comandos:
  bee start       - Inicia a Abelha
  bee query       - Faz uma query local
  bee discover    - Descobre peers na rede
  bee status      - Mostra status da Abelha
  bee identity    - Gerencia identidade
  bee config      - Gerencia configuração
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .config import BeeConfig, load_config, generate_identity, load_identity, get_default_data_dir
from .service import BeeService


def cmd_start(args: argparse.Namespace) -> int:
    """Inicia a Abelha."""
    config = load_config(args)
    print(f"Iniciando Abelha {config.node_id}...")
    print(f"  Data dir: {config.data_dir}")
    print(f"  Host: {config.host}:{config.port}")
    print(f"  Ollama: {config.ollama_base_url}")
    print(f"  Modelo: {config.model}")
    print(f"  Web fallback: {'Sim' if config.allow_web else 'Não'}")

    bee = BeeService(config)

    loop = asyncio.get_event_loop()
    for sig in ("SIGTERM", "SIGINT"):
        try:
            loop.add_signal_handler(getattr(__import__("signal"), sig), lambda: asyncio.create_task(bee.stop()))
        except NotImplementedError:
            pass  # Windows

    try:
        loop.run_until_complete(bee.start())
        print(f"\n✅ Abelha {config.node_id} ONLINE")
        print("Pressione Ctrl+C para parar\n")
        loop.run_forever()
    except KeyboardInterrupt:
        print("\nParando...")
    finally:
        loop.run_until_complete(bee.stop())
        print("Abelha parada.")

    return 0


async def _run_query(config: BeeConfig, query: str) -> dict:
    """Executa query usando serviço local (sem iniciar servidor completo)."""
    from .librarian import LocalBeeLibrarian
    from .memory import BeeMemory

    memory = BeeMemory(config.data_dir / "memory.db")
    await memory.initialize()

    librarian = LocalBeeLibrarian(
        data_dir=config.data_dir,
        ollama_url=config.ollama_base_url,
        model=config.model,
        memory=memory,
    )
    await librarian.initialize()

    result = await librarian.search(query)

    await librarian.close()
    await memory.close()

    return result


def cmd_query(args: argparse.Namespace) -> int:
    """Executa uma query local."""
    config = load_config(args)

    if not args.query:
        print("Erro: query é obrigatória")
        return 1

    print(f"Query: {args.query}")
    print("Processando...")

    result = asyncio.run(_run_query(config, args.query))

    print(f"\n📝 Resposta ({result.get('source', 'unknown')}, confiança: {result.get('confidence', 0):.2f}):")
    print(result.get("answer", "Sem resposta"))

    if args.verbose:
        print(f"\n📊 Metadados: {json.dumps(result.get('metadata', {}), indent=2, ensure_ascii=False)}")

    return 0


async def _discover_peers(config: BeeConfig) -> list:
    """Descobre peers via mDNS."""
    from .discovery import BeeDiscoveryService

    peers_found = []

    def on_found(peer):
        peers_found.append(peer)
        print(f"  🐝 {peer.node_id} ({peer.role}) - {peer.host}:{peer.port} - caps: {peer.capabilities}")

    discovery = BeeDiscoveryService(
        node_id=config.node_id,
        host=config.host,
        port=config.port,
        capabilities=["rag", "vector_search", "embeddings"],
        models=[],
        on_peer_found=on_found,
    )

    await discovery.start()
    print("Descobrindo peers (10s)...")
    await asyncio.sleep(10)
    await discovery.stop()

    return peers_found


def cmd_discover(args: argparse.Namespace) -> int:
    """Descobre peers na rede."""
    config = load_config(args)
    print(f"Descobrindo peers como {config.node_id}...")

    peers = asyncio.run(_discover_peers(config))

    if not peers:
        print("Nenhum peer encontrado.")
    else:
        print(f"\nTotal: {len(peers)} peer(s)")

    return 0


async def _show_status(config: BeeConfig) -> dict:
    """Mostra status da Abelha."""
    from .librarian import LocalBeeLibrarian
    from .memory import BeeMemory
    from .discovery import BeeDiscoveryService

    memory = BeeMemory(config.data_dir / "memory.db")
    await memory.initialize()

    librarian = LocalBeeLibrarian(
        data_dir=config.data_dir,
        ollama_url=config.ollama_base_url,
        model=config.model,
        memory=memory,
    )
    await librarian.initialize()

    discovery = BeeDiscoveryService(
        node_id=config.node_id,
        host=config.host,
        port=config.port,
        capabilities=["rag", "vector_search", "embeddings"],
        models=[],
    )
    await discovery.start()
    await asyncio.sleep(2)  # Aguardar descoberta

    mem_stats = memory.get_stats()
    lib_stats = librarian.get_stats()
    disc_stats = discovery.get_stats()

    await discovery.stop()
    await librarian.close()
    await memory.close()

    return {
        "node_id": config.node_id,
        "data_dir": str(config.data_dir),
        "ollama_url": config.ollama_base_url,
        "model": config.model,
        "allow_web": config.allow_web,
        "memory": mem_stats,
        "librarian": lib_stats,
        "discovery": disc_stats,
    }


def cmd_status(args: argparse.Namespace) -> int:
    """Mostra status da Abelha."""
    config = load_config(args)
    status = asyncio.run(_show_status(config))

    print(f"\n🐝 Abelha: {status['node_id']}")
    print(f"📁 Data dir: {status['data_dir']}")
    print(f"🔗 Ollama: {status['ollama_url']}")
    print(f"🤖 Modelo: {status['model']}")
    print(f"🌐 Web fallback: {'Sim' if status['allow_web'] else 'Não'}")

    print(f"\n💾 Memória:")
    for k, v in status['memory'].items():
        print(f"  {k}: {v}")

    print(f"\n📚 Bibliotecário:")
    for k, v in status['librarian'].items():
        print(f"  {k}: {v}")

    print(f"\n🔍 Descoberta:")
    print(f"  Peers ativos: {status['discovery']['active_peers']}")
    for peer in status['discovery']['peers']:
        print(f"  - {peer['node_id']} ({peer['host']}:{peer['port']}) - {peer['state']}")

    return 0


def cmd_identity(args: argparse.Namespace) -> int:
    """Gerencia identidade da Abelha."""
    config = load_config(args)

    if args.identity_action == "show":
        identity = load_identity(config.data_dir)
        if identity:
            print(json.dumps(identity, indent=2))
        else:
            print("Nenhuma identidade encontrada.")
    elif args.identity_action == "generate":
        identity = generate_identity(config.data_dir)
        print("Nova identidade gerada:")
        print(json.dumps(identity, indent=2))
    elif args.identity_action == "reset":
        identity_file = config.data_dir / "identity.json"
        if identity_file.exists():
            identity_file.unlink()
        identity = generate_identity(config.data_dir)
        print("Identidade resetada:")
        print(json.dumps(identity, indent=2))

    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Gerencia configuração."""
    config = load_config(args)

    if args.config_action == "show":
        print(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))
    elif args.config_action == "save":
        config.save()
        print(f"Configuração salva em {config.data_dir / 'config.json'}")
    elif args.config_action == "path":
        print(config.data_dir / "config.json")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="bee",
        description="ENXAME Bee - Abelha Standalone",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Global args
    for sub in [subparsers]:
        sub._defaults = {}

    # Argumentos comuns
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", type=Path, help="Diretório de dados")
    common.add_argument("--host", default="0.0.0.0", help="Host de escuta")
    common.add_argument("--port", type=int, default=8765, help="Porta HTTP")
    common.add_argument("--ollama-url", default="http://localhost:11434", help="URL do Ollama")
    common.add_argument("--model", help="Modelo Ollama")
    common.add_argument("--allow-web", action="store_true", help="Permitir fallback web")
    common.add_argument("--shared-secret", help="Segredo compartilhado HMAC")
    common.add_argument("--log-level", default="INFO", help="Nível de log")

    # start
    start_parser = subparsers.add_parser("start", parents=[common], help="Inicia a Abelha")

    # query
    query_parser = subparsers.add_parser("query", parents=[common], help="Executa query local")
    query_parser.add_argument("query", nargs="?", help="Query a executar")
    query_parser.add_argument("-v", "--verbose", action="store_true", help="Saída verbosa")

    # discover
    discover_parser = subparsers.add_parser("discover", parents=[common], help="Descobre peers")

    # status
    status_parser = subparsers.add_parser("status", parents=[common], help="Mostra status")

    # identity
    identity_parser = subparsers.add_parser("identity", parents=[common], help="Gerencia identidade")
    identity_sub = identity_parser.add_subparsers(dest="identity_action", required=True)
    identity_sub.add_parser("show", help="Mostra identidade")
    identity_sub.add_parser("generate", help="Gera nova identidade")
    identity_sub.add_parser("reset", help="Reseta identidade")

    # config
    config_parser = subparsers.add_parser("config", parents=[common], help="Gerencia configuração")
    config_sub = config_parser.add_subparsers(dest="config_action", required=True)
    config_sub.add_parser("show", help="Mostra configuração")
    config_sub.add_parser("save", help="Salva configuração atual")
    config_sub.add_parser("path", help="Mostra caminho do arquivo de config")

    args = parser.parse_args()

    # Setup logging
    import logging
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    commands = {
        "start": cmd_start,
        "query": cmd_query,
        "discover": cmd_discover,
        "status": cmd_status,
        "identity": cmd_identity,
        "config": cmd_config,
    }

    cmd_func = commands.get(args.command)
    if not cmd_func:
        parser.print_help()
        return 1

    return cmd_func(args)


if __name__ == "__main__":
    sys.exit(main())