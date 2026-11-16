"""Contratos do atalho pós-instalação "Abrir Enxame (WebUI)".

Cobre:
- `run_enxame.py`: mapeamento de host bind-all -> URL navegável, sonda
  `/health` (stdlib) e flags `--ensure-running`/`--open-only`;
- `bees.webui_shortcut`: renderizadores .bat/.command/.desktop, destinos por SO
  e install/remove herméticos (tmp_path).
"""

from __future__ import annotations

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from bees.webui_shortcut import (
    LINUX_DESKTOP_NAME,
    LINUX_ICON_NAME,
    MACOS_COMMAND_NAME,
    SHORTCUT_DISPLAY_NAME,
    WINDOWS_BAT_NAME,
    install_webui_shortcuts,
    remove_webui_shortcuts,
    render_linux_desktop,
    render_macos_command,
    render_windows_bat,
    shortcut_locations,
)

# ---------------------------------------------------------------------------
# run_enxame.py helpers (carregado por caminho: vive na raiz do repo)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_ENXAME_PATH = REPO_ROOT / "run_enxame.py"


def _load_run_enxame():
    spec = importlib.util.spec_from_file_location("run_enxame", RUN_ENXAME_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def launcher():
    return _load_run_enxame()


class TestBrowserUrl:
    @pytest.mark.parametrize(
        ("host", "expected"),
        [
            ("0.0.0.0", "http://localhost:8765"),
            ("::", "http://localhost:8765"),
            ("", "http://localhost:8765"),
            ("*", "http://localhost:8765"),
            ("127.0.0.1", "http://127.0.0.1:8765"),
            ("192.168.1.10", "http://192.168.1.10:8765"),
            ("::1", "http://[::1]:8765"),
        ],
    )
    def test_browser_url_for(self, launcher, host, expected):
        assert launcher.browser_url_for(host, 8765) == expected

    def test_probe_host_for(self, launcher):
        assert launcher.probe_host_for("0.0.0.0") == "127.0.0.1"
        assert launcher.probe_host_for("::") == "127.0.0.1"
        assert launcher.probe_host_for("10.0.0.5") == "10.0.0.5"

    def test_wildcard_hosts_constant_includes_bind_all(self, launcher):
        assert "0.0.0.0" in launcher.WILDCARD_HOSTS


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
        else:
            body = b"not found"
            self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture()
def health_server():
    server = HTTPServer(("127.0.0.1", 0), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestHealthProbe:
    def test_running_when_health_ok(self, launcher, health_server):
        assert launcher.is_enxame_running(health_server) is True

    def test_not_running_connection_refused(self, launcher, health_server):
        assert launcher.is_enxame_running(health_server + 20000) is False

    def test_wait_for_ready_immediately(self, launcher, health_server):
        assert launcher.wait_for_enxame(health_server, timeout=5) is True

    def test_wait_for_timeout(self, launcher, health_server):
        assert launcher.wait_for_enxame(health_server + 20000, timeout=1, interval=0.2) is False

    def test_port_param_flows_to_probe(self, launcher, monkeypatch):
        calls: dict = {}

        def fake_probe(port, host="127.0.0.1", timeout=2.0):
            calls["port"] = port
            calls["host"] = host
            return True

        monkeypatch.setattr(launcher, "is_enxame_running", fake_probe)
        opened: list = []
        monkeypatch.setattr(launcher.webbrowser, "open", opened.append)

        args = launcher.build_parser().parse_args(["--ensure-running", "--port", "9999"])
        assert launcher.EnxameLauncher(args).run() == 0
        assert calls == {"port": 9999, "host": "127.0.0.1"}
        assert opened == ["http://localhost:9999"]

    def test_ensure_running_already_up_opens_browser_only(self, launcher, monkeypatch):
        monkeypatch.setattr(launcher, "is_enxame_running", lambda *a, **k: True)
        opened: list = []
        monkeypatch.setattr(launcher.webbrowser, "open", opened.append)

        args = launcher.build_parser().parse_args(["--ensure-running"])
        assert launcher.EnxameLauncher(args).run() == 0
        assert opened == ["http://localhost:8765"]

    def test_open_only_without_server_returns_1(self, launcher, monkeypatch):
        monkeypatch.setattr(launcher, "is_enxame_running", lambda *a, **k: False)
        opened: list = []
        monkeypatch.setattr(launcher.webbrowser, "open", opened.append)

        args = launcher.build_parser().parse_args(["--open-only"])
        assert launcher.EnxameLauncher(args).run() == 1
        assert opened == []


# ---------------------------------------------------------------------------
# bees.webui_shortcut: renderizadores
# ---------------------------------------------------------------------------

class TestRenderers:
    def test_windows_bat_content(self):
        content = render_windows_bat(
            python_cmd="py",
            repo_dir="C:\\enxame",
            data_dir="C:\\enxame data",
            port=8888,
        )
        assert content.splitlines()[0] == "@echo off"
        assert "cd /d \"C:\\enxame\"" in content
        assert "py run_enxame.py --ensure-running" in content
        assert "--data-dir \"C:\\enxame data\"" in content
        assert "--port 8888" in content
        assert "if errorlevel 1 pause" in content

    def test_macos_command_content(self, tmp_path):
        repo = tmp_path / "enxame repo"
        content = render_macos_command(
            python_cmd="python3", repo_dir=repo, data_dir=tmp_path / "data space"
        )
        assert content.splitlines()[0] == "#!/bin/bash"
        assert "run_enxame.py --ensure-running" in content
        assert "--port 8765" in content
        # Caminhos com espaço precisam de quoting shell
        assert "cd " in content and ("'" in content or "\\" in content)

    def test_linux_desktop_content(self):
        content = render_linux_desktop(
            python_cmd="python3",
            repo_dir="/opt/enxame",
            data_dir="/home/u/.enxame/bee",
            port=8765,
            icon_path="/home/u/.local/share/icons/enxame-webui.svg",
        )
        assert "[Desktop Entry]" in content
        assert f"Name={SHORTCUT_DISPLAY_NAME}" in content
        assert "run_enxame.py --ensure-running" in content
        assert "Icon=/home/u/.local/share/icons/enxame-webui.svg" in content
        assert "Terminal=true" in content

    def test_display_name_ptbr(self):
        assert SHORTCUT_DISPLAY_NAME == "Abrir Enxame (WebUI)"


# ---------------------------------------------------------------------------
# bees.webui_shortcut: destinos por SO (injetados, sem tocar no HOME real)
# ---------------------------------------------------------------------------

class TestLocations:
    def test_windows_locations(self, tmp_path):
        home = tmp_path / "home"
        appdata = tmp_path / "appdata"
        locs = shortcut_locations("windows", home=home, env={"APPDATA": str(appdata)})
        assert locs["start_menu_dir"] == (
            appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Enxame"
        )
        assert str(locs["desktop_dir"]).startswith(str(home))

    def test_darwin_locations(self, tmp_path):
        locs = shortcut_locations("darwin", home=tmp_path)
        assert locs["applications_dir"] == Path("/Applications/Enxame")
        assert locs["desktop_dir"] == tmp_path / "Desktop"

    def test_linux_locations(self, tmp_path):
        locs = shortcut_locations("linux", home=tmp_path)
        assert locs["applications_dir"] == tmp_path / ".local" / "share" / "applications"
        assert locs["icons_dir"] == tmp_path / ".local" / "share" / "icons"
        assert locs["desktop_dir"] == tmp_path / "Desktop"


# ---------------------------------------------------------------------------
# bees.webui_shortcut: install/remove herméticos
# ---------------------------------------------------------------------------

def _fake_locations(os_name: str, root: Path) -> dict:
    return {
        key: (root / key if path is not None else None)
        for key, path in shortcut_locations(os_name).items()
    }


class TestInstallRemove:
    def test_install_windows(self, tmp_path):
        locs = _fake_locations("windows", tmp_path)
        created = install_webui_shortcuts(
            "windows",
            repo_dir=tmp_path / "repo",
            data_dir=tmp_path / "data",
            locations=locs,
        )
        assert created == [locs["start_menu_dir"] / WINDOWS_BAT_NAME,
                            locs["desktop_dir"] / WINDOWS_BAT_NAME]
        for path in created:
            assert path.is_file()
            assert "run_enxame.py --ensure-running" in path.read_text(encoding="utf-8")

        removed = remove_webui_shortcuts("windows", locations=locs)
        assert set(removed) == set(created)
        assert not any(p.exists() for p in created)

    def test_install_darwin_executable(self, tmp_path):
        import os as _os
        import stat as _stat

        locs = _fake_locations("darwin", tmp_path)
        created = install_webui_shortcuts(
            "darwin",
            repo_dir=tmp_path / "repo",
            data_dir=tmp_path / "data",
            locations=locs,
        )
        assert [p.name for p in created] == [MACOS_COMMAND_NAME, MACOS_COMMAND_NAME]
        for path in created:
            mode = _os.stat(path).st_mode
            assert mode & _stat.S_IXUSR, f"{path} deve ser executável"
        remove_webui_shortcuts("darwin", locations=locs)
        assert not any(p.exists() for p in created)

    def test_install_linux_copies_icon_and_desktop(self, tmp_path):
        web_dir = tmp_path / "repo" / "web"
        web_dir.mkdir(parents=True)
        fake_icon = web_dir / "icon.svg"
        fake_icon.write_text("<svg></svg>", encoding="utf-8")

        locs = _fake_locations("linux", tmp_path)
        created = install_webui_shortcuts(
            "linux",
            repo_dir=tmp_path / "repo",
            data_dir=tmp_path / "data",
            locations=locs,
        )
        assert [p.name for p in created] == [LINUX_DESKTOP_NAME, LINUX_DESKTOP_NAME]
        installed_icon = locs["icons_dir"] / LINUX_ICON_NAME
        assert installed_icon.is_file()
        assert created[0].read_text(encoding="utf-8").find(str(installed_icon)) != -1

        removed = remove_webui_shortcuts("linux", locations=locs)
        assert installed_icon in removed
        assert not installed_icon.exists()

    def test_install_linux_missing_icon_uses_fallback(self, tmp_path):
        locs = _fake_locations("linux", tmp_path)
        created = install_webui_shortcuts(
            "linux",
            repo_dir=tmp_path / "repo-sem-icone",
            data_dir=tmp_path / "data",
            locations=locs,
        )
        entry = created[0].read_text(encoding="utf-8")
        assert "Icon=preferences-system-network" in entry

    def test_remove_missing_is_noop(self, tmp_path):
        locs = _fake_locations("linux", tmp_path)
        assert remove_webui_shortcuts("linux", locations=locs) == []

    def test_no_desktop_copy_opt_out(self, tmp_path):
        locs = _fake_locations("linux", tmp_path)
        created = install_webui_shortcuts(
            "linux",
            repo_dir=tmp_path / "repo",
            data_dir=tmp_path / "data",
            copy_to_desktop=False,
            locations=locs,
        )
        assert created == [locs["applications_dir"] / LINUX_DESKTOP_NAME]
