#!/usr/bin/env python3
"""
BEE-0001 — Standalone Bee Service
=================================
Uma Abelha autônoma que opera offline-first, descobre peers via mDNS,
e segue a política LOCAL -> ENXAME -> WEB.

Este é o ponto de entrada principal para executar uma Abelha standalone.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import os
import secrets
import signal
import sys
import time
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from aiohttp import web

from core.exp.http import build_auth_headers
from core.exp.security import EXPSecurity

# O guardião é opcional em runtime: se o pacote não for importável a abelha
# ainda precisa servir consultas, mas registra em WARNING que está sem
# inspeção de segurança — nunca silenciosamente.
try:
    from guardian import Guardian, GuardianPatrol
except ImportError:  # pragma: no cover - depende do layout de instalação
    Guardian = None
    GuardianPatrol = None

from .protocol.envelope import BeeEnvelope
from .protocol.handler import BeeProtocolHandler
from .protocol.messages import BeeMessageType, BeeState, BeeVisionRequest, BeeVisionResponse, BeeStateChange, BeePeerLost
from .librarian import LocalBeeLibrarian
from .memory import BeeMemory
from .discovery import BeeDiscoveryService, DiscoveredPeer
from .config import BeeConfig, load_config
from .capabilities.discovery import discover_capabilities
from .capabilities.selector import recommend_model
from .cluster import (
    ClusterMonitor,
    ClusterState,
    ClusterRole,
    load_cluster_state,
    save_cluster_state,
    elect_roles,
    score_peer,
    InternetGate,
    InternetPurpose,
    GlobalIndex,
    build_global_index,
    start_monitoring,
    stop_monitoring,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bee")


# Tempo de vida do token de sessão do UI (mesma política que o antigo
# juiz/app.py usava; aquele módulo foi removido junto com a stack antiga,
# e este contrato passou a ser o único).
UI_SESSION_TTL = timedelta(minutes=30)


@dataclass
class UiTask:
    """Tarefa de chat aberta pelo UI web.

    Espelha o contrato que ``web/app.js`` consome: ele abre um EventSource em
    ``/api/chat/stream/{task_id}`` e espera eventos ``data: {"event": ...}``,
    tratando ``final`` (usa ``content``) e ``error`` (usa ``message``).
    """

    task_id: str
    prompt: str
    status: str = "pending"  # pending | running | completed | failed | cancelled
    events: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def emit(self, event: str, **payload: Any) -> None:
        self.events.append({"event": event, **payload})


class BeeService:
    """Serviço principal da Abelha - stand-alone, offline-first."""

    def __init__(self, config: BeeConfig) -> None:
        self.config = config
        self.node_id = config.node_id
        self.state = BeeState.STARTING

        self._security = EXPSecurity(config.shared_secret) if config.shared_secret else None
        self._handler = BeeProtocolHandler(
            node_id=self.node_id,
            shared_secret=config.shared_secret,
        )

        self._librarian: LocalBeeLibrarian | None = None
        self._memory: BeeMemory | None = None
        self._discovery: BeeDiscoveryService | None = None

        self._running = False
        self._stopping = False
        self._tasks: list[asyncio.Task] = []

        # Servidor HTTP (precisam existir desde o __init__: stop() é chamado
        # pelo finally de main() mesmo quando start() falha no meio, e antes
        # eles só eram criados no passo 8 de start() -> AttributeError no
        # shutdown mascarava o erro real do startup.)
        self._own_http_server = False
        self._http_runner: Any = None

        # Interface web (web/): sessões e tarefas de chat. Um bee standalone
        # faz tudo que o enxame faz em uma máquina só, então precisa servir o
        # MESMO contrato de UI que o juiz expõe — senão a interface, que existe
        # justamente para quem não usa terminal, só funcionava no enxame.
        self._ui_sessions: dict[str, datetime] = {}
        self._ui_tasks: dict[str, UiTask] = {}
        self._ui_paused: set[str] = set()

        # Guarda: a rotina de segurança precisa rodar em QUEM RECEBE O PROMPT e
        # em QUEM FAZ A CURADORIA. Antes só o juiz inspecionava (o antigo juiz/app.py
        # chama detect_injection) e a abelha — que em modo standalone é justamente
        # quem recebe o prompt e quem cura a resposta — não aplicava nenhuma.
        self._guardian: Any = None
        self._guardian_patrol: Any = None
        self._patrol_task: "asyncio.Task | None" = None

        # Formação dinâmica do enxame: peers que aparecem DEPOIS do boot.
        self._cluster_reelect_task: "asyncio.Task | None" = None
        self._cluster_reelect_lock = asyncio.Lock()
        self._guardian_alerts: list[dict[str, Any]] = []
        self._guard_stats: dict[str, int] = {
            "prompts_inspecionados": 0,
            "prompts_bloqueados": 0,
            "respostas_inspecionadas": 0,
            "respostas_retidas": 0,
        }

        self._register_protocol_handlers()

        # Capacidades descobertas (BEE-0003)
        self._capabilities: dict[str, Any] | None = None

        # Cluster (EIP-0009)
        self.cluster_state: ClusterState | None = None
        self.cluster_role: ClusterRole | None = None
        self._cluster_monitor: ClusterMonitor | None = None
        self._internet_gate: InternetGate | None = None
        self._global_index: GlobalIndex | None = None
        # True quando há <3 peers: a abelha faz tudo sozinha (juiz +
        # bibliotecária + guarda na mesma máquina). Usado pelo UI para
        # desenhá-la como rainha em vez de worker.
        self._standalone = True

    def _register_protocol_handlers(self) -> None:
        """Registra handlers para mensagens do protocolo BEE."""
        from .protocol.messages import (
            BeeHello,
            BeeHelloAck,
            BeeHeartbeat,
            BeeKnowledgeQuery,
            BeeKnowledgeResponse,
            BeeResearchRequest,
            BeeResearchResult,
            BeeModelRequest,
            BeeModelResponse,
            BeeCapabilityQuery,
            BeeCapabilityResponse,
            BeeStateChange,
            BeePeerLost,
        )

        self._handler.register_handler(BeeMessageType.HELLO, self._handle_hello)
        self._handler.register_handler(BeeMessageType.HELLO_ACK, self._handle_hello_ack)
        self._handler.register_handler(BeeMessageType.HEARTBEAT, self._handle_heartbeat)
        self._handler.register_handler(BeeMessageType.HEARTBEAT_ACK, self._handle_heartbeat_ack)
        self._handler.register_handler(BeeMessageType.KNOWLEDGE_QUERY, self._handle_knowledge_query)
        self._handler.register_handler(BeeMessageType.RESEARCH_REQUEST, self._handle_research_request)
        self._handler.register_handler(BeeMessageType.MODEL_REQUEST, self._handle_model_request)
        self._handler.register_handler(BeeMessageType.VISION_REQUEST, self._handle_vision_request)
        self._handler.register_handler(BeeMessageType.CAPABILITY_QUERY, self._handle_capability_query)
        self._handler.register_handler(BeeMessageType.STATE_CHANGE, self._handle_state_change)
        self._handler.register_handler(BeeMessageType.PEER_LOST, self._handle_peer_lost)

    async def start(self, *, start_http: bool = True, http_app: "web.Application | None" = None) -> None:
        """
        Inicializa todos os componentes da Abelha.
        
        Args:
            start_http: Se True, inicia servidor HTTP próprio.
                       Se False, usa http_app fornecido (para integração com EnxameKernel).
            http_app: Aplicação aiohttp externa para adicionar rotas da Abelha.
        """
        logger.info(f"Iniciando Abelha {self.node_id}...")

        # 1. Carregar identidade persistente
        await self._load_identity()

        # 2. Descobrir capacidades (BEE-0003) - hardware, Ollama, capacidades locais
        logger.info("Descobrindo capacidades do sistema...")
        self._capabilities = await discover_capabilities(
            enxame_data_path=str(self.config.data_dir),
            ollama_base_url=self.config.ollama_base_url,
        )
        
        # Selecionar melhor modelo baseado no hardware (BEE-0003 §9)
        if self._capabilities and self._capabilities.ollama and self._capabilities.ollama.available:
            hw = self._capabilities.hardware
            ollama = self._capabilities.ollama
            recommended = recommend_model(
                available_models=ollama.models,
                ram_gb=hw.ram_total_gb,
                gpu_vram_gb=hw.gpu_vram_gb,
                has_gpu=hw.gpu_available,
            )
            if recommended:
                self.config.model = recommended
                logger.info(f"Modelo recomendado pelo hardware: {recommended}")
            else:
                logger.warning("Nenhum modelo adequado encontrado, usando configuração padrão")

        # 3. Inicializar memória local (SQLite)
        self._memory = BeeMemory(self.config.data_dir / "memory.db")
        await self._memory.initialize()
        logger.info("Memória local inicializada")

        # 4. Inicializar Bibliotecário Local (RAG offline)
        self._librarian = LocalBeeLibrarian(
            data_dir=self.config.data_dir,
            ollama_url=self.config.ollama_base_url,
            model=self.config.model,
            memory=self._memory,
            embedding_model=self.config.embedding_model,
            offline_mode=self.config.offline_mode,
        )
        await self._librarian.initialize()
        logger.info("Bibliotecário local inicializado")

        # 5. Inicializar descoberta de peers (mDNS) com capacidades descobertas
        self._discovery = BeeDiscoveryService(
            node_id=self.node_id,
            host=self.config.host,
            port=self.config.port,
            capabilities=self._get_capabilities_list(),
            models=self._get_models_list(),
            on_peer_found=self._on_peer_discovered,
            on_peer_lost=self._on_peer_lost,
        )
        await self._discovery.start()
        logger.info("Descoberta mDNS iniciada")

        # 6. Anunciar presença via mDNS usando BeeDiscoveryService (não NodeAnnouncer)
        #
        # Quem desativou o cluster NÃO se anuncia. As outras abelhas contam os
        # anúncios para medir o tamanho do enxame e distribuem papéis entre quem
        # aparece; uma abelha opt-out visível seria contada e poderia ser eleita
        # juiz sem nunca agir — um enxame com líder ausente. Continua descobrindo
        # e servindo a própria interface, apenas invisível para eleição.
        if self._cluster_enabled():
            await self._discovery.start_announcement()
            logger.info(f"Anunciando via mDNS em {self.config.host_ip}:{self.config.port}")
        else:
            logger.info("cluster.enabled=false: fora do enxame, não anunciando no mDNS")

        # 7. Inicializar Cluster (EIP-0009) - aguardar descoberta inicial
        await self._initialize_cluster()

        # 8. Servidor HTTP
        self._own_http_server = False
        if start_http:
            if http_app is not None:
                # Modo integração: adicionar rotas da Abelha à app externa
                await self._add_routes_to_app(http_app)
            else:
                # Modo standalone: iniciar servidor próprio
                await self._start_http_server()
                self._own_http_server = True

        # 9. Guarda: inspeção de prompts/respostas + ronda contínua.
        # Precisa vir ANTES dos loops de background porque a ronda é uma task
        # como as outras e o stop() cancela tudo que estiver em self._tasks.
        self._init_guardian()

        # 10. Iniciar loops de background
        self._running = True
        self._tasks = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._peer_maintenance_loop()),
            asyncio.create_task(self._load_metrics_loop()),
        ]
        patrol_task = self._start_guardian_patrol()
        if patrol_task is not None:
            self._tasks.append(patrol_task)

        self.state = BeeState.RUNNING
        logger.info(f"Abelha {self.node_id} ONLINE - Estado: RUNNING")

    async def stop(self) -> None:
        """Finaliza graceful da Abelha. Idempotente.

        `main()` registra um handler de sinal que agenda `bee.stop()` e, ao
        final, chama `await bee.stop()` outra vez. As duas chamadas corriam
        juntas: ambas passavam no `if self._http_runner` antes de qualquer uma
        colocá-lo em None, e o segundo `cleanup()` encontrava o servidor já
        desligado — AttributeError: 'NoneType' object has no attribute
        'pre_shutdown'. O processo morria com traceback e código diferente de
        zero, o que num serviço systemd/Windows (criado pelo instalador)
        aparece como "failed".
        """
        if self._stopping:
            logger.debug(f"stop() já em andamento em {self.node_id}; ignorando duplicata")
            return
        self._stopping = True

        logger.info(f"Parando Abelha {self.node_id}...")
        self.state = BeeState.STOPPING
        self._running = False

        # Parar a ronda do guardião (o cancelamento das tasks vem logo abaixo)
        if self._guardian_patrol:
            self._guardian_patrol.stop()
            self._guardian_patrol = None

        # Cancelar reavaliação de enxame pendente
        if self._cluster_reelect_task is not None:
            self._cluster_reelect_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._cluster_reelect_task
            self._cluster_reelect_task = None

        # Notificar peers sobre parada
        if self._handler:
            state_change = self._handler.create_state_change(
                new_state=BeeState.STOPPING,
                reason="shutdown",
                estimated_return_seconds=None,
            )
            # Broadcast para peers ativos
            if self._discovery:
                for peer in self._discovery.get_active_peers():
                    state_change.target_node_id = peer.node_id
                    await self._send_to_peer(peer, state_change)

        # Cancelar tasks de background
        for task in self._tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        # Parar monitoramento de cluster
        if self._cluster_monitor:
            await stop_monitoring(self._cluster_monitor)
            self._cluster_monitor = None

        # Parar servidor HTTP próprio (se iniciamos)
        if self._own_http_server and self._http_runner:
            runner, self._http_runner = self._http_runner, None
            try:
                await runner.cleanup()
            except Exception as exc:
                # Nada aqui pode impedir o resto do desligamento (mDNS,
                # bibliotecário, memória) de acontecer.
                logger.warning(f"Falha ao encerrar o servidor HTTP: {exc}")

        # Parar anúncio mDNS
        if self._discovery:
            await self._discovery.stop_announcement()

        # Parar descoberta
        if self._discovery:
            await self._discovery.stop()

        # Fechar bibliotecário
        if self._librarian:
            await self._librarian.close()

        # Fechar memória
        if self._memory:
            await self._memory.close()

        self.state = BeeState.STOPPED
        logger.info(f"Abelha {self.node_id} OFFLINE")

    def _self_peer(self) -> DiscoveredPeer:
        """Representa ESTA abelha como um `DiscoveredPeer`.

        A descoberta mDNS lista apenas os OUTROS nodes — o próprio node nunca
        aparece em `get_active_peers()`. Mas a eleição distribui papéis entre
        todos os participantes do enxame, inclusive este. Sem uma representação
        própria, esta abelha ficava de fora da eleição e
        `cluster_state.get_role(self.node_id)` devolvia None.
        """
        return DiscoveredPeer(
            node_id=self.node_id,
            role="bee",
            host=self.config.host_ip,
            port=self.config.port,
            capabilities=self._get_capabilities_list(),
            models=self._get_models_list(),
        )

    def _cluster_flag(self, name: str, default: bool) -> bool:
        """Lê um booleano de config.cluster tolerando configuração malformada."""
        cluster_cfg = getattr(self.config, "cluster", None) or {}
        try:
            return bool(cluster_cfg.get(name, default))
        except AttributeError:
            return default

    def _cluster_enabled(self) -> bool:
        """Se esta abelha pode participar de um enxame.

        `cluster.enabled` era gravado pelo instalador (`enable_cluster_mode`) e
        nunca lido pelo serviço: responder "n" à pergunta "Deseja ativar modo
        cluster?" não impedia nada — bastavam 2 outras abelhas na rede para o
        enxame se formar à revelia do usuário.
        """
        return self._cluster_flag("enabled", True)

    def _auto_elect_enabled(self) -> bool:
        """Se a eleição pode rodar sozinha (False = só estado persistido)."""
        return self._cluster_flag("auto_elect", True)

    def _apply_standalone_roles(self) -> None:
        """Papéis de quem opera sozinho: sem enxame, sem papel de liderança."""
        self._standalone = True
        self.cluster_role = ClusterRole.WORKER
        if self.cluster_state and self.node_id in self.cluster_state.artist_workers:
            self.cluster_role = ClusterRole.WORKER_ARTIST

    def _min_bees_for_cluster(self) -> int:
        """Quantas abelhas (contando esta) formam um enxame. Default: 3."""
        cluster_cfg = getattr(self.config, "cluster", None) or {}
        try:
            value = int(cluster_cfg.get("min_peers", 3))
        except (AttributeError, TypeError, ValueError):
            value = 3
        return max(1, value)

    async def _initialize_cluster(self) -> None:
        """Inicializa cluster: carrega estado, elege papéis se 3+ abelhas, inicia monitoramento."""
        # Carregar estado persistido
        self.cluster_state = load_cluster_state(self.config.data_dir)

        # Opt-out: o usuário pode ter dito "não" ao instalador.
        if not self._cluster_enabled():
            logger.info("cluster.enabled=false: esta abelha não forma enxame (standalone)")
            self._apply_standalone_roles()
            return

        # Aguardar descoberta inicial de peers (2s)
        await asyncio.sleep(2)
        
        peers: list[DiscoveredPeer] = []
        if self._discovery:
            peers = self._discovery.get_active_peers()

        # DOIS erros viviam aqui:
        #
        # 1) O enxame é formado por esta abelha + as descobertas, mas `peers`
        #    vem do mDNS e NÃO inclui o próprio node. O teste `len(peers) >= 3`
        #    exigia portanto 4 MÁQUINAS para formar enxame, enquanto a
        #    especificação é "3+ abelhas". Com exatamente 3 abelhas cada uma via
        #    2 peers e todas ficavam standalone — o enxame nunca nascia.
        #
        # 2) `elect_roles(peers)` recebia a lista SEM esta abelha. Como a
        #    eleição sorteia juiz/bibliotecário/guarda entre os elementos da
        #    lista e joga o resto em workers, esta abelha não recebia papel
        #    algum: `get_role(self.node_id)` devolvia None e a linha
        #    `self.cluster_role.value` logo abaixo levantaria AttributeError,
        #    derrubando o startup. Era um crash latente que só não acontecia
        #    porque o erro (1) impedia este ramo de executar.
        enxame = [*peers, self._self_peer()]
        min_bees = self._min_bees_for_cluster()

        logger.info(
            f"Abelhas no enxame: {len(enxame)} ({len(peers)} peer(s) + esta) "
            f"| mínimo para cluster: {min_bees}"
        )

        if len(enxame) >= min_bees and not self._auto_elect_enabled():
            # Sem eleição automática só entra num enxame que já está registrado.
            if not (self.cluster_state and self.cluster_state.juiz_id):
                logger.info("cluster.auto_elect=false e sem estado persistido: standalone")
                self._apply_standalone_roles()
                return
            logger.info("cluster.auto_elect=false: reaproveitando os papéis persistidos")

        if len(enxame) >= min_bees:
            self._standalone = False
            if self._auto_elect_enabled():
                # Eleger papéis entre TODAS as abelhas do enxame, inclusive esta
                self.cluster_state = elect_roles(enxame, self.cluster_state)
            # `or ClusterRole.WORKER`: se a eleição não atribuir papel a este
            # node (ex.: estado persistido inconsistente), assumir worker em vez
            # de deixar None e estourar AttributeError no .value abaixo.
            self.cluster_role = self.cluster_state.get_role(self.node_id) or ClusterRole.WORKER
            
            # Determinar se é Worker Artist
            if self.cluster_role == ClusterRole.WORKER and self.node_id in self.cluster_state.artist_workers:
                self.cluster_role = ClusterRole.WORKER_ARTIST
            
            logger.info(f"Cluster eleito: Juiz={self.cluster_state.juiz_id}, Bib={self.cluster_state.bibliotecario_id}, Guarda={self.cluster_state.guarda_id}, Workers={len(self.cluster_state.workers)}")
            logger.info(f"Meu papel: {self.cluster_role.value}")
            
            # Salvar estado
            save_cluster_state(self.config.data_dir, self.cluster_state)
            
            # Inicializar InternetGate
            self._internet_gate = InternetGate(self.cluster_state, self.node_id)
            
            # Se sou Bibliotecário, construir índice global lendo o índice de
            # TODAS as abelhas do enxame (build_global_index pula a si mesma
            # comparando node_id, então passar `enxame` é seguro).
            if self.cluster_role == ClusterRole.BIBLIOTECARIO:
                self._global_index = await build_global_index(self, enxame)
                self.cluster_state.global_index = self._global_index.data
                save_cluster_state(self.config.data_dir, self.cluster_state)
            
            # Iniciar monitoramento de failover
            # O monitor chama save_state_fn(state) com UM argumento, mas
            # save_cluster_state(data_dir, state) exige DOIS. Passar a função
            # crua quebrava o failover na primeira vez que ele era acionado
            # (TypeError engolido e logado como "Erro no monitoramento").
            self._cluster_monitor = await start_monitoring(
                self,
                self.cluster_state,
                lambda state: save_cluster_state(self.config.data_dir, state),
                check_interval=60.0,
            )
        else:
            logger.info(
                f"Menos de {min_bees} abelhas ({len(enxame)}), operando como standalone"
            )
            self._apply_standalone_roles()

    def _get_capabilities_list(self) -> list[str]:
        """Retorna lista de capabilities da Abelha baseada em descoberta BEE-0003."""
        if not self._capabilities:
            # Fallback básico
            caps = ["rag", "vector_search", "embeddings", "query", "index", "memory"]
        else:
            caps = self._capabilities.to_manifesto_dict().get("capabilities", [])
            # Adicionar capabilities básicas se não estiverem
            for base in ["rag", "vector_search", "embeddings", "query", "index", "memory"]:
                if base not in caps:
                    caps.append(base)
        
        if self._librarian and self._librarian.has_ocr():
            if "ocr" not in caps:
                caps.append("ocr")
        if self._librarian and self._librarian.has_vision():
            if "vision" not in caps:
                caps.append("vision")
        if self._librarian and self._librarian.has_zim():
            if "zim" not in caps:
                caps.append("zim")
        if self.config.allow_web:
            if "web_fallback" not in caps:
                caps.append("web_fallback")
        return caps

    def _get_models_list(self) -> list[str]:
        """Retorna lista de modelos disponíveis baseada em descoberta BEE-0003."""
        if self._capabilities and self._capabilities.ollama and self._capabilities.ollama.available:
            return self._capabilities.to_manifesto_dict().get("models", [])
        if self._librarian:
            return self._librarian.get_available_models()
        return []

    def _on_peer_discovered(self, peer: DiscoveredPeer) -> None:
        """Callback quando novo peer é descoberto."""
        logger.info(f"Peer descoberto: {peer.node_id} ({peer.role}) em {peer.host}:{peer.port}")
        self._maybe_form_cluster()

    def _maybe_form_cluster(self) -> None:
        """Reavalia a formação do enxame quando peers aparecem depois do boot.

        `_initialize_cluster()` roda UMA vez no startup, com uma janela de 2s de
        descoberta. No caso real — uma abelha ligada aqui, outra acolá, minutos
        depois — quem subiu sozinha ficava standalone para sempre, mesmo com o
        enxame completo na rede. Aqui o enxame se forma assim que o número de
        abelhas atinge o mínimo.

        Callback síncrono (vem do zeroconf), então apenas agenda a tarefa.
        """
        if not self._running or self._standalone is False:
            return  # ainda no boot, ou já faz parte de um enxame
        if not self._cluster_enabled():
            return  # opt-out do usuário: não formar enxame nem dinamicamente
        if self._cluster_reelect_task is not None:
            return  # já existe uma reavaliação agendada
        if not self._discovery:
            return
        total = len(self._discovery.get_active_peers()) + 1
        if total < self._min_bees_for_cluster():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # chamado fora de um loop asyncio: nada a agendar
        self._cluster_reelect_task = loop.create_task(self._reelect_cluster())

    async def _reelect_cluster(self) -> None:
        """Reexecuta a eleição com debounce e de forma serializada."""
        try:
            # Debounce: o mDNS anuncia vários peers em rajada. Esperar um pouco
            # evita uma eleição por peer descoberto e guerra de estados.
            await asyncio.sleep(3.0)
            async with self._cluster_reelect_lock:
                if not self._running or not self._standalone:
                    return
                logger.info("Peers suficientes descobertos: formando o enxame")
                await self._initialize_cluster()
                if not self._standalone:
                    # A ronda decide no construtor se agrega localmente ou
                    # reporta ao juiz; ao entrar num enxame é preciso recriá-la.
                    self._restart_guardian_patrol()
        except Exception as exc:
            logger.warning(f"Falha ao formar o enxame dinamicamente: {exc}")
        finally:
            self._cluster_reelect_task = None

    def _on_peer_lost(self, node_id: str) -> None:
        """Callback quando peer é perdido."""
        logger.warning(f"Peer perdido: {node_id}")

    async def _load_identity(self) -> None:
        """Carrega ou gera identidade persistente."""
        identity_file = self.config.data_dir / "identity.json"
        if identity_file.exists():
            import json
            with open(identity_file) as f:
                data = json.load(f)
            self.node_id = data.get("node_id", self.node_id)
            logger.info(f"Identidade carregada: {self.node_id}")
        else:
            # Identidade já foi gerada no config
            logger.info(f"Nova identidade: {self.node_id}")

    # =========================================================================
    # Interface web (web/) — mesmo contrato que o antigo juiz/app.py expunha
    # =========================================================================

    def _ui_new_session(self) -> str:
        """Cria um token de sessão para o browser."""
        token = secrets.token_urlsafe(16)
        self._ui_sessions[token] = datetime.now(UTC)
        return token

    def _ui_prune_sessions(self) -> None:
        now = datetime.now(UTC)
        for token in [t for t, ts in self._ui_sessions.items() if now - ts > UI_SESSION_TTL]:
            self._ui_sessions.pop(token, None)

    def _ui_session_ok(self, request: Any) -> bool:
        """Valida sessão pelo header x-session-token ou query string ?session=.

        O EventSource do browser não permite enviar headers, então o stream
        precisa aceitar o token por query string (igual ao juiz).
        """
        token = request.headers.get("x-session-token") or request.query.get("session")
        if not token or token not in self._ui_sessions:
            return False
        self._ui_sessions[token] = datetime.now(UTC)
        self._ui_prune_sessions()
        return True

    def _ui_node_snapshot(self, node_id: str, role: str, models: list[str]) -> dict[str, Any]:
        """Métricas de um nó no formato que web/app.js desenha no canvas."""
        cpu_pct = 0.0
        free_ram_gb = 0.0
        try:
            import psutil

            cpu_pct = psutil.cpu_percent(interval=None)
            free_ram_gb = round(psutil.virtual_memory().available / (1024 ** 3), 2)
        except Exception:
            pass

        active = sum(1 for t in self._ui_tasks.values() if t.status == "running")
        max_concurrency = max(1, int(getattr(self.config, "max_concurrent_queries", 4) or 4))
        return {
            "node_id": node_id,
            "cluster_role": role,
            "active_tasks": active if node_id == self.node_id else 0,
            "max_concurrency": max_concurrency,
            "queue_size": 0,
            "utilization": round(min(1.0, active / max_concurrency), 3),
            "cpu_pct": cpu_pct,
            "free_ram_gb": free_ram_gb,
            "est_tps": 0.0,
            "models": models,
            "fail_count": 0,
            "benchmark_score": 0.0,
            "paused": node_id in self._ui_paused,
            "ready": self._running,
        }

    def _ui_role_for(self, node_id: str, fallback: str = "") -> str:
        """Papel de um node para exibição no UI.

        `peer.role` vem do anúncio mDNS e é sempre "bee". Quem sabe o papel de
        cada abelha é o `cluster_state`, resultado da eleição. Enquanto o UI
        usava `peer.role`, todas as colegas apareciam como "bee" e o usuário não
        via o enxame (juiz / bibliotecária / guarda) que acabara de ser eleito —
        justamente o que a interface existe para mostrar.
        """
        role = ""
        if node_id == self.node_id:
            role = self._ui_cluster_role()
        elif self.cluster_state is not None:
            elected = self.cluster_state.get_role(node_id)
            if elected is not None:
                role = getattr(elected, "value", str(elected))
        if not role:
            role = fallback or "worker"
        # web/app.js compara com 'bibliotecaria' (feminino) para pintar de azul.
        return "bibliotecaria" if role == "bibliotecario" else role

    def _ui_cluster_role(self) -> str:
        """Papel para exibição no UI.

        Standalone (<3 peers): a abelha faz tudo sozinha na mesma máquina —
        recebe o prompt, consulta o próprio RAG, busca na web se preciso e faz
        a curadoria. Por isso aparece como 'juiz' (a rainha no canvas), e não
        como 'worker', que é o que cluster_role guarda internamente nesse caso.
        Em enxame, usa o papel eleito de fato.
        """
        if self._standalone or self.cluster_role is None:
            return "juiz"
        value = getattr(self.cluster_role, "value", str(self.cluster_role))
        # web/app.js compara com 'bibliotecaria' (feminino) para pintar de azul.
        return "bibliotecaria" if value == "bibliotecario" else value

    def _ui_models(self) -> list[str]:
        try:
            return list(self._get_models_list())
        except Exception:
            return [self.config.model] if self.config.model else []

    async def _ui_run_task(self, task: UiTask) -> None:
        """Executa o chat e publica os eventos que o UI espera."""
        task.status = "running"
        task.emit("task_received", task_id=task.task_id,
                  timestamp=datetime.now(UTC).isoformat())
        try:
            task.emit("decomposed", subtasks=1, timestamp=datetime.now(UTC).isoformat())
            result = await self.process_query(task.prompt)
            source = str(result.get("source", "local"))
            task.emit("dispatch", subtask=task.prompt[:120], specialty=source,
                      timestamp=datetime.now(UTC).isoformat())
            task.emit("judge", candidates=1, specialty=source,
                      confidence=result.get("confidence", 0.0),
                      timestamp=datetime.now(UTC).isoformat())
            answer = result.get("answer") or "(sem resposta)"
            if result.get("fallback"):
                answer += "  [fallback: nenhuma fonte local relevante]"
            task.emit("final", content=answer, source=source,
                      timestamp=datetime.now(UTC).isoformat())
            task.status = "completed"
        except asyncio.CancelledError:
            task.status = "cancelled"
            task.emit("error", message="tarefa cancelada")
            raise
        except Exception as e:
            logger.error(f"Erro na tarefa de UI {task.task_id}: {e}")
            task.status = "failed"
            task.emit("error", message=str(e))

    def _register_protocol_routes(self, app: Any) -> None:
        """Registra POST /api/v1/bee/message — o endpoint que RECEBE envelopes.

        Este era o único elo que faltava para o enxame existir de fato:

        * `BeeProtocolHandler.handle_message()` já estava completo (validação,
          expiração, verificação de assinatura HMAC, atualização de peer e
          dispatch para o handler do tipo);
        * `BeeService._register_protocol_handlers()` já registrava 11 handlers
          (HELLO, HEARTBEAT, KNOWLEDGE_QUERY, RESEARCH_REQUEST, MODEL_REQUEST,
          VISION_REQUEST, CAPABILITY_QUERY, STATE_CHANGE, PEER_LOST...);
        * os emissores `_send_to_peer()` e `_send_with_response()` já faziam
          POST para `/api/v1/bee/message`.

        Mas NENHUM node servia essa rota. Toda mensagem caía no mount estático
        "/" e voltava **405 Method Not Allowed**. Na prática o protocolo BEE
        inteiro era código morto: eleição de papéis, descoberta de quem tem o
        conhecimento offline, delegação de pesquisa e curadoria distribuída
        nunca chegaram a acontecer.

        Precisa ser registrada ANTES do mount estático em "/" (aiohttp casa as
        rotas na ordem de registro).
        """
        from aiohttp import web

        async def bee_message(request: Any) -> Any:
            try:
                data = await request.json()
            except Exception:
                return web.json_response({"error": "corpo JSON inválido"}, status=400)
            if not isinstance(data, dict):
                return web.json_response({"error": "corpo deve ser um objeto"}, status=400)

            try:
                envelope = BeeEnvelope.from_dict(data)
            except Exception as exc:
                logger.warning(f"Envelope BEE malformado recebido: {exc}")
                return web.json_response({"error": f"envelope inválido: {exc}"}, status=400)

            # Aceita broadcast (target_node_id None) e o que é para este node.
            # Rejeitar o endereçado a outro evita processar mensagem que chegou
            # aqui por engano (ex.: descoberta com porta trocada).
            if envelope.target_node_id and envelope.target_node_id != self.node_id:
                logger.debug(
                    f"Envelope destinado a {envelope.target_node_id} "
                    f"ignorado por {self.node_id}"
                )
                return web.json_response(
                    {"error": "destino não é este node",
                     "target_node_id": envelope.target_node_id},
                    status=404,
                )

            logger.debug(
                f"BEE recebido: {envelope.msg_type} de {envelope.source_node_id or '?'} "
                f"(correlation={envelope.correlation_id})"
            )

            try:
                response = await self._handler.handle_message(envelope)
            except Exception as exc:
                logger.error(f"Erro ao processar {envelope.msg_type}: {exc}")
                return web.json_response({"error": str(exc)}, status=500)

            if response is None:
                # Aceita sem resposta (ex.: HEARTBEAT_ACK, STATE_CHANGE, PEER_LOST)
                return web.json_response(
                    {"status": "accepted", "msg_id": envelope.msg_id}, status=202
                )
            return web.json_response(response.to_dict())

        app.router.add_post("/api/v1/bee/message", bee_message)

    def _register_ui_routes(self, app: Any) -> None:
        """Registra as rotas consumidas por web/app.js.

        Sem isto, o bee montava a pasta web/ em "/" mas não tinha NENHUM dos
        endpoints que o app.js chama (/api/session, /api/status, /api/chat,
        /api/chat/stream/{id}, /api/node/{id}/pause, /api/cluster/*): a página
        carregava e toda chamada dava 404.
        """
        from aiohttp import web

        async def ui_session(request: Any) -> Any:
            return web.json_response({"token": self._ui_new_session()})

        async def ui_status(request: Any) -> Any:
            if not self._ui_session_ok(request):
                return web.json_response({"detail": "Sessão inválida ou expirada"}, status=401)
            agents = [self._ui_node_snapshot(self.node_id, self._ui_cluster_role(), self._ui_models())]
            if self._discovery:
                for peer in self._discovery.get_active_peers():
                    agents.append(self._ui_node_snapshot(
                        peer.node_id,
                        self._ui_role_for(peer.node_id, peer.role or ""),
                        list(peer.models),
                    ))
            return web.json_response({
                "node": self.node_id,
                "agents": agents,
                "tasks_total": len(self._ui_tasks),
            })

        async def ui_models(request: Any) -> Any:
            if not self._ui_session_ok(request):
                return web.json_response({"detail": "Sessão inválida ou expirada"}, status=401)
            try:
                from core.ollama.client import OllamaClient, OllamaError

                client = OllamaClient(self.config.ollama_base_url)
                try:
                    models = await client.list_models()
                    best = await client.select_best_model()
                except OllamaError:
                    models, best = [], None
                finally:
                    await client.close()
            except Exception:
                models, best = [], None
            return web.json_response({
                "models": [{"name": m.name, "size_mb": round(m.size_mb, 1)} for m in models],
                "best": best,
            })

        async def ui_discover(request: Any) -> Any:
            if not self._ui_session_ok(request):
                return web.json_response({"detail": "Sessão inválida ou expirada"}, status=401)
            peers: list[dict[str, Any]] = []
            if self._discovery:
                for p in self._discovery.get_active_peers():
                    peers.append({
                        "node_id": p.node_id,
                        "ip": p.host,
                        "http_port": p.port,
                        "ws_port": p.port,
                        "role": self._ui_role_for(p.node_id, p.role or ""),
                        "score": round(score_peer(p), 2),
                        "models": list(p.models),
                    })
            return web.json_response({"peers": peers})

        async def ui_chat(request: Any) -> Any:
            if not self._ui_session_ok(request):
                return web.json_response({"detail": "Sessão inválida ou expirada"}, status=401)
            try:
                body = await request.json()
            except Exception:
                body = {}
            prompt = str((body or {}).get("prompt", "")).strip()
            if not prompt:
                return web.json_response({"detail": "Campo 'prompt' é obrigatório"}, status=400)

            task_id = f"t-{secrets.token_hex(5)}"
            task = UiTask(task_id=task_id, prompt=prompt)
            self._ui_tasks[task_id] = task
            # Limpeza simples: mantém no máximo as 200 últimas tarefas.
            if len(self._ui_tasks) > 200:
                for old in sorted(self._ui_tasks, key=lambda k: self._ui_tasks[k].created_at)[:-200]:
                    self._ui_tasks.pop(old, None)

            asyncio.create_task(self._ui_run_task(task))
            return web.json_response({"task_id": task_id, "status": task.status})

        async def ui_stream(request: Any) -> Any:
            if not self._ui_session_ok(request):
                return web.json_response({"detail": "Sessão inválida ou expirada"}, status=401)
            task_id = request.match_info["task_id"]
            task = self._ui_tasks.get(task_id)
            if task is None:
                return web.json_response({"detail": "Tarefa não encontrada"}, status=404)

            resp = web.StreamResponse(
                status=200,
                headers={
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
            await resp.prepare(request)

            sent = 0
            while True:
                while sent < len(task.events):
                    payload = json.dumps(task.events[sent], ensure_ascii=False)
                    await resp.write(f"data: {payload}\n\n".encode("utf-8"))
                    sent += 1
                if task.status in {"completed", "failed", "cancelled"} and sent >= len(task.events):
                    break
                await asyncio.sleep(0.1)
            with suppress(Exception):
                await resp.write_eof()
            return resp

        async def ui_pause(request: Any) -> Any:
            if not self._ui_session_ok(request):
                return web.json_response({"detail": "Sessão inválida ou expirada"}, status=401)
            node_id = request.match_info["node_id"]
            known = {self.node_id}
            if self._discovery:
                known |= {p.node_id for p in self._discovery.get_active_peers()}
            if node_id not in known:
                return web.json_response({"detail": "Nó não encontrado"}, status=404)
            try:
                body = await request.json()
            except Exception:
                body = {}
            paused = bool((body or {}).get("paused", True))
            if paused:
                self._ui_paused.add(node_id)
            else:
                self._ui_paused.discard(node_id)
            return web.json_response({"node_id": node_id, "paused": paused})

        async def ui_guardian(request: Any) -> Any:
            """Estado de segurança desta abelha: guarda ativo, contadores de
            inspeção e alertas da ronda. Sem isto não há como o usuário
            constatar que a rotina de guarda está de fato rodando."""
            if not self._ui_session_ok(request):
                return web.json_response({"detail": "Sessão inválida ou expirada"}, status=401)
            return web.json_response(self.guardian_summary())

        app.router.add_post("/api/session", ui_session)
        app.router.add_get("/api/status", ui_status)
        app.router.add_get("/api/cluster/models", ui_models)
        app.router.add_get("/api/cluster/discover", ui_discover)
        app.router.add_post("/api/chat", ui_chat)
        app.router.add_get("/api/chat/stream/{task_id}", ui_stream)
        app.router.add_post("/api/node/{node_id}/pause", ui_pause)
        app.router.add_get("/api/guardian", ui_guardian)

    async def _start_http_server(self) -> None:
        """Inicia servidor HTTP para API, WebSocket e UI estática."""
        from aiohttp import web
        from aiohttp.web import Request, Response
        from pathlib import Path

        app = web.Application()

        # Health check
        async def health(request: Request) -> Response:
            return web.json_response({
                "status": "ok",
                "node_id": self.node_id,
                "state": self.state.value,
                "peers": len(self._discovery.get_active_peers()) if self._discovery else 0,
                "offline_mode": self.config.offline_mode,
            })

        # Query endpoint (processa LOCAL -> ENXAME -> WEB)
        async def query(request: Request) -> Response:
            try:
                data = await request.json()
                query_text = data.get("query", "").strip()
                if not query_text:
                    return web.json_response({"error": "query required"}, status=400)

                result = await self.process_query(query_text)
                return web.json_response(result)
            except Exception as e:
                logger.error(f"Erro no query: {e}")
                return web.json_response({"error": str(e)}, status=500)

        # Capabilities endpoint
        async def capabilities(request: Request) -> Response:
            return web.json_response({
                "capabilities": self._get_capabilities_list(),
                "models": self._get_models_list(),
                "indexes": ["documents"] if self._librarian else [],
                "load": self._calculate_load(),
            })

        # Peer discovery endpoint
        async def peers(request: Request) -> Response:
            if not self._discovery:
                return web.json_response({"peers": []})
            peers = self._discovery.get_active_peers()
            return web.json_response({"peers": [
                {
                    "node_id": p.node_id,
                    "role": p.role,
                    "host": p.host,
                    "port": p.port,
                    "capabilities": p.capabilities,
                    "models": p.models,
                    "load": p.load,
                    "state": p.state.value,
                }
                for p in peers
            ]})

        # Status endpoint (para UI)
        async def status(request: Request) -> Response:
            peer_count = len(self._discovery.get_active_peers()) if self._discovery else 0
            ollama_available = False
            try:
                import httpx
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(f"{self.config.ollama_base_url}/api/tags")
                    ollama_available = resp.status_code == 200
            except Exception:
                pass
            
            return web.json_response({
                "kernel": "online" if self.state == BeeState.RUNNING else self.state.value,
                "runtime": "online" if self.state == BeeState.RUNNING else self.state.value,
                "bibliotecario": "online" if self._librarian else "offline",
                "ollama": "online" if ollama_available else "offline",
                "peers": peer_count,
                "offline_mode": self.config.offline_mode,
            })

        # File ingestion endpoint
        async def ingest(request: Request) -> Response:
            try:
                # Multipart form data
                reader = await request.multipart()
                file_field = None
                async for field in reader:
                    if field.name == 'file':
                        file_field = field
                        break
                
                if not file_field:
                    return web.json_response({"error": "file required"}, status=400)
                
                filename = file_field.filename
                content = await file_field.read()
                
                if self._librarian:
                    # Salvar arquivo temporário e processar
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
                        tmp.write(content)
                        tmp_path = tmp.name
                    
                    try:
                        result = await self._librarian.indexer.index_file(tmp_path)
                        return web.json_response({
                            "success": True,
                            "document_id": result.get("document_id"),
                            "chunks": result.get("chunks", 0),
                            "filename": filename,
                        })
                    finally:
                        import os
                        os.unlink(tmp_path)
                else:
                    return web.json_response({"error": "Librarian not available"}, status=503)
                    
            except Exception as e:
                logger.error(f"Erro no ingest: {e}")
                return web.json_response({"error": str(e)}, status=500)

        app.router.add_get("/health", health)
        app.router.add_get("/api/v1/status", status)
        app.router.add_post("/api/v1/query", query)
        app.router.add_get("/api/v1/capabilities", capabilities)
        app.router.add_get("/api/v1/peers", peers)
        app.router.add_post("/api/v1/ingest", ingest)

        # Protocolo BEE entre abelhas + rotas da interface web (web/app.js).
        # Precisam vir ANTES do mount estático em "/" — no aiohttp as rotas
        # casam na ordem de registro, e add_static('/') capturaria tudo que não
        # estivesse registrado acima (era assim que /api/v1/bee/message voltava
        # 405 em vez de chegar ao handler).
        self._register_protocol_routes(app)
        self._register_ui_routes(app)

        # Servir arquivos estáticos da Web UI
        # parents[1] = raiz do repositório (este arquivo é <repo>/bees/service.py).
        # Antes usava parents[2], que apontava para FORA do repositório
        # (<pai-do-repo>/web), então a pasta nunca existia e a UI nunca era
        # servida — o browser recebia 404 em "/".
        web_dir = Path(__file__).resolve().parents[1] / "web"
        index_file = web_dir / "index.html"
        if index_file.is_file():
            # Rota explícita para "/" e "/index.html".
            #
            # Isto é obrigatório: o add_static do aiohttp NÃO serve index.html
            # sozinho. Para um caminho que é diretório ele faz exatamente duas
            # coisas (web_urldispatcher.StaticResource._resolve_path_to_response):
            #   show_index=True  -> devolve a LISTAGEM do diretório
            #   show_index=False -> devolve 403 Forbidden
            # Ou seja, com show_index=True (o que estava aqui) quem abria
            # http://localhost:8765/ via "Index of /." com links para app.js e
            # style.css em vez da interface - a URL que o instalador manda abrir
            # nunca mostrou o painel. Com show_index=False daria 403. A rota
            # registrada antes do mount resolve os dois casos e ainda evita
            # expor a listagem de arquivos.
            async def _serve_index(request: web.Request) -> web.FileResponse:
                return web.FileResponse(index_file)

            app.router.add_get('/', _serve_index)
            app.router.add_get('/index.html', _serve_index)
            app.router.add_static('/', web_dir, show_index=False)
            logger.info(f"Servindo Web UI de {web_dir}")
        elif web_dir.exists():
            app.router.add_static('/', web_dir, show_index=False)
            logger.warning(
                f"Web UI sem index.html em {web_dir}: servindo apenas estáticos"
            )
        else:
            logger.warning(f"Web UI não encontrada em {web_dir}")

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.config.host, self.config.port)
        await site.start()
        logger.info(f"Servidor HTTP iniciado em {self.config.host}:{self.config.port}")

        self._http_runner = runner

    async def _add_routes_to_app(self, app: "web.Application") -> None:
        """Adiciona rotas da Abelha a uma aplicação aiohttp externa (para EnxameKernel)."""
        from aiohttp.web import Request, Response

        # Health check
        async def health(request: Request) -> Response:
            return web.json_response({
                "status": "ok",
                "node_id": self.node_id,
                "state": self.state.value,
                "peers": len(self._discovery.get_active_peers()) if self._discovery else 0,
            })

        # Query endpoint (processa LOCAL -> ENXAME -> WEB)
        async def query(request: Request) -> Response:
            try:
                data = await request.json()
                query_text = data.get("query", "").strip()
                if not query_text:
                    return web.json_response({"error": "query required"}, status=400)

                result = await self.process_query(query_text)
                return web.json_response(result)
            except Exception as e:
                logger.error(f"Erro no query: {e}")
                return web.json_response({"error": str(e)}, status=500)

        # Capabilities endpoint
        async def capabilities(request: Request) -> Response:
            caps = self._get_capabilities_list()
            if self.cluster_state:
                caps.append("cluster")
            return web.json_response({
                "capabilities": caps,
                "models": self._get_models_list(),
                "indexes": ["documents"] if self._librarian else [],
                "load": self._calculate_load(),
            })

        # Cluster status endpoint (EIP-0009)
        async def cluster_status(request: Request) -> Response:
            if not self.cluster_state:
                return web.json_response({
                    "cluster": False,
                    "message": "Operando como standalone (menos de 3 peers)"
                })
            
            return web.json_response({
                "cluster": True,
                "epoch": self.cluster_state.epoch,
                "my_role": self.cluster_role.value if self.cluster_role else "unknown",
                "roles": {
                    "juiz": self.cluster_state.juiz_id,
                    "bibliotecario": self.cluster_state.bibliotecario_id,
                    "guarda": self.cluster_state.guarda_id,
                    "workers": self.cluster_state.workers,
                    "artist_workers": self.cluster_state.artist_workers,
                },
                "secondary_roles": {
                    k: [r.value for r in v] for k, v in self.cluster_state.secondary_roles.items()
                },
                "juiz_failover_active": self.cluster_state.is_juiz_failover_active(),
                "juiz_failover_elapsed_hours": round(self.cluster_state.get_juiz_failover_elapsed_hours(), 2),
                "global_index_stats": {
                    "domains": len(self.cluster_state.global_index),
                    "entries": sum(len(v) for v in self.cluster_state.global_index.values()),
                },
                "internet_access": [p.value for p in self._internet_gate.get_allowed_purposes()] if self._internet_gate else [],
            })

        # Peer discovery endpoint
        async def peers(request: Request) -> Response:
            if not self._discovery:
                return web.json_response({"peers": []})
            peers = self._discovery.get_active_peers()
            return web.json_response({"peers": [
                {
                    "node_id": p.node_id,
                    "role": p.role,
                    "host": p.host,
                    "port": p.port,
                    "capabilities": p.capabilities,
                    "models": p.models,
                }
                for p in peers
            ]})

        app.router.add_get("/health", health)
        app.router.add_post("/api/v1/query", query)
        app.router.add_get("/api/v1/capabilities", capabilities)
        app.router.add_get("/api/v1/cluster", cluster_status)
        app.router.add_get("/api/v1/peers", peers)

        # Protocolo BEE e interface web: mesmo contrato, também quando a
        # Abelha roda embutida numa aplicação aiohttp externa (EnxameKernel).
        self._register_protocol_routes(app)
        self._register_ui_routes(app)

        logger.info("Rotas da Abelha registradas na aplicação externa")

    def _calculate_load(self) -> float:
        """Calcula carga atual da Abelha (0.0 a 1.0)."""
        import psutil
        cpu = psutil.cpu_percent(interval=0.1) / 100.0
        mem = psutil.virtual_memory().percent / 100.0
        return (cpu + mem) / 2.0

    # =========================================================================
    # Handlers do Protocolo BEE
    # =========================================================================

    async def _handle_hello(self, envelope: BeeEnvelope) -> BeeEnvelope:
        """Handler para HELLO - handshake inicial."""
        from .protocol.messages import BeeHello, BeeHelloAck, BeeIdentity, BeeManifesto
        import secrets

        hello = BeeHello.from_dict(envelope.payload)
        logger.info(f"HELLO recebido de {hello.identity.node_id}")

        # Gerar nonce para resposta
        nonce = secrets.token_urlsafe(16)

        # Criar nosso manifesto
        manifesto = BeeManifesto(
            capabilities=self._get_capabilities_list(),
            models=self._get_models_list(),
            indexes=["documents"] if self._librarian else [],
            load=self._calculate_load(),
            uptime_seconds=int(asyncio.get_event_loop().time()),
            version="1.0.0",
        )

        hello_ack = BeeHelloAck(
            identity=BeeIdentity(node_id=self.node_id, protocol_version="1.0"),
            manifesto=manifesto,
            nonce=nonce,
            echo_nonce=hello.nonce,
        )

        return self._handler.create_hello_ack(
            target_node_id=envelope.source_node_id,
            manifesto=manifesto,
            nonce=nonce,
            echo_nonce=hello.nonce,
            correlation_id=envelope.correlation_id or envelope.msg_id,
        )

    async def _handle_hello_ack(self, envelope: BeeEnvelope) -> BeeEnvelope | None:
        """Handler para HELLO_ACK - resposta do handshake."""
        from .protocol.messages import BeeHelloAck
        hello_ack = BeeHelloAck.from_dict(envelope.payload)
        logger.info(f"HELLO_ACK recebido de {hello_ack.identity.node_id}")
        # Armazenar manifesto do peer
        if self._discovery:
            await self._discovery.update_peer_manifesto(envelope.source_node_id, hello_ack.manifesto)
        return None

    async def _handle_heartbeat(self, envelope: BeeEnvelope) -> BeeEnvelope:
        """Handler para HEARTBEAT."""
        from .protocol.messages import BeeHeartbeat
        heartbeat = BeeHeartbeat.from_dict(envelope.payload)

        if self._discovery:
            await self._discovery.update_peer_heartbeat(
                envelope.source_node_id,
                heartbeat.state,
                heartbeat.load,
                heartbeat.sequence,
            )

        return self._handler.create_heartbeat_ack(
            target_node_id=envelope.source_node_id,
            ack_sequence=heartbeat.sequence,
            load=self._calculate_load(),
        )

    async def _handle_heartbeat_ack(self, envelope: BeeEnvelope) -> BeeEnvelope | None:
        """Handler para HEARTBEAT_ACK."""
        from .protocol.messages import BeeHeartbeatAck
        ack = BeeHeartbeatAck.from_dict(envelope.payload)
        if self._discovery:
            await self._discovery.confirm_heartbeat(envelope.source_node_id, ack.ack_sequence)
        return None

    async def _handle_knowledge_query(self, envelope: BeeEnvelope) -> BeeEnvelope:
        """Handler para KNOWLEDGE_QUERY - consulta leve de conhecimento."""
        from .protocol.messages import BeeKnowledgeQuery
        query = BeeKnowledgeQuery.from_dict(envelope.payload)

        has_knowledge = False
        confidence = 0.0
        document_count = 0
        topics = []

        if self._librarian:
            # Verificação rápida sem RAG completo
            result = await self._librarian.quick_knowledge_check(query.subject, query.keywords)
            has_knowledge = result.get("has_knowledge", False)
            confidence = result.get("confidence", 0.0)
            document_count = result.get("document_count", 0)
            topics = result.get("topics", [])

        return self._handler.create_knowledge_response(
            target_node_id=envelope.source_node_id,
            query_id=query.query_id,
            has_knowledge=has_knowledge,
            confidence=confidence,
            document_count=document_count,
            topics=topics,
            correlation_id=envelope.correlation_id,
        )

    async def _handle_research_request(self, envelope: BeeEnvelope) -> BeeEnvelope:
        """Handler para RESEARCH_REQUEST - pesquisa completa com RAG."""
        from .protocol.messages import BeeResearchRequest, ResearchResultItem
        request = BeeResearchRequest.from_dict(envelope.payload)

        # `LocalLibrarian.search()` devolve {"answer","confidence","source",
        # "metadata","sources"} — NÃO existe chave "results". O laço antigo
        # iterava search_result.get("results", []), que era sempre vazio, então
        # RESEARCH_RESULT voltava com zero itens e o juiz descartava a resposta
        # mesmo quando a abelha consultada TINHA o conhecimento. Era o último
        # elo quebrado da delegação no enxame.
        results = []
        started = time.perf_counter()

        # GUARDA — quem RECEBE a pergunta delegada também inspeciona.
        # A especificação pede a rotina de guarda em quem recebe o prompt e em
        # quem faz a curadoria. No enxame o texto chega aqui pela rede, vindo de
        # outra abelha; sem inspeção, um prompt malicioso já barrado pelo juiz
        # entraria pela porta lateral do RESEARCH_REQUEST. Devolver zero itens
        # faz o juiz cair no fallback normal.
        bloqueado = self._guard_prompt(request.query) is not None
        if bloqueado:
            logger.warning(f"RESEARCH_REQUEST bloqueado pelo guardião em {self.node_id}")

        if self._librarian and not bloqueado:
            search_result = await self._librarian.search(request.query, request.max_results)
            answer = str(search_result.get("answer") or "").strip()
            if answer:
                metadata = dict(search_result.get("metadata") or {})
                # Proveniência vai no metadata (não como itens separados): o juiz
                # concatena o conteúdo dos itens, e repetir o mesmo texto uma vez
                # por arquivo duplicaria a resposta.
                metadata["sources"] = list(search_result.get("sources") or [])
                metadata["answered_by"] = self.node_id
                results.append(ResearchResultItem(
                    content=answer,
                    source=search_result.get("source"),
                    confidence=float(search_result.get("confidence", 0.0)),
                    metadata=metadata,
                ))
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        return self._handler.create_research_result(
            target_node_id=envelope.source_node_id,
            request_id=request.request_id,
            results=results,
            total_results=len(results),
            processing_time_ms=elapsed_ms,
            model_used=self.config.model,
            correlation_id=envelope.correlation_id,
        )

    async def _handle_model_request(self, envelope: BeeEnvelope) -> BeeEnvelope:
        """Handler para MODEL_REQUEST - inferência usando modelo local."""
        from .protocol.messages import BeeModelRequest
        request = BeeModelRequest.from_dict(envelope.payload)

        generation = ""
        if self._librarian:
            result = await self._librarian.generate(
                request.prompt,
                request.system_prompt,
                request.max_tokens,
                request.temperature,
            )
            generation = result.get("generation", "")

        return self._handler.create_model_response(
            target_node_id=envelope.source_node_id,
            request_id=request.request_id,
            generation=generation,
            model_used=self.config.model,
            correlation_id=envelope.correlation_id,
        )

    async def _handle_vision_request(self, envelope: BeeEnvelope) -> BeeEnvelope:
        """Handler para VISION_REQUEST - análise de imagem usando modelo de visão."""
        from .protocol.messages import BeeVisionRequest
        request = BeeVisionRequest.from_dict(envelope.payload)

        description = ""
        model_used = None
        error = None
        processing_time_ms = 0

        if self._librarian:
            import time
            start = time.perf_counter()
            try:
                image_bytes = base64.b64decode(request.image_base64)
                if request.structured_output:
                    result = await self._librarian.analyze_image_with_structured_output(image_bytes)
                else:
                    result = await self._librarian.analyze_image(
                        image_bytes,
                        request.prompt,
                        request.system_prompt,
                    )
                description = result.get("description", "")
                model_used = result.get("model")
                error = result.get("error")
            except Exception as e:
                error = str(e)
                logger.error(f"Erro na visão: {e}")
            processing_time_ms = int((time.perf_counter() - start) * 1000)

        return self._handler.create_vision_response(
            target_node_id=envelope.source_node_id,
            request_id=request.request_id,
            description=description,
            model_used=model_used,
            processing_time_ms=processing_time_ms,
            error=error,
            correlation_id=envelope.correlation_id,
        )

    async def _handle_capability_query(self, envelope: BeeEnvelope) -> BeeEnvelope:
        """Handler para CAPABILITY_QUERY."""
        from .protocol.messages import BeeCapabilityQuery
        query = BeeCapabilityQuery.from_dict(envelope.payload)

        has_cap = query.capability in self._get_capabilities_list()

        return self._handler.create_capability_response(
            target_node_id=envelope.source_node_id,
            has_capability=has_cap,
            confidence=1.0 if has_cap else 0.0,
            document_count=0,
            correlation_id=envelope.correlation_id,
        )

    async def _handle_state_change(self, envelope: BeeEnvelope) -> BeeEnvelope | None:
        """Handler para STATE_CHANGE - notificação de mudança de estado de peer."""
        from .protocol.messages import BeeStateChange, BeeState
        state_change = BeeStateChange.from_dict(envelope.payload)
        logger.info(f"Peer {state_change.node_id} mudou para estado: {state_change.new_state.value} - {state_change.reason}")
        
        # Atualizar peer no discovery
        if self._discovery and state_change.node_id in self._discovery._peers:
            peer = self._discovery._peers[state_change.node_id]
            peer.state = state_change.new_state
            if state_change.new_state == BeeState.STOPPING:
                # Peer vai parar, remover após timeout estimado
                pass
        
        # Cluster-specific handling (EIP-0009)
        if self.cluster_state and state_change.reason in ("juiz_failover", "juiz_restored", "new_election"):
            if state_change.reason == "juiz_failover":
                logger.warning(f"Failover de Juiz detectado: {state_change.node_id} assumiu")
                # Atualizar estado local se necessário
            elif state_change.reason == "juiz_restored":
                logger.info(f"Juiz original restaurado: {state_change.node_id}")
            elif state_change.reason == "new_election":
                logger.info(f"Nova eleição no cluster detectada")
                # Forçar re-eleição local na próxima verificação
                self.cluster_state.epoch = 0  # Marcar para re-eleição
        
        return None

    async def _handle_peer_lost(self, envelope: BeeEnvelope) -> BeeEnvelope | None:
        """Handler para PEER_LOST - notificação de peer perdido."""
        from .protocol.messages import BeePeerLost
        peer_lost = BeePeerLost.from_dict(envelope.payload)
        logger.warning(f"Peer perdido notificado: {peer_lost.node_id} - {peer_lost.reason}")
        
        # Remover peer do discovery se estiver lá
        if self._discovery:
            self._discovery._remove_peer(peer_lost.node_id)
        return None

    # =========================================================================
    # Loops de Background
    # =========================================================================

    async def _heartbeat_loop(self) -> None:
        """Envia heartbeats periódicos para peers ativos."""
        while self._running:
            try:
                if self._discovery:
                    peers = self._discovery.get_active_peers()
                    load = self._calculate_load()
                    for peer in peers:
                        envelope = self._handler.create_heartbeat()
                        # Atualizar load no heartbeat
                        envelope.payload["load"] = load
                        await self._send_to_peer(peer, envelope)
            except Exception as e:
                logger.error(f"Erro no heartbeat loop: {e}")
            await asyncio.sleep(self.config.heartbeat_interval)

    async def _peer_maintenance_loop(self) -> None:
        """Mantém lista de peers ativos, remove inativos."""
        while self._running:
            try:
                if self._discovery:
                    await self._discovery.cleanup_stale_peers()
            except Exception as e:
                logger.error(f"Erro no peer maintenance: {e}")
            await asyncio.sleep(30)

    async def _load_metrics_loop(self) -> None:
        """Atualiza métricas de carga e reanuncia via mDNS."""
        while self._running:
            try:
                load = self._calculate_load()
                # Atualizar anúncio mDNS com nova carga via BeeDiscoveryService
                if self._discovery:
                    await self._discovery.update_announcement(load, self.state)
            except Exception as e:
                logger.error(f"Erro no load metrics: {e}")
            await asyncio.sleep(60)

    async def _send_to_peer(self, peer: DiscoveredPeer, envelope: BeeEnvelope) -> None:
        """Envia envelope para peer via HTTP."""
        try:
            import aiohttp
            url = f"http://{peer.host}:{peer.port}/api/v1/bee/message"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=envelope.to_dict(), timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        response_envelope = BeeEnvelope.from_dict(data)
                        self._handler.complete_pending_request(envelope.correlation_id or envelope.msg_id, response_envelope)
        except Exception as e:
            logger.debug(f"Falha ao enviar para {peer.node_id}: {e}")

    # =========================================================================
    # Pipeline de Query: LOCAL -> ENXAME -> WEB
    # =========================================================================

    # ------------------------------------------------------------------
    # Guarda (rotina de segurança da abelha)
    # ------------------------------------------------------------------
    def _init_guardian(self) -> None:
        """Cria o guardião desta abelha.

        Tolerante a falha: um erro ao criar o guardião não pode impedir o node
        de subir, mas fica registrado em WARNING.
        """
        if Guardian is None:
            logger.warning(
                "Pacote 'guardian' não importável: esta abelha está rodando SEM "
                "inspeção de segurança de prompts/respostas"
            )
            return
        try:
            self._guardian = Guardian(self.node_id)
        except Exception as exc:
            logger.warning(f"Não foi possível iniciar o guardião: {exc}")
            self._guardian = None
            return

        # O Guardian cria './quarantine' relativo ao CWD no próprio __init__, o
        # que sujaria o diretório de onde o usuário executou o comando (no
        # repositório, apareceria como pasta não rastreada). Aponta para o
        # data_dir da abelha e remove a pasta stray, se estiver vazia.
        stray = Path("quarantine")
        try:
            quarantine = Path(self.config.data_dir) / "quarantine"
            quarantine.mkdir(parents=True, exist_ok=True)
            self._guardian.quarantine_dir = str(quarantine)
        except Exception as exc:
            logger.debug(f"Não foi possível mover o quarantine para o data_dir: {exc}")
        else:
            try:
                # rmdir só remove diretório VAZIO: se houver algo dentro (ou se a
                # pasta já existia com conteúdo do usuário), falha sem efeito.
                stray.rmdir()
            except OSError:
                pass

        logger.info(f"Guardião ativo em {self.node_id}")

    def _guard_prompt(self, prompt: str) -> dict[str, Any] | None:
        """ENTRADA: inspeciona o prompt antes de processá-lo.

        Retorna um resultado já bloqueado (pronto para o UI) quando o guardião
        reprova, ou None quando o prompt pode seguir.
        """
        if not self._guardian:
            return None

        self._guard_stats["prompts_inspecionados"] += 1
        try:
            verdict = self._guardian.inspect_prompt(prompt)
        except Exception as exc:
            # Uma falha na inspeção não pode derrubar a consulta inteira.
            logger.warning(f"Inspeção de segurança falhou, seguindo sem ela: {exc}")
            return None

        if verdict.get("safe"):
            return None

        reasons = [str(r) for r in (verdict.get("reasons") or [])]
        self._guard_stats["prompts_bloqueados"] += 1
        logger.warning(
            f"Guardião bloqueou prompt em {self.node_id} "
            f"(camada {verdict.get('layer')}): {reasons}"
        )
        return {
            "answer": verdict.get("error_message")
            or "Requisição bloqueada pela rotina de guarda.",
            "source": "guardian",
            "confidence": 0.0,
            "blocked": True,
            "guard": {"layer": verdict.get("layer"), "reasons": reasons},
        }

    def _guard_answer(self, answer: str) -> str:
        """CURADORIA: inspeciona a resposta antes de entregá-la ao usuário.

        Isso importa sobretudo no RAG: um documento indexado pode carregar
        instruções injetadas que só se revelam na saída, então inspecionar só a
        entrada não basta.
        """
        if not answer or not self._guardian:
            return answer

        self._guard_stats["respostas_inspecionadas"] += 1
        try:
            verdict = self._guardian.inspect_prompt(answer)
        except Exception as exc:
            logger.debug(f"Curadoria de segurança falhou: {exc}")
            return answer

        if verdict.get("safe"):
            return answer

        reasons = ", ".join(str(r) for r in (verdict.get("reasons") or []))[:180]
        self._guard_stats["respostas_retidas"] += 1
        logger.warning(f"Guardião reteve resposta na curadoria: {reasons}")
        return (
            "\u26a0\ufe0f A resposta foi retida pela rotina de guarda: o conteúdo "
            f"gerado apresenta padrões inseguros ({reasons}). Reformule a pergunta "
            "ou revise os documentos indexados nesta abelha."
        )

    def _record_guardian_alert(self, alert: dict[str, Any]) -> None:
        """Guarda alertas localmente, em anel limitado (não cresce sem fim)."""
        self._guardian_alerts.append(alert)
        if len(self._guardian_alerts) > 50:
            del self._guardian_alerts[: len(self._guardian_alerts) - 50]

    async def _report_guardian_alert_to_juiz(self, alert: dict[str, Any]) -> None:
        """Em enxame, reporta a ronda ao juiz (POST assinado).

        Mesmo contrato que o antigo bibliotecario/app.py usava: agrega o estado de
        segurança do cluster em /api/v1/guardian.
        """
        juiz_url = os.getenv("JUIZ_HTTP_URL", "http://localhost:7700")
        body = json.dumps(alert, ensure_ascii=False).encode("utf-8")
        headers: dict[str, str] = {"content-type": "application/json"}
        if self._security:
            try:
                headers.update(build_auth_headers(self._security, body))
            except Exception as exc:
                logger.debug(f"Sem assinatura EXP no alerta do guardião: {exc}")
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{juiz_url}/api/v1/guardian/report", content=body, headers=headers
                )
        except Exception as exc:
            logger.debug(f"Falha ao reportar alerta do guardião ao juiz: {exc}")

    def _start_guardian_patrol(self) -> "asyncio.Task | None":
        """Inicia a ronda contínua do guardião nesta abelha.

        Standalone: a abelha é o próprio juiz, então agrega os alertas
        localmente. Em enxame: agrega localmente E reporta ao juiz.
        """
        if GuardianPatrol is None or self._guardian is None:
            return None
        try:
            interval = float(os.getenv("GUARDIAN_PATROL_INTERVAL", "15"))
        except ValueError:
            interval = 15.0
        try:
            self._guardian_patrol = GuardianPatrol(
                node_id=self.node_id,
                interval_seconds=interval,
                local_callback=self._record_guardian_alert,
                remote_reporter=None if self._standalone else self._report_guardian_alert_to_juiz,
            )
        except Exception as exc:
            logger.warning(f"Não foi possível criar a ronda do guardião: {exc}")
            return None

        logger.info(
            "Ronda do guardião ativa "
            f"({'standalone: alertas locais' if self._standalone else 'reportando ao juiz'})"
        )
        self._patrol_task = asyncio.create_task(self._guardian_patrol.run_forever())
        return self._patrol_task

    def _restart_guardian_patrol(self) -> None:
        """Recria a ronda para refletir o modo atual (standalone <-> enxame).

        `GuardianPatrol` decide no construtor se entrega alertas localmente
        (este node É o juiz) ou se os reporta por POST assinado ao juiz. Quando
        o enxame se forma depois do boot, essa decisão muda e a ronda precisa
        ser recriada — senão a abelha continuaria agregando alertas sozinha em
        vez de enviá-los ao juiz eleito.
        """
        if self._guardian_patrol is not None:
            self._guardian_patrol.stop()
            self._guardian_patrol = None
        old_task = self._patrol_task
        self._patrol_task = None
        if old_task is not None:
            old_task.cancel()
            if old_task in self._tasks:
                self._tasks.remove(old_task)
        new_task = self._start_guardian_patrol()
        if new_task is not None:
            self._tasks.append(new_task)

    def guardian_summary(self) -> dict[str, Any]:
        """Estado de segurança desta abelha (observabilidade)."""
        return {
            "node_id": self.node_id,
            "ativo": self._guardian is not None,
            "ronda": self._guardian_patrol is not None,
            "standalone": self._standalone,
            "contadores": dict(self._guard_stats),
            "alertas": list(self._guardian_alerts),
        }

    async def process_query(self, query: str) -> dict[str, Any]:
        """
        Processa query seguindo a política LOCAL -> ENXAME -> WEB (com cluster),
        com a rotina de guarda nas duas pontas: inspeção do prompt na ENTRADA e
        curadoria da resposta na SAÍDA.

        Returns:
            dict com answer, source, confidence, metadata
        """
        # GUARDA — entrada: quem recebe o prompt inspeciona antes de processar.
        blocked = self._guard_prompt(query)
        if blocked is not None:
            return blocked

        result = await self._process_query_policy(query)

        # GUARDA — curadoria: a resposta também é inspecionada antes de sair.
        if not result.get("blocked"):
            answer = result.get("answer")
            if isinstance(answer, str) and answer:
                curated = self._guard_answer(answer)
                if curated != answer:
                    result["answer"] = curated
                    result["source"] = "guardian"
                    result["curated"] = True
        return result

    async def _process_query_policy(self, query: str) -> dict[str, Any]:
        """Política LOCAL -> ENXAME -> WEB.

        Chamado por process_query, que acrescenta a inspeção de guarda na
        entrada e na saída.
        """
        logger.info(f"Processando query: {query[:100]}...")

        # 1. LOCAL - Memória semântica + RAG local
        local_result = await self._query_local(query)
        if local_result["confidence"] >= self.config.confidence_threshold_enxame:
            return {"answer": local_result["answer"], "source": "local", **local_result}

        # 2. ENXAME - Consultar peers se disponíveis
        if self._discovery and self._discovery.get_active_peers():
            enxame_result = await self._query_enxame(query)
            if enxame_result["confidence"] >= self.config.confidence_threshold_web:
                return {"answer": enxame_result["answer"], "source": "enxame", **enxame_result}

        # 3. WEB - Fallback se habilitado E papel permite (EIP-0009)
        if self.config.allow_web and self._librarian and self._internet_gate:
            if self._internet_gate.can_access(InternetPurpose.BIBLIOTECARIO_FALLBACK):
                web_result = await self._librarian.search_web(query)
                return {"answer": web_result.get("answer", ""), "source": "web", **web_result}
            else:
                logger.debug(f"Node {self.node_id} sem permissão de acesso à internet para fallback")

        # Fallback: melhor resultado disponível
        return {
            "answer": local_result.get("answer", "Não encontrei informação relevante."),
            "source": "local",
            "confidence": local_result.get("confidence", 0.0),
            "fallback": True,
        }

    async def _query_local(self, query: str) -> dict[str, Any]:
        """Consulta fontes locais: memória + RAG."""
        # 1. Memória semântica
        if self._memory:
            # BeeMemory é 100% síncrono (sqlite3, criado com check_same_thread=False).
            # `await self._memory.search_semantic(...)` estourava
            # "object NoneType can't be used in 'await' expression" e quebrava
            # todo POST /api/v1/query. Roda em thread para não bloquear o loop.
            mem_result = await asyncio.to_thread(self._memory.search_semantic, query)
            if mem_result and mem_result.get("confidence", 0) > 0.8:
                return {"answer": mem_result["response"], "confidence": mem_result["confidence"], "source_type": "memory"}

        # 2. RAG local via Bibliotecário
        if self._librarian:
            result = await self._librarian.search(query)
            return {
                "answer": result.get("answer", ""),
                "confidence": result.get("confidence", 0.0),
                "source_type": "rag",
                "metadata": result.get("metadata", {}),
            }

        return {"answer": "", "confidence": 0.0, "source_type": "none"}

    async def _query_enxame(self, query: str) -> dict[str, Any]:
        """Consulta peers via protocolo BEE usando índice global do Bibliotecário."""
        if not self._discovery:
            return {"answer": "", "confidence": 0.0}

        peers = self._discovery.get_active_peers()
        if not peers:
            return {"answer": "", "confidence": 0.0}

        # 1. Se temos índice global (sou Bibliotecário ou recebi do Bibliotecário), usar para rotear
        # `target_peers` é SEMPRE list[DiscoveredPeer]. O índice global devolve
        # PeerKnowledge (que tem `peer_id`, não `node_id`), então ele serve só
        # para obter os ids, que são mapeados de volta para os peers ativos.
        # Reutilizar a mesma variável para os dois tipos fazia o mypy inferir
        # PeerKnowledge e reportar "has no attribute node_id" em todo o laço
        # abaixo — em runtime estava correto, mas o tipo mentia e escondia
        # erros reais de atributo nessa função.
        target_peers: list[DiscoveredPeer] = []
        if self._global_index:
            known = self._global_index.get_peers_for_subject(query, min_confidence=0.5)
            target_peer_ids = [pk.peer_id for pk in known]
            # Filtrar peers ativos
            target_peers = [p for p in peers if p.node_id in target_peer_ids]
            logger.debug(f"Roteando via índice global: {len(target_peers)} peers alvo para '{query}'")
        elif self.cluster_state and self.cluster_state.bibliotecario_id:
            # Consultar Bibliotecário para saber onde buscar
            bib_peer = next((p for p in peers if p.node_id == self.cluster_state.bibliotecario_id), None)
            if bib_peer:
                from .cluster.global_index import query_bibliotecario_where
                target_ids = await query_bibliotecario_where(bib_peer, query, self._global_index)
                target_peers = [p for p in peers if p.node_id in target_ids]
                logger.debug(f"Roteando via Bibliotecário: {len(target_peers)} peers alvo para '{query}'")
        
        # Se não temos roteamento, consultar todos
        if not target_peers:
            target_peers = peers

        # 2. KNOWLEDGE_QUERY para filtrar peers relevantes
        best_peer = None
        best_confidence = 0.0

        for peer in target_peers:
            envelope = self._handler.create_knowledge_query(
                target_node_id=peer.node_id,
                subject=query,
                timeout_ms=2000,
            )
            try:
                response = await self._send_with_response(envelope, peer, timeout_ms=3000)
                if response and response.msg_type == BeeMessageType.KNOWLEDGE_RESPONSE:
                    from .protocol.messages import BeeKnowledgeResponse
                    kq_resp = BeeKnowledgeResponse.from_dict(response.payload)
                    if kq_resp.has_knowledge and kq_resp.confidence > best_confidence:
                        best_confidence = kq_resp.confidence
                        best_peer = peer
            except Exception as e:
                logger.debug(f"Erro consultando peer {peer.node_id}: {e}")
                continue

        # 3. Se encontrou peer relevante, fazer RESEARCH_REQUEST
        if best_peer:
            envelope = self._handler.create_research_request(
                target_node_id=best_peer.node_id,
                query=query,
            )
            try:
                response = await self._send_with_response(envelope, best_peer, timeout_ms=35000)
                if response and response.msg_type == BeeMessageType.RESEARCH_RESULT:
                    from .protocol.messages import BeeResearchResult
                    rr = BeeResearchResult.from_dict(response.payload)
                    if rr.results:
                        answer_parts = [r.content for r in rr.results[:3]]
                        return {
                            "answer": "\n\n".join(answer_parts),
                            "confidence": 0.85,
                            "source": "enxame",
                            "peer": best_peer.node_id,
                            "metadata": {
                                "total_results": rr.total_results,
                                "processing_time_ms": rr.processing_time_ms,
                                "model_used": rr.model_used,
                            },
                        }
            except Exception as e:
                logger.debug(f"Erro em research request para {best_peer.node_id}: {e}")

        return {"answer": "", "confidence": best_confidence}

    async def _send_with_response(self, envelope: BeeEnvelope, peer: DiscoveredPeer, timeout_ms: int = 5000) -> BeeEnvelope | None:
        """Envia envelope para peer e aguarda resposta via HTTP/WebSocket."""
        try:
            import aiohttp
            url = f"http://{peer.host}:{peer.port}/api/v1/bee/message"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    json=envelope.to_dict(), 
                    timeout=aiohttp.ClientTimeout(total=timeout_ms / 1000)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return BeeEnvelope.from_dict(data)
        except Exception as e:
            logger.debug(f"Falha ao enviar para {peer.node_id}: {e}")
        return None


async def main() -> int:
    parser = argparse.ArgumentParser(description="ENXAME Bee - Abelha Standalone")
    parser.add_argument("--config", type=Path, help="Arquivo de configuração")
    parser.add_argument("--data-dir", type=Path, help="Diretório de dados")
    parser.add_argument("--host", default="0.0.0.0", help="Host de escuta")
    parser.add_argument("--port", type=int, default=8765, help="Porta HTTP")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="URL do Ollama")
    parser.add_argument("--model", help="Modelo Ollama a usar")
    parser.add_argument("--allow-web", action="store_true", help="Permitir fallback web")
    parser.add_argument("--shared-secret", help="Segredo compartilhado para HMAC")
    parser.add_argument("--log-level", default="INFO", help="Nível de log")
    args = parser.parse_args()

    logging.getLogger().setLevel(args.log_level)

    # Carregar configuração
    config = load_config(args)

    # Criar e iniciar serviço
    bee = BeeService(config)

    # Setup signal handlers
    # NOTE: loop.add_signal_handler() não existe no Windows (ProactorEventLoop
    # levanta NotImplementedError). Sem este guard o bee morria no startup em
    # Windows, que é uma das plataformas que o instalador declara suportar.
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError, ValueError, OSError, RuntimeError):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(bee.stop()))

    try:
        await bee.start()
        # Manter rodando
        while bee._running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await bee.stop()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))