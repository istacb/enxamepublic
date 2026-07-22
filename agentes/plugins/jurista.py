from __future__ import annotations

from .base import SpecialtyPlugin


class JuristaPlugin(SpecialtyPlugin):
    name = "jurista"
    version = "1.0.0"
    description = "Especialista em análise jurídica e interpretação normativa"
    keywords = (
        "lei",
        "jurídico",
        "contrato",
        "norma",
        "regulamentação",
        "compliance",
        "direito",
        "cláusula",
    )

    def system_prompt(self) -> str:
        return (
            "Você é um Jurista do ENXAME. "
            "Forneça análise técnica em pt-BR com base em princípios jurídicos gerais, "
            "indicando limites e necessidade de validação profissional local."
        )


PLUGIN_CLASS = JuristaPlugin
