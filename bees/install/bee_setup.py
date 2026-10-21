"""Etapa final da instalação: configurar a abelha, atalhos e serviço.

Separado do `bee_installer.py` para ser importável e testável sem executar uma
instalação inteira (o instalador baixa modelo e cria venv; os testes não podem).

Decisões que evitam repetir bugs antigos:

* O data-dir vem de `cluster_setup.resolve_data_dir()`, o MESMO que
  `bees.config.load_config()` usa. A versão antiga gravava em `~/enxame/data`
  enquanto o serviço lia `~/.local/share/enxame/bee` — a configuração escrita
  pelo instalador nunca era lida.
* `--node-id` é gravado em `identity.json`, não só em `config.json`, porque
  `bees/service.py::_load_identity()` sobrescreve o nome com o de identity.json.
* Não existe atalho "Parar": a versão anterior gerava um .bat que dava POST em
  `/api/v1/shutdown`, rota que nunca existiu. Parar é fechar o terminal ou
  `systemctl --user stop enxame-bee`.
"""

from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any, Callable

try:
    # Uso normal: dentro do pacote (repo clonado ou AppImage/.app).
    from . import cluster_setup
except ImportError:  # pragma: no cover
    # bees/install não tem __init__.py; importado como módulo solto.
    sys_path_fix = str(Path(__file__).resolve().parent)
    if sys_path_fix not in __import__("sys").path:
        __import__("sys").path.insert(0, sys_path_fix)
    import cluster_setup

LogFn = Callable[[str], None]


def _print(msg: str) -> None:
    print(msg)


# ---------------------------------------------------------------------------
# Comando de execução
# ---------------------------------------------------------------------------

def bee_start_command(
    venv_py: Path | str,
    data_dir: Path | str,
    port: int,
    ollama_url: str,
    model: str,
    repo_root: Path | str,
) -> list[str]:
    """Comando que sobe a abelha.

    `-m bees.service` a partir da RAIZ do repositório: o módulo usa imports
    relativos e importa `core`, então `python bees/service.py` não funciona.
    """
    return [
        str(venv_py), "-m", "bees.service",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--data-dir", str(data_dir),
        "--ollama-url", ollama_url,
        "--model", model,
    ]


def _sugerir_node_id(data_dir: Path) -> str:
    """Nome sugerido: o já persistido, senão o hostname."""
    identidade = data_dir / "identity.json"
    if identidade.exists():
        try:
            import json

            with open(identidade, "r", encoding="utf-8") as f:
                dados = json.load(f)
            existente = str(dados.get("node_id") or "").strip()
            if existente:
                return existente
        except (ValueError, OSError):
            pass
    return socket.gethostname().split(".")[0] or "abelha"


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

def configure_bee(
    *,
    data_dir: Path,
    port: int,
    ollama_url: str,
    model: str,
    node_id: str | None = None,
    cluster: bool | None = None,
    auto: bool = False,
    allow_web: bool = True,
    venv_py: Path | str | None = None,
    repo_root: Path | None = None,
    dry_run: bool = False,
    log_info: LogFn = _print,
    log_warn: LogFn = _print,
) -> dict[str, Any]:
    """Grava config.json/identity.json e resolve a participação no enxame.

    `cluster`: True/False = decisão explícita via --cluster/--no-cluster;
    None = perguntar (ou aceitar em --auto) só se houver abelhas na rede.

    Retorna um resumo do que ficou configurado. `cluster` no retorno é
    True/False quando houve decisão gravada, e None quando nada foi gravado
    (não havia o que perguntar) — nesse caso a abelha segue o default do
    serviço, que é participar do enxame se encontrar peers.
    """
    data_dir = Path(data_dir)
    resumo: dict[str, Any] = {
        "data_dir": data_dir,
        "port": port,
        "ollama_url": ollama_url,
        "model": model,
        "node_id": node_id or _sugerir_node_id(data_dir),
        "cluster": None,
        "allow_web": allow_web,
    }

    if dry_run:
        log_info(f"  [dry-run] pularia: gravar {data_dir / 'config.json'}")
        log_info(f"  [dry-run] node_id sugerido: {resumo['node_id']}")
        log_info(f"  [dry-run] pularia: definir cluster={cluster!r}")
        return resumo

    data_dir.mkdir(parents=True, exist_ok=True)
    cluster_setup.write_bee_config(
        data_dir,
        host="0.0.0.0",
        port=port,
        model=model,
        ollama_base_url=ollama_url,
        allow_web=allow_web,
        log_level="INFO",
    )
    log_info(f"  config.json gravado em {data_dir}")

    identidade = data_dir / "identity.json"
    if node_id:
        caminho = cluster_setup.set_node_id(data_dir, node_id)
        log_info(f"  identidade fixada como '{node_id}' ({caminho})")
        resumo["node_id"] = node_id
    elif identidade.exists():
        # Já existe identidade: não trocar o nome de uma abelha que pode já
        # participar de um enxame (a eleição desempata por node_id).
        resumo["node_id"] = _sugerir_node_id(data_dir)
        log_info(f"  identidade existente mantida: '{resumo['node_id']}'")
    else:
        # Primeira instalação neste data-dir: FIXAR um nome estável.
        #
        # Sem isto o node_id vem do default de BeeConfig (`uuid.uuid4()`), e
        # `_load_identity()` não persiste nada quando identity.json não existe.
        # Resultado observado numa instalação real: a abelha subiu como
        # "bb5c32e7-7e80-4d5d-a282-73cb9bc1b45e" e ganharia OUTRO uuid a cada
        # reinício. Como a eleição de papéis desempata por node_id, os papéis do
        # enxame mudariam toda vez que a máquina reiniciasse.
        nome = _sugerir_node_id(data_dir)
        cluster_setup.set_node_id(data_dir, nome)
        resumo["node_id"] = nome
        log_info(f"  identidade criada e fixada como '{nome}'")

    if cluster is True:
        cluster_setup.enable_cluster_mode(data_dir)
        resumo["cluster"] = True
        log_info("  modo cluster: ATIVADO (--cluster)")
    elif cluster is False:
        cluster_setup.disable_cluster_mode(data_dir)
        resumo["cluster"] = False
        log_info("  modo cluster: DESATIVADO (--no-cluster) — abelha isolada")
    else:
        # venv_py/repo_root importam: o Python do sistema não tem zeroconf,
        # então sem eles a descoberta voltaria vazia e a pergunta nunca seria
        # feita durante uma instalação real.
        decisao = cluster_setup.prompt_cluster_optin(
            data_dir, auto=auto,
            python_exe=str(venv_py) if venv_py else None,
            repo_root=repo_root,
            log_info=log_info, log_warn=log_warn,
        )
        if decisao is True:
            cluster_setup.enable_cluster_mode(data_dir)
            resumo["cluster"] = True
            log_info("  modo cluster: ATIVADO")
        elif decisao is False:
            cluster_setup.disable_cluster_mode(data_dir)
            resumo["cluster"] = False
            log_info("  modo cluster: DESATIVADO — esta abelha não forma enxame")
        else:
            log_warn(
                "  nenhuma outra abelha na rede agora: nada gravado. O enxame se "
                "forma sozinho quando 3+ abelhas estiverem no ar."
            )

    return resumo


# ---------------------------------------------------------------------------
# Atalhos
# ---------------------------------------------------------------------------

def _rodar(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60, **kwargs)


def create_bee_shortcuts(
    *,
    venv_py: Path | str,
    data_dir: Path | str,
    port: int,
    ollama_url: str,
    model: str,
    repo_root: Path | str,
    dry_run: bool = False,
    log_info: LogFn = _print,
    log_warn: LogFn = _print,
) -> list[Path]:
    """Cria um atalho "Iniciar Abelha" no lugar certo de cada SO.

    Retorna os caminhos criados (vazio se nada foi criado).
    """
    repo_root = Path(repo_root)
    cmd = bee_start_command(venv_py, data_dir, port, ollama_url, model, repo_root)
    sistema = platform.system()
    criados: list[Path] = []

    if dry_run:
        log_info("  [dry-run] pularia: criar atalho de inicialização")
        return criados

    try:
        if sistema == "Windows":
            desktop = Path(os.getenv("USERPROFILE", Path.home())) / "Desktop"
            desktop.mkdir(parents=True, exist_ok=True)
            alvo = desktop / "Iniciar Abelha.bat"
            linhas = [
                "@echo off",
                "title Abelha ENXAME",
                # Citado: sem aspas, `cd /d C:\Users\Maria Silva\enxamepublic`
                # falha e a abelha é iniciada no diretório errado — onde
                # `-m bees.service` não encontra o pacote `bees` nem o `core`.
                f'cd /d {_quote_windows(repo_root)}',
                " ".join(_quote_windows(p) for p in cmd),
                "pause",
            ]
            _gravar_bat(alvo, linhas)
        elif sistema == "Darwin":
            desktop = Path.home() / "Desktop"
            desktop.mkdir(parents=True, exist_ok=True)
            alvo = desktop / "Iniciar Abelha.command"
            corpo = "\n".join([
                "#!/bin/bash",
                f"cd {shlex_quote(str(repo_root))}",
                " ".join(shlex_quote(p) for p in cmd),
            ]) + "\n"
            alvo.write_text(corpo, encoding="utf-8")
            alvo.chmod(0o755)
        else:
            apps = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "applications"
            apps.mkdir(parents=True, exist_ok=True)
            alvo = apps / "enxame-bee.desktop"
            # Path= é a chave da especificação para o diretório de trabalho, e
            # não sofre divisão de palavras — substitui o `bash -c 'cd ...'`
            # anterior, cujas aspas simples aninhadas quebravam em caminho com
            # espaço (o mesmo defeito que o `cd /d` sem aspas tinha no Windows).
            exec_line = " ".join(_desktop_quote(parte) for parte in cmd)
            corpo = "\n".join([
                "[Desktop Entry]",
                "Type=Application",
                "Version=1.0",
                "Name=Abelha ENXAME",
                "Comment=Inicia a abelha e a interface web",
                f"Exec={exec_line}",
                f"Path={repo_root}",
                "Terminal=true",
                "Categories=Utility;",
            ]) + "\n"
            alvo.write_text(corpo, encoding="utf-8")
            alvo.chmod(0o644)
        criados.append(alvo)
        log_info(f"  atalho criado: {alvo}")
    except OSError as exc:
        # Atalho é conveniência: falhar aqui não pode abortar a instalação.
        log_warn(f"  não foi possível criar o atalho ({exc})")

    return criados


# Metacaracteres do cmd.exe: sem aspas, qualquer um destes quebra a linha de
# comando — `&` separa comandos, `^` escapa, `()` agrupam, `|` tubula,
# `<`/`>` redirecionam, `,`/`;`/`=` delimitam argumentos. Dentro de aspas o
# cmd.exe os trata como texto.
_CMD_META = set('&^()|<>,;=" \t')


def _quote_windows(parte: str) -> str:
    """Cita um argumento para cmd.exe / arquivo .bat.

    Citava só quando havia espaço ou tab, o que era insuficiente: um caminho como
    `C:\\Dev\\R&D\\enxamepublic` partia o comando no `&` e o atalho executava
    outra coisa. Espaço em caminho de usuário (`C:\\Users\\Maria Silva\\...`) é o
    caso comum; `&`, `^` e `()` são menos comuns, mas igualmente fatais.
    """
    texto = str(parte)
    if any(c in _CMD_META for c in texto):
        return '"' + texto.replace('"', '\\"') + '"'
    return texto


def _bat_encoding() -> str:
    """Codepage em que o cmd.exe lê arquivos .bat.

    O cmd.exe interpreta .bat na codepage OEM do sistema (cp850 num Windows em
    português, cp437 nos EUA), NÃO em UTF-8. Gravar UTF-8 corrompe caminho com
    acento na hora de executar: `C:\\Users\\José\\...` é lido como
    `C:\\Users\\JosÃ©\\...` e o atalho morre com "O sistema não pode encontrar o
    caminho especificado" — um atalho quebrado justamente para quem tem nome com
    acento.
    """
    if os.name == "nt":
        try:
            import ctypes

            cp = ctypes.windll.kernel32.GetOEMCP()
            if cp:
                return f"cp{cp}"
        except Exception:
            pass
    return "utf-8"


def _gravar_bat(alvo: Path, linhas: list[str]) -> None:
    """Grava um .bat com CRLF na codepage certa, com UTF-8 como último recurso."""
    texto = "\r\n".join(linhas) + "\r\n"
    try:
        alvo.write_text(texto, encoding=_bat_encoding())
    except UnicodeEncodeError:
        # Caractere fora da codepage OEM. UTF-8 ainda vai exibir o caminho errado,
        # mas o arquivo existe e o resto do .bat funciona — melhor que abortar.
        alvo.write_text(texto, encoding="utf-8")


# Caracteres reservados pela Desktop Entry Specification no valor de `Exec=`.
_DESKTOP_RESERVADOS = set(" \t\n\\\"'`><~|&;$*?#()")


def _desktop_quote(parte: str) -> str:
    """Cita um argumento para a chave `Exec=` de um arquivo .desktop.

    NÃO é shlex.quote. A especificação de entrada de área de trabalho agrupa
    argumentos com ASPAS DUPLAS — aspas simples são caracteres literais ali. Por
    isso `Exec=bash -c 'cd ...'` nunca funcionou como parecia: o ambiente
    dividia a linha nos espaços e passava `'cd`, o caminho e `&&` como argv
    separados, então o bash executava só `'cd`. Dentro das aspas duplas a
    especificação exige escapar `\\`, `"`, `$` e `` ` ``.
    """
    texto = str(parte)
    if not any(c in _DESKTOP_RESERVADOS for c in texto):
        return texto
    escapado = (texto.replace("\\", "\\\\").replace('"', '\\"')
                     .replace("$", "\\$").replace("`", "\\`"))
    return f'"{escapado}"'


def shlex_quote(parte: str) -> str:
    try:
        import shlex

        return shlex.quote(parte)
    except Exception:  # pragma: no cover - shlex é stdlib
        return "'" + parte.replace("'", "'\\''") + "'"


# ---------------------------------------------------------------------------
# Serviço de inicialização automática
# ---------------------------------------------------------------------------

def install_bee_service(
    *,
    venv_py: Path | str,
    data_dir: Path | str,
    port: int,
    ollama_url: str,
    model: str,
    repo_root: Path | str,
    dry_run: bool = False,
    log_info: LogFn = _print,
    log_warn: LogFn = _print,
) -> dict[str, Any]:
    """Instala a abelha como serviço do usuário e tenta ativá-lo.

    Retorna {"criado": Path|None, "ativo": bool, "comando_parar": str}.
    `ativo` só é True se o comando de ativação realmente devolveu sucesso —
    reportar sucesso sem verificar foi a causa de várias "instalações" que
    nunca funcionaram.
    """
    repo_root = Path(repo_root)
    cmd = bee_start_command(venv_py, data_dir, port, ollama_url, model, repo_root)
    sistema = platform.system()
    resultado: dict[str, Any] = {"criado": None, "ativo": False, "comando_parar": ""}

    if dry_run:
        log_info("  [dry-run] pularia: instalar serviço de inicialização automática")
        return resultado

    try:
        if sistema == "Linux" and shutil.which("systemctl"):
            unidade_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "systemd" / "user"
            unidade_dir.mkdir(parents=True, exist_ok=True)
            unidade = unidade_dir / "enxame-bee.service"
            corpo = "\n".join([
                "[Unit]",
                "Description=Abelha ENXAME (bee standalone)",
                "After=network-online.target",
                "Wants=network-online.target",
                "",
                "[Service]",
                "Type=simple",
                # WorkingDirectory é obrigatório: sem ele `-m bees.service` falha
                # porque o pacote `bees` e o `core` não estão no sys.path.
                f"WorkingDirectory={repo_root}",
                f"Environment=BEE_DATA_DIR={data_dir}",
                "ExecStart=" + " ".join(shlex_quote(p) for p in cmd),
                "Restart=on-failure",
                "RestartSec=5",
                "",
                "[Install]",
                "WantedBy=default.target",
            ]) + "\n"
            unidade.write_text(corpo, encoding="utf-8")
            resultado["criado"] = unidade
            resultado["comando_parar"] = "systemctl --user stop enxame-bee"
            log_info(f"  unidade systemd criada: {unidade}")

            _rodar(["systemctl", "--user", "daemon-reload"])
            proc = _rodar(["systemctl", "--user", "enable", "--now", "enxame-bee"])
            if proc.returncode == 0:
                resultado["ativo"] = True
                log_info("  serviço ativado (inicia no login e já está rodando)")
            else:
                erro = (proc.stderr or proc.stdout or "").strip().splitlines()
                log_warn("  unidade criada, mas não foi possível ativá-la agora:")
                for linha in erro[-3:]:
                    log_warn(f"    {linha}")
                log_warn(
                    "  Em servidor sem sessão gráfica pode ser necessário: "
                    "sudo loginctl enable-linger $USER"
                )
        elif sistema == "Darwin":
            agentes = Path.home() / "Library" / "LaunchAgents"
            agentes.mkdir(parents=True, exist_ok=True)
            plist = agentes / "com.enxame.bee.plist"
            args_xml = "\n".join(
                f"        <string>{_xml_escape(p)}</string>" for p in cmd
            )
            corpo = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                '<plist version="1.0">\n<dict>\n'
                "    <key>Label</key>\n    <string>com.enxame.bee</string>\n"
                "    <key>ProgramArguments</key>\n    <array>\n"
                f"{args_xml}\n    </array>\n"
                f"    <key>WorkingDirectory</key>\n    <string>{_xml_escape(str(repo_root))}</string>\n"
                "    <key>RunAtLoad</key>\n    <true/>\n"
                "    <key>KeepAlive</key>\n    <true/>\n"
                "</dict>\n</plist>\n"
            )
            plist.write_text(corpo, encoding="utf-8")
            resultado["criado"] = plist
            resultado["comando_parar"] = "launchctl unload ~/Library/LaunchAgents/com.enxame.bee.plist"
            log_info(f"  LaunchAgent criado: {plist}")
            proc = _rodar(["launchctl", "load", str(plist)])
            resultado["ativo"] = proc.returncode == 0
            if not resultado["ativo"]:
                log_warn(f"  plist criado, mas `launchctl load` falhou: {proc.stderr.strip()[:200]}")
        elif sistema == "Windows":
            if not shutil.which("schtasks"):
                log_warn("  schtasks indisponível; serviço não criado")
                return resultado
            executar = (f'cmd /c cd /d {_quote_windows(repo_root)} && '
                        + " ".join(_quote_windows(p) for p in cmd))
            proc = _rodar([
                "schtasks", "/Create", "/TN", "EnxameBee",
                "/TR", executar, "/SC", "ONLOGON", "/RL", "LIMITED", "/F",
            ])
            if proc.returncode == 0:
                resultado["criado"] = Path("schtasks:EnxameBee")
                resultado["ativo"] = True
                resultado["comando_parar"] = 'schtasks /End /TN "EnxameBee"'
                log_info("  tarefa de logon 'EnxameBee' criada")
            else:
                log_warn(f"  não foi possível criar a tarefa: {proc.stderr.strip()[:200]}")
        else:
            log_warn("  sem sistema de serviço suportado neste SO; nada criado")
    except (OSError, subprocess.SubprocessError) as exc:
        log_warn(f"  falha ao instalar o serviço: {exc}")

    return resultado


def _xml_escape(texto: str) -> str:
    return (
        texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
