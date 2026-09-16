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
from .capabilities.discovery import discover_capabilities
from .capabilities.selector import recommend_model, get_model_recommendations_table, calculate_min_requirements


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
        use_emoji = sys.stdout.encoding and 'utf' in sys.stdout.encoding.lower()
        ok = "✅" if use_emoji else "[OK]"
        print(f"\n{ok} Abelha {config.node_id} ONLINE")
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
    """Descobre peers via mDNS e capacidades completas."""
    from .discovery import BeeDiscoveryService
    from .capabilities.discovery import discover_capabilities

    # Descobrir capacidades locais primeiro
    caps = await discover_capabilities(
        enxame_data_path=str(config.data_dir),
        ollama_base_url=config.ollama_base_url,
    )

    peers_found = []

    def on_found(peer):
        peers_found.append(peer)
        caps_str = ", ".join(peer.capabilities[:5]) + ("..." if len(peer.capabilities) > 5 else "")
        models_str = ", ".join(peer.models[:3]) + ("..." if len(peer.models) > 3 else "")
        print(f"  🐝 {peer.node_id} ({peer.role}) - {peer.host}:{peer.port}")
        print(f"     Caps: {caps_str}")
        print(f"     Models: {models_str}")
        print(f"     Load: {peer.load:.2f}, State: {peer.state.value}")

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

    # Mostrar capacidades locais descobertas
    if caps:
        print(f"\n📊 Capacidades locais descobertas:")
        hw = caps.hardware
        print(f"  OS: {hw.os} {hw.os_version} ({hw.architecture})")
        print(f"  CPU: {hw.cpu_cores}C/{hw.cpu_logical}T @ {hw.cpu_freq_ghz:.1f}GHz")
        print(f"  RAM: {hw.ram_total_gb:.1f}GB total, {hw.ram_available_gb:.1f}GB livre")
        print(f"  GPU: {hw.gpu_name or 'Não detectada'} ({hw.gpu_vram_gb:.1f}GB VRAM)")
        print(f"  Disco: {hw.storage_total_gb:.0f}GB total, {hw.storage_free_gb:.0f}GB livre")
        
        if caps.ollama and caps.ollama.available:
            print(f"  Ollama: {caps.ollama.version} em {caps.ollama.base_url}")
            print(f"  Modelos: {', '.join([m.name for m in caps.ollama.models[:5]])}")
            print(f"  Carregados: {', '.join(caps.ollama.loaded_models) or 'Nenhum'}")
        
        print(f"  Capacidades: {', '.join(caps.to_manifesto_dict().get('capabilities', []))}")

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
    """Mostra status da Abelha com capacidades completas."""
    from .librarian import LocalBeeLibrarian
    from .memory import BeeMemory
    from .discovery import BeeDiscoveryService
    from .capabilities.discovery import discover_capabilities

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

    # Descobrir capacidades completas
    caps = await discover_capabilities(
        enxame_data_path=str(config.data_dir),
        ollama_base_url=config.ollama_base_url,
    )

    mem_stats = memory.get_stats()
    lib_stats = librarian.get_stats()
    disc_stats = discovery.get_stats()

    await discovery.stop()
    await librarian.close()
    await memory.close()

    result = {
        "node_id": config.node_id,
        "data_dir": str(config.data_dir),
        "ollama_url": config.ollama_base_url,
        "model": config.model,
        "allow_web": config.allow_web,
        "memory": mem_stats,
        "librarian": lib_stats,
        "discovery": disc_stats,
    }

    # Adicionar capacidades descobertas
    if caps:
        result["capabilities"] = caps.to_manifesto_dict()
        # Adicionar recomendações de modelo
        if caps.ollama and caps.ollama.available:
            hw = caps.hardware
            rec = recommend_model(
                available_models=caps.ollama.models,
                ram_gb=hw.ram_total_gb,
                gpu_vram_gb=hw.gpu_vram_gb,
                has_gpu=hw.gpu_available,
            )
            result["model_recommendation"] = rec

    return result


def cmd_status(args: argparse.Namespace) -> int:
    """Mostra status da Abelha."""
    config = load_config(args)
    status = asyncio.run(_show_status(config))

    print(f"\n🐝 Abelha: {status['node_id']}")
    print(f"📁 Data dir: {status['data_dir']}")
    print(f"🔗 Ollama: {status['ollama_url']}")
    print(f"🤖 Modelo: {status['model']}")
    print(f"🌐 Web fallback: {'Sim' if status['allow_web'] else 'Não'}")

    # Capacidades descobertas (BEE-0003)
    if "capabilities" in status:
        caps = status["capabilities"]
        print(f"\n📊 Capacidades descobertas:")
        hw = caps.get("hardware", {})
        print(f"  OS: {hw.get('os', 'N/A')} ({hw.get('architecture', 'N/A')})")
        print(f"  CPU: {hw.get('cpu_cores', 0)} cores")
        print(f"  RAM: {hw.get('ram_gb', 0)}GB")
        print(f"  GPU: {hw.get('gpu', 'Não detectada')}")
        print(f"  Capabilities: {', '.join(caps.get('capabilities', []))}")
        print(f"  Modelos: {', '.join(caps.get('models', [])) or 'Nenhum'}")
        if "ollama_version" in caps:
            print(f"  Ollama version: {caps['ollama_version']}")

    if "model_recommendation" in status and status["model_recommendation"]:
        print(f"\n💡 Modelo recomendado: {status['model_recommendation']}")

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


def cmd_capabilities(args: argparse.Namespace) -> int:
    """Mostra capacidades do hardware e modelos recomendados."""
    config = load_config(args)
    
    async def _show_caps():
        from .capabilities.discovery import discover_capabilities
        from .capabilities.selector import get_model_recommendations_table, calculate_min_requirements
        
        caps = await discover_capabilities(
            enxame_data_path=str(config.data_dir),
            ollama_base_url=config.ollama_base_url,
        )
        
        if not caps:
            print("Não foi possível descobrir capacidades.")
            return 1
        
        hw = caps.hardware
        print(f"\n🖥️  Hardware:")
        print(f"  OS: {hw.os} {hw.os_version} ({hw.architecture})")
        print(f"  CPU: {hw.cpu_cores} cores físicos, {hw.cpu_logical} lógicos @ {hw.cpu_freq_ghz:.1f}GHz")
        print(f"  RAM: {hw.ram_total_gb:.1f}GB total, {hw.ram_available_gb:.1f}GB livre ({100 - hw.ram_percent:.0f}% livre)" if hasattr(hw, 'ram_percent') else f"  RAM: {hw.ram_total_gb:.1f}GB total, {hw.ram_available_gb:.1f}GB livre")
        print(f"  GPU: {hw.gpu_name or 'Não detectada'}")
        if hw.gpu_available:
            print(f"    VRAM: {hw.gpu_vram_gb:.1f}GB")
        print(f"  Disco: {hw.storage_total_gb:.0f}GB total, {hw.storage_free_gb:.0f}GB livre")
        
        if caps.ollama and caps.ollama.available:
            print(f"\n🦙 Ollama: {caps.ollama.version} em {caps.ollama.base_url}")
            print(f"  Modelos instalados:")
            for m in caps.ollama.models:
                loaded = " ✓" if m.is_loaded else ""
                emb = " (embedding)" if m.is_embedding else ""
                print(f"    - {m.name} [{m.parameter_size}{emb}]{loaded}")
                print(f"      Contexto: {m.context_length} tokens, Quantização: {m.quantization or 'N/A'}")
                if m.recommended_for:
                    print(f"      Recomendado para: {', '.join(m.recommended_for)}")
            if caps.ollama.loaded_models:
                print(f"  Carregados na VRAM: {', '.join(caps.ollama.loaded_models)}")
        else:
            print(f"\n🦙 Ollama: Não disponível")
        
        print(f"\n🔧 Capacidades locais:")
        local = caps.local
        print(f"  Embeddings: {'Sim' if local.embeddings_available else 'Não'} ({local.embeddings_model or 'N/A'})")
        print(f"  OCR: {'Sim' if local.ocr_available else 'Não'}")
        print(f"  RAG: {'Sim' if local.rag_available else 'Não'}")
        print(f"  ZIM: {'Sim' if local.zim_available else 'Não'} ({local.zim_file_count} arquivos)")
        print(f"  Web: {'Sim' if local.web_available else 'Não'}")
        
        print(f"\n📋 Manifesto para peers:")
        manifesto = caps.to_manifesto_dict()
        print(f"  Capabilities: {', '.join(manifesto.get('capabilities', []))}")
        print(f"  Models: {', '.join(manifesto.get('models', [])) or 'Nenhum'}")
        
        # Tabela de recomendações
        print(f"\n📊 Tabela de referência de modelos por hardware:")
        table = get_model_recommendations_table()
        for row in table:
            print(f"  RAM {row['ram']} / GPU {row['gpu_vram']} → {row['recommended']}")
        
        # Requisitos mínimos para modelos instalados
        if caps.ollama and caps.ollama.available:
            print(f"\n📐 Requisitos mínimos por modelo:")
            for m in caps.ollama.models:
                if not m.is_embedding and m.parameter_size != "unknown":
                    req = calculate_min_requirements(m.parameter_size)
                    if req["min_ram_gb"] > 0:
                        status = "✅" if hw.ram_total_gb >= req["min_ram_gb"] else "⚠️"
                        print(f"  {status} {m.name} ({m.parameter_size}): RAM mín {req['min_ram_gb']:.1f}GB, RAM rec {req['recommended_ram_gb']:.1f}GB, VRAM mín {req['min_vram_gb']:.1f}GB")
        
        return 0
    
    return asyncio.run(_show_caps())


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

    # capabilities
    caps_parser = subparsers.add_parser("capabilities", parents=[common], help="Mostra capacidades do hardware e modelos recomendados")

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
        "capabilities": cmd_capabilities,
    }

    cmd_func = commands.get(args.command)
    if not cmd_func:
        parser.print_help()
        return 1

    return cmd_func(args)


if __name__ == "__main__":
    sys.exit(main())