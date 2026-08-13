from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx


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


@dataclass(slots=True)
class ElectionResult:
    juiz_node_id: str
    bibliotecaria_node_id: str
    agent_node_ids: list[str]
    ranking: list[NodeBenchmark]
    quorum: bool


def calculate_hardware_score(cpu_cores: int, cpu_freq_ghz: float, ram_gb: float, vram_gb: float) -> float:
    """
    Calcula o Score de Capacidade (S) conforme fórmula:
    S = (CPU_cores × CPU_Freq_GHz) + RAM_GB + VRAM_GB
    
    Este score é usado para eleição do nó Juiz em caso de failover.
    """
    return (cpu_cores * cpu_freq_ghz) + ram_gb + vram_gb


@dataclass(slots=True)
class PeerNode:
    """Informações de um nó peer conhecido."""
    node_id: str
    ip: str
    port: int
    role: str
    score: float
    last_heartbeat: float = 0.0
    is_juiz: bool = False


class HeartbeatManager:
    """
    Gerencia envio e recebimento de heartbeats entre nós do cluster.
    
    - Envia heartbeat a cada 2 segundos
    - Detecta falha se nenhum heartbeat por mais de 5 segundos
    - Inicia eleição quando Juiz ativo falha
    """
    
    HEARTBEAT_INTERVAL = 2.0  # segundos
    JUIC_TIMEOUT = 5.0  # segundos sem heartbeat para considerar Juiz inativo
    
    def __init__(
        self,
        node_id: str,
        ip: str,
        port: int,
        role: str,
        score: float,
        on_election_trigger: Callable[[list[PeerNode]], None] | None = None,
    ) -> None:
        self.node_id = node_id
        self.ip = ip
        self.port = port
        self.role = role
        self.score = score
        self.peers: dict[str, PeerNode] = {}
        self.running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.on_election_trigger = on_election_trigger
        self._http_client = httpx.Client(timeout=2.0)
        
    def register_peer(self, peer: PeerNode) -> None:
        """Registra um peer conhecido."""
        with self._lock:
            self.peers[peer.node_id] = peer
            
    def remove_peer(self, node_id: str) -> None:
        """Remove um peer."""
        with self._lock:
            self.peers.pop(node_id, None)
    
    def receive_heartbeat(self, node_id: str, score: float, ip: str, port: int, role: str, is_juiz: bool = False) -> None:
        """Recebe heartbeat de um peer."""
        with self._lock:
            now = time.time()
            if node_id in self.peers:
                peer = self.peers[node_id]
                peer.last_heartbeat = now
                peer.score = score
                peer.is_juiz = is_juiz
            else:
                self.peers[node_id] = PeerNode(
                    node_id=node_id,
                    ip=ip,
                    port=port,
                    role=role,
                    score=score,
                    last_heartbeat=now,
                    is_juiz=is_juiz,
                )
    
    def _send_heartbeat_to_peer(self, peer: PeerNode) -> bool:
        """Envia heartbeat para um peer específico."""
        try:
            payload = {
                'type': 'heartbeat',
                'node_id': self.node_id,
                'score': self.score,
                'ip': self.ip,
                'port': self.port,
                'role': self.role,
                'is_juiz': self.role == 'juiz',
                'timestamp': time.time(),
            }
            resp = self._http_client.post(
                f'http://{peer.ip}:{peer.port}/api/v1/heartbeat',
                json=payload,
            )
            return resp.status_code == 200
        except Exception:
            return False
    
    def _check_juiz_alive(self) -> PeerNode | None:
        """Verifica se o Juiz atual está vivo."""
        with self._lock:
            for peer in self.peers.values():
                if peer.is_juiz:
                    elapsed = time.time() - peer.last_heartbeat
                    if elapsed > self.JUIC_TIMEOUT:
                        return peer  # Juiz encontrado mas inativo
                    return None  # Juiz está vivo
            return None
    
    def _detect_failed_peers(self) -> list[PeerNode]:
        """Detecta peers que não enviaram heartbeat dentro do timeout."""
        failed = []
        now = time.time()
        with self._lock:
            for peer in self.peers.values():
                if peer.node_id == self.node_id:
                    continue
                elapsed = now - peer.last_heartbeat
                if elapsed > self.JUIC_TIMEOUT:
                    failed.append(peer)
        return failed
    
    def _trigger_election(self, failed_juiz: PeerNode | None = None) -> None:
        """Inicia processo de eleição."""
        print(f'[ELECTION] Triggering election. Failed juiz: {failed_juiz.node_id if failed_juiz else "none"}')
        
        with self._lock:
            # Coleta todos os peers ativos (incluindo a si mesmo)
            active_peers = [
                p for p in self.peers.values()
                if (time.time() - p.last_heartbeat) <= self.JUIC_TIMEOUT or p.node_id == self.node_id
            ]
            
            # Adiciona a si mesmo na lista se não estiver lá
            self_present = any(p.node_id == self.node_id for p in active_peers)
            if not self_present:
                active_peers.append(PeerNode(
                    node_id=self.node_id,
                    ip=self.ip,
                    port=self.port,
                    role=self.role,
                    score=self.score,
                    last_heartbeat=time.time(),
                    is_juiz=False,
                ))
        
        if self.on_election_trigger:
            self.on_election_trigger(active_peers)
    
    def _heartbeat_loop(self) -> None:
        """Loop principal de envio de heartbeats."""
        while self.running:
            try:
                # Envia heartbeat para todos os peers
                with self._lock:
                    peers_copy = list(self.peers.values())
                
                for peer in peers_copy:
                    if peer.node_id == self.node_id:
                        continue
                    self._send_heartbeat_to_peer(peer)
                
                # Verifica se Juiz falhou
                failed_juiz = self._check_juiz_alive()
                if failed_juiz:
                    print(f'[ELECTION] Juiz {failed_juiz.node_id} não responde há >{self.JUIC_TIMEOUT}s. Iniciando eleição!')
                    self._trigger_election(failed_juiz)
                
                # Limpa peers falhos
                failed_peers = self._detect_failed_peers()
                for peer in failed_peers:
                    print(f'[HEARTBEAT] Peer {peer.node_id} marcado como inativo')
                    self.remove_peer(peer.node_id)
                
            except Exception as e:
                print(f'[HEARTBEAT] Erro no loop: {e}')
            
            time.sleep(self.HEARTBEAT_INTERVAL)
    
    def start(self) -> None:
        """Inicia o loop de heartbeat em thread separada."""
        self.running = True
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        print(f'[HEARTBEAT] Started for node {self.node_id} ({self.role})')
    
    def stop(self) -> None:
        """Para o loop de heartbeat."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        self._http_client.close()


class FailoverElection:
    """
    Implementa eleição de novo Juiz quando o atual falha.
    
    O nó com maior Score de Hardware assume o papel de Juiz.
    """
    
    def __init__(self, node_id: str, current_role: str, score: float) -> None:
        self.node_id = node_id
        self.current_role = current_role
        self.score = score
        self._lock = threading.Lock()
        self.election_in_progress = False
    
    def run_election(self, candidates: list[PeerNode]) -> tuple[bool, str]:
        """
        Executa eleição entre candidatos.
        
        Retorna (venceu, node_id_do_vencedor)
        """
        with self._lock:
            if self.election_in_progress:
                return False, ''
            self.election_in_progress = True
        
        try:
            if not candidates:
                return False, ''
            
            # Ordena por score (maior primeiro)
            ranked = sorted(candidates, key=lambda c: c.score, reverse=True)
            winner = ranked[0]
            
            print(f'[ELECTION] Ranking: {[f"{c.node_id}(S={c.score:.1f})" for c in ranked]}')
            print(f'[ELECTION] Vencedor: {winner.node_id} com score {winner.score:.1f}')
            
            # Se este nó venceu e não era Juiz, assume o papel
            if winner.node_id == self.node_id:
                if self.current_role != 'juiz':
                    print(f'[ELECTION] Este nó ({self.node_id}) assumindo papel de JUIZ!')
                    # Aqui seria feito o rebind da porta do orquestrador
                    return True, self.node_id
                else:
                    print(f'[ELECTION] Este nó já é Juiz, mantendo liderança.')
                    return True, self.node_id
            else:
                print(f'[ELECTION] Nó {winner.node_id} eleito como novo Juiz.')
                return False, winner.node_id
                
        finally:
            with self._lock:
                self.election_in_progress = False


class ClusterElection:
    """Eleição simplificada estilo bully com votação por maioria."""

    def rank(self, nodes: list[NodeBenchmark]) -> list[NodeBenchmark]:
        ordered = sorted(nodes, key=lambda n: n.score, reverse=True)
        if ordered:
            ordered[0].role_hint = 'juiz'
        if len(ordered) > 1:
            ordered[-1].role_hint = 'bibliotecaria'
        for item in ordered[1:-1]:
            item.role_hint = 'agente'
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
