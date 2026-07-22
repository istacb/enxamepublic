"""
ENXAME v3 - Sistema de Failover Automático

Gerencia a detecção de queda de nós e redistribuição automática de papéis.
Quando um nó crítico (Juiz, Bibliotecário) cai, o sistema elege um substituto
baseado no benchmark e confiabilidade.

Funcionalidades:
- Monitoramento contínuo de heartbeats
- Detecção de falhas em tempo real
- Eleição automática de substitutos
- Migração suave de estado
- Notificação aos demais nós
"""

import os
import json
import time
import sqlite3
import threading
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

ENXAME_DIR = os.path.expanduser("~/enxame")
FAILOVER_DB = os.path.join(ENXAME_DIR, "failover", "estado.db")
LOG_FILE = os.path.join(ENXAME_DIR, "logs", "failover.log")


@dataclass
class NodeInfo:
    node_id: str
    ip: str
    porta: int
    papel: str
    score: float
    confiabilidade: float
    ultimo_heartbeat: float
    estado: str  # ativo, suspeito, inativo
    metadata: Dict[str, Any]


def init_failover_db():
    """Inicializa o banco de dados de failover."""
    os.makedirs(os.path.dirname(FAILOVER_DB), exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    conn = sqlite3.connect(FAILOVER_DB)
    
    # Estado atual dos nós
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nos (
            node_id TEXT PRIMARY KEY,
            ip TEXT NOT NULL,
            porta INTEGER NOT NULL,
            papel TEXT NOT NULL,
            score REAL DEFAULT 0,
            confiabilidade REAL DEFAULT 1.0,
            ultimo_heartbeat REAL NOT NULL,
            estado TEXT DEFAULT 'ativo',
            metadata TEXT DEFAULT '{}',
            criado_em TEXT NOT NULL
        )
    """)
    
    # Histórico de eleições de failover
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eleicoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            papel_vacante TEXT NOT NULL,
            no_caido TEXT,
            no_eleito TEXT,
            participantes TEXT,
            resultado TEXT,
            duracao_ms INTEGER
        )
    """)
    
    # Log de eventos de failover
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            tipo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            no_afetado TEXT,
            acao_tomada TEXT
        )
    """)
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_nos_estado ON nos(estado)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_eleicoes_timestamp ON eleicoes(timestamp)")
    conn.commit()
    return conn


def log_failover(msg: str):
    """Escreve uma mensagem no log de failover."""
    timestamp = datetime.now().isoformat()
    linha = f"[{timestamp}] {msg}\n"
    print(linha.strip())
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha)


def registrar_no(
    conn: sqlite3.Connection,
    node_id: str,
    ip: str,
    porta: int,
    papel: str,
    score: float = 0,
    metadata: Optional[Dict] = None
):
    """Registra ou atualiza um nó no sistema de failover."""
    agora = time.time()
    agora_str = datetime.now().isoformat()
    metadata_str = json.dumps(metadata or {})
    
    conn.execute("""
        INSERT INTO nos (node_id, ip, porta, papel, score, ultimo_heartbeat, estado, metadata, criado_em)
        VALUES (?, ?, ?, ?, ?, ?, 'ativo', ?, ?)
        ON CONFLICT(node_id) DO UPDATE SET
            ip = excluded.ip,
            porta = excluded.porta,
            papel = excluded.papel,
            score = excluded.score,
            ultimo_heartbeat = excluded.ultimo_heartbeat,
            estado = CASE WHEN estado = 'inativo' THEN 'ativo' ELSE estado END,
            metadata = excluded.metadata
    """, (node_id, ip, porta, papel, score, agora, metadata_str, agora_str))
    conn.commit()


def atualizar_heartbeat(conn: sqlite3.Connection, node_id: str):
    """Atualiza o heartbeat de um nó."""
    agora = time.time()
    conn.execute(
        "UPDATE nos SET ultimo_heartbeat = ? WHERE node_id = ?",
        (agora, node_id)
    )
    conn.commit()


def detectar_nos_inativos(conn: sqlite3.Connection, timeout_segundos: int = 30) -> List[NodeInfo]:
    """Detecta nós que não enviaram heartbeat dentro do timeout."""
    limite = time.time() - timeout_segundos
    
    cur = conn.execute(
        "SELECT node_id, ip, porta, papel, score, confiabilidade, ultimo_heartbeat, estado, metadata FROM nos WHERE ultimo_heartbeat < ?",
        (limite,)
    )
    
    nos_inativos = []
    for row in cur.fetchall():
        nos_inativos.append(NodeInfo(
            node_id=row[0],
            ip=row[1],
            porta=row[2],
            papel=row[3],
            score=row[4],
            confiabilidade=row[5],
            ultimo_heartbeat=row[6],
            estado=row[7],
            metadata=json.loads(row[8])
        ))
    
    return nos_inativos


def marcar_no_como_suspeito(conn: sqlite3.Connection, node_id: str):
    """Marca um nó como suspeito (primeiro estágio antes de inativo)."""
    conn.execute(
        "UPDATE nos SET estado = 'suspeito' WHERE node_id = ?",
        (node_id,)
    )
    conn.commit()
    log_failover(f"Nó {node_id} marcado como SUSPEITO")


def marcar_no_como_inativo(conn: sqlite3.Connection, node_id: str):
    """Marca um nó como inativo."""
    conn.execute(
        "UPDATE nos SET estado = 'inativo' WHERE node_id = ?",
        (node_id,)
    )
    conn.commit()
    log_failover(f"Nó {node_id} marcado como INATIVO")


def obter_nos_ativos_por_papel(conn: sqlite3.Connection, papel: str) -> List[NodeInfo]:
    """Obtém todos os nós ativos que podem assumir um determinado papel."""
    cur = conn.execute("""
        SELECT node_id, ip, porta, papel, score, confiabilidade, ultimo_heartbeat, estado, metadata
        FROM nos
        WHERE estado = 'ativo' AND (papel = ? OR papel = 'agente')
        ORDER BY (score * confiabilidade) DESC
    """, (papel,))
    
    nos = []
    for row in cur.fetchall():
        nos.append(NodeInfo(
            node_id=row[0],
            ip=row[1],
            porta=row[2],
            papel=row[3],
            score=row[4],
            confiabilidade=row[5],
            ultimo_heartbeat=row[6],
            estado=row[7],
            metadata=json.loads(row[8])
        ))
    
    return nos


def eleger_substituto(
    conn: sqlite3.Connection,
    papel_vacante: str,
    no_caido: str
) -> Optional[NodeInfo]:
    """Elege um substituto para um papel vacante baseado em score e confiabilidade."""
    candidatos = obter_nos_ativos_por_papel(conn, papel_vacante)
    
    if not candidatos:
        log_failover(f"Sem candidatos disponíveis para assumir o papel de {papel_vacante}")
        return None
    
    # O melhor candidato é o primeiro (ordenado por score * confiabilidade)
    eleito = candidatos[0]
    
    # Registrar eleição
    timestamp = datetime.now().isoformat()
    participantes = json.dumps([c.node_id for c in candidatos])
    
    conn.execute("""
        INSERT INTO eleicoes (timestamp, papel_vacante, no_caido, no_eleito, participantes, resultado, duracao_ms)
        VALUES (?, ?, ?, ?, ?, 'sucesso', 0)
    """, (timestamp, papel_vacante, no_caido, eleito.node_id, participantes))
    conn.commit()
    
    log_failover(f"Eleição concluída: {eleito.node_id} eleito para {papel_vacante} (substituindo {no_caido})")
    
    return eleito


def notificar_nos_sobre_failover(
    nos_ativos: List[NodeInfo],
    papel_vacante: str,
    no_caido: str,
    no_eleito: NodeInfo
):
    """Notifica todos os nós ativos sobre a mudança de papel."""
    payload = {
        "tipo": "failover",
        "papel_vacante": papel_vacante,
        "no_caido": no_caido,
        "novo_dono_papel": no_eleito.node_id,
        "timestamp": datetime.now().isoformat()
    }
    
    for no in nos_ativos:
        try:
            httpx.post(
                f"http://{no.ip}:{no.porta}/api/v1/notificacao",
                json=payload,
                timeout=5
            )
        except Exception as e:
            log_failover(f"Falha ao notificar {no.node_id}: {e}")


def registrar_evento(
    conn: sqlite3.Connection,
    tipo: str,
    descricao: str,
    no_afetado: Optional[str] = None,
    acao_tomada: Optional[str] = None
):
    """Registra um evento de failover."""
    timestamp = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO eventos (timestamp, tipo, descricao, no_afetado, acao_tomada)
        VALUES (?, ?, ?, ?, ?)
    """, (timestamp, tipo, descricao, no_afetado, acao_tomada))
    conn.commit()


def processar_failover(conn: sqlite3.Connection, no_inativo: NodeInfo):
    """Processa o failover de um nó inativo."""
    log_failover(f"Processando failover para {no_inativo.node_id} (papel: {no_inativo.papel})")
    
    # Marcar como inativo
    marcar_no_como_inativo(conn, no_inativo.node_id)
    
    # Registrar evento
    registrar_evento(
        conn,
        tipo="falha_no",
        descricao=f"Nó {no_inativo.node_id} ({no_inativo.papel}) não responde há mais de 30s",
        no_afetado=no_inativo.node_id,
        acao_tomada="Iniciando eleição de substituto"
    )
    
    # Papéis críticos que precisam de substituto imediato
    papeis_criticos = ["juiz", "bibliotecario", "guardiao"]
    
    if no_inativo.papel.lower() in papeis_criticos:
        log_failover(f"Papel crítico {no_inativo.papel} vacante. Iniciando eleição...")
        
        # Eleger substituto
        substituto = eleger_substituto(conn, no_inativo.papel, no_inativo.node_id)
        
        if substituto:
            # Atualizar papel do substituto
            conn.execute(
                "UPDATE nos SET papel = ? WHERE node_id = ?",
                (no_inativo.papel, substituto.node_id)
            )
            conn.commit()
            
            # Notificar outros nós
            nos_ativos = [n for n in obter_todos_nos_ativos(conn) if n.node_id != substituto.node_id]
            notificar_nos_sobre_failover(nos_ativos, no_inativo.papel, no_inativo.node_id, substituto)
            
            registrar_evento(
                conn,
                tipo="failover_concluido",
                descricao=f"{substituto.node_id} assumiu papel de {no_inativo.papel}",
                no_afetado=substituto.node_id,
                acao_tomada=f"Notificação enviada a {len(nos_ativos)} nós"
            )
        else:
            registrar_evento(
                conn,
                tipo="failover_falhou",
                descricao=f"Não foi possível encontrar substituto para {no_inativo.papel}",
                no_afetado=no_inativo.node_id,
                acao_tomada="Aguardando novo nó se registrar"
            )


def obter_todos_nos_ativos(conn: sqlite3.Connection) -> List[NodeInfo]:
    """Obtém todos os nós ativos."""
    cur = conn.execute("""
        SELECT node_id, ip, porta, papel, score, confiabilidade, ultimo_heartbeat, estado, metadata
        FROM nos WHERE estado = 'ativo'
    """)
    
    nos = []
    for row in cur.fetchall():
        nos.append(NodeInfo(
            node_id=row[0],
            ip=row[1],
            porta=row[2],
            papel=row[3],
            score=row[4],
            confiabilidade=row[5],
            ultimo_heartbeat=row[6],
            estado=row[7],
            metadata=json.loads(row[8])
        ))
    
    return nos


class FailoverManager:
    """Gerenciador principal de failover."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or FAILOVER_DB
        self.conn = init_failover_db()
        self.running = False
        self._thread = None
    
    def close(self):
        """Para o gerenciador e fecha conexão."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self.conn:
            self.conn.close()
    
    def registrar_node(
        self,
        node_id: str,
        ip: str,
        porta: int,
        papel: str,
        score: float = 0,
        metadata: Optional[Dict] = None
    ):
        """Registra um nó no sistema de failover."""
        registrar_no(self.conn, node_id, ip, porta, papel, score, metadata)
        log_failover(f"Nó registrado: {node_id} ({papel}) em {ip}:{porta}")
    
    def heartbeat(self, node_id: str):
        """Recebe heartbeat de um nó."""
        atualizar_heartbeat(self.conn, node_id)
    
    def iniciar_monitoramento(self, intervalo_verificacao: int = 10):
        """Inicia o loop de monitoramento em thread separada."""
        self.running = True
        
        def loop():
            log_failover("Iniciando monitoramento de failover...")
            
            while self.running:
                try:
                    # Detectar nós inativos
                    nos_inativos = detectar_nos_inativos(self.conn, timeout_segundos=30)
                    
                    for no in nos_inativos:
                        # Primeiro marcar como suspeito
                        cur = self.conn.execute(
                            "SELECT estado FROM nos WHERE node_id = ?", (no.node_id,)
                        )
                        estado_atual = cur.fetchone()[0]
                        
                        if estado_atual == 'ativo':
                            marcar_no_como_suspeito(self.conn, no.node_id)
                            log_failover(f"Nó {no.node_id} não responde. Marcado como suspeito.")
                        elif estado_atual == 'suspeito':
                            # Já era suspeito, agora é inativo
                            processar_failover(self.conn, no)
                    
                    # Limpar suspeitos antigos que voltaram a responder
                    self._limpar_suspeitos_recuperados()
                    
                except Exception as e:
                    log_failover(f"Erro no loop de monitoramento: {e}")
                
                time.sleep(intervalo_verificacao)
        
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()
    
    def _limpar_suspeitos_recuperados(self):
        """Limpa status de suspeito para nós que voltaram a responder."""
        limite = time.time() - 10  # Se teve heartbeat nos últimos 10s
        self.conn.execute(
            "UPDATE nos SET estado = 'ativo' WHERE estado = 'suspeito' AND ultimo_heartbeat > ?",
            (limite,)
        )
        self.conn.commit()
    
    def obter_estado_cluster(self) -> Dict:
        """Obtém o estado atual do cluster."""
        nos_ativos = obter_todos_nos_ativos(self.conn)
        
        estado = {
            "total_nos": len(nos_ativos),
            "papeis": {},
            "nos": [
                {
                    "node_id": n.node_id,
                    "ip": n.ip,
                    "porta": n.porta,
                    "papel": n.papel,
                    "score": n.score,
                    "confiabilidade": n.confiabilidade
                }
                for n in nos_ativos
            ]
        }
        
        for no in nos_ativos:
            if no.papel not in estado["papeis"]:
                estado["papeis"][no.papel] = []
            estado["papeis"][no.papel].append(no.node_id)
        
        return estado
    
    def listar_historico_eleicoes(self, limite: int = 20) -> List[Dict]:
        """Lista histórico de eleições."""
        cur = self.conn.execute("""
            SELECT * FROM eleicoes ORDER BY timestamp DESC LIMIT ?
        """, (limite,))
        
        colunas = ["id", "timestamp", "papel_vacante", "no_caido", "no_eleito", 
                   "participantes", "resultado", "duracao_ms"]
        return [dict(zip(colunas, row)) for row in cur.fetchall()]


if __name__ == "__main__":
    # Teste rápido
    manager = FailoverManager()
    
    # Registrar nós de teste
    manager.registrar_node("node1", "192.168.1.10", 7700, "juiz", score=95)
    manager.registrar_node("node2", "192.168.1.11", 7710, "bibliotecario", score=88)
    manager.registrar_node("node3", "192.168.1.12", 9000, "agente", score=75)
    manager.registrar_node("node4", "192.168.1.13", 9001, "agente", score=82)
    
    # Iniciar monitoramento
    manager.iniciar_monitoramento(intervalo_verificacao=5)
    
    print("Failover Manager iniciado. Pressione Ctrl+C para sair.")
    print(f"Estado do cluster: {manager.obter_estado_cluster()}")
    
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        manager.close()
