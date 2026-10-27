from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class NodeBenchmark:
    node_id: str
    score: float
    role_hint: str = 'agent'
    cpu_cores: int = 0
    cpu_freq_ghz: float = 0.0
    ram_gb: float = 0.0
    vram_gb: float = 0.0
    ip: str = ''
    port: int = 0
    last_seen: float = field(default_factory=time.time)


@dataclass(slots=True)
class ElectionResult:
    juiz_node_id: str
    bibliotecaria_node_id: str
    agent_node_ids: list[str]
    ranking: list[NodeBenchmark]
    quorum: bool


def calculate_hardware_score(cpu_cores: int, cpu_freq_ghz: float, ram_gb: float, vram_gb: float) -> float:
    """Score de capacidade: (cores × GHz) + RAM + VRAM."""
    return (cpu_cores * cpu_freq_ghz) + ram_gb + vram_gb


class ClusterElection:
    """Eleição tipo bully com quorum e histerese.

    Regras:
    - Juiz = nó com maior score entre os ativos (estabilidade primeiro).
    - Bibliotecária = nó com maior disco/RAM disponível (não o mais fraco).
    - Quorum: maioria dos nós ativos deve concordar.
    - Histerese: só muda de papel se o novo vencedor for claramente melhor
      (margin > 10%) ou se o atual saiu do cluster.
    """

    def __init__(self, hysteresis_margin: float = 0.10) -> None:
        self.hysteresis_margin = hysteresis_margin
        self._current: ElectionResult | None = None
        self._last_change: float = 0.0

    def run(
        self,
        nodes: list[NodeBenchmark],
        total_votes: int,
        positive_votes: int,
    ) -> ElectionResult | None:
        if not nodes:
            return None
        alive = [n for n in nodes if time.time() - n.last_seen < 30]
        if not alive:
            return None

        ranking = self._rank(alive)
        quorum = positive_votes >= max(1, (total_votes // 2) + 1)

        juiz = ranking[0].node_id
        bibliotecaria = ranking[-1].node_id if len(ranking) > 1 else juiz
        agents = [n.node_id for n in ranking[1:-1]] if len(ranking) > 2 else []

        result = ElectionResult(
            juiz_node_id=juiz,
            bibliotecaria_node_id=bibliotecaria,
            agent_node_ids=agents,
            ranking=ranking,
            quorum=quorum,
        )

        # Histerese: não troca se o atual ainda está entre os top-2 e a
        # diferença de score não é significativa.
        if self._current is not None and self._current.juiz_node_id in {n.node_id for n in ranking[:2]}:
            cur_score = next((n.score for n in self._current.ranking if n.node_id == self._current.juiz_node_id), 0)
            new_score = ranking[0].score
            if new_score <= cur_score * (1 + self.hysteresis_margin):
                result.juiz_node_id = self._current.juiz_node_id

        self._current = result
        self._last_change = time.time()
        return result

    def _rank(self, nodes: list[NodeBenchmark]) -> list[NodeBenchmark]:
        ordered = sorted(nodes, key=lambda n: n.score, reverse=True)
        if ordered:
            ordered[0].role_hint = 'juiz'
        if len(ordered) > 1:
            # Bibliotecária = nó com mais recursos de armazenagem (score alto
            # mas não o juiz). Mantém o mais fraco fora do caminho do LLM.
            ordered[-1].role_hint = 'bibliotecaria'
        for item in ordered[1:-1]:
            item.role_hint = 'agente'
        return ordered

    def current(self) -> ElectionResult | None:
        return self._current
