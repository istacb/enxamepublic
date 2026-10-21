"""Configuração de cluster compartilhada pelos instaladores.

Existe um único instalador (`bees/install/bee_installer.py`); este módulo reúne
as peças de configuração que ele usa e que os testes conseguem importar sem
executar uma instalação inteira.

Duas coisas importantes que estavam erradas antes de existir este arquivo:

* `cluster.enabled` era gravado no config.json e nunca lido pelo serviço, então
  responder "n" à pergunta do instalador não impedia o enxame de se formar.
* A descoberta de peers usava `ENXAMEMDNSBrowser` como se ela tivesse um
  callback `on_node_found`. Ela não tem — popula `browser.nodes`. O callback
  atribuído nunca era chamado, `discover_local_peers` devolvia sempre lista
  vazia e a pergunta de cluster NUNCA era feita, mesmo com abelhas na rede.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

MIN_PEERS_PADRAO = 3


def default_data_dir() -> Path:
    """Data-dir padrão — o MESMO que `bees.config.load_config()` usa.

    Isto não é cosmético: `load_config` lê `<data_dir>/config.json` do diretório
    padrão quando ninguém passa --data-dir. Se o instalador gravasse em outro
    lugar (a versão antiga usava ~/enxame/data), a abelha jamais leria o que o
    instalador escreveu e toda a configuração seria ignorada.
    """
    try:
        from bees.config import get_default_data_dir

        return Path(get_default_data_dir())
    except Exception:
        pass

    # Espelho de bees.config.get_default_data_dir, para o caso de o pacote bees
    # ainda não ser importável (instalador rodando antes das dependências).
    import os
    import platform

    sistema = platform.system()
    if sistema == "Windows":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sistema == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "enxame" / "bee"


def resolve_data_dir(explicito: str | None = None) -> Path:
    """--data-dir > BEE_DATA_DIR > padrão, na mesma ordem de load_config."""
    if explicito:
        return Path(explicito).expanduser()
    import os

    do_env = os.getenv("BEE_DATA_DIR")
    if do_env:
        return Path(do_env).expanduser()
    return default_data_dir()


# ---------------------------------------------------------------------------
# config.json da abelha
# ---------------------------------------------------------------------------

def bee_config_path(data_dir: Path) -> Path:
    """Caminho do config.json que `bees.config.load_config` de fato lê."""
    return Path(data_dir) / "config.json"


def _read_config(data_dir: Path) -> dict[str, Any]:
    caminho = bee_config_path(data_dir)
    if not caminho.exists():
        return {}
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, dict) else {}
    except (json.JSONDecodeError, OSError):
        # Um config.json corrompido não pode impedir a instalação; o serviço
        # usa os defaults. Preservamos o arquivo em vez de sobrescrevê-lo.
        return {}


def _write_config(data_dir: Path, config: dict[str, Any]) -> None:
    caminho = bee_config_path(data_dir)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def write_bee_config(
    data_dir: Path,
    *,
    node_id: str | None = None,
    host: str | None = None,
    port: int | None = None,
    model: str | None = None,
    ollama_base_url: str | None = None,
    allow_web: bool | None = None,
    log_level: str | None = None,
) -> Path:
    """Grava/atualiza o config.json da abelha sem apagar o que já existe.

    Só escreve os campos informados: reinstalar o instalador não deve zerar uma
    configuração que o usuário ajustou à mão.
    """
    config = _read_config(data_dir)
    campos = {
        "node_id": node_id,
        "host": host,
        "port": port,
        "model": model,
        "ollama_base_url": ollama_base_url,
        "allow_web": allow_web,
        "log_level": log_level,
    }
    for chave, valor in campos.items():
        if valor is not None:
            config[chave] = valor

    _write_config(data_dir, config)
    return bee_config_path(data_dir)


def set_node_id(data_dir: Path, node_id: str) -> Path | None:
    """Fixa o nome da abelha onde o serviço de fato o procura.

    `bees/service.py::_load_identity()` sobrescreve `config.node_id` com o
    conteúdo de `data_dir/identity.json`. Escrever o nome só no config.json
    seria decorativo — o serviço usaria outro. Por isso gravamos nos dois,
    preservando as chaves Ed25519 que `bees.config.generate_identity()` criou.

    Retorna o caminho de identity.json, ou None se node_id for vazio.
    """
    if not node_id:
        return None
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    caminho = data_dir / "identity.json"
    identidade: dict[str, Any] = {}
    if caminho.exists():
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                dados = json.load(f)
            if isinstance(dados, dict):
                identidade = dados
        except (json.JSONDecodeError, OSError):
            # identity.json ilegível: reescrevemos só o node_id. Perdem-se as
            # chaves, mas um arquivo corrompido já não servia para assinar nada.
            identidade = {}
    identidade["node_id"] = node_id
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(identidade, f, indent=2, ensure_ascii=False)

    write_bee_config(data_dir, node_id=node_id)
    return caminho


def set_cluster_mode(data_dir: Path, enabled: bool) -> None:
    """Liga/desliga o modo cluster preservando as outras chaves de cluster."""
    config = _read_config(data_dir)
    cluster = dict(config.get("cluster") or {})
    cluster["enabled"] = bool(enabled)
    cluster.setdefault("auto_elect", True)
    cluster.setdefault("min_peers", MIN_PEERS_PADRAO)
    config["cluster"] = cluster
    _write_config(data_dir, config)


def enable_cluster_mode(data_dir: Path) -> None:
    """Habilita o modo cluster na configuração da abelha."""
    set_cluster_mode(data_dir, True)


def disable_cluster_mode(data_dir: Path) -> None:
    """Grava a recusa do usuário: esta abelha não forma enxame.

    Sem isto a pergunta do instalador era decorativa.
    """
    if not bee_config_path(data_dir).exists():
        return
    set_cluster_mode(data_dir, False)


def read_cluster_mode(data_dir: Path) -> bool | None:
    """True/False se estiver definido; None se o usuário nunca escolheu."""
    cluster = _read_config(data_dir).get("cluster") or {}
    if "enabled" in cluster:
        return bool(cluster["enabled"])
    return None


# ---------------------------------------------------------------------------
# Descoberta de peers (para saber se vale perguntar sobre cluster)
# ---------------------------------------------------------------------------

_SCRIPT_DESCOBERTA = r"""
import json, sys, time

espera = float(sys.argv[1])
try:
    from core.discovery.browser import ENXAMEMDNSBrowser
except Exception as exc:
    print(json.dumps({"peers": [], "erro": f"import: {exc}"}))
    sys.exit(0)

browser = None
nodes = []
erro = ""
try:
    browser = ENXAMEMDNSBrowser()
    browser.start()
    time.sleep(espera)
    nodes = list(getattr(browser, "nodes", {}).values())
except Exception as exc:
    erro = f"browser: {exc}"
finally:
    if browser is not None:
        try:
            browser.stop()
        except Exception:
            pass

peers = []
for n in nodes:
    peers.append({
        "node_id": getattr(n, "node_id", "") or "",
        "role": getattr(n, "role", "") or "",
        "host": getattr(n, "host", "") or "",
        "port": getattr(n, "port", 0) or 0,
        "capabilities": getattr(n, "capabilities", ""),
        "models": getattr(n, "models", ""),
    })
print(json.dumps({"peers": peers, "erro": erro}))
"""


def discover_local_peers(
    data_dir: Path,
    timeout: float = 5.0,
    python_exe: str | None = None,
    repo_root: Path | None = None,
) -> list[dict]:
    """Descobre abelhas na rede local via mDNS.

    `ENXAMEMDNSBrowser` acumula os serviços em `browser.nodes`; ele NÃO tem
    callback. A versão anterior atribuía `browser.on_node_found`, que ninguém
    chamava, e por isso devolvia sempre [] — a pergunta de cluster nunca era
    feita. Aqui lemos `nodes` depois de esperar.

    `python_exe` é o que torna isto útil DE VERDADE durante a instalação: o
    instalador roda com o Python do sistema, que não tem zeroconf (e nem pode
    ter, por PEP 668). Sem ele a descoberta falharia silenciosamente e a
    pergunta nunca apareceria. Passando o Python do venv — criado no passo
    anterior — a descoberta roda onde as dependências existem.
    """
    peers_brutos = None
    if python_exe:
        peers_brutos = _descobrir_via_subprocesso(python_exe, timeout, repo_root)
    if peers_brutos is None:
        peers_brutos = _descobrir_no_processo(timeout)

    peers: list[dict] = []
    for node in peers_brutos:
        peers.append({
            "node_id": node.get("node_id", ""),
            "role": node.get("role", ""),
            "host": node.get("host", ""),
            "port": node.get("port", 0),
            # No anúncio mDNS capabilities/models vêm como string: a abelha
            # serializa lista em JSON (["rag", ...]). CSV é o fallback.
            "capabilities": _parse_lista(node.get("capabilities", "")),
            "models": _parse_lista(node.get("models", "")),
        })
    return peers


def _descobrir_via_subprocesso(
    python_exe: str, timeout: float, repo_root: Path | None
) -> list[dict] | None:
    """Roda a descoberta com outro interpretador. None se não for possível."""
    import subprocess

    cwd = str(repo_root) if repo_root else None
    try:
        proc = subprocess.run(
            [str(python_exe), "-c", _SCRIPT_DESCOBERTA, str(max(0.5, timeout))],
            capture_output=True, text=True, timeout=timeout + 30, cwd=cwd,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    for linha in reversed(proc.stdout.strip().splitlines()):
        linha = linha.strip()
        if not linha.startswith("{"):
            continue
        try:
            dados = json.loads(linha)
        except ValueError:
            continue
        peers = dados.get("peers")
        if isinstance(peers, list):
            return [p for p in peers if isinstance(p, dict)]
    return None


def _descobrir_no_processo(timeout: float) -> list[dict]:
    """Descoberta no próprio processo (só funciona se zeroconf já existir)."""
    try:
        from core.discovery.browser import ENXAMEMDNSBrowser
    except Exception:
        return []

    browser = None
    try:
        browser = ENXAMEMDNSBrowser()
        browser.start()
        time.sleep(max(0.5, timeout))
        nodes = list(getattr(browser, "nodes", {}).values())
    except Exception:
        return []
    finally:
        if browser is not None:
            try:
                browser.stop()
            except Exception:
                pass

    return [
        {
            "node_id": getattr(n, "node_id", "") or "",
            "role": getattr(n, "role", "") or "",
            "host": getattr(n, "host", "") or "",
            "port": getattr(n, "port", 0) or 0,
            "capabilities": getattr(n, "capabilities", ""),
            "models": getattr(n, "models", ""),
        }
        for n in nodes
    ]


def _parse_lista(valor: Any) -> list[str]:
    """Converte o valor anunciado em lista de strings.

    A abelha anuncia capabilities/models como JSON (`["rag", "index"]`); tratar
    como CSV produzia itens como `["rag"` e o instalador imprimia lixo.
    """
    if isinstance(valor, (list, tuple)):
        return [str(v) for v in valor]
    if not valor:
        return []
    texto = str(valor).strip()
    if texto.startswith("["):
        try:
            import json as _json

            dados = _json.loads(texto)
            if isinstance(dados, list):
                return [str(item) for item in dados]
        except (ValueError, TypeError):
            pass
    return [parte.strip() for parte in texto.split(",") if parte.strip()]


def prompt_cluster_optin(
    data_dir: Path,
    auto: bool = False,
    *,
    python_exe: str | None = None,
    repo_root: Path | None = None,
    log_info: Callable[[str], None] = print,
    log_warn: Callable[[str], None] = print,
    confirmar: Callable[[str], str] | None = None,
) -> bool | None:
    """Pergunta se deseja formar cluster quando há abelhas suficientes na rede.

    Retorna True (aceitou), False (recusou) ou None (não houve o que perguntar).
    O None importa: recusar grava cluster.enabled=false, mas não ter perguntado
    não deve gravar nada, porque o enxame pode se formar depois quando outras
    abelhas aparecerem.

    `confirmar` permite injetar a resposta em teste (default: input()).
    """
    log_info("Verificando se há outras abelhas na rede para formar cluster...")

    peers = discover_local_peers(
        data_dir, timeout=8.0, python_exe=python_exe, repo_root=repo_root
    )
    abelhas = [p for p in peers if p.get("role") == "bee"]

    if len(abelhas) < MIN_PEERS_PADRAO - 1:
        return None

    print("\n" + "=" * 60)
    print("  🐝 CLUSTER DETECTADO!")
    print("=" * 60)
    print(f"\nDetectamos {len(abelhas)} outra(s) abelha(s) na rede local:")
    for peer in abelhas[:8]:
        caps = ", ".join(peer.get("capabilities", [])[:3]) or "sem capacidades anunciadas"
        print(f"  • {peer['node_id']} ({peer['host']}:{peer['port']}) - {caps}")

    print(f"\nCom estas {len(abelhas)} abelha(s) mais a desta máquina dá para formar um")
    print("enxame: as abelhas elegem os papéis entre si (Juiz, Bibliotecária,")
    print("Guarda e Workers). Isso traz failover automático, índice global e")
    print("roteamento da pergunta para a abelha que tem o conhecimento.")

    if auto:
        return True

    if confirmar is not None:
        resposta = confirmar("\nDeseja ativar o modo cluster? [S/n]: ")
    else:
        resposta = input("\nDeseja ativar o modo cluster? [S/n]: ")
    return resposta.strip().lower() in ("s", "sim", "y", "yes", "")
