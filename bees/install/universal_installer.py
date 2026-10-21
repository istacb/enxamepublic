#!/usr/bin/env python3
"""Compatibilidade: este arquivo NÃO é mais um instalador paralelo.

`universal_installer.py` era uma segunda implementação completa (1300 linhas)
que competia com `install-bee-smart.py`. Duas consequências práticas:

* A camada de Ollama daqui tinha os bugs que já haviam sido corrigidos no outro
  instalador: `curl ... | sh` sem conferir o código de retorno (falso sucesso),
  instalação Windows sem winget e sem atualizar o PATH, verificação via
  `shutil.which` que falha logo após instalar no Windows, e
  `systemctl --user start ollama` quando o instalador oficial cria um serviço de
  SISTEMA.
* Qualquer correção precisava ser feita duas vezes, e geralmente era feita só
  numa delas.

A implementação única é `bees/install/bee_installer.py`. Este arquivo continua
existindo por dois motivos legítimos:

1. `build_installer.py` e `enxame_installer.spec` o usam como entry point do
   PyInstaller (.app/.dmg) e do AppImage — agora esses pacotes rodam o
   instalador unificado em vez de uma cópia desatualizada.
2. Testes e código antigo importam daqui os helpers de configuração de cluster,
   que hoje vivem em `bees/install/cluster_setup.py` (cópia única).
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
# <repo>/bees/install -> <repo>/bees -> <repo>
_REPO_ROOT = _SCRIPT_DIR.parents[1]
for _caminho in (str(_REPO_ROOT), str(_SCRIPT_DIR.parent)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

# Import RELATIVO primeiro. Importar `bees.install.cluster_setup` daqui criaria
# uma segunda instância do módulo quando o chamador chegou por outra raiz
# (`install.universal_installer`), com globals próprios: um patch de teste numa
# instância não afetaria a outra e a descoberta mDNS real vazaria para dentro do
# teste. Assim a instância usada é sempre a mesma pela qual o chamador entrou.
try:
    from . import cluster_setup as _cluster_setup
    from . import bee_setup as _bee_setup
except ImportError:  # pragma: no cover - módulo solto / empacotado
    try:
        from bees.install import cluster_setup as _cluster_setup  # type: ignore[no-redef]
        from bees.install import bee_setup as _bee_setup  # type: ignore[no-redef]
    except ImportError:
        import cluster_setup as _cluster_setup  # type: ignore[no-redef]
        import bee_setup as _bee_setup  # type: ignore[no-redef]

# --- API de configuração de cluster (cópia única em cluster_setup.py) ---
write_bee_config = _cluster_setup.write_bee_config
bee_config_path = _cluster_setup.bee_config_path
enable_cluster_mode = _cluster_setup.enable_cluster_mode
disable_cluster_mode = _cluster_setup.disable_cluster_mode
set_cluster_mode = _cluster_setup.set_cluster_mode
read_cluster_mode = _cluster_setup.read_cluster_mode
discover_local_peers = _cluster_setup.discover_local_peers
prompt_cluster_optin = _cluster_setup.prompt_cluster_optin
set_node_id = _cluster_setup.set_node_id
default_data_dir = _cluster_setup.default_data_dir
resolve_data_dir = _cluster_setup.resolve_data_dir

# --- Etapa final (config.json, atalhos, serviço) ---
configure_bee = _bee_setup.configure_bee
create_shortcuts = _bee_setup.create_bee_shortcuts
create_bee_shortcuts = _bee_setup.create_bee_shortcuts
install_bee_service = _bee_setup.install_bee_service
bee_start_command = _bee_setup.bee_start_command


def main() -> int:
    """Delega ao instalador único.

    Mantém o contrato de entry point esperado pelo PyInstaller/AppImage.
    """
    try:
        from .bee_installer import main as _main_unificado
    except ImportError:  # pragma: no cover
        try:
            from bees.install.bee_installer import main as _main_unificado  # type: ignore[no-redef]
        except ImportError:
            import bee_installer as _modulo  # type: ignore[no-redef]

            _main_unificado = _modulo.main
    resultado = _main_unificado()
    return 0 if resultado is None else int(resultado)


if __name__ == "__main__":
    sys.exit(main())
