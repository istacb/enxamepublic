from __future__ import annotations

from abc import ABC


class SpecialtyPlugin(ABC):
    """Contrato base para plugins de especialidade."""

    name: str = "generalista"
    version: str = "1.0.0"
    description: str = "Especialidade genérica"
    keywords: tuple[str, ...] = tuple()

    def match_score(self, text: str) -> float:
        text_l = text.lower()
        score = 0.0
        for kw in self.keywords:
            if kw.lower() in text_l:
                score += 1.0
        return score

    def system_prompt(self) -> str:
        return (
            "Você é um especialista técnico do ENXAME. "
            "Responda em português brasileiro com objetividade, precisão e estrutura clara."
        )

    def build_prompt(self, subtask: str, context: str | None = None) -> str:
        base = self.system_prompt()
        if context:
            return f"{base}\n\nContexto adicional:\n{context}\n\nTarefa:\n{subtask}"
        return f"{base}\n\nTarefa:\n{subtask}"
