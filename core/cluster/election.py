from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class NodeBenchmark:
    node_id: str
    score: float
    role_hint: str = "agent"


@dataclass(slots=True)
class ElectionResult:
    juiz_node_id: str
    bibliotecaria_node_id: str
    agent_node_ids: list[str]
    ranking: list[NodeBenchmark]
    quorum: bool


class ClusterElection:
    """Eleição simplificada estilo bully com votação por maioria."""

    def rank(self, nodes: list[NodeBenchmark]) -> list[NodeBenchmark]:
        ordered = sorted(nodes, key=lambda n: n.score, reverse=True)
        if ordered:
            ordered[0].role_hint = "juiz"
        if len(ordered) > 1:
            ordered[-1].role_hint = "bibliotecaria"
        for item in ordered[1:-1]:
            item.role_hint = "agente"
        return ordered

    def run(self, nodes: list[NodeBenchmark], total_votes: int, positive_votes: int) -> ElectionResult | None:
        if not nodes:
            return None
        ranking = self.rank(nodes)
        juiz = ranking[0].node_id
        bibliotecaria = ranking[-1].node_id
        agents = [n.node_id for n in ranking[1:-1]]
        quorum = positive_votes >= max(1, (total_votes // 2) + 1)
        return ElectionResult(
            juiz_node_id=juiz,
            bibliotecaria_node_id=bibliotecaria,
            agent_node_ids=agents,
            ranking=ranking,
            quorum=quorum,
        )
