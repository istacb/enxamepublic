#!/usr/bin/env python3
"""Instalador do ENXAME — ponto de entrada documentado.

A implementação ÚNICA mora em `bees/install/bee_installer.py`. Este arquivo
existe só para que o comando da documentação funcione a partir da raiz do
repositório, sem duplicar nada:

    python3 install-bee-smart.py --auto

Houve 22 arquivos de instalação e 5 comandos documentados diferentes, apontando
para 3 stacks distintas. Era a causa raiz de "instalei e nada funciona": cada
caminho instalava uma coisa diferente. Agora todos convergem para cá.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from bees.install.bee_installer import main
except ImportError as exc:  # pragma: no cover - só em checkout incompleto
    sys.stderr.write(
        "Não consegui carregar bees/install/bee_installer.py.\n"
        f"Erro: {exc}\n"
        "Verifique se você está na raiz do repositório clonado (o diretório que\n"
        "contém bees/, core/ e web/).\n"
    )
    sys.exit(2)

if __name__ == "__main__":
    sys.exit(main())
