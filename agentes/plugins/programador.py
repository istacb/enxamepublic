from __future__ import annotations

from .base import SpecialtyPlugin


class ProgramadorPlugin(SpecialtyPlugin):
    name = "programador"
    version = "1.0.0"
    description = "Especialista em desenvolvimento de software, depuração e arquitetura"
    keywords = (
        "código",
        "python",
        "bug",
        "api",
        "algoritmo",
        "refator",
        "docker",
        "teste",
        "backend",
        "frontend",
    )

    def system_prompt(self) -> str:
        return (
            "Você é um Programador Sênior do ENXAME. "
            "Entregue soluções práticas, seguras e testáveis em pt-BR. "
            "Quando necessário, detalhe passos e inclua exemplos de código concisos."
        )


PLUGIN_CLASS = ProgramadorPlugin
