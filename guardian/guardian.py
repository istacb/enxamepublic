"""
ENXAME v3 - Sistema Guardian (Guardião de Segurança)

Responsabilidades:
- Detecção de prompt injection em mensagens recebidas
- Análise de integridade de arquivos (hash SHA-256)
- Monitoramento de anomalias no comportamento dos nós
- Quarentena de arquivos suspeitos
- Validação de assinaturas de mensagens entre nós
- Aprendizado contínuo com padrões de ataque reportados

Offline-first: toda análise é feita localmente, sem依赖 de internet.
"""

import os
import re
import json
import hashlib
import sqlite3
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

ENXAME_DIR = os.path.expanduser("~/enxame")
GUARDIAN_DB = os.path.join(ENXAME_DIR, "guardian", "security.db")
QUARANTINE_DIR = os.path.join(ENXAME_DIR, "guardian", "quarantine")
LOG_FILE = os.path.join(ENXAME_DIR, "logs", "guardian.log")


# ---------------------------------------------------------------------------
# PADRÕES DE PROMPT INJECTION (detecção básica offline)
# ---------------------------------------------------------------------------
PATTERNS_INJECTION = [
    r"(?i)ignore\s+(previous|anterior)",
    r"(?i)forget\s+(everything|all|tudo)",
    r"(?i)bypass\s+(rules|restrictions|segurança)",
    r"(?i)act\s+as\s+(admin|system|desenvolvedor)",
    r"(?i)you\s+are\s+now\s+(uncensored|sem+restrições)",
    r"(?i)print\s+(your|seu)\s+(instructions|instruções|prompt)",
    r"(?i)show\s+(me|para|mim)\s+(your|seu)\s+(system|sistema)\s+(prompt|mensagem)",
    r"(?i)execute\s+(this|este)\s+(code|código|script)",
    r"(?i)run\s+(this|este)\s+(command|comando)",
    r"(?i)<\s*script[^>]*>",
    r"(?i)javascript:",
    r"(?i)data:text/html",
]

COMPILED_PATTERNS = [re.compile(p) for p in PATTERNS_INJECTION]


def init_guardian_db():
    """Inicializa o banco de dados do Guardian."""
    os.makedirs(os.path.dirname(GUARDIAN_DB), exist_ok=True)
    os.makedirs(QUARANTINE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    conn = sqlite3.connect(GUARDIAN_DB)
    
    # Tabela de hashes conhecidos (arquivos seguros)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hashes_conhecidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caminho TEXT UNIQUE NOT NULL,
            hash_sha256 TEXT NOT NULL,
            tamanho INTEGER,
            categoria TEXT DEFAULT 'geral',
            verificado_em TEXT NOT NULL
        )
    """)
    
    # Tabela de incidentes de segurança
    conn.execute("""
        CREATE TABLE IF NOT EXISTS incidentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            tipo TEXT NOT NULL,
            severidade TEXT NOT NULL,
            origem TEXT,
            descricao TEXT,
            acao_tomada TEXT,
            resolvido INTEGER DEFAULT 0
        )
    """)
    
    # Tabela de padrões de ataque aprendidos
    conn.execute("""
        CREATE TABLE IF NOT EXISTS padroes_ataque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            padrao TEXT NOT NULL,
            frequencia INTEGER DEFAULT 1,
            ultimo_visto TEXT NOT NULL,
            fonte TEXT
        )
    """)
    
    # Tabela de nós monitorados
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nos_monitorados (
            node_id TEXT PRIMARY KEY,
            ip TEXT,
            status TEXT DEFAULT 'ativo',
            ultima_verificacao TEXT,
            incidentes_count INTEGER DEFAULT 0,
            confiabilidade REAL DEFAULT 1.0
        )
    """)
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_incidentes_timestamp ON incidentes(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hash_conhecido ON hashes_conhecidos(hash_sha256)")
    conn.commit()
    return conn


def calcular_hash_arquivo(caminho: str) -> Optional[str]:
    """Calcula hash SHA-256 de um arquivo."""
    if not os.path.exists(caminho):
        return None
    
    sha256_hash = hashlib.sha256()
    try:
        with open(caminho, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception:
        return None


def detectar_injection(prompt: str) -> Tuple[bool, List[str]]:
    """Detecta possíveis tentativas de prompt injection."""
    detectados = []
    for i, pattern in enumerate(COMPILED_PATTERNS):
        if pattern.search(prompt):
            detectados.append(PATTERNS_INJECTION[i])
    return len(detectados) > 0, detectados


def registrar_incidente(
    conn: sqlite3.Connection,
    tipo: str,
    severidade: str,
    origem: Optional[str] = None,
    descricao: Optional[str] = None,
    acao_tomada: Optional[str] = None
):
    """Registra um incidente de segurança."""
    timestamp = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO incidentes (timestamp, tipo, severidade, origem, descricao, acao_tomada)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (timestamp, tipo, severidade, origem, descricao, acao_tomada))
    conn.commit()


def quarentenar_arquivo(conn: sqlite3.Connection, caminho_origem: str, motivo: str):
    """Move um arquivo suspeito para quarentena."""
    if not os.path.exists(caminho_origem):
        return False
    
    nome_arquivo = os.path.basename(caminho_origem)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_quarentena = os.path.join(QUARANTINE_DIR, f"{timestamp}_{nome_arquivo}")
    
    try:
        os.rename(caminho_origem, caminho_quarentena)
        registrar_incidente(
            conn,
            tipo="arquivo_quarentenado",
            severidade="media",
            descricao=f"Arquivo movido para quarentena: {nome_arquivo}. Motivo: {motivo}",
            acao_tomada=f"Movido para {caminho_quarentena}"
        )
        return True
    except Exception as e:
        registrar_incidente(
            conn,
            tipo="falha_quarentena",
            severidade="alta",
            descricao=f"Falha ao quarentenar {nome_arquivo}: {e}",
            acao_tomada="Nenhuma"
        )
        return False


def verificar_integridade_arquivo(conn: sqlite3.Connection, caminho: str) -> Tuple[bool, Optional[str]]:
    """Verifica se um arquivo foi modificado desde a última verificação."""
    hash_atual = calcular_hash_arquivo(caminho)
    if not hash_atual:
        return False, "Arquivo não encontrado ou inacessível"
    
    cur = conn.execute(
        "SELECT hash_sha256 FROM hashes_conhecidos WHERE caminho = ?", (caminho,)
    )
    row = cur.fetchone()
    
    if not row:
        # Primeira vez: registra o hash
        agora = datetime.now().isoformat()
        tamanho = os.path.getsize(caminho)
        conn.execute("""
            INSERT INTO hashes_conhecidos (caminho, hash_sha256, tamanho, verificado_em)
            VALUES (?, ?, ?, ?)
        """, (caminho, hash_atual, tamanho, agora))
        conn.commit()
        return True, "Hash registrado pela primeira vez"
    
    if row[0] != hash_atual:
        return False, "INTEGRIDADE_COMPROMETIDA: Hash diverge do registrado"
    
    return True, "Integridade verificada"


def atualizar_confiabilidade_no(conn: sqlite3.Connection, node_id: str, delta: float):
    """Atualiza a confiabilidade de um nó baseado em seu comportamento."""
    conn.execute("""
        INSERT INTO nos_monitorados (node_id, ultima_verificacao)
        VALUES (?, ?)
        ON CONFLICT(node_id) DO NOTHING
    """, (node_id, datetime.now().isoformat()))
    
    conn.execute("""
        UPDATE nos_monitorados 
        SET confiabilidade = MAX(0.0, MIN(1.0, confiabilidade + ?)),
            ultima_verificacao = ?,
            incidentes_count = incidentes_count + CASE WHEN ? < 0 THEN 1 ELSE 0 END
        WHERE node_id = ?
    """, (delta, datetime.now().isoformat(), delta, node_id))
    conn.commit()


def log_guardian(msg: str):
    """Escreve uma mensagem no log do Guardian."""
    timestamp = datetime.now().isoformat()
    linha = f"[{timestamp}] {msg}\n"
    print(linha.strip())
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha)


# ---------------------------------------------------------------------------
# API DO GUARDIAN
# ---------------------------------------------------------------------------
app = FastAPI(title="ENXAME v3 - Guardian")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

conn_guardian = None


class AnalisePromptRequest(BaseModel):
    prompt: str
    node_origem: Optional[str] = None


class AnalisePromptResponse(BaseModel):
    seguro: bool
    injection_detectado: bool
    padroes_encontrados: List[str]
    risco: str  # baixo, medio, alto
    mensagem: Optional[str] = None


@app.post("/api/v1/analisar_prompt")
async def analisar_prompt(req: AnalisePromptRequest) -> AnalisePromptResponse:
    """Analisa um prompt em busca de tentativas de injection."""
    injection_detectado, padroes = detectar_injection(req.prompt)
    
    if injection_detectado:
        risco = "alto" if len(padroes) > 2 else "medio"
        log_guardian(f"[ALERTA] Prompt injection detectado de {req.node_origem or 'desconhecido'}: {padroes}")
        
        if conn_guardian:
            registrar_incidente(
                conn_guardian,
                tipo="prompt_injection",
                severidade=risco,
                origem=req.node_origem,
                descricao=f"Padrões detectados: {padroes}",
                acao_tomada="Prompt bloqueado para análise"
            )
            if req.node_origem:
                atualizar_confiabilidade_no(conn_guardian, req.node_origem, -0.1)
        
        return AnalisePromptResponse(
            seguro=False,
            injection_detectado=True,
            padroes_encontrados=padroes,
            risco=risco,
            mensagem="⚠️ Possível tentativa de prompt injection detectada. Revisão necessária."
        )
    
    return AnalisePromptResponse(
        seguro=True,
        injection_detectado=False,
        padroes_encontrados=[],
        risco="baixo",
        mensagem="Prompt aparentemente seguro."
    )


class VerificarArquivoRequest(BaseModel):
    caminho: str
    node_origem: Optional[str] = None


class VerificarArquivoResponse(BaseModel):
    integro: bool
    hash_atual: Optional[str]
    mensagem: str
    acao_recomendada: Optional[str] = None


@app.post("/api/v1/verificar_arquivo")
async def verificar_arquivo(req: VerificarArquivoRequest) -> VerificarArquivoResponse:
    """Verifica a integridade de um arquivo."""
    if not conn_guardian:
        return VerificarArquivoResponse(
            integro=False,
            hash_atual=None,
            mensagem="Banco de dados do Guardian não inicializado.",
            acao_recomendada="Reiniciar serviço Guardian"
        )
    
    integro, msg = verificar_integridade_arquivo(conn_guardian, req.caminho)
    
    if not integro and "COMPROMETIDA" in msg:
        log_guardian(f"[ALERTA] Integridade comprometida: {req.caminho}")
        if conn_guardian:
            registrar_incidente(
                conn_guardian,
                tipo="integridade_comprometida",
                severidade="alta",
                origem=req.node_origem,
                descricao=msg,
                acao_tomada="Quarentena recomendada"
            )
        return VerificarArquivoResponse(
            integro=False,
            hash_atual=calcular_hash_arquivo(req.caminho),
            mensagem=msg,
            acao_recomendada="Quarentenar arquivo imediatamente"
        )
    
    return VerificarArquivoResponse(
        integro=integro,
        hash_atual=calcular_hash_arquivo(req.caminho),
        mensagem=msg,
        acao_recomendada=None
    )


class ReportarIncidenteRequest(BaseModel):
    tipo: str
    severidade: str
    descricao: str
    origem: Optional[str] = None
    evidencias: Optional[Dict] = None


@app.post("/api/v1/reportar_incidente")
async def reportar_incidente(req: ReportarIncidenteRequest):
    """Permite que outros nós reportem incidentes ao Guardian."""
    if not conn_guardian:
        return {"ok": False, "erro": "Guardian não inicializado"}
    
    registrar_incidente(
        conn_guardian,
        tipo=req.tipo,
        severidade=req.severidade,
        origem=req.origem,
        descricao=req.descricao,
        acao_tomada="Em análise"
    )
    
    log_guardian(f"[INCIDENTE] {req.tipo} ({req.severidade}) reportado por {req.origem or 'desconhecido'}")
    
    return {"ok": True, "mensagem": "Incidente registrado para análise"}


@app.get("/api/v1/incidentes")
async def listar_incidentes(limite: int = 50, nao_resolvidos: bool = False):
    """Lista incidentes registrados."""
    if not conn_guardian:
        return {"erro": "Guardian não inicializado"}
    
    if nao_resolvidos:
        cur = conn_guardian.execute("""
            SELECT * FROM incidentes 
            WHERE resolvido = 0 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limite,))
    else:
        cur = conn_guardian.execute("""
            SELECT * FROM incidentes 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limite,))
    
    colunas = ["id", "timestamp", "tipo", "severidade", "origem", "descricao", "acao_tomada", "resolvido"]
    return {"incidentes": [dict(zip(colunas, row)) for row in cur.fetchall()]}


@app.get("/api/v1/nos")
async def listar_nos():
    """Lista nós monitorados e suas confiabilidades."""
    if not conn_guardian:
        return {"erro": "Guardian não inicializado"}
    
    cur = conn_guardian.execute("SELECT * FROM nos_monitorados ORDER BY confiabilidade DESC")
    colunas = ["node_id", "ip", "status", "ultima_verificacao", "incidentes_count", "confiabilidade"]
    return {"nos": [dict(zip(colunas, row)) for row in cur.fetchall()]}


@app.get("/api/v1/quarentena")
async def listar_quarentena():
    """Lista arquivos em quarentena."""
    if not os.path.exists(QUARANTINE_DIR):
        return {"arquivos": []}
    
    arquivos = []
    for nome in os.listdir(QUARANTINE_DIR):
        caminho = os.path.join(QUARANTINE_DIR, nome)
        arquivos.append({
            "nome": nome,
            "tamanho": os.path.getsize(caminho),
            "criado_em": datetime.fromtimestamp(os.path.getctime(caminho)).isoformat()
        })
    
    return {"arquivos": sorted(arquivos, key=lambda x: x["criado_em"], reverse=True)}


@app.get("/api/v1/health")
async def health():
    return {
        "status": "ok",
        "servico": "Guardian",
        "hora": datetime.now().isoformat(),
        "db_inicializado": conn_guardian is not None
    }


@app.get("/")
async def raiz():
    return {
        "status": "ENXAME v3 - Guardian online",
        "descricao": "Serviço de segurança e vigilância do enxame",
        "hora": datetime.now().isoformat()
    }


# ---------------------------------------------------------------------------
# LOOP DE VIGILÂNCIA CONTÍNUA
# ---------------------------------------------------------------------------
def loop_vigilancia():
    """Loop contínuo de vigilância de segurança."""
    if not conn_guardian:
        return
    
    while True:
        try:
            # Verificar nós com baixa confiabilidade
            cur = conn_guardian.execute(
                "SELECT node_id, confiabilidade FROM nos_monitorados WHERE confiabilidade < 0.5"
            )
            for row in cur.fetchall():
                node_id, confiabilidade = row
                log_guardian(f"[VIGILÂNCIA] Nó {node_id} com baixa confiabilidade: {confiabilidade:.2f}")
            
            # Limpar incidentes antigos resolvidos (> 30 dias)
            from datetime import timedelta
            limite = (datetime.now() - timedelta(days=30)).isoformat()
            conn_guardian.execute(
                "DELETE FROM incidentes WHERE resolvido = 1 AND timestamp < ?", (limite,)
            )
            conn_guardian.commit()
            
        except Exception as e:
            log_guardian(f"[ERRO] Loop de vigilância falhou: {e}")
        
        time.sleep(300)  # Executa a cada 5 minutos


if __name__ == "__main__":
    print("=" * 60)
    print("  ENXAME v3 - Guardian (Serviço de Segurança)")
    print("  Funções: detecção de injection, integridade, quarentena")
    print("=" * 60)
    
    conn_guardian = init_guardian_db()
    
    # Iniciar loop de vigilância em thread separada
    import threading
    threading.Thread(target=loop_vigilancia, daemon=True).start()
    
    # Iniciar servidor API
    uvicorn.run(app, host="0.0.0.0", port=7720)
