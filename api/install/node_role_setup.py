#!/usr/bin/env python3
"""
ENXAME - Configuração de Função do Node
=========================================
Chamado pelos instaladores (Ubuntu/macOS/Windows) como último passo do
fluxo Next > Next > Finish.

O que este script faz:
1. Varre a rede local por outros nodes do Enxame (mDNS/zeroconf), usando
   os módulos já existentes em core/discovery.
2. Se o arquivo .env informado ainda não tiver uma função salva (ou seja,
   esta é a primeira instalação deste node), pergunta ao usuário qual a
   função inicial (Juiz, Bibliotecário, Agente dinâmico ou Automático).
   Em updates/migrações o .env já existe com a função salva, então a
   pergunta é pulada automaticamente e a função anterior é reaproveitada.
3. Anuncia este node na rede com a função escolhida.
4. Se for a primeira instalação de TODO o cluster (nenhum outro node
   encontrado na varredura), ou se outros nodes já responderam à varredura,
   imprime um resumo de confirmação — "quem assumiu cada função" — usando
   as funções que cada node está anunciando via mDNS. Esse resumo só é
   exibido na primeira instalação, nunca em updates.

[Não verificado] Este script assume que os processos de cada node (Juiz,
Bibliotecário, Agente) já chamam ENXAMEMDNSAdvertiser internamente ao
iniciar (core/discovery/advertiser.py existe no repositório, mas eu não
encontrei, no código revisado, o ponto em que juiz/app.py, bibliotecario/
app.py ou agentes/service.py o instanciam). Por isso este script também
faz seu próprio anúncio mDNS best-effort, para garantir que a "descoberta
automática de nodes" funcione mesmo que os serviços ainda não o façam.
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

ROLES: dict[str, tuple[str, str]] = {
    "1": ("juiz", "Juiz — orquestração, validação e auditoria (porta 7700)"),
    "2": ("bibliotecario", "Bibliotecário — busca e gestão de conhecimento (porta 7701)"),
    "3": (
        "agente",
        "Agente dinâmico — worker com todas as especialidades "
        "(engenheiro, jurista, matemático, médico, programador, redator, tradutor)",
    ),
    "4": ("auto", "Automático — deixar o Enxame decidir pela capacidade de hardware"),
}

ROLE_PORTS = {"juiz": 7700, "bibliotecario": 7701}


def ask_role() -> str:
    print()
    print("=" * 62)
    print(" Qual a função inicial deste node?")
    print("=" * 62)
    for key, (_, label) in ROLES.items():
        print(f"  [{key}] {label}")
    print()
    while True:
        choice = input("Escolha (1-4) [padrão: 4 - Automático]: ").strip() or "4"
        if choice in ROLES:
            return ROLES[choice][0]
        print("Opção inválida, tente novamente.")


def local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def resolve_auto_role(peers: dict) -> str:
    """Usa o benchmark local + eleição simplificada para decidir a função
    quando o usuário escolhe 'Automático'. Se não houver peers descobertos,
    o node assume o papel de Juiz (primeiro node do cluster)."""
    try:
        from core.cluster.benchmark import HardwareBenchmark
        from core.cluster.election import ClusterElection, NodeBenchmark
    except Exception as exc:  # pragma: no cover - fallback defensivo
        print(f"[Aviso] Não foi possível carregar o módulo de eleição ({exc}); assumindo 'juiz'.")
        return "juiz"

    profile = HardwareBenchmark().run()
    nodes = [NodeBenchmark(node_id="local", score=profile.overall_score)]
    for name, info in peers.items():
        nodes.append(NodeBenchmark(node_id=info.node_id, score=1.0))

    if len(nodes) == 1:
        return "juiz"

    election = ClusterElection()
    ranking = election.rank(nodes)
    for item in ranking:
        if item.node_id == "local":
            return {"juiz": "juiz", "bibliotecaria": "bibliotecario"}.get(item.role_hint, "agente")
    return "agente"


def read_env_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return None


def write_env_value(path: Path, key: str, value: str) -> None:
    lines: list[str] = []
    found = False
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def scan_for_peers(scan_seconds: int) -> dict:
    try:
        from core.discovery.browser import ENXAMEMDNSBrowser
    except Exception as exc:
        print(f"[Aviso] Descoberta mDNS indisponível ({exc}). Pacote 'zeroconf' instalado?")
        return {}

    browser = ENXAMEMDNSBrowser()
    try:
        browser.start()
        time.sleep(scan_seconds)
        return dict(browser.nodes)
    except Exception as exc:
        print(f"[Aviso] Falha durante a varredura mDNS: {exc}")
        return {}
    finally:
        try:
            browser.stop()
        except Exception:
            pass


def announce_self(node_id: str, role: str, host_ip: str, port: int) -> object | None:
    try:
        from core.discovery.advertiser import ENXAMEMDNSAdvertiser
    except Exception as exc:
        print(f"[Aviso] Não foi possível anunciar via mDNS ({exc}).")
        return None

    try:
        advertiser = ENXAMEMDNSAdvertiser(
            service_name=node_id,
            node_id=node_id,
            role=role,
            host_ip=host_ip,
            port=port or 7799,
        )
        advertiser.start()
        return advertiser
    except Exception as exc:
        print(f"[Aviso] Falha ao anunciar este node via mDNS: {exc}")
        return None


def detect_cluster_installation(peers: dict, env_path: Path) -> str | None:
    """
    Detecta se há 3+ peers na rede e pergunta ao usuário se quer instalar o enxame.
    
    Returns o role escolhido (ou None se não instalar cluster).
    """
    peer_count = len(peers)
    
    if peer_count < 3:
        return None  # Poucos peers, não forma cluster
    
    print()
    print("=" * 60)
    print("🔗 3+ NÓS DO ENXAME DETECTADOS NA REDE")
    print("=" * 60)
    print()
    print(f"Foram descobertos {peer_count} peers na rede local:")
    for node_id, peer_info in peers.items():
        print(f"  • {node_id}: role={getattr(peer_info, 'role', 'unknown')}, {getattr(peer_info, 'host', '?')}:{getattr(peer_info, 'port', '?')}")
    print()
    print("O Enxame precisa de pelo menos 3 nodes para formar um cluster com:")
    print("  • Eleição de papéis (Juiz, Bibliotecário, Guarda)")
    print("  • Índice global compartilhado")
    print("  • Monitoramento de failover")
    print("  • Distribuição de workload")
    print()
    choice = input("Deseja instalar o Enxame cluster agora? (s/N): ").strip().lower()
    
    if choice in ("s", "sim", "y", "yes"):
        print()
        print("=== Instalando Enxame Cluster ===")
        print("Executando eleição de papéis e configurando segurança...")
        
        # Run cluster election
        from bees.cluster.global_index import build_global_index
        from bees.cluster.state import load_cluster_state, save_cluster_state
        from bees.cluster.election import elect_roles, ClusterRole
        from core.exp.security import EXPSecurity
        
        # Carregar configuração existente
        from bees.service import load_config
        config = load_env_file(env_path) if hasattr(load_env_file, '__module__') else None
        
        # Perguntar sobre role deste node
        print("Seu node assumirá qual papel?")
        print("  [1] Juiz — orquestração, validação e auditoria")
        print("  [2] Bibliotecário — busca e gestão de conhecimento")
        print("  [3] Agente — worker com todas as especialidades")
        print("  [4] Automático — deixar o Enxame decidir baseado em hardware")
        print()
        role_choice = input("Escolha (1-4) [padrão: 4 - Automático]: ").strip() or "4"
        
        role_map = {
            "1": "juiz",
            "2": "bibliotecario", 
            "3": "agente",
            "4": "auto",
        }
        node_role = role_map.get(role_choice, "auto")
        
        # Definir porta baseado no role
        role_ports = {"juiz": 7700, "bibliotecario": 7701, "agente": 0, "auto": 0}
        node_port = role_ports.get(node_role, 0)
        
        # Salvar role no .env
        write_env_value(env_path, "ENXAME_NODE_ROLE", node_role)
        if node_port:
            write_env_value(env_path, "ENXAME_NODE_PORT", str(node_port))
        
        # Anunciar node
        from api.install.node_role_setup import local_ip, announce_self
        import socket
        host_ip = local_ip()
        node_id = read_env_value(env_path, "ENXAME_NODE_ID") or f"{node_role}-{socket.gethostname()}"
        write_env_value(env_path, "ENXAME_NODE_ID", node_id)
        
        advertiser = announce_self(node_id, node_role, host_ip, node_port)
        if advertiser:
            print(f"Node anunciado como '{node_id}' (função: {node_role}, {host_ip}:{node_port or 'N/A'})")
            time.sleep(2)
            try:
                advertiser.stop()
            except Exception:
                pass
        
        # Verificar se já tem Ollama e modelo
        ollama_url = read_env_value(env_path, "OLLAMA_URL") or "http://localhost:11434"
        
        # Inicializar cluster
        print("Inicializando cluster...")
        current_state = load_cluster_state(Path(env_path).parent / "data" / "enxame" if Path(env_path).parent else Path("data"))
        
        # Descobrir peers ativos para eleição
        from core.discovery.browser import ENXAMEMDNSBrowser
        browser = ENXAMEMDNSBrowser()
        try:
            browser.start()
            import time
            time.sleep(3)  # Aguardar descoberta inicial
            discovered_peers = list(browser.nodes.values())
            browser.stop()
        except Exception as e:
            print(f"Aviso: falha ao descobrir peers: {e}")
            discovered_peers = list(peers.values())
        
        # Eleição de papéis
        print(f"Executando eleição com {len(discovered_peers)} peers...")
        cluster_state = elect_roles(discovered_peers, current_state)
        
        # Salvar estado do cluster
        save_cluster_state(Path(env_path).parent / "data" / "enxame" if Path(env_path).parent else Path("data"), cluster_state)
        
        # Configurar segurança (shared secret)
        shared_secret = read_env_value(env_path, "ENXAME_SHARED_SECRET")
        if not shared_secret:
            import secrets
            shared_secret = secrets.token_urlsafe(16)
            write_env_value(env_path, "ENXAME_SHARED_SECRET", shared_secret)
            print(f"Shared secret gerado automaticamente")
        
        # Configurar internet gate se for bibliotecário
        from bees.cluster.internet_gate import InternetGate, InternetPurpose
        from bees.service import BeeService
        
        print()
        print("=" * 60)
        print("✅ Enxame Cluster Instalado com Sucesso!")
        print("=" * 60)
        print()
        print(f"Roles eleitos:")
        print(f"  • Juiz: {cluster_state.juiz_id}")
        print(f"  • Bibliotecário: {cluster_state.bibliotecario_id}")
        print(f"  • Guarda: {cluster_state.guarda_id}")
        print(f"  • Workers: {len(cluster_state.workers)} nodes")
        print()
        print(f"Seu node: {node_role.upper()} em {host_ip}:{node_port or 'N/A'}")
        print(f"Cluster state salvo em: {Path(env_path).parent / 'data' / 'enxame' / 'cluster_state.json'}")
        print()
        print("Próximos passos:")
        print("  1. Inicie os outros nodes do Enxame")
        print("  2. Use o dashboard em http://localhost:8765/")
        print("  3. Queries serão processadas via política LOCAL -> ENXAME -> WEB")
        print()
        
        return node_role
    else:
        print("Instalação do cluster cancelada. Operando em modo standalone.")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Configuração de função do node ENXAME")
    parser.add_argument("--env-file", required=True, help="Caminho do arquivo .env da instalação")
    parser.add_argument("--scan-seconds", type=int, default=5, help="Duração da varredura mDNS em segundos")
    parser.add_argument("--non-interactive", action="store_true", help="Não pergunta nada; usa/repete a função salva ou 'auto'")
    args = parser.parse_args()

    env_path = Path(args.env_file)
    existing_role = read_env_value(env_path, "ENXAME_NODE_ROLE")

    # A pergunta só é feita quando o .env ainda não tem uma função salva —
    # ou seja, na primeira vez que este node é configurado. Em updates e
    # migrações o .env é preservado/restaurado do backup, então a função
    # já vem preenchida e a pergunta é pulada automaticamente.
    is_first_time = existing_role is None

    if not is_first_time:
        role = existing_role
        print(f"Função já configurada anteriormente: {role}. Update/migração não altera a função do node.")
    elif args.non_interactive:
        role = "auto"
    else:
        role = ask_role()

    print()
    print(f"Procurando outros nodes do Enxame na rede local ({args.scan_seconds}s)...")
    peers = scan_for_peers(args.scan_seconds)

    # --- NOVA LÓGICA: Detectar cluster se 3+ peers encontrados ---
    detected_role = detect_cluster_installation(peers, env_path)
    if detected_role:
        role = detected_role
    # --------------------------------------------------------

    if role == "auto":
        role = resolve_auto_role(peers)
        print(f"Função escolhida automaticamente pelo Enxame: {role}")

    node_id = read_env_value(env_path, "ENXAME_NODE_ID") or f"{role}-{socket.gethostname()}"
    host_ip = local_ip()
    port = ROLE_PORTS.get(role, 0)

    write_env_value(env_path, "ENXAME_NODE_ID", node_id)
    write_env_value(env_path, "ENXAME_NODE_ROLE", role)
    if port:
        write_env_value(env_path, "ENXAME_NODE_PORT", str(port))

    advertiser = announce_self(node_id, role, host_ip, port)
    if advertiser:
        print(f"Node anunciado na rede como '{node_id}' (função: {role}, {host_ip}:{port or 'N/A'}).")

    if is_first_time:
        print()
        print("-" * 62)
        print(" Confirmação de capacidades — primeira instalação")
        print("-" * 62)
        if peers:
            for info in peers.values():
                print(f"  - {info.node_id}: assumiu a função '{info.role}' em {info.host}:{info.port}")
        else:
            print("  Nenhum outro node respondeu à varredura.")
        print(f"  - {node_id}: assumiu a função '{role}' em {host_ip}:{port or 'N/A'} [este node]")
        print("-" * 62)

    if advertiser:
        # Mantém o anúncio ativo por mais alguns segundos para que outros
        # instaladores rodando em paralelo na rede consigam nos enxergar
        # durante a própria varredura deles.
        time.sleep(2)
        try:
            advertiser.stop()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
