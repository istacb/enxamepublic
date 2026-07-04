from __future__ import annotations

from .base import SpecialtyPlugin


class MatematicoPlugin(SpecialtyPlugin):
    name = "matematico"
    version = "1.0.0"
    description = "Especialista em matemática aplicada, estatística e lógica"
    keywords = (
        "equação",
        "cálculo",
        "integral",
        "derivada",
        "estatística",
        "probabilidade",
        "álgebra",
        "teorema",
    )

    def system_prompt(self) -> str:
        return (
            "Você é um Matemático do ENXAME. "
            "Explique raciocínio de forma rigorosa e didática em pt-BR, "
            "mostrando fórmulas e etapas essenciais de resolução."
        )


PLUGIN_CLASS = MatematicoPlugin
