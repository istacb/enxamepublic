"""
EvolvedAgent — Agente Evoluído com Perfil Auto-Selecionável
===========================================================
Combina:
- Funcionalidade standalone da Abelha (offline-first, mDNS)
- Sistema de plugins existente (hot-load, match_score)
- Perfis dinâmicos baseados em capacidades
- Seleção automática de perfil por tarefa
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import httpx
import websockets

# Reutilizar componentes existentes
from core.cluster import HardwareBenchmark, LocalSearchEngine
from core.exp.envelope import EXPEnvelope, EXPNode
from core.exp.http import build_auth_headers
from core.exp.security import EXPSecurity
from core.exp.types import EXPMessageType
from core.ollama.client import OllamaClient, OllamaGenerateRequest
from guardian import GuardianPatrol

from agentes.metrics import MetricsCollector
from agentes.plugin_manager import PluginManager
from agentes.worker_pool import WorkerPool, WorkItem, now_utc

# Componentes evoluídos
from enxame_evolved.profiles.profile_manager import ProfileManager, AgentProfileSpec
from enxame_evolved.multimodal.multimodal_processor import MultiModalProcessor
from enxame_evolved.tasks.task_orchestrator import TaskOrchestrator
from enxame_evolved.discovery.swarm_discovery import SwarmDiscovery

logger = logging.getLogger(__name__)


class AgentCapability(str, Enum):
    """Capacidades possíveis de um agente."""
    # Básicas
    TEXT_GENERATION = "text_generation"
    CODE_GENERATION = "code_generation"
    DEBUGGING = "debugging"
    ARCHITECTURE = "architecture"
    
    # Conhecimento
    RAG_LOCAL = "rag_local"
    RAG_DISTRIBUTED = "rag_distributed"
    WEB_SEARCH = "web_search"
    SEMANTIC_MEMORY = "semantic_memory"
    
    # Multimodal
    OCR = "ocr"
    IMAGE_ANALYSIS = "image_analysis"
    DOCUMENT_PROCESSING = "document_processing"
    PHOTO_ANALYSIS = "photo_analysis"
    
    # Orquestração
    TASK_PLANNING = "task_planning"
    SPRINT_ORCHESTRATION = "sprint_orchestration"
    AGENT_COORDINATION = "agent_coordination"
    
    # Especializações
    LEGAL = "legal"
    MEDICAL = "medical"
    FINANCIAL = "financial"
    SCIENTIFIC = "scientific"


@dataclass(slots=True)
class AgentProfile:
    """Perfil dinâmico de um agente."""
    agent_id: str
    name: str
    capabilities: list[AgentCapability] = field(default_factory=list)
    specialties: list[str] = field(default_factory=list)  # Nomes dos plugins
    model: str = "llama3.2:3b"
    system_prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    # Métricas de performance
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    tasks_completed: int = 0
    
    def has_capability(self, cap: AgentCapability) -> bool:
        return cap in self.capabilities
    
    def match_score(self, task_description: str) -> float:
        """Score de compatibilidade com uma tarefa."""
        score = 0.0
        text_lower = task_description.lower()
        
        # Score por capabilities
        cap_keywords = {
            AgentCapability.CODE_GENERATION: ['código', 'code', 'programa', 'script', 'função', 'api'],
            AgentCapability.DEBUGGING: ['bug', 'erro', 'debug', 'falha', 'exception', 'traceback'],
            AgentCapability.ARCHITECTURE: ['arquitetura', 'design', 'estrutura', 'sistema', 'scalab'],
            AgentCapability.OCR: ['ocr', 'imagem', 'pdf', 'escaneado', 'foto', 'leitura'],
            AgentCapability.IMAGE_ANALYSIS: ['analisar imagem', 'visão', 'computer vision', 'foto'],
            AgentCapability.DOCUMENT_PROCESSING: ['documento', 'arquivo', 'pdf', 'word', 'excel'],
            AgentCapability.LEGAL: ['jurídico', 'legal', 'lei', 'contrato', 'processo'],
            AgentCapability.MEDICAL: ['médico', 'saúde', 'diagnóstico', 'paciente'],
            AgentCapability.TASK_PLANNING: ['planejar', 'organizar', 'tarefas', 'sprint', 'roadmap'],
        }
        
        for cap in self.capabilities:
            if cap in cap_keywords:
                for kw in cap_keywords[cap]:
                    if kw in text_lower:
                        score += 2.0
        
        # Score por specialties (plugins)
        for spec in self.specialties:
            if spec.lower() in text_lower:
                score += 3.0
        
        # Bonus por performance histórica
        if self.tasks_completed > 10:
            score *= (1.0 + min(self.success_rate * 0.2, 0.2))
        
        return score


class EvolvedAgent:
    """
    Agente Evoluído — Standalone + Cluster
    
    Funciona como:
    1. Abelha standalone (offline-first, mDNS discovery)
    2. Nó de cluster (conecta ao Juiz via WebSocket)
    3. Orquestrador de tarefas com perfis auto-selecionáveis
    4. Processador multimodal (OCR, imagens, docs)
    """
    
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        
        # Identidade
        self.agent_id = config.get('agent_id', f'enx-{uuid.uuid4().hex[:8]}')
        self.name = config.get('name', f'EvolvedAgent-{self.agent_id[:8]}')
        self.role = config.get('role', 'evolved')
        self.cluster_role = config.get('cluster_role', 'agent')
        
        # Rede
        self.juiz_url = config.get('juiz_url', 'ws://localhost:7700/exp')
        self.juiz_http_url = config.get('juiz_http_url', 'http://localhost:7700')
        self.secret = config.get('secret', 'enxame-dev-secret')
        self.ollama_url = config.get('ollama_url', 'http://localhost:11434')
        self.default_model = config.get('model', 'llama3.2:3b')
        
        # Configurações
        self.heartbeat_interval = config.get('heartbeat_interval', 5.0)
        self.reconnect_interval = config.get('reconnect_interval', 2.0)
        self.task_timeout = config.get('task_timeout', 120.0)
        self.worker_pool_size = config.get('worker_pool_size', 4)
        self.max_queue = config.get('max_queue', 128)
        
        # Diretórios
        self.data_dir = Path(config.get('data_dir', Path.home() / '.enxame' / 'evolved' / self.agent_id))
        self.docs_dir = self.data_dir / 'documents'
        self.zim_dir = self.data_dir / 'zim'
        self.cache_dir = self.data_dir / 'cache'
        
        for d in [self.data_dir, self.docs_dir, self.zim_dir, self.cache_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Componentes core
        self.security = EXPSecurity(self.secret)
        self.ollama = OllamaClient(self.ollama_url)
        self.node = EXPNode(node_id=self.agent_id, role=self.role, address=None)
        
        # Plugin manager existente
        self.plugin_manager = PluginManager()
        
        # Componentes evoluídos
        self.profile_manager = ProfileManager(data_dir=self.data_dir / 'profiles')
        self.multimodal = MultiModalProcessor(
            ollama_url=self.ollama_url,
            model=self.default_model,
            cache_dir=self.cache_dir
        )
        self.task_orchestrator = TaskOrchestrator(
            agent_id=self.agent_id,
            profile_manager=self.profile_manager,
            plugin_manager=self.plugin_manager,
            multimodal=self.multimodal,
        )
        self.swarm_discovery = SwarmDiscovery(
            agent_id=self.agent_id,
            host=config.get('host', '0.0.0.0'),
            port=config.get('port', 8765),
            on_peer_found=self._on_peer_found,
            on_peer_lost=self._on_peer_lost,
        )
        
        # Métricas e pool
        self.metrics = MetricsCollector()
        self.pool = WorkerPool(workers=self.worker_pool_size, max_queue=self.max_queue)
        
        # Busca local
        self.search_engine = LocalSearchEngine(docs_dir=str(self.docs_dir), zim_dir=str(self.zim_dir))
        self.benchmark_profile = HardwareBenchmark().run()
        
        # Guardião
        self.guardian_patrol = GuardianPatrol(
            node_id=self.agent_id,
            interval_seconds=config.get('guardian_interval', 15),
            remote_reporter=self._report_guardian_alert,
        )
        
        # Estado
        self._running = False
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._tasks: list[asyncio.Task] = []
        self._current_profile: AgentProfile | None = None
        self._peer_agents: dict[str, dict[str, Any]] = {}
        
        # Auto-criar perfil padrão se não existir
        self._ensure_default_profile()
    
    def _ensure_default_profile(self) -> None:
        """Garante que existe um perfil padrão."""
        default_spec = AgentProfileSpec(
            agent_id=self.agent_id,
            name="Generalista",
            capabilities=[
                AgentCapability.TEXT_GENERATION,
                AgentCapability.CODE_GENERATION,
                AgentCapability.RAG_LOCAL,
                AgentCapability.SEMANTIC_MEMORY,
            ],
            specialties=['programador', 'redator', 'tradutor'],
            model=self.default_model,
            system_prompt=(
                "Você é um Agente Evoluído do ENXAME v2. "
                "Responda em português brasileiro com objetividade, precisão e estrutura clara. "
                "Use suas capacidades multimodais quando necessário."
            ),
        )
        self.profile_manager.create_or_update(default_spec)
    
    async def start(self) -> None:
        """Inicia o agente evoluído."""
        logger.info(f"Iniciando {self.name} ({self.agent_id})...")
        
        # Carregar plugins
        self.plugin_manager.load_all()
        
        # Iniciar pool de workers
        await self.pool.start(self._execute_work_item)
        
        # Iniciar descoberta de enxame (mDNS)
        await self.swarm_discovery.start()
        
        # Iniciar guardião
        self._guardian_task = asyncio.create_task(self.guardian_patrol.run_forever())
        
        # Conectar ao cluster (Juiz) se configurado
        if self.juiz_url:
            self._cluster_task = asyncio.create_task(self._cluster_loop())
        
        # Loop de descoberta de capacidades dos peers
        self._capability_discovery_task = asyncio.create_task(self._discover_peer_capabilities())
        
        self._running = True
        logger.info(f"{self.name} ONLINE - Modo: {'Cluster' if self.juiz_url else 'Standalone'}")
    
    async def stop(self) -> None:
        """Para o agente gracefully."""
        logger.info(f"Parando {self.name}...")
        self._running = False
        
        # Cancelar tasks
        for task in [getattr(self, '_cluster_task', None), 
                     getattr(self, '_capability_discovery_task', None),
                     getattr(self, '_guardian_task', None)]:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        
        # Parar componentes
        await self.swarm_discovery.stop()
        await self.pool.stop()
        self.guardian_patrol.stop()
        
        if self._ws:
            await self._ws.close()
        
        logger.info(f"{self.name} OFFLINE")
    
    async def _cluster_loop(self) -> None:
        """Loop de conexão com o Juiz (cluster)."""
        while self._running:
            try:
                async with websockets.connect(
                    self.juiz_url, 
                    ping_interval=15, 
                    ping_timeout=15
                ) as ws:
                    self._ws = ws
                    await self._send_hello(ws)
                    
                    hb_task = asyncio.create_task(self._heartbeat_loop(ws))
                    try:
                        async for raw in ws:
                            envelope = self._decode_envelope(raw)
                            if envelope is None:
                                continue
                            await self._handle_cluster_message(ws, envelope)
                    finally:
                        hb_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await hb_task
            except Exception as exc:
                logger.warning(f'Falha de conexão com Juiz: {exc}')
                await asyncio.sleep(self.reconnect_interval)
    
    async def _send_hello(self, ws) -> None:
        """Envia HELLO com perfil e capacidades."""
        profile = self._current_profile or self.profile_manager.get_default()
        
        payload = {
            'agent_id': self.agent_id,
            'name': self.name,
            'profile': {
                'capabilities': [c.value for c in profile.capabilities],
                'specialties': profile.specialties,
                'model': profile.model,
            },
            'capabilities': [
                'evolved', 'multimodal', 'hotload', 'profiles', 
                'task_orchestration', 'swarm_coordination'
            ],
            'benchmark': self.benchmark_profile.as_dict(),
            'capacity': {
                'max_concurrency': self.pool.workers,
                'queue_max': self.pool.queue.maxsize,
            },
            'metrics': self.metrics.snapshot(),
        }
        
        hello = EXPEnvelope(source=self.node, type=EXPMessageType.HELLO, payload=payload)
        await self._send_ws(ws, hello)
    
    async def _heartbeat_loop(self, ws) -> None:
        """Heartbeat para o cluster."""
        while self._running:
            hb = EXPEnvelope(
                source=self.node,
                type=EXPMessageType.HEARTBEAT,
                payload=self._status_payload(),
            )
            await self._send_ws(ws, hb)
            await asyncio.sleep(self.heartbeat_interval)
    
    def _status_payload(self) -> dict:
        profile = self._current_profile
        return {
            'timestamp': datetime.now(UTC).isoformat(),
            'model': profile.model if profile else self.default_model,
            'cluster_role': self.cluster_role,
            'current_profile': profile.name if profile else 'none',
            'benchmark': self.benchmark_profile.as_dict(),
            'load': self.pool.load_snapshot(),
            'metrics': self.metrics.snapshot(),
            'peer_count': len(self._peer_agents),
        }
    
    async def _handle_cluster_message(self, ws, envelope: EXPEnvelope) -> None:
        """Processa mensagens do cluster (Juiz)."""
        if envelope.type == EXPMessageType.TASK_DISPATCH:
            await self._handle_task_dispatch(ws, envelope)
        elif envelope.type == EXPMessageType.ROLE_ASSIGN:
            await self._handle_role_assign(ws, envelope)
        elif envelope.type == EXPMessageType.PLUGIN_LOAD:
            await self._handle_plugin_control(ws, envelope)
        elif envelope.type == EXPMessageType.QUERY:
            await self._handle_query(ws, envelope)
        elif envelope.type == EXPMessageType.SPRINT_PLAN:
            await self._handle_sprint_plan(ws, envelope)
    
    async def _handle_task_dispatch(self, ws, envelope: EXPEnvelope) -> None:
        """Processa tarefa do cluster com seleção automática de perfil."""
        payload = envelope.payload
        task_id = payload.get('task_id', f't-{uuid.uuid4().hex[:10]}')
        subtask = payload.get('subtask', '')
        context = payload.get('context')
        sprint_id = payload.get('sprint_id')
        eip_id = payload.get('eip_id')
        
        # Selecionar melhor perfil para a tarefa
        profile = await self.profile_manager.select_best_profile(subtask, context)
        self._current_profile = profile
        
        # Se tem sprint/EIP, orquestrar
        if sprint_id or eip_id:
            result = await self.task_orchestrator.execute_task(
                task_id=task_id,
                subtask=subtask,
                context=context,
                profile=profile,
                sprint_id=sprint_id,
                eip_id=eip_id,
            )
        else:
            # Enfileirar para worker pool
            item = WorkItem(
                correlation_id=envelope.correlation_id or envelope.msg_id,
                task_id=task_id,
                subtask=subtask,
                specialty=profile.specialties[0] if profile.specialties else None,
                context=context,
                source_node=envelope.source.model_dump(mode='json') if envelope.source else {},
                enqueued_at=now_utc(),
                metadata={'profile': profile.name, 'sprint_id': sprint_id, 'eip_id': eip_id},
            )
            
            try:
                fut = await self.pool.submit(item)
                result = await asyncio.wait_for(fut, timeout=self.task_timeout)
            except asyncio.QueueFull:
                await self._send_retry(ws, envelope, task_id, 'overloaded')
                return
            except TimeoutError:
                await self._send_retry(ws, envelope, task_id, 'timeout')
                return
        
        # Enviar resultado
        response = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id or envelope.msg_id,
            type=EXPMessageType.TASK_RESULT,
            payload={
                'task_id': task_id,
                'result': result,
                'profile_used': profile.name,
                'capabilities_used': [c.value for c in profile.capabilities],
                'metrics': self.metrics.snapshot(),
            },
        )
        await self._send_ws(ws, response)
    
    async def _handle_sprint_plan(self, ws, envelope: EXPEnvelope) -> None:
        """Processa planejamento de sprint."""
        sprint_spec = envelope.payload
        result = await self.task_orchestrator.plan_sprint(sprint_spec)
        
        response = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id or envelope.msg_id,
            type=EXPMessageType.SPRINT_PLAN_RESULT,
            payload=result,
        )
        await self._send_ws(ws, response)
    
    async def _handle_role_assign(self, ws, envelope: EXPEnvelope) -> None:
        """Atribui papel/especialidade."""
        specialty = envelope.payload.get('specialty', '')
        accepted = bool(specialty and self.plugin_manager.get(specialty))
        
        if accepted:
            # Atualizar perfil ativo
            profile = self.profile_manager.get_by_specialty(specialty)
            if profile:
                self._current_profile = profile
        
        ack = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id or envelope.msg_id,
            type=EXPMessageType.ROLE_ACK,
            payload={
                'accepted': accepted,
                'specialty': specialty,
                'current_profile': self._current_profile.name if self._current_profile else None,
            },
        )
        await self._send_ws(ws, ack)
    
    async def _handle_plugin_control(self, ws, envelope: EXPEnvelope) -> None:
        """Controle de plugins (hot-load)."""
        action = envelope.payload.get('action', 'list')
        plugin_name = envelope.payload.get('plugin', '')
        
        if action == 'load' and plugin_name:
            meta = self.plugin_manager.load_plugin(plugin_name)
            detail = {'plugin': meta.name, 'loaded': meta is not None}
        elif action == 'unload' and plugin_name:
            removed = self.plugin_manager.unload_plugin(plugin_name)
            detail = {'plugin': plugin_name, 'removed': removed}
        elif action == 'refresh':
            changed = self.plugin_manager.refresh_changed()
            detail = {'changed': [p.name for p in changed]}
        else:
            detail = {'plugins': [p.name for p in self.plugin_manager.list_plugins()]}
        
        response = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id or envelope.msg_id,
            type=EXPMessageType.QUERY_RESULT,
            payload={'status': 'ok', 'action': action, **detail},
        )
        await self._send_ws(ws, response)
    
    async def _handle_query(self, ws, envelope: EXPEnvelope) -> None:
        """Processa queries locais (busca, status, etc.)."""
        action = envelope.payload.get('action', 'status')
        
        if action == 'local_search':
            query = envelope.payload.get('query', '')
            hit = self.search_engine.search(query, limit=5)
            payload = {
                'action': 'local_search',
                'found': hit.found,
                'source': hit.source,
                'snippets': hit.snippets,
                'sources': hit.sources,
            }
        elif action == 'profile_info':
            profile = self._current_profile or self.profile_manager.get_default()
            payload = {
                'action': 'profile_info',
                'profile': {
                    'name': profile.name,
                    'capabilities': [c.value for c in profile.capabilities],
                    'specialties': profile.specialties,
                    'model': profile.model,
                    'metrics': {
                        'success_rate': profile.success_rate,
                        'avg_latency_ms': profile.avg_latency_ms,
                        'tasks_completed': profile.tasks_completed,
                    },
                },
            }
        elif action == 'peer_status':
            payload = {
                'action': 'peer_status',
                'peers': self._peer_agents,
            }
        else:
            payload = self._status_payload()
        
        response = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id or envelope.msg_id,
            type=EXPMessageType.QUERY_RESULT,
            payload=payload,
        )
        await self._send_ws(ws, response)
    
    async def _send_ws(self, ws, envelope: EXPEnvelope) -> None:
        envelope.signature = self.security.sign_payload(envelope.as_signable_dict())
        await ws.send(envelope.model_dump_json())
    
    def _decode_envelope(self, raw: str) -> EXPEnvelope | None:
        try:
            data = json.loads(raw)
            signature = data.get('signature')
            signable = {k: v for k, v in data.items() if k != 'signature'}
            if not signature or not self.security.verify_payload(signable, signature):
                return None
            return EXPEnvelope.model_validate(data)
        except Exception:
            return None
    
    async def _send_retry(self, ws, envelope: EXPEnvelope, task_id: str, reason: str) -> None:
        retry = EXPEnvelope(
            source=self.node,
            target=envelope.source,
            correlation_id=envelope.correlation_id or envelope.msg_id,
            type=EXPMessageType.TASK_RETRY,
            payload={'task_id': task_id, 'reason': reason, 'load': self.pool.load_snapshot()},
        )
        await self._send_ws(ws, retry)
    
    async def _report_guardian_alert(self, alert: dict) -> None:
        body = json.dumps(alert, ensure_ascii=False).encode('utf-8')
        headers = build_auth_headers(self.security, body)
        headers['content-type'] = 'application/json'
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f'{self.juiz_http_url}/api/v1/guardian/report', content=body, headers=headers)
    
    # =========================================================================
    # Execução de Work Items (Worker Pool)
    # =========================================================================
    
    async def _execute_work_item(self, item: WorkItem) -> str:
        """Executa um item de trabalho com perfil e capacidades multimodais."""
        profile = self.profile_manager.get(item.metadata.get('profile', '')) if item.metadata else None
        if not profile:
            profile = self._current_profile or self.profile_manager.get_default()
        
        self._current_profile = profile
        
        # Verificar se precisa de processamento multimodal
        subtask = item.subtask
        context = item.context
        
        # Processar anexos multimodais se houver
        if item.metadata and 'attachments' in item.metadata:
            multimodal_results = await self.multimodal.process_attachments(
                item.metadata['attachments'],
                subtask
            )
            if multimodal_results:
                context = (context or '') + '\n\n[Conteúdo Multimodal Extraído]:\n' + multimodal_results
        
        # Busca local primeiro (offline-first)
        local_hit = self.search_engine.search(subtask, limit=3)
        if local_hit.found:
            self.metrics.track_success()
            return '\n'.join(local_hit.snippets)
        
        # Selecionar plugin baseado no perfil
        plugin = None
        if profile and profile.specialties:
            for spec in profile.specialties:
                plugin = self.plugin_manager.get(spec)
                if plugin:
                    break
        
        if not plugin:
            plugin = self.plugin_manager.best_for(subtask)
        
        # Executar com prompt do plugin
        prompt = plugin.build_prompt(subtask=subtask, context=context)
        
        started = time.perf_counter()
        try:
            answer = await self.ollama.generate(
                OllamaGenerateRequest(
                    model=profile.model if profile else self.default_model,
                    prompt=prompt,
                    temperature=0.3,
                    num_ctx=8192,
                )
            )
            self.metrics.track_success()
            
            # Atualizar métricas do perfil
            latency_ms = (time.perf_counter() - started) * 1000
            self.metrics.track_latency(latency_ms)
            if profile:
                profile.tasks_completed += 1
                profile.avg_latency_ms = (
                    (profile.avg_latency_ms * (profile.tasks_completed - 1) + latency_ms) 
                    / profile.tasks_completed
                )
            
            return answer
        except Exception as e:
            self.metrics.track_failure()
            if profile:
                profile.success_rate = max(0, profile.success_rate - 0.01)
            raise
    
    # =========================================================================
    # Descoberta de Peers (Swarm)
    # =========================================================================
    
    def _on_peer_found(self, peer_info: dict[str, Any]) -> None:
        """Callback quando peer descoberto via mDNS."""
        peer_id = peer_info.get('node_id')
        if peer_id and peer_id != self.agent_id:
            self._peer_agents[peer_id] = peer_info
            logger.info(f"Peer descoberto: {peer_id} - {peer_info.get('capabilities', [])}")
            
            # Solicitar perfil do peer
            asyncio.create_task(self._request_peer_profile(peer_id, peer_info))
    
    def _on_peer_lost(self, peer_id: str) -> None:
        """Callback quando peer perdido."""
        if peer_id in self._peer_agents:
            del self._peer_agents[peer_id]
            logger.warning(f"Peer perdido: {peer_id}")
    
    async def _request_peer_profile(self, peer_id: str, peer_info: dict[str, Any]) -> None:
        """Solicita perfil do peer via HTTP."""
        try:
            host = peer_info.get('host', 'localhost')
            port = peer_info.get('port', 8765)
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f'http://{host}:{port}/api/v1/profile')
                if resp.status_code == 200:
                    self._peer_agents[peer_id]['profile'] = resp.json()
        except Exception:
            pass
    
    async def _discover_peer_capabilities(self) -> None:
        """Loop periódico para descobrir capacidades dos peers."""
        while self._running:
            try:
                for peer_id, peer_info in list(self._peer_agents.items()):
                    if 'profile' not in peer_info:
                        await self._request_peer_profile(peer_id, peer_info)
            except Exception as e:
                logger.debug(f"Erro na descoberta de capacidades: {e}")
            await asyncio.sleep(30)
    
    # =========================================================================
    # API Pública
    # =========================================================================
    
    async def process_query(self, query: str, attachments: list[dict] | None = None) -> dict[str, Any]:
        """
        Processa query local com seleção automática de perfil e multimodal.
        
        Args:
            query: Pergunta/tarefa
            attachments: Lista de anexos (arquivos, imagens, etc.)
            
        Returns:
            Dict com resposta, perfil usado, fontes, etc.
        """
        # Selecionar melhor perfil
        profile = await self.profile_manager.select_best_profile(query)
        self._current_profile = profile
        
        # Processar anexos multimodais
        multimodal_context = ""
        if attachments:
            multimodal_results = await self.multimodal.process_attachments(attachments, query)
            if multimodal_results:
                multimodal_context = f'\n\n[Multimodal]:\n{multimodal_results}'
        
        # Busca local
        local_hit = self.search_engine.search(query, limit=5)
        
        # Preparar contexto
        context_parts = []
        if local_hit.found:
            context_parts.append(f'[Busca Local]:\n' + '\n'.join(local_hit.snippets))
        if multimodal_context:
            context_parts.append(multimodal_context)
        
        context = '\n\n'.join(context_parts) if context_parts else None
        
        # Executar via plugin do perfil
        plugin = None
        if profile.specialties:
            for spec in profile.specialties:
                plugin = self.plugin_manager.get(spec)
                if plugin:
                    break
        
        if not plugin:
            plugin = self.plugin_manager.best_for(query)
        
        prompt = plugin.build_prompt(subtask=query, context=context)
        
        started = time.perf_counter()
        answer = await self.ollama.generate(
            OllamaGenerateRequest(
                model=profile.model,
                prompt=prompt,
                temperature=0.3,
                num_ctx=8192,
            )
        )
        latency_ms = (time.perf_counter() - started) * 1000
        
        # Atualizar métricas
        profile.tasks_completed += 1
        profile.avg_latency_ms = (
            (profile.avg_latency_ms * (profile.tasks_completed - 1) + latency_ms) 
            / profile.tasks_completed
        )
        
        return {
            'answer': answer,
            'profile': profile.name,
            'capabilities_used': [c.value for c in profile.capabilities],
            'specialties': profile.specialties,
            'latency_ms': latency_ms,
            'sources': local_hit.sources if local_hit.found else [],
            'multimodal_processed': bool(attachments),
        }
    
    async def create_agent_profile(self, spec: AgentProfileSpec) -> AgentProfile:
        """Cria novo perfil de agente."""
        return self.profile_manager.create_or_update(spec)
    
    async def plan_sprint(self, sprint_spec: dict[str, Any]) -> dict[str, Any]:
        """Planeja uma sprint baseada na especificação."""
        return await self.task_orchestrator.plan_sprint(sprint_spec)
    
    async def execute_eip(self, eip_spec: dict[str, Any]) -> dict[str, Any]:
        """Executa uma EIP (Especificação de Implementação)."""
        return await self.task_orchestrator.execute_eip(eip_spec)
    
    def get_status(self) -> dict[str, Any]:
        """Retorna status completo do agente."""
        profile = self._current_profile or self.profile_manager.get_default()
        return {
            'agent_id': self.agent_id,
            'name': self.name,
            'running': self._running,
            'mode': 'cluster' if self.juiz_url else 'standalone',
            'current_profile': {
                'name': profile.name,
                'capabilities': [c.value for c in profile.capabilities],
                'specialties': profile.specialties,
                'model': profile.model,
                'metrics': {
                    'success_rate': profile.success_rate,
                    'avg_latency_ms': profile.avg_latency_ms,
                    'tasks_completed': profile.tasks_completed,
                },
            },
            'peer_count': len(self._peer_agents),
            'peers': list(self._peer_agents.keys()),
            'pool': {
                'workers': self.pool.workers,
                'queue_size': self.pool.queue.qsize(),
                'load': self.pool.load_snapshot(),
            },
            'metrics': self.metrics.snapshot(),
            'benchmark': self.benchmark_profile.as_dict(),
        }


# Função de conveniência para criar agente
async def create_evolved_agent(config: dict[str, Any] | None = None) -> EvolvedAgent:
    """Factory para criar e iniciar agente evoluído."""
    agent = EvolvedAgent(config)
    await agent.start()
    return agent