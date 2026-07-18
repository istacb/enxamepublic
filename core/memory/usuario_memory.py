"""
ENXAME v3 - Sistema de Memória de Longo Prazo do Usuário

Armazena contexto, preferências, histórico de decisões e padrões de trabalho
do usuário para agilizar e melhorar respostas futuras. Offline-first.
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any

ENXAME_DIR = os.path.expanduser("~/enxame")
MEMORY_DB = os.path.join(ENXAME_DIR, "memory", "usuario.db")


def init_memory_db():
    """Inicializa o banco de dados de memória do usuário."""
    os.makedirs(os.path.dirname(MEMORY_DB), exist_ok=True)
    conn = sqlite3.connect(MEMORY_DB)
    
    # Tabela de contexto persistente (preferências, padrões)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contexto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE NOT NULL,
            valor TEXT NOT NULL,
            categoria TEXT DEFAULT 'geral',
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
    """)
    
    # Tabela de histórico de interações
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            prompt TEXT NOT NULL,
            resposta TEXT NOT NULL,
            worker_origem TEXT,
            perfil_usado TEXT,
            fontes_contexto TEXT,
            decisao_usuario TEXT,
            feedback_usuario TEXT
        )
    """)
    
    # Tabela de memória semântica (embeddings simples em texto)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memoria_semantica (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conteudo TEXT NOT NULL,
            resumo TEXT,
            tags TEXT,
            relevancia INTEGER DEFAULT 1,
            criado_em TEXT NOT NULL,
            ultimo_acesso TEXT
        )
    """)
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_historico_timestamp ON historico(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memoria_tags ON memoria_semantica(tags)")
    conn.commit()
    return conn


def salvar_contexto(conn: sqlite3.Connection, chave: str, valor: Any, categoria: str = "geral"):
    """Salva ou atualiza um contexto persistente do usuário."""
    agora = datetime.now().isoformat()
    valor_str = json.dumps(valor, ensure_ascii=False) if not isinstance(valor, str) else valor
    
    conn.execute("""
        INSERT INTO contexto (chave, valor, categoria, criado_em, atualizado_em)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(chave) DO UPDATE SET
            valor = excluded.valor,
            categoria = excluded.categoria,
            atualizado_em = excluded.atualizado_em
    """, (chave, valor_str, categoria, agora, agora))
    conn.commit()


def carregar_contexto(conn: sqlite3.Connection, chave: str) -> Optional[Any]:
    """Carrega um contexto específico do usuário."""
    cur = conn.execute("SELECT valor FROM contexto WHERE chave = ?", (chave,))
    row = cur.fetchone()
    if row:
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return row[0]
    return None


def listar_contextos(conn: sqlite3.Connection, categoria: Optional[str] = None) -> List[Dict]:
    """Lista todos os contextos, opcionalmente filtrados por categoria."""
    if categoria:
        cur = conn.execute(
            "SELECT chave, valor, categoria, criado_em, atualizado_em FROM contexto WHERE categoria = ?",
            (categoria,)
        )
    else:
        cur = conn.execute("SELECT chave, valor, categoria, criado_em, atualizado_em FROM contexto")
    
    resultados = []
    for row in cur.fetchall():
        try:
            valor = json.loads(row[1])
        except json.JSONDecodeError:
            valor = row[1]
        resultados.append({
            "chave": row[0],
            "valor": valor,
            "categoria": row[2],
            "criado_em": row[3],
            "atualizado_em": row[4]
        })
    return resultados


def registrar_interacao(
    conn: sqlite3.Connection,
    prompt: str,
    resposta: str,
    worker_origem: str = "",
    perfil_usado: str = "",
    fontes_contexto: Optional[List[str]] = None,
    decisao_usuario: Optional[str] = None,
    feedback_usuario: Optional[str] = None
):
    """Registra uma interação completa no histórico."""
    timestamp = datetime.now().isoformat()
    fontes_str = json.dumps(fontes_contexto) if fontes_contexto else "[]"
    
    conn.execute("""
        INSERT INTO historico (timestamp, prompt, resposta, worker_origem, perfil_usado, 
                               fontes_contexto, decisao_usuario, feedback_usuario)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, prompt, resposta, worker_origem, perfil_usado, fontes_str, 
          decisao_usuario, feedback_usuario))
    conn.commit()


def buscar_historico(
    conn: sqlite3.Connection,
    termo: Optional[str] = None,
    limite: int = 50,
    ordem: str = "DESC"
) -> List[Dict]:
    """Busca no histórico de interações."""
    query = "SELECT * FROM historico"
    params = []
    
    if termo:
        query += " WHERE prompt LIKE ? OR resposta LIKE ?"
        termo_like = f"%{termo}%"
        params = [termo_like, termo_like]
    
    query += f" ORDER BY timestamp {ordem} LIMIT ?"
    params.append(limite)
    
    cur = conn.execute(query, params)
    colunas = ["id", "timestamp", "prompt", "resposta", "worker_origem", 
               "perfil_usado", "fontes_contexto", "decisao_usuario", "feedback_usuario"]
    
    resultados = []
    for row in cur.fetchall():
        item = dict(zip(colunas, row))
        try:
            item["fontes_contexto"] = json.loads(item["fontes_contexto"])
        except (json.JSONDecodeError, TypeError):
            item["fontes_contexto"] = []
        resultados.append(item)
    
    return resultados


def adicionar_memoria_semantica(
    conn: sqlite3.Connection,
    conteudo: str,
    resumo: Optional[str] = None,
    tags: Optional[List[str]] = None,
    relevancia: int = 1
):
    """Adiciona conteúdo à memória semântica para recuperação futura."""
    agora = datetime.now().isoformat()
    tags_str = json.dumps(tags) if tags else "[]"
    
    conn.execute("""
        INSERT INTO memoria_semantica (conteudo, resumo, tags, relevancia, criado_em)
        VALUES (?, ?, ?, ?, ?)
    """, (conteudo, resumo, tags_str, relevancia, agora))
    conn.commit()


def buscar_memoria_semantica(
    conn: sqlite3.Connection,
    termo: str,
    limite: int = 10
) -> List[Dict]:
    """Busca na memória semântica por termo ou tags."""
    termo_like = f"%{termo}%"
    cur = conn.execute("""
        SELECT id, conteudo, resumo, tags, relevancia, criado_em, ultimo_acesso
        FROM memoria_semantica
        WHERE conteudo LIKE ? OR tags LIKE ?
        ORDER BY relevancia DESC, criado_em DESC
        LIMIT ?
    """, (termo_like, termo_like, limite))
    
    resultados = []
    for row in cur.fetchall():
        try:
            tags = json.loads(row[3])
        except (json.JSONDecodeError, TypeError):
            tags = []
        resultados.append({
            "id": row[0],
            "conteudo": row[1],
            "resumo": row[2],
            "tags": tags,
            "relevancia": row[4],
            "criado_em": row[5],
            "ultimo_acesso": row[6]
        })
    
    # Atualiza último acesso
    for r in resultados:
        conn.execute(
            "UPDATE memoria_semantica SET ultimo_acesso = ? WHERE id = ?",
            (datetime.now().isoformat(), r["id"])
        )
    conn.commit()
    
    return resultados


def atualizar_relevancia_memoria(conn: sqlite3.Connection, id_memoria: int, delta: int = 1):
    """Aumenta ou diminui a relevância de uma memória."""
    conn.execute("""
        UPDATE memoria_semantica 
        SET relevancia = MAX(0, relevancia + ?)
        WHERE id = ?
    """, (delta, id_memoria))
    conn.commit()


def limpar_historico_antigo(conn: sqlite3.Connection, dias: int = 90):
    """Remove histórico mais antigo que N dias."""
    from datetime import timedelta
    limite = (datetime.now() - timedelta(days=dias)).isoformat()
    conn.execute("DELETE FROM historico WHERE timestamp < ?", (limite,))
    conn.commit()


class UsuarioMemory:
    """Classe principal para gerenciamento da memória do usuário."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or MEMORY_DB
        self.conn = init_memory_db()
    
    def close(self):
        """Fecha a conexão com o banco de dados."""
        if self.conn:
            self.conn.close()
    
    def salvar_preferencia(self, chave: str, valor: Any, categoria: str = "preferencias"):
        """Salva uma preferência do usuário."""
        salvar_contexto(self.conn, chave, valor, categoria)
    
    def carregar_preferencia(self, chave: str) -> Optional[Any]:
        """Carrega uma preferência do usuário."""
        return carregar_contexto(self.conn, chave)
    
    def registrar_decisao(self, prompt: str, resposta_sugerida: str, decisao: str):
        """Registra a decisão final do usuário sobre uma resposta sugerida."""
        registrar_interacao(
            self.conn,
            prompt=prompt,
            resposta=resposta_sugerida,
            decisao_usuario=decisao
        )
    
    def aprender_padrao(self, contexto: str, padrao: Dict[str, Any]):
        """Aprende um padrão de trabalho do usuário."""
        salvar_contexto(self.conn, f"padrao:{contexto}", padrao, "padroes")
    
    def carregar_padrao(self, contexto: str) -> Optional[Dict]:
        """Carrega um padrão de trabalho aprendido."""
        return carregar_contexto(self.conn, f"padrao:{contexto}")
    
    def buscar_contexto_relevante(self, query: str, limite: int = 5) -> List[Dict]:
        """Busca contexto relevante para uma query."""
        resultados = []
        
        # Busca no histórico recente
        historico = buscar_historico(self.conn, termo=query, limite=limite)
        for h in historico:
            resultados.append({
                "tipo": "historico",
                "conteudo": h["resposta"],
                "timestamp": h["timestamp"]
            })
        
        # Busca na memória semântica
        memorias = buscar_memoria_semantica(self.conn, termo=query, limite=limite)
        for m in memorias:
            resultados.append({
                "tipo": "memoria",
                "conteudo": m["conteudo"],
                "resumo": m.get("resumo"),
                "tags": m.get("tags")
            })
        
        return resultados[:limite]


if __name__ == "__main__":
    # Teste rápido
    mem = UsuarioMemory()
    
    # Salvar preferência
    mem.salvar_preferencia("idioma", "pt-BR")
    mem.salvar_preferencia("tom_respostas", "formal")
    
    # Aprender padrão
    mem.aprender_padrao("relatorios", {
        "formato": "markdown",
        "secoes": ["resumo", "analise", "recomendacoes"],
        "incluir_fontes": True
    })
    
    # Buscar contexto
    ctx = mem.buscar_contexto_relevante("relatório")
    print(f"Contexto encontrado: {ctx}")
    
    mem.close()
    print("Memória do usuário inicializada com sucesso!")
