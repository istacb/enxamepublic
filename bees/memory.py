#!/usr/bin/env python3
"""
BeeMemory — Memória Persistente da Abelha (SQLite)
==================================================
Armazena:
- Contexto/preferências (key-value)
- Histórico de interações
- Memória semântica (tags, conceitos, relevância)

Reutiliza padrões do core/memory/usuario_memory.py
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("bee.memory")


@dataclass(slots=True)
class Interaction:
    """Interação registrada na memória."""
    id: int
    timestamp: float
    query: str
    response: str
    source: str  # local, enxame, web, memory
    confidence: float
    metadata: dict[str, Any]


@dataclass(slots=True)
class SemanticMemory:
    """Entrada de memória semântica."""
    id: int
    content: str
    tags: list[str]
    relevance: float
    accessed_at: float | None
    created_at: float


class BeeMemory:
    """
    Memória persistente da Abelha usando SQLite.
    
    Tabelas:
    - context: key-value para preferências e contexto
    - interactions: histórico de queries e respostas
    - semantic_memory: memória semântica com tags e relevância
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        """Inicializa banco de dados e cria tabelas."""
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        with closing(self._conn.cursor()) as cur:
            # Contexto/preferências
            cur.execute("""
                CREATE TABLE IF NOT EXISTS context (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)

            # Histórico de interações
            cur.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL DEFAULT (strftime('%s', 'now')),
                    query TEXT NOT NULL,
                    response TEXT,
                    source TEXT,
                    confidence REAL,
                    metadata TEXT
                )
            """)

            # Memória semântica
            cur.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    tags TEXT,
                    relevance REAL DEFAULT 1.0,
                    accessed_at REAL,
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)

            # Índices para performance
            cur.execute("CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_interactions_source ON interactions(source)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_semantic_relevance ON semantic_memory(relevance)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_semantic_accessed ON semantic_memory(accessed_at)")

            self._conn.commit()

        logger.info(f"Memória inicializada em {self.db_path}")

    async def close(self) -> None:
        """Fecha conexão com banco."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _ensure_conn(self) -> sqlite3.Connection:
        if not self._conn:
            raise RuntimeError("Memória não inicializada. Chame initialize() primeiro.")
        return self._conn

    # =========================================================================
    # Contexto (key-value persistente)
    # =========================================================================

    def set_context(self, key: str, value: Any) -> None:
        """Salva valor no contexto."""
        conn = self._ensure_conn()
        with closing(conn.cursor()) as cur:
            cur.execute(
                "INSERT OR REPLACE INTO context (key, value, updated_at) VALUES (?, ?, ?)",
                (key, json.dumps(value, ensure_ascii=False), time.time()),
            )
            conn.commit()

    def get_context(self, key: str, default: Any = None) -> Any:
        """Recupera valor do contexto."""
        conn = self._ensure_conn()
        with closing(conn.cursor()) as cur:
            cur.execute("SELECT value FROM context WHERE key = ?", (key,))
            row = cur.fetchone()
            if row:
                return json.loads(row["value"])
            return default

    def delete_context(self, key: str) -> bool:
        """Remove chave do contexto."""
        conn = self._ensure_conn()
        with closing(conn.cursor()) as cur:
            cur.execute("DELETE FROM context WHERE key = ?", (key,))
            conn.commit()
            return cur.rowcount > 0

    def get_all_context(self) -> dict[str, Any]:
        """Retorna todo o contexto."""
        conn = self._ensure_conn()
        with closing(conn.cursor()) as cur:
            cur.execute("SELECT key, value FROM context")
            return {row["key"]: json.loads(row["value"]) for row in cur.fetchall()}

    # =========================================================================
    # Histórico de Interações
    # =========================================================================

    def save_interaction(
        self,
        query: str,
        response: str,
        source: str,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Registra interação no histórico."""
        conn = self._ensure_conn()
        with closing(conn.cursor()) as cur:
            cur.execute(
                """
                INSERT INTO interactions (query, response, source, confidence, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (query, response, source, confidence, json.dumps(metadata or {}), time.time()),
            )
            conn.commit()
            return cur.lastrowid

    def get_recent_interactions(self, limit: int = 50) -> list[Interaction]:
        """Recupera interações recentes."""
        conn = self._ensure_conn()
        with closing(conn.cursor()) as cur:
            cur.execute(
                "SELECT * FROM interactions ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
            return [
                Interaction(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    query=row["query"],
                    response=row["response"] or "",
                    source=row["source"] or "unknown",
                    confidence=row["confidence"] or 0.0,
                    metadata=json.loads(row["metadata"] or "{}"),
                )
                for row in rows
            ]

    def get_interactions_by_source(self, source: str, limit: int = 100) -> list[Interaction]:
        """Recupera interações por fonte."""
        conn = self._ensure_conn()
        with closing(conn.cursor()) as cur:
            cur.execute(
                "SELECT * FROM interactions WHERE source = ? ORDER BY timestamp DESC LIMIT ?",
                (source, limit),
            )
            rows = cur.fetchall()
            return [
                Interaction(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    query=row["query"],
                    response=row["response"] or "",
                    source=row["source"] or "unknown",
                    confidence=row["confidence"] or 0.0,
                    metadata=json.loads(row["metadata"] or "{}"),
                )
                for row in rows
            ]

    def prune_interactions(self, max_count: int = 1000) -> int:
        """Remove interações antigas mantendo apenas as mais recentes."""
        conn = self._ensure_conn()
        with closing(conn.cursor()) as cur:
            cur.execute(
                """
                DELETE FROM interactions
                WHERE id NOT IN (
                    SELECT id FROM interactions ORDER BY timestamp DESC LIMIT ?
                )
                """,
                (max_count,),
            )
            conn.commit()
            return cur.rowcount

    # =========================================================================
    # Memória Semântica
    # =========================================================================

    def save_semantic(
        self,
        content: str,
        tags: list[str] | None = None,
        relevance: float = 1.0,
    ) -> int:
        """Salva entrada na memória semântica."""
        conn = self._ensure_conn()
        with closing(conn.cursor()) as cur:
            cur.execute(
                """
                INSERT INTO semantic_memory (content, tags, relevance, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (content, json.dumps(tags or []), relevance, time.time()),
            )
            conn.commit()
            return cur.lastrowid

    def search_semantic(
        self,
        query: str,
        min_relevance: float = 0.5,
        limit: int = 10,
    ) -> dict[str, Any] | None:
        """
        Busca na memória semântica por similaridade textual simples.
        Retorna a melhor correspondência com resposta associada.
        """
        conn = self._ensure_conn()
        query_lower = query.lower()
        words = [w for w in query_lower.split() if len(w) > 2]

        if not words:
            return None

        with closing(conn.cursor()) as cur:
            # Buscar por tags ou conteúdo contendo palavras da query
            placeholders = ",".join(["?"] * len(words))
            sql = f"""
                SELECT * FROM semantic_memory
                WHERE relevance >= ?
                AND (
                    content LIKE {' OR content LIKE '.join(['?'] * len(words))}
                    OR tags LIKE {' OR tags LIKE '.join(['?'] * len(words))}
                )
                ORDER BY relevance DESC, accessed_at DESC
                LIMIT ?
            """

            params = [min_relevance]
            for w in words:
                params.append(f"%{w}%")
            for w in words:
                params.append(f"%{w}%")
            params.append(limit)

            cur.execute(sql, params)
            rows = cur.fetchall()

            if not rows:
                return None

            # Melhor resultado
            best = rows[0]

            # Atualizar accessed_at e relevance decay
            new_relevance = min(best["relevance"] * 1.05, 2.0)  # Boost por acesso
            cur.execute(
                "UPDATE semantic_memory SET accessed_at = ?, relevance = ? WHERE id = ?",
                (time.time(), new_relevance, best["id"]),
            )
            conn.commit()

            # Buscar resposta associada nas interações recentes
            response = self._find_associated_response(query)

            return {
                "content": best["content"],
                "tags": json.loads(best["tags"] or "[]"),
                "relevance": best["relevance"],
                "response": response,
                "confidence": min(best["relevance"] / 2.0, 1.0),
            }

    def _find_associated_response(self, query: str) -> str | None:
        """Busca resposta associada à query nas interações."""
        conn = self._ensure_conn()
        query_lower = query.lower()
        words = [w for w in query_lower.split() if len(w) > 3]

        if not words:
            return None

        with closing(conn.cursor()) as cur:
            placeholders = " OR ".join(["query LIKE ?"] * len(words))
            sql = f"""
                SELECT response FROM interactions
                WHERE ({placeholders})
                AND confidence > 0.7
                ORDER BY timestamp DESC LIMIT 1
            """
            params = [f"%{w}%" for w in words]
            cur.execute(sql, params)
            row = cur.fetchone()
            return row["response"] if row else None

    def update_relevance(self, memory_id: int, delta: float) -> bool:
        """Atualiza relevância de uma memória (feedback positivo/negativo)."""
        conn = self._ensure_conn()
        with closing(conn.cursor()) as cur:
            cur.execute(
                "UPDATE semantic_memory SET relevance = MAX(0.1, relevance + ?) WHERE id = ?",
                (delta, memory_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def decay_relevance(self, factor: float = 0.99, min_relevance: float = 0.1) -> int:
        """Aplica decay de relevância em memórias não acessadas recentemente."""
        conn = self._ensure_conn()
        cutoff = time.time() - (30 * 24 * 3600)  # 30 dias
        with closing(conn.cursor()) as cur:
            cur.execute(
                """
                UPDATE semantic_memory
                SET relevance = MAX(?, relevance * ?)
                WHERE (accessed_at IS NULL OR accessed_at < ?)
                AND relevance > ?
                """,
                (min_relevance, factor, cutoff, min_relevance),
            )
            conn.commit()
            return cur.rowcount

    def get_stats(self) -> dict[str, Any]:
        """Estatísticas da memória."""
        conn = self._ensure_conn()
        with closing(conn.cursor()) as cur:
            cur.execute("SELECT COUNT(*) as c FROM context")
            context_count = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) as c FROM interactions")
            interactions_count = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) as c FROM semantic_memory")
            semantic_count = cur.fetchone()["c"]

            cur.execute("SELECT AVG(relevance) as avg FROM semantic_memory")
            avg_relevance = cur.fetchone()["avg"] or 0.0

            return {
                "context_entries": context_count,
                "interactions": interactions_count,
                "semantic_memories": semantic_count,
                "avg_relevance": round(avg_relevance, 3),
                "db_size_mb": round(self.db_path.stat().st_size / (1024 * 1024), 2) if self.db_path.exists() else 0,
            }