from __future__ import annotations

from .base import SpecialtyPlugin


class EngenheiroPlugin(SpecialtyPlugin):
    name = "engenheiro"
    version = "1.0.0"
    description = "Especialista em engenharia de sistemas, processos e infraestrutura"
    keywords = (
        "engenharia",
        "infraestrutura",
        "projeto",
        "sistema",
        "escala",
        "desempenho",
        "capacidade",
        "confiabilidade",
    )

    def system_prompt(self) -> str:
        return (
            "Você é um Engenheiro de Sistemas do ENXAME. "
            "Responda com foco em viabilidade técnica, trade-offs, confiabilidade e operação."
        )


PLUGIN_CLASS = EngenheiroPlugin
