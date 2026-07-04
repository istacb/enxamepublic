from __future__ import annotations

from .base import SpecialtyPlugin


class RedatorPlugin(SpecialtyPlugin):
    name = "redator"
    version = "1.0.0"
    description = "Especialista em escrita técnica, revisão e estrutura textual"
    keywords = (
        "texto",
        "artigo",
        "resumo",
        "redação",
        "revisão",
        "copy",
        "conteúdo",
        "parágrafo",
    )

    def system_prompt(self) -> str:
        return (
            "Você é um Redator Profissional do ENXAME. "
            "Escreva em pt-BR com clareza, coesão e adequação ao público. "
            "Priorize estrutura lógica e objetividade."
        )


PLUGIN_CLASS = RedatorPlugin
