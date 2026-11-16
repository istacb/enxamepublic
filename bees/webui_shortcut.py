#!/usr/bin/env python3
"""
bees.webui_shortcut — Atalho pós-instalação "Abrir Enxame (WebUI)"
==================================================================
Gera o atalho de 1 clique que abre a Colmeia no navegador:

- Windows: ``Abrir Enxame WebUI.bat`` (Menu Iniciar + Desktop)
- macOS: ``Abrir Enxame WebUI.command`` (/Applications/Enxame + Desktop)
- Linux: ``enxame-webui.desktop`` (menu de aplicações + Desktop)

O atalho executa ``run_enxame.py --ensure-running``: se o Enxame já estiver
rodando (serviço, terminal ou outra sessão), só abre o navegador; senão,
sobe o kernel e abre a WebUI quando `/health` responder.

Só usa stdlib. Caminhos de destino são injetáveis (`locations=`) para testes
herméticos e para desinstaladores (`remove_webui_shortcuts`).
"""

from __future__ import annotations

import contextlib
import os
import shlex
import shutil
import subprocess
from pathlib import Path

SHORTCUT_DISPLAY_NAME = "Abrir Enxame (WebUI)"
WINDOWS_BAT_NAME = "Abrir Enxame WebUI.bat"
MACOS_COMMAND_NAME = "Abrir Enxame WebUI.command"
LINUX_DESKTOP_NAME = "enxame-webui.desktop"
LINUX_ICON_NAME = "enxame-webui.svg"
LINUX_ICON_FALLBACK = "preferences-system-network"
DEFAULT_PORT = 8765


# ============================================================================
# Renderizadores puros (conteúdo dos atalhos)
# ============================================================================

def _bat_quote(path: str | Path) -> str:
    """Aspas duplas defensivas para batch (remove quebras e aspas internas)."""
    clean = str(path).replace('"', "").replace("\r", "").replace("\n", "")
    return f'"{clean}"'


def render_windows_bat(
    *,
    python_cmd: str,
    repo_dir: str | Path,
    data_dir: str | Path,
    port: int = DEFAULT_PORT,
) -> str:
    """Conteúdo do `.bat` do Menu Iniciar/Desktop (fecha sozinho se OK)."""
    return (
        "@echo off\n"
        f"title {SHORTCUT_DISPLAY_NAME}\n"
        f"cd /d {_bat_quote(repo_dir)}\n"
        f"{python_cmd} run_enxame.py --ensure-running "
        f"--data-dir {_bat_quote(data_dir)} --port {port}\n"
        "if errorlevel 1 pause\n"
    )


def render_macos_command(
    *,
    python_cmd: str,
    repo_dir: str | Path,
    data_dir: str | Path,
    port: int = DEFAULT_PORT,
) -> str:
    """Conteúdo do `.command` clicável no Finder/Terminal."""
    return (
        "#!/bin/bash\n"
        f"cd {shlex.quote(str(repo_dir))} || exit 1\n"
        f"exec {python_cmd} run_enxame.py --ensure-running "
        f"--data-dir {shlex.quote(str(data_dir))} --port {port}\n"
    )


def render_linux_desktop(
    *,
    python_cmd: str,
    repo_dir: str | Path,
    data_dir: str | Path,
    port: int = DEFAULT_PORT,
    icon_path: str | Path = LINUX_ICON_FALLBACK,
) -> str:
    """Conteúdo do `.desktop` (menu de aplicações + Desktop)."""
    inner = (
        f"cd {shlex.quote(str(repo_dir))} "
        f"&& exec {python_cmd} run_enxame.py --ensure-running "
        f"--data-dir {shlex.quote(str(data_dir))} --port {port}"
    )
    return (
        "[Desktop Entry]\n"
        "Version=1.0\n"
        "Type=Application\n"
        f"Name={SHORTCUT_DISPLAY_NAME}\n"
        "Comment=Abre a Colmeia no navegador (sobe o Enxame local se preciso)\n"
        f"Exec=bash -c {shlex.quote(inner)}\n"
        f"Icon={icon_path}\n"
        "Terminal=true\n"
        "Categories=Network;Utility;\n"
        "StartupNotify=true\n"
    )


# ============================================================================
# Destinos por SO
# ============================================================================

def _windows_desktop_dir(home: Path) -> Path:
    """Pasta Desktop real no Windows (respeita nome localizado via registro)."""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "Desktop")
            if value:
                return Path(value)
    except Exception:
        pass
    return home / "Desktop"


def shortcut_locations(
    os_name: str,
    *,
    home: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Path | None]:
    """Destinos padrão dos atalhos WebUI por SO (`home`/`env` injetáveis)."""
    home = Path(home) if home is not None else Path.home()
    env = env if env is not None else os.environ
    if os_name == "windows":
        appdata = Path(env.get("APPDATA", str(home / "AppData" / "Roaming")))
        return {
            "start_menu_dir": (
                appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Enxame"
            ),
            "desktop_dir": _windows_desktop_dir(home),
            "applications_dir": None,
            "icons_dir": None,
        }
    if os_name == "darwin":
        return {
            "start_menu_dir": None,
            "desktop_dir": home / "Desktop",
            "applications_dir": Path("/Applications/Enxame"),
            "icons_dir": None,
        }
    # Linux e demais unix
    return {
        "start_menu_dir": None,
        "desktop_dir": home / "Desktop",
        "applications_dir": home / ".local" / "share" / "applications",
        "icons_dir": home / ".local" / "share" / "icons",
    }


def _install_linux_icon(
    icon_src: str | Path | None,
    icons_dir: Path | None,
    repo_dir: Path,
) -> str:
    """Instala `web/icon.svg` em `~/.local/share/icons` (fallbacks inclusos)."""
    candidates: list[Path] = []
    if icon_src:
        candidates.append(Path(icon_src))
    candidates.append(repo_dir / "web" / "icon.svg")
    src = next((c for c in candidates if c.is_file()), None)
    if src is not None and icons_dir is not None:
        try:
            icons_dir.mkdir(parents=True, exist_ok=True)
            dest = icons_dir / LINUX_ICON_NAME
            shutil.copyfile(src, dest)
            return str(dest)
        except OSError:
            pass
    if src is not None:
        return str(src)
    return LINUX_ICON_FALLBACK


def _mark_trusted_desktop_entry(desktop_file: Path) -> None:
    """Marca o `.desktop` como confiável no GNOME (silencioso se indisponível)."""
    with contextlib.suppress(OSError):
        desktop_file.chmod(0o755)
    if not shutil.which("gio"):
        return
    with contextlib.suppress(Exception):
        subprocess.run(
            ["gio", "set", str(desktop_file), "metadata::trusted", "true"],
            capture_output=True,
            timeout=10,
            check=False,
        )


# ============================================================================
# Instalação / remoção
# ============================================================================

def install_webui_shortcuts(
    os_name: str,
    *,
    repo_dir: str | Path,
    data_dir: str | Path,
    port: int = DEFAULT_PORT,
    python_cmd: str = "python3",
    copy_to_desktop: bool = True,
    icon_src: str | Path | None = None,
    locations: dict[str, Path | None] | None = None,
) -> list[Path]:
    """Cria o atalho "Abrir Enxame (WebUI)". Devolve os caminhos criados."""
    locs = locations or shortcut_locations(os_name)
    repo_dir = Path(repo_dir)
    created: list[Path] = []

    if os_name == "windows":
        start_menu = locs["start_menu_dir"]
        assert start_menu is not None
        start_menu.mkdir(parents=True, exist_ok=True)
        bat = start_menu / WINDOWS_BAT_NAME
        content = render_windows_bat(
            python_cmd=python_cmd, repo_dir=repo_dir, data_dir=data_dir, port=port
        )
        bat.write_text(content, encoding="utf-8")
        created.append(bat)
        if copy_to_desktop and locs["desktop_dir"]:
            desk = locs["desktop_dir"]
            desk.mkdir(parents=True, exist_ok=True)
            desk_bat = desk / WINDOWS_BAT_NAME
            desk_bat.write_text(content, encoding="utf-8")
            created.append(desk_bat)
        return created

    if os_name == "darwin":
        apps_dir = locs["applications_dir"]
        assert apps_dir is not None
        apps_dir.mkdir(parents=True, exist_ok=True)
        content = render_macos_command(
            python_cmd=python_cmd, repo_dir=repo_dir, data_dir=data_dir, port=port
        )
        cmd = apps_dir / MACOS_COMMAND_NAME
        cmd.write_text(content, encoding="utf-8")
        cmd.chmod(0o755)
        created.append(cmd)
        if copy_to_desktop and locs["desktop_dir"]:
            desk = locs["desktop_dir"]
            desk.mkdir(parents=True, exist_ok=True)
            desk_cmd = desk / MACOS_COMMAND_NAME
            desk_cmd.write_text(content, encoding="utf-8")
            desk_cmd.chmod(0o755)
            created.append(desk_cmd)
        return created

    # Linux e demais unix: .desktop no menu + cópia no Desktop
    apps_dir = locs["applications_dir"]
    assert apps_dir is not None
    icon_path = _install_linux_icon(icon_src, locs["icons_dir"], repo_dir)
    content = render_linux_desktop(
        python_cmd=python_cmd,
        repo_dir=repo_dir,
        data_dir=data_dir,
        port=port,
        icon_path=icon_path,
    )
    apps_dir.mkdir(parents=True, exist_ok=True)
    entry = apps_dir / LINUX_DESKTOP_NAME
    entry.write_text(content, encoding="utf-8")
    entry.chmod(0o755)
    created.append(entry)
    if copy_to_desktop and locs["desktop_dir"]:
        desk = locs["desktop_dir"]
        desk.mkdir(parents=True, exist_ok=True)
        desk_entry = desk / LINUX_DESKTOP_NAME
        desk_entry.write_text(content, encoding="utf-8")
        _mark_trusted_desktop_entry(desk_entry)
        created.append(desk_entry)
    return created


def remove_webui_shortcuts(
    os_name: str,
    *,
    locations: dict[str, Path | None] | None = None,
) -> list[Path]:
    """Remove os atalhos WebUI (para desinstaladores). Devolve os removidos."""
    locs = locations or shortcut_locations(os_name)
    targets: list[Path] = []
    if os_name == "windows":
        if locs["start_menu_dir"]:
            targets.append(locs["start_menu_dir"] / WINDOWS_BAT_NAME)
        if locs["desktop_dir"]:
            targets.append(locs["desktop_dir"] / WINDOWS_BAT_NAME)
    elif os_name == "darwin":
        if locs["applications_dir"]:
            targets.append(locs["applications_dir"] / MACOS_COMMAND_NAME)
        if locs["desktop_dir"]:
            targets.append(locs["desktop_dir"] / MACOS_COMMAND_NAME)
    else:
        if locs["applications_dir"]:
            targets.append(locs["applications_dir"] / LINUX_DESKTOP_NAME)
        if locs["desktop_dir"]:
            targets.append(locs["desktop_dir"] / LINUX_DESKTOP_NAME)
        if locs["icons_dir"]:
            targets.append(locs["icons_dir"] / LINUX_ICON_NAME)

    removed: list[Path] = []
    for target in targets:
        try:
            if target.is_file():
                target.unlink()
                removed.append(target)
        except OSError:
            pass
    return removed
