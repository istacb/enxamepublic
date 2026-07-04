from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import WebSocket

from core.cluster import ClusterElection, NodeBenchmark
from core.exp.envelope import EXPEnvelope, EXPNode
from core.exp.security import EXPSecurity
from core.exp.types import EXPMessageType
from core.ollama.client import OllamaClient, OllamaError, OllamaGenerateRequest


@dataclass
class AgentConnection:
    node: EXPNode
    websocket: WebSocket
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active_tasks: int = 0
    capabilities: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    specialties: list[str] = field(default_factory=list)
    max_concurrency: int = 1
    queue_max: int = 0
    queue_size: int = 0
    utilization: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)
    fail_count: int = 0
    benchmark_score: float = 0.0
    benchmark: dict[str, Any] = field(default_factory=dict)
    cluster_role: str = "agente"


@dataclass
class TaskState:
    task_id: str
    prompt: str
    status: str = "queued"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    result: str | None = None
    error: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)


class JuizService:
    def __init__(self, node_id: str, ollama_url: str, security: EXPSecurity) -> None:
        self.node = EXPNode(node_id=node_id, role="juiz", address=None)
        self.ollama = OllamaClient(ollama_url)
        self.security = security
        self.agents: dict[str, AgentConnection] = {}
        self.tasks: dict[str, TaskState] = {}
        self.pending_subtasks: dict[str, asyncio.Future[str]] = {}
        self.pending_role_acks: dict[str, asyncio.Future[bool]] = {}
        self.agent_query_cache: dict[str, dict[str, Any]] = {}
        self.election = ClusterElection()
        self.election_candidates: dict[str, NodeBenchmark] = {}
        self.election_votes: dict[str, bool] = {}
        self.current_roles: dict[str, str] = {}
        self.zim_distribution: dict[str, list[str]] = {}
        self.lock = asyncio.Lock()
        self.agent_timeout = timedelta(seconds=20)

    async def _emit(self, task: TaskState, event: str, data: dict[str, Any]) -> None:
        payload = {"event": event, **data, "timestamp": datetime.now(timezone.utc).isoformat()}
        task.events.append(payload)
        task.updated_at = datetime.now(timezone.utc)

    async def register_agent(self, envelope: EXPEnvelope, websocket: WebSocket) -> EXPEnvelope:
        node = envelope.source
        payload = envelope.payload
        capacity = payload.get("capacity", {}) if isinstance(payload.get("capacity"), dict) else {}

        benchmark = payload.get("benchmark", {}) if isinstance(payload.get("benchmark"), dict) else {}
        benchmark_score = float(benchmark.get("overall_score", 0.0))
        cluster_role = str(payload.get("cluster_role", "agente")).strip() or "agente"

        conn = AgentConnection(
            node=node,
            websocket=websocket,
            capabilities=[str(v) for v in payload.get("capabilities", [])],
            models=[str(v) for v in payload.get("models", [])],
            specialties=[str(v) for v in payload.get("specialties", [])],
            max_concurrency=max(1, int(capacity.get("max_concurrency", 1))),
            queue_max=max(0, int(capacity.get("queue_max", 0))),
            metrics=payload.get("metrics", {}),
            benchmark=benchmark,
            benchmark_score=benchmark_score,
            cluster_role=cluster_role,
        )
        self.agents[node.node_id] = conn
        return EXPEnvelope(
            source=self.node,
            target=node,
            correlation_id=envelope.msg_id,
            type=EXPMessageType.HELLO_ACK,
            payload={"registered": True, "cluster_agents": len(self.agents)},
        )

    async def heartbeat(self, envelope: EXPEnvelope) -> None:
        node_id = envelope.source.node_id
        conn = self.agents.get(node_id)
        if not conn:
            return

        payload = envelope.payload
        conn.last_seen = datetime.now(timezone.utc)
        load = payload.get("load", {}) if isinstance(payload.get("load"), dict) else {}
        capacity = payload.get("capacity", {}) if isinstance(payload.get("capacity"), dict) else {}
        conn.metrics = payload.get("metrics", {}) if isinstance(payload.get("metrics"), dict) else {}

        benchmark = payload.get("benchmark") if isinstance(payload.get("benchmark"), dict) else None
        if benchmark is not None:
            conn.benchmark = benchmark
            conn.benchmark_score = float(benchmark.get("overall_score", conn.benchmark_score))
        conn.cluster_role = str(payload.get("cluster_role", conn.cluster_role))

        conn.specialties = [str(v) for v in payload.get("specialties", conn.specialties)]
        conn.queue_size = int(load.get("queue_size", conn.queue_size))
        conn.queue_max = int(capacity.get("queue_max", conn.queue_max))
        conn.utilization = float(load.get("utilization", conn.utilization))
        conn.max_concurrency = max(1, int(capacity.get("max_concurrency", conn.max_concurrency)))

    async def accept_role_ack(self, envelope: EXPEnvelope) -> None:
        corr = envelope.correlation_id
        if not corr:
            return
        fut = self.pending_role_acks.get(corr)
        if fut and not fut.done():
            accepted = bool(envelope.payload.get("accepted", False))
            fut.set_result(accepted)

    async def accept_query_result(self, envelope: EXPEnvelope) -> None:
        self.agent_query_cache[envelope.source.node_id] = envelope.payload

    async def accept_election_propose(self, envelope: EXPEnvelope) -> None:
        payload = envelope.payload
        bench = payload.get("benchmark", {}) if isinstance(payload.get("benchmark"), dict) else {}
        score = float(bench.get("overall_score", 0.0))
        node_id = envelope.source.node_id
        self.election_candidates[node_id] = NodeBenchmark(node_id=node_id, score=score)

    async def accept_election_vote(self, envelope: EXPEnvelope) -> None:
        self.election_votes[envelope.source.node_id] = bool(envelope.payload.get("approve", False))

    async def run_election_if_possible(self) -> dict[str, Any] | None:
        self._prune_stale_agents()
        if not self.agents:
            return None

        candidates = []
        for node_id, conn in self.agents.items():
            score = conn.benchmark_score
            if node_id in self.election_candidates:
                score = self.election_candidates[node_id].score
            candidates.append(NodeBenchmark(node_id=node_id, score=score))

        result = self.election.run(
            candidates,
            total_votes=max(1, len(self.agents)),
            positive_votes=sum(1 for v in self.election_votes.values() if v),
        )
        if result is None:
            return None

        self.current_roles = {result.juiz_node_id: "juiz", result.bibliotecaria_node_id: "bibliotecaria"}
        for node_id in result.agent_node_ids:
            self.current_roles[node_id] = "agente"

        await self._query_zim_inventory_all_nodes()
        self._build_zim_distribution()
        await self._broadcast_role_changes(self.current_roles)

        return {
            "quorum": result.quorum,
            "juiz": result.juiz_node_id,
            "bibliotecaria": result.bibliotecaria_node_id,
            "agentes": result.agent_node_ids,
            "ranking": [{"node_id": n.node_id, "score": n.score, "role": n.role_hint} for n in result.ranking],
            "zim_distribution": self.zim_distribution,
        }

    async def _broadcast_role_changes(self, roles: dict[str, str]) -> None:
        for node_id, role in roles.items():
            conn = self.agents.get(node_id)
            if conn is None:
                continue
            conn.cluster_role = role
            corr = str(uuid4())
            env = EXPEnvelope(
                source=self.node,
                target=conn.node,
                correlation_id=corr,
                type=EXPMessageType.ROLE_CHANGE,
                payload={
                    "node_id": node_id,
                    "new_role": role,
                    "zim_files": self.zim_distribution.get(node_id, []),
                },
            )
            env.signature = self.security.sign_payload(env.as_signable_dict())
            try:
                await conn.websocket.send_text(env.model_dump_json())
            except Exception:
                continue

    async def _query_zim_inventory_all_nodes(self) -> None:
        self.agent_query_cache = {}
        corr = str(uuid4())
        for conn in self.agents.values():
            env = EXPEnvelope(
                source=self.node,
                target=conn.node,
                correlation_id=corr,
                type=EXPMessageType.QUERY,
                payload={"action": "zim_inventory"},
            )
            env.signature = self.security.sign_payload(env.as_signable_dict())
            try:
                await conn.websocket.send_text(env.model_dump_json())
            except Exception:
                continue
        await asyncio.sleep(1.2)

    def _build_zim_distribution(self) -> None:
        node_ids = sorted(self.agents.keys())
        if not node_ids:
            self.zim_distribution = {}
            return

        all_files: dict[str, str] = {}
        for node_id, payload in self.agent_query_cache.items():
            if str(payload.get("action", "")).lower() != "zim_inventory":
                continue
            for path in payload.get("zim_files", []) if isinstance(payload.get("zim_files"), list) else []:
                all_files[str(path)] = node_id

        distribution: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        for zim_path in sorted(all_files.keys()):
            digest = hashlib.sha1(zim_path.encode("utf-8")).hexdigest()
            idx = int(digest, 16) % len(node_ids)
            owner = node_ids[idx]
            distribution[owner].append(zim_path)

        self.zim_distribution = distribution

    def _prune_stale_agents(self) -> None:
        now = datetime.now(timezone.utc)
        stale = [agent_id for agent_id, conn in self.agents.items() if now - conn.last_seen > self.agent_timeout]
        for agent_id in stale:
            self.agents.pop(agent_id, None)

    def _find_bibliotecaria(self) -> AgentConnection | None:
        for conn in self.agents.values():
            if conn.cluster_role == "bibliotecaria":
                return conn
        return None

    async def _query_local_all_nodes(self, query: str) -> list[str]:
        self.agent_query_cache = {}
        corr = str(uuid4())
        targets = list(self.agents.values())

        for conn in targets:
            env = EXPEnvelope(
                source=self.node,
                target=conn.node,
                correlation_id=corr,
                type=EXPMessageType.QUERY,
                payload={"action": "local_search", "query": query},
            )
            env.signature = self.security.sign_payload(env.as_signable_dict())
            try:
                await conn.websocket.send_text(env.model_dump_json())
            except Exception:
                continue

        await asyncio.sleep(1.2)
        snippets: list[str] = []
        for node_id, payload in self.agent_query_cache.items():
            if not payload.get("found"):
                continue
            local_snippets = payload.get("snippets", [])
            if isinstance(local_snippets, list):
                snippets.extend([f"[{node_id}] {str(s)}" for s in local_snippets[:3]])
        return snippets[:8]

    def _infer_specialty(self, subtask: str) -> str:
        text = subtask.lower()
        mappings = {
            "programador": ("código", "python", "api", "bug", "refator"),
            "medico": ("sintoma", "saúde", "medicamento", "diagnóstico"),
            "matematico": ("equação", "cálculo", "estatística", "probabilidade"),
            "redator": ("redigir", "texto", "resumo", "artigo"),
            "tradutor": ("traduz", "tradução", "idioma", "inglês"),
            "engenheiro": ("arquitetura", "infraestrutura", "escala", "confiabilidade"),
            "jurista": ("lei", "jurídico", "contrato", "compliance"),
        }
        for specialty, terms in mappings.items():
            if any(term in text for term in terms):
                return specialty
        return "programador"

    def _select_agents(self, replicas: int = 2, specialty: str | None = None) -> list[AgentConnection]:
        self._prune_stale_agents()
        healthy = [a for a in self.agents.values() if a.cluster_role != "bibliotecaria"]
        if specialty:
            specialized = [a for a in healthy if specialty in a.specialties]
            if specialized:
                healthy = specialized

        def score(conn: AgentConnection) -> float:
            capacity_factor = conn.active_tasks / max(1, conn.max_concurrency)
            queue_factor = conn.queue_size / max(1, conn.queue_max) if conn.queue_max > 0 else 0.0
            return capacity_factor + queue_factor + conn.utilization + conn.fail_count * 0.2

        healthy.sort(key=score)
        return healthy[: max(1, min(replicas, len(healthy)))]

    async def _ask_llama3(self, prompt: str, temperature: float = 0.2) -> str:
        req = OllamaGenerateRequest(
            model="llama3",
            prompt=prompt,
            temperature=temperature,
            num_ctx=8192,
        )
        return await self.ollama.generate(req)

    async def decompose_task(self, prompt: str) -> list[str]:
        planner_prompt = (
            "Decomponha a tarefa abaixo em até 3 subtarefas objetivas em JSON no formato "
            "{\"subtasks\":[\"...\"]}. Retorne apenas JSON.\n\n"
            f"Tarefa: {prompt}"
        )
        try:
            response = await self._ask_llama3(planner_prompt)
            data = json.loads(response)
            subtasks = [str(s).strip() for s in data.get("subtasks", []) if str(s).strip()]
            return subtasks[:3] if subtasks else [prompt]
        except (OllamaError, json.JSONDecodeError):
            return [prompt]

    async def _assign_role(self, conn: AgentConnection, specialty: str, task_id: str) -> bool:
        corr = str(uuid4())
        fut: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self.pending_role_acks[corr] = fut

        env = EXPEnvelope(
            source=self.node,
            target=conn.node,
            correlation_id=corr,
            type=EXPMessageType.ROLE_ASSIGN,
            payload={"task_id": task_id, "specialty": specialty, "temporary": True},
        )
        env.signature = self.security.sign_payload(env.as_signable_dict())
        try:
            await conn.websocket.send_text(env.model_dump_json())
            return await asyncio.wait_for(fut, timeout=4)
        except Exception:
            return False
        finally:
            self.pending_role_acks.pop(corr, None)

    async def dispatch_subtask(self, task_id: str, subtask: str) -> list[str]:
        # 1) Busca local distribuída em TODOS os nós
        distributed_hits = await self._query_local_all_nodes(subtask)
        if distributed_hits:
            return distributed_hits

        # 2) Sem hit local, usa Bibliotecária como fallback para internet
        bibliotecaria = self._find_bibliotecaria()
        if bibliotecaria is not None:
            corr = str(uuid4())
            fut: asyncio.Future[str] = asyncio.get_running_loop().create_future()
            self.pending_subtasks[corr] = fut
            envelope = EXPEnvelope(
                source=self.node,
                target=bibliotecaria.node,
                correlation_id=corr,
                type=EXPMessageType.TASK_DISPATCH,
                payload={
                    "task_id": task_id,
                    "subtask": subtask,
                    "specialty": "bibliotecaria",
                    "allow_internet": True,
                    "mode": "internet_fallback",
                },
            )
            envelope.signature = self.security.sign_payload(envelope.as_signable_dict())
            try:
                await bibliotecaria.websocket.send_text(envelope.model_dump_json())
                answer = await asyncio.wait_for(fut, timeout=60)
                return [answer] if answer else []
            except Exception:
                pass
            finally:
                self.pending_subtasks.pop(corr, None)

        # 3) Fallback legado para agentes/LLM local
        specialty = self._infer_specialty(subtask)
        selected = self._select_agents(replicas=2, specialty=specialty)
        if not selected:
            fallback = await self._ask_llama3(
                f"Resolva a seguinte subtarefa em português brasileiro:\n{subtask}", temperature=0.3
            )
            return [fallback]

        results: list[str] = []
        for conn in selected:
            corr = str(uuid4())
            fut: asyncio.Future[str] = asyncio.get_running_loop().create_future()
            self.pending_subtasks[corr] = fut
            conn.active_tasks += 1

            if specialty and specialty in conn.specialties:
                await self._assign_role(conn, specialty=specialty, task_id=task_id)

            envelope = EXPEnvelope(
                source=self.node,
                target=conn.node,
                correlation_id=corr,
                type=EXPMessageType.TASK_DISPATCH,
                payload={"task_id": task_id, "subtask": subtask, "specialty": specialty, "allow_internet": False},
            )
            envelope.signature = self.security.sign_payload(envelope.as_signable_dict())

            try:
                await conn.websocket.send_text(envelope.model_dump_json())
                answer = await asyncio.wait_for(fut, timeout=50)
                conn.fail_count = max(0, conn.fail_count - 1)
                results.append(answer)
            except TimeoutError:
                conn.fail_count += 1
            except Exception:
                conn.fail_count += 1
            finally:
                conn.active_tasks = max(0, conn.active_tasks - 1)
                self.pending_subtasks.pop(corr, None)

        if not results:
            fallback = await self._ask_llama3(
                f"Resolva a seguinte subtarefa em português brasileiro:\n{subtask}", temperature=0.3
            )
            return [fallback]
        return results

    async def resolve_conflicts(self, prompt: str, candidates: list[str]) -> str:
        if len(candidates) == 1:
            return candidates[0]

        judge_prompt = (
            "Você é o Juiz do ENXAME. Dada a pergunta e respostas candidatas, escolha a melhor "
            "considerando precisão, completude e clareza em pt-BR. Retorne apenas o número da melhor resposta.\n\n"
            f"Pergunta: {prompt}\n\n"
            + "\n".join([f"{i+1}) {txt}" for i, txt in enumerate(candidates)])
        )
        try:
            pick = await self._ask_llama3(judge_prompt, temperature=0.1)
            idx = int("".join(ch for ch in pick if ch.isdigit()) or "1") - 1
            idx = max(0, min(idx, len(candidates) - 1))
            return candidates[idx]
        except Exception:
            return max(candidates, key=len)

    async def synthesize(self, prompt: str, partials: list[str]) -> str:
        synthesis_prompt = (
            "Sintetize uma única resposta final em português brasileiro, técnica, objetiva e consistente.\n\n"
            f"Pergunta original: {prompt}\n\n"
            "Contribuições:\n"
            + "\n\n".join(f"- {p}" for p in partials)
        )
        try:
            return await self._ask_llama3(synthesis_prompt, temperature=0.2)
        except Exception:
            return "\n\n".join(partials)

    async def submit_task(self, prompt: str) -> TaskState:
        if not self.current_roles:
            await self.run_election_if_possible()

        task = TaskState(task_id=f"t-{uuid4().hex[:10]}", prompt=prompt, status="running")
        self.tasks[task.task_id] = task
        await self._emit(task, "task_received", {"task_id": task.task_id})

        try:
            subtasks = await self.decompose_task(prompt)
            await self._emit(task, "decomposed", {"subtasks": len(subtasks)})

            winners: list[str] = []
            for sub in subtasks:
                specialty = self._infer_specialty(sub)
                await self._emit(task, "dispatch", {"subtask": sub, "specialty": specialty})
                candidates = await self.dispatch_subtask(task.task_id, sub)
                winner = await self.resolve_conflicts(sub, candidates)
                winners.append(winner)
                await self._emit(task, "judge", {"candidates": len(candidates), "specialty": specialty})

            final = await self.synthesize(prompt, winners)
            task.result = final
            task.status = "completed"
            await self._emit(task, "final", {"content": final})
        except Exception as exc:  # pragma: no cover
            task.error = str(exc)
            task.status = "failed"
            await self._emit(task, "error", {"message": str(exc)})

        return task

    async def accept_task_result(self, envelope: EXPEnvelope) -> None:
        corr = envelope.correlation_id
        if not corr:
            return
        fut = self.pending_subtasks.get(corr)
        if fut and not fut.done():
            fut.set_result(str(envelope.payload.get("result", "")))
