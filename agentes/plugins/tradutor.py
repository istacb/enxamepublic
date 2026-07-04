from __future__ import annotations

from .base import SpecialtyPlugin


class TradutorPlugin(SpecialtyPlugin):
    name = "tradutor"
    version = "1.0.0"
    description = "Especialista em tradução e adaptação multilíngue"
    keywords = (
        "traduza",
        "traduzir",
        "tradução",
        "inglês",
        "espanhol",
        "francês",
        "idioma",
        "localização",
    )

    def system_prompt(self) -> str:
        return (
            "Você é um Tradutor Técnico do ENXAME. "
            "Traduza com fidelidade semântica, naturalidade e preservação de contexto. "
            "Explique ambiguidades quando necessário."
        )


PLUGIN_CLASS = TradutorPlugin
