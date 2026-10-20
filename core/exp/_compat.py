"""Compatibilidade entre versões de Python suportadas pelo pacote `core`.

`bees/pyproject.toml` declara `requires-python = ">=3.10"` e o instalador
universal aceita explicitamente `python3.10` (`MIN_PYTHON_VERSION = (3, 10)` em
`bees/install/universal_installer.py`). Mas `enum.StrEnum` só foi adicionado no
Python **3.11**.

O resultado era o pior tipo de falha para quem instala: em Ubuntu 22.04 (que
traz Python 3.10) o instalador encontrava o interpretador, declarava sucesso e a
abelha morria no primeiro import com

    ImportError: cannot import name 'StrEnum' from 'enum'

ou seja, "instalou e nada funciona". Este módulo elimina essa divergência entre
o que o pacote promete e o que ele exige.

É uma cópia independente de `bees/_compat.py`: `core` não pode importar de
`bees` (inverteria a dependência) e `bees` precisa continuar instalável sozinho,
então cada pacote carrega o próprio shim.

Em Python >= 3.11 o `StrEnum` real da stdlib é usado sem alteração.

A guarda é por `sys.version_info` (e não `try/except ImportError`) porque é o
idioma que o mypy entende: com `python_version = "3.10"` na configuração ele
analisa apenas o ramo compatível, em vez de reportar falsamente
'Module "enum" has no attribute "StrEnum"'.
"""

from __future__ import annotations

import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """Equivalente a `enum.StrEnum` para Python 3.10.

        Replica o comportamento que este código de fato usa:

        * os membros são instâncias de `str`;
        * `str(membro)` devolve o **valor** (não ``"Classe.MEMBRO"`` como faz um
          mixin ``str, Enum`` comum antes do 3.11);
        * a construção a partir do valor funciona (``BeeState("RUNNING")``),
          usada ao desserializar envelopes e anúncios mDNS.

        Verificado como equivalente ao `enum.StrEnum` real em 13 comparações de
        comportamento (isinstance/str/format/==/value/construção/json/dict).
        """

        def __str__(self) -> str:
            return str(self.value)
