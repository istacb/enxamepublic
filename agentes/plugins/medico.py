from __future__ import annotations

from .base import SpecialtyPlugin


class MedicoPlugin(SpecialtyPlugin):
    name = "medico"
    version = "1.0.0"
    description = "Especialista em orientação médica informativa e triagem textual"
    keywords = (
        "sintoma",
        "diagnóstico",
        "saúde",
        "tratamento",
        "doença",
        "medicamento",
        "clínico",
        "febre",
        "dor",
    )

    def system_prompt(self) -> str:
        return (
            "Você é um médico assistente textual do ENXAME. "
            "Forneça orientação informativa com linguagem clara em pt-BR, "
            "destaque sinais de gravidade e recomende avaliação presencial quando necessário. "
            "Não prescreva doses específicas sem ressalvas."
        )


PLUGIN_CLASS = MedicoPlugin
