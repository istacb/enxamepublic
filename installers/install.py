#!/usr/bin/env python3
"""
ENXAME — Instalador Unificado Next-Next-Finish
==============================================
Fluxo interativo para Windows, macOS e Linux:
  1. Boas-vindas  →  2. Plataforma  →  3. Pasta  →  4. Boot  →  5. Função  →  6. Concluir

Detecta o SO automaticamente e instala o Enxame com serviço em segundo plano,
atalho na área de trabalho e arquivo .env de configuração.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Cores de terminal (sem dependências externas)
# ---------------------------------------------------------------------------
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    RED = "\033[31m"
    CYAN = "\033[36m"

    @classmethod
    def disable(cls) -> None:
        for attr in vars(cls):
            if attr.isupper():
                setattr(cls, attr, "")


def detect_platform() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    if system == "linux":
        try:
            with open("/etc/os-release", encoding="utf-8") as f:
                content = f.read().lower()
            for distro in ("ubuntu", "debian", "mint", "pop", "elementary", "zorin"):
                if distro in content:
                    return "debian"
            for distro in ("arch", "manjaro", "endeavouros", "garuda", "artix"):
                if distro in content:
                    return "arch"
            for distro in ("fedora", "rhel", "centos", "rocky", "alma"):
                if distro in content:
                    return "fedora"
        except Exception:
            pass
        return "linux"
    return "unknown"


def is_admin() -> bool:
    try:
        if platform.system().lower() == "windows":
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        return os.geteuid() == 0
    except Exception:
        return False


def confirm(prompt: str, default: str = "s") -> bool:
    """Pergunta sim/não. Retorna True para 's', False para 'n'."""
    while True:
        resp = input(f"{prompt} [{default}/n]: ").strip().lower()
        if not resp:
            resp = default
        if resp in ("s", "sim", "y", "yes"):
            return True
        if resp in ("n", "não", "nao", "no"):
            return False
        print(f"{C.YELLOW}Responda com s ou n.{C.RESET}")


def escolha(prompt: str, opcoes: dict[str, str], padrao: str = "4") -> str:
    """Mostra opções numeradas e devolve a chave escolhida."""
    print(prompt)
    for chave, label in opcoes.items():
        marca = " (padrão)" if chave == padrao else ""
        print(f"  [{chave}] {label}{marca}")
    while True:
        resp = input(f"Escolha [{padrao}]: ").strip() or padrao
        if resp in opcoes:
            return resp
        print(f"{C.YELLOW}Opção inválida. Tente novamente.{C.RESET}")


def banner(titulo: str) -> None:
    print()
    print(f"{C.BOLD}{C.BLUE}╔═════════════════════════════════════════════════════════════╗{C.RESET}")
    print(f"{C.BOLD}{C.BLUE}║  {titulo:<58}║{C.RESET}")
    print(f"{C.BOLD}{C.BLUE}╚═════════════════════════════════════════════════════════════╝{C.RESET}")
    print()


def passo(numero: int, total: int, texto: str) -> None:
    print(f"{C.CYAN}>>> PASSO {numero}/{total}: {texto}{C.RESET}")


def ok(msg: str) -> None:
    print(f"{C.GREEN}[OK]{C.RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{C.YELLOW}[!]{C.RESET} {msg}")


def erro(msg: str) -> None:
    print(f"{C.RED}[ERRO]{C.RESET} {msg}")


# ---------------------------------------------------------------------------
# Instalação por plataforma
# ---------------------------------------------------------------------------
def instalar_windows(install_dir: Path, env_file: Path, role: str, boot: bool) -> int:
    """Instala no Windows via xcopy/robocopy + tarefa agendada + atalho."""
    passo(4, 6, "Instalando arquivos")
    install_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[1]
    # Copia tudo exceto .git, .venv, __pycache__
    for item in repo_root.iterdir():
        if item.name in (".git", ".venv", "__pycache__", "installers"):
            continue
        dst = install_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst)
    ok("Arquivos copiados")

    data_dir = Path(os.environ.get("APPDATA", install_dir)) / "Enxame" / "data"
    log_dir = Path(os.environ.get("LOCALAPPDATA", install_dir)) / "Enxame" / "Logs"
    config_dir = Path(os.environ.get("APPDATA", install_dir)) / "Enxame" / "Config"
    for d in (data_dir, log_dir, config_dir):
        d.mkdir(parents=True, exist_ok=True)
    ok(f"Diretórios criados: dados={data_dir}, logs={log_dir}, config={config_dir}")

    # .env
    if not env_file.exists():
        port = 7700 if role == "juiz" else 7701 if role == "bibliotecario" else 8765
        env_file.write_text(
            f"# Configuração do Enxame\n"
            f"ENXAME_ENV=production\n"
            f"ENXAME_HOST=0.0.0.0\n"
            f"ENXAME_INSTALL_DIR={install_dir}\n"
            f"ENXAME_DATA_PATH={data_dir}\n"
            f"ENXAME_LOG_PATH={log_dir}\n"
            f"ENXAME_NODE_ROLE={role}\n"
            f"ENXAME_NODE_PORT={port}\n"
            f"OLLAMA_URL=http://localhost:11434\n",
            encoding="utf-8",
        )
        ok(f"Arquivo .env criado em {env_file}")
    else:
        warn("Arquivo .env já existe. Mantido.")

    # Tarefa agendada (boot)
    if boot:
        ps_cmd = (
            f'schtasks /Create /TN "Enxame" /TR '
            f'"python "{install_dir / "api" / "install" / "run_node.py"}" --env-file {env_file}" '
            f'/SC ONSTART /RL HIGHEST /F'
        )
        r = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True)
        if r.returncode == 0:
            ok("Tarefa agendada criada (inicia junto ao boot).")
        else:
            warn(f"Não foi possível criar tarefa agendada: {r.stderr.strip()}")

    # Inicia serviço agora
    subprocess.Popen(
        [sys.executable, str(install_dir / "api" / "install" / "run_node.py"), "--env-file", str(env_file)],
        cwd=str(install_dir),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    ok("Serviço iniciado em segundo plano.")

    # Atalho na área de trabalho
    desktop = Path(os.environ.get("USERPROFILE", install_dir)) / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    shortcut = desktop / "Enxame.lnk"
    ps_cmd = (
        f'$WshShell = New-Object -comObject WScript.Shell; '
        f'$Shortcut = $WshShell.CreateShortcut("{shortcut}"); '
        f'$Shortcut.TargetPath = "python"; '
        f'$Shortcut.Arguments = "{install_dir / "api" / "install" / "enxame-desktop.bat"} {install_dir} {env_file}"; '
        f'$Shortcut.Description = "Reiniciar serviço e abrir o Enxame no navegador"; '
        f'$Shortcut.WorkingDirectory = "{install_dir}"; '
        f'$Shortcut.Save()'
    )
    subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
    ok(f"Atalho criado na área de trabalho: {shortcut}")

    # Script wrapper do atalho
    wrapper = install_dir / "api" / "install" / "enxame-desktop.bat"
    wrapper.write_text(
        f'@echo off\n'
        f'set INSTALL_DIR={install_dir}\n'
        f'set ENV_FILE={env_file}\n'
        f'set PORT=8765\n'
        f'set URL=http://localhost:%PORT%/\n'
        f'echo Verificando se o Enxame esta em segundo plano...\n'
        f'tasklist /FI "IMAGENAME eq python.exe" | findstr /i "python" >nul || (\n'
        f'    echo Iniciando o Enxame em segundo plano...\n'
        f'    start /B "" python "!INSTALL_DIR!\\run_enxame.py" --no-browser\n'
        f'    timeout /t 5 /nobreak >nul\n'
        f')\n'
        f'echo Abrindo o navegador em !URL!\n'
        f'start "" "!URL!"\n'
        f'exit /b 0\n',
        encoding="utf-8",
    )
    return 0


def instalar_unix(install_dir: Path, env_file: Path, role: str, boot: bool, sistema: str) -> int:
    """Instala no Linux/macOS via rsync + systemd/launchd + atalho .desktop."""
    passo(4, 6, "Instalando arquivos")
    install_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[1]
    for item in repo_root.iterdir():
        if item.name in (".git", ".venv", "__pycache__", "installers"):
            continue
        dst = install_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst)
    ok("Arquivos copiados")

    if sistema == "linux":
        data_dir = Path("/var/lib/enxame/data")
        log_dir = Path("/var/log/enxame")
        config_dir = Path("/etc/enxame")
    else:
        data_dir = Path.home() / "Library" / "Application Support" / "Enxame" / "data"
        log_dir = Path.home() / "Library" / "Logs" / "Enxame"
        config_dir = Path.home() / "Library" / "Preferences" / "Enxame"

    for d in (data_dir, log_dir, config_dir):
        d.mkdir(parents=True, exist_ok=True)
    ok(f"Diretórios criados: dados={data_dir}, logs={log_dir}, config={config_dir}")

    # .env
    if not env_file.exists():
        port = 7700 if role == "juiz" else 7701 if role == "bibliotecario" else 8765
        env_file.write_text(
            f"# Configuração do Enxame\n"
            f"ENXAME_ENV=production\n"
            f"ENXAME_HOST=0.0.0.0\n"
            f"ENXAME_INSTALL_DIR={install_dir}\n"
            f"ENXAME_DATA_PATH={data_dir}\n"
            f"ENXAME_LOG_PATH={log_dir}\n"
            f"ENXAME_NODE_ROLE={role}\n"
            f"ENXAME_NODE_PORT={port}\n"
            f"OLLAMA_URL=http://localhost:11434\n",
            encoding="utf-8",
        )
        ok(f"Arquivo .env criado em {env_file}")
    else:
        warn("Arquivo .env já existe. Mantido.")

    # Serviço de boot
    if sistema == "linux":
        service_file = Path("/etc/systemd/system/enxame.service")
        port = 7700 if role == "juiz" else 7701 if role == "bibliotecario" else 8765
        service_file.write_text(
            f"[Unit]\n"
            f"Description=Enxame Node ({role})\n"
            f"After=network-online.target\n"
            f"Wants=network-online.target\n\n"
            f"[Service]\n"
            f"Type=simple\n"
            f"User=root\n"
            f"WorkingDirectory={install_dir}\n"
            f"EnvironmentFile={env_file}\n"
            f"ExecStart=/usr/bin/env python3 {install_dir / 'api' / 'install' / 'run_node.py'} --env-file {env_file}\n"
            f"Restart=on-failure\n"
            f"RestartSec=5\n"
            f"StandardOutput=journal\n"
            f"StandardError=journal\n\n"
            f"[Install]\n"
            f"WantedBy=multi-user.target\n",
            encoding="utf-8",
        )
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        subprocess.run(["systemctl", "enable", "enxame.service"], capture_output=True)
        if boot:
            subprocess.run(["systemctl", "start", "enxame.service"], capture_output=True)
            ok("Serviço systemd criado e iniciado (boot habilitado).")
        else:
            ok("Serviço systemd criado (não inicia junto ao boot por sua opção).")
    else:
        plist = Path.home() / "Library" / "LaunchAgents" / "com.enxame.node.plist"
        port = 7700 if role == "juiz" else 7701 if role == "bibliotecario" else 8765
        plist.write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "\n'
            f'  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            f'<plist version="1.0">\n'
            f'<dict>\n'
            f'  <key>Label</key><string>com.enxame.node</string>\n'
            f'  <key>ProgramArguments</key><array>\n'
            f'    <string>/usr/bin/python3</string>\n'
            f'    <string>{install_dir / "api" / "install" / "run_node.py"}</string>\n'
            f'    <string>--env-file</string>\n'
            f'    <string>{env_file}</string>\n'
            f'  </array>\n'
            f'  <key>WorkingDirectory</key><string>{install_dir}</string>\n'
            f'  <key>EnvironmentVariables</key><dict>\n'
            f'    <key>ENXAME_NODE_ROLE</key><string>{role}</string>\n'
            f'    <key>ENXAME_NODE_PORT</key><string>{port}</string>\n'
            f'  </dict>\n'
            f'  <key>RunAtLoad</key>{"true" if boot else "false"}\n'
            f'  <key>KeepAlive</key>true\n'
            f'</dict>\n'
            f'</plist>\n',
            encoding="utf-8",
        )
        if boot:
            subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)], capture_output=True)
            subprocess.run(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/com.enxame.node"], capture_output=True)
            ok("LaunchAgent carregado (inicia junto ao boot).")
        else:
            ok("LaunchAgent criado (não inicia junto ao boot por sua opção).")

    # Atalho .desktop (Linux) ou script (macOS)
    if sistema == "linux":
        desktop = Path.home() / "Desktop"
        desktop.mkdir(parents=True, exist_ok=True)
        shortcut = desktop / "Enxame.desktop"
        shortcut.write_text(
            f"[Desktop Entry]\n"
            f"Name=Enxame\n"
            f"GenericName=Enxame - IA Descentralizada\n"
            f"Comment=Reiniciar serviço e abrir o Enxame no navegador\n"
            f"Exec=python3 {install_dir / 'api' / 'install' / 'enxame-desktop'} {install_dir} {env_file}\n"
            f"Icon={install_dir / 'web' / 'icon.svg'}\n"
            f"Terminal=false\n"
            f"Type=Application\n"
            f"Categories=Network;WebBrowser;\n"
            f"StartupNotify=true\n",
            encoding="utf-8",
        )
        shortcut.chmod(0o755)
        ok(f"Atalho criado na área de trabalho: {shortcut}")

        wrapper = install_dir / "api" / "install" / "enxame-desktop"
        wrapper.write_text(
            f"#!/bin/bash\n"
            f"set -e\n"
            f"INSTALL_DIR=\"{install_dir}\"\n"
            f"ENV_FILE=\"{env_file}\"\n"
            f"PORT=\"8765\"\n"
            f"URL=\"http://localhost:${{PORT}}/\"\n"
            f"if ! pgrep -f \"run_enxame.py\" >/dev/null 2>&1; then\n"
            f"  echo \"Iniciando o Enxame em segundo plano (Web UI em $URL)...\"\n"
            f"  nohup /usr/bin/env python3 \"$INSTALL_DIR/run_enxame.py\" --no-browser >\"$INSTALL_DIR/enxame-nohup.log\" 2>&1 &\n"
            f"  for i in $(seq 1 30); do\n"
            f"    if curl -s --max-time 1 http://localhost:${{PORT}}/health >/dev/null 2>&1; then break; fi\n"
            f"    sleep 1\n"
            f"  done\n"
            f"else\n"
            f"  echo \"Enxame já está rodando em segundo plano.\"\n"
            f"fi\n"
            f"if command -v xdg-open >/dev/null 2>&1; then xdg-open \"$URL\" &\n"
            f"elif command -v sensible-browser >/dev/null 2>&1; then sensible-browser \"$URL\" &\n"
            f"elif command -v firefox >/dev/null 2>&1; then firefox \"$URL\" &\n"
            f"elif command -v chromium-browser >/dev/null 2>&1; then chromium-browser \"$URL\" &\n"
            f"elif command -v google-chrome >/dev/null 2>&1; then google-chrome \"$URL\" &\n"
            f"else echo \"Acesse manualmente: $URL\"; fi\n"
            f"exit 0\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
    else:
        # macOS: criar app bundle simples ou script
        shortcut = Path.home() / "Desktop" / "Enxame.command"
        shortcut.write_text(
            f"#!/bin/bash\n"
            f"INSTALL_DIR=\"{install_dir}\"\n"
            f"ENV_FILE=\"{env_file}\"\n"
            f"PORT=\"8765\"\n"
            f"URL=\"http://localhost:${{PORT}}/\"\n"
            f"if ! pgrep -f \"run_enxame.py\" >/dev/null 2>&1; then\n"
            f"  echo \"Iniciando o Enxame em segundo plano (Web UI em $URL)...\"\n"
            f"  nohup /usr/bin/env python3 \"$INSTALL_DIR/run_enxame.py\" --no-browser >\"$INSTALL_DIR/enxame-nohup.log\" 2>&1 &\n"
            f"  for i in $(seq 1 30); do\n"
            f"    if curl -s --max-time 1 http://localhost:${{PORT}}/health >/dev/null 2>&1; then break; fi\n"
            f"    sleep 1\n"
            f"  done\n"
            f"else\n"
            f"  echo \"Enxame já está rodando em segundo plano.\"\n"
            f"fi\n"
            f"open \"$URL\"\n"
            f"exit 0\n",
            encoding="utf-8",
        )
        shortcut.chmod(0o755)
        ok(f"Atalho criado na área de trabalho: {shortcut}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Instalador Unificado ENXAME (next-next-finish)")
    parser.add_argument("--auto", action="store_true", help="Instalação automática sem perguntas")
    parser.add_argument("--role", choices=["juiz", "bibliotecario", "agente", "auto"], default="auto")
    parser.add_argument("--boot", action="store_true", help="Iniciar junto ao boot")
    parser.add_argument("--no-boot", action="store_true", help="Não iniciar junto ao boot")
    parser.add_argument("--dir", type=Path, help="Pasta de instalação")
    parser.add_argument("--dry-run", action="store_true", help="Simular sem instalar")
    parser.add_argument("--simular", action="store_true", help="Alias para --dry-run")
    args = parser.parse_args()

    dry_run = args.dry_run or args.simular
    if dry_run:
        C.disable()

    sistema = detect_platform()
    if sistema == "unknown":
        erro("Sistema operacional não suportado.")
        return 1

    if not args.auto:
        banner("ENXAME — Instalador Unificado v1.0.0")
        print(f"{C.BOLD}Sistema detectado:{C.RESET} {sistema}")
        print(f"{C.BOLD}Usuário:{C.RESET} {getpass.getuser()}")
        print(f"{C.BOLD}Administrador/root:{C.RESET} {'sim' if is_admin() else 'não'}")
        print()
        if not confirm("Deseja continuar com a instalação?", default="s"):
            print("Instalação cancelada pelo usuário.")
            return 1

        passo(2, 6, "Pasta de instalação")
        default_dir = Path("/opt/enxame") if sistema in ("linux", "macos") else Path("C:\\Program Files\\Enxame")
        resp = input(f"Onde instalar o Enxame? [{default_dir}]: ").strip()
        install_dir = Path(resp) if resp else default_dir
        print()
        ok(f"Pasta de instalação: {install_dir}")

        passo(3, 6, "Iniciar junto ao boot")
        boot_default = "s" if is_admin() else "n"
        boot = confirm("Iniciar o Enxame automaticamente junto ao boot?", default=boot_default)
        if args.no_boot:
            boot = False
        print()
        ok(f"Iniciar junto ao boot: {'SIM' if boot else 'NÃO'}")

        passo(4, 6, "Função do node")
        role_resp = escolha(
            "Qual a função inicial deste node?",
            {
                "1": "Juiz — orquestração, validação e auditoria (porta 7700)",
                "2": "Bibliotecário — busca e gestão de conhecimento (porta 7701)",
                "3": "Agente — worker com todas as especialidades",
                "4": "Automático — deixar o Enxame decidir pelo hardware",
            },
            padrao="4",
        )
        role_map = {"1": "juiz", "2": "bibliotecario", "3": "agente", "4": "auto"}
        role = role_map[role_resp]
        print()
        ok(f"Função do node: {role}")
    else:
        install_dir = args.dir or (Path("/opt/enxame") if sistema in ("linux", "macos") else Path("C:\\Program Files\\Enxame"))
        boot = args.boot and not args.no_boot
        role = args.role

    if dry_run:
        print(f"\n{C.CYAN}[SIMULAR]{C.RESET} Instalaria em: {install_dir}")
        print(f"  Role: {role} | Boot: {boot} | Plataforma: {sistema}")
        print(f"  Nenhum arquivo foi modificado.\n")
        return 0

    passo(5, 6, "Copiando arquivos e configurando")
    if sistema == "windows":
        rc = instalar_windows(install_dir, install_dir / "config" / ".env", role, boot)
    else:
        rc = instalar_unix(install_dir, install_dir / "config" / ".env", role, boot, sistema)

    if rc != 0:
        erro("Falha durante a instalação.")
        return rc

    passo(6, 6, "Concluído")
    print()
    print(f"{C.BOLD}{C.GREEN}╔═════════════════════════════════════════════════════════════╗{C.RESET}")
    print(f"{C.BOLD}{C.GREEN}║           INSTALAÇÃO CONCLUÍDA COM SUCESSO!                ║{C.RESET}")
    print(f"{C.BOLD}{C.GREEN}╚═════════════════════════════════════════════════════════════╝{C.RESET}")
    print()
    print(f"  Pasta de instalação: {install_dir}")
    print(f"  Config:              {install_dir / 'config' / '.env'}")
    print(f"  Função do node:      {role}")
    print(f"  Iniciar junto ao boot: {'SIM' if boot else 'NÃO'}")
    print()
    print("Como usar:")
    print("  • Duplo-clique no atalho 'Enxame' na área de trabalho para")
    print("    iniciar/reiniciar o serviço e abrir o navegador.")
    print(f"  • Acesse também em: http://localhost:8765/ (Web UI)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())