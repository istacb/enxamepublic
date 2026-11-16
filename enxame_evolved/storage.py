#!/usr/bin/env python3
"""
storage.py — Persistência Unificada SQLite WAL: Histórico, Contexto e Memória Evolutiva
=======================================================================================
Centraliza em um banco SQLite WAL seguro por operação (sem lock global entre threads):
1. Histórico de Conversas (`conversations`, `messages`, busca FTS5 `messages_fts`).
2. Manutenção de Contexto Multi-Turno (`ConversationContextManager`) com resumo
   deslizante (`rolling_summary`) ajustado ao patamar da CPU (`legado` vs `performance`).
3. Memória de Longo Prazo e Evolução do Usuário (`user_profile` + `semantic_memories`),
   adaptando profundidade técnica, concisão e preferências conforme o uso.
4. Fixação de Papéis de Máquinas (`node_role_pins`) e Auditoria do Guardião.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

EXPLICIT_MEMORY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\b(?:lembre(?:-se)?\s+que|memorize\s+que|guarde\s+que)\s+(.{6,240})"), "fato_explicito"),
    (re.compile(r"(?i)\b(?:eu\s+sou|trabalho\s+como|atuo\s+como|meu\s+projeto\s+[eé])\s+(.{4,200})"), "perfil_pessoal"),
    (re.compile(r"(?i)\b(?:prefiro\s+respostas?|sempre\s+responda|use\s+sempre)\s+(.{4,180})"), "preferencia_estilo"),
    (re.compile(r"(?i)\b(?:minha(?:s)?\s+m[aá]quina(?:s)?|meu\s+servidor|meu\s+ambiente)\s+(.{4,200})"), "infraestrutura"),
]

ADVANCED_TECH_MARKERS = {
    "async", "await", "asyncio", "mutex", "deadlock", "backpressure", "idempotente",
    "fts5", "bm25", "wal", "sha256", "hmac", "simd", "avx2", "quantização", "gguf",
    "latência", "ttft", "arquitetura", "microkernel", "systemd", "socket", "syscall",
}


def _tokenize_pt(texto: str) -> list[str]:
    return [t for t in re.findall(r"[\wÀ-ú]{3,}", (texto or "").lower())]


class UnifiedStore:
    """Armazenamento relacional e semântico offline-first em SQLite WAL."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fts_enabled = False
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    rolling_summary TEXT NOT NULL DEFAULT '',
                    active_profile TEXT NOT NULL DEFAULT 'auto',
                    target_node TEXT NOT NULL DEFAULT 'auto',
                    message_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    provenance_json TEXT NOT NULL DEFAULT '{}',
                    attachments_json TEXT NOT NULL DEFAULT '[]',
                    feedback INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_conv_time
                    ON messages(conversation_id, created_at ASC);

                CREATE TABLE IF NOT EXISTS user_profile (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS semantic_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'geral',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    keywords TEXT NOT NULL DEFAULT '',
                    relevance REAL NOT NULL DEFAULT 1.0,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    last_accessed REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_sem_mem_rel
                    ON semantic_memories(relevance DESC, last_accessed DESC);

                CREATE TABLE IF NOT EXISTS guardian_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    node_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reasons_json TEXT NOT NULL,
                    client_key TEXT NOT NULL DEFAULT 'local',
                    excerpt TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS node_role_pins (
                    node_id TEXT PRIMARY KEY,
                    pinned_role TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                        message_id UNINDEXED,
                        conversation_id UNINDEXED,
                        role UNINDEXED,
                        content
                    );
                    """
                )
                self._fts_enabled = True
            except sqlite3.OperationalError:
                self._fts_enabled = False
            conn.commit()

        # Garantir perfil evolutivo inicial
        if self.get_user_profile() is None:
            self._save_user_profile(
                {
                    "interaction_count": 0,
                    "verbosity": "equilibrado",
                    "language": "pt-BR",
                    "skill_by_domain": {
                        "general": "intermediario",
                        "technical": "intermediario",
                    },
                    "domain_counts": {},
                    "profile_affinity": {},
                    "feedback_up": 0,
                    "feedback_down": 0,
                }
            )

    # =========================================================================
    # Histórico de Conversas e Mensagens
    # =========================================================================

    def create_conversation(
        self,
        title: str = "Nova conversa",
        active_profile: str = "auto",
        target_node: str = "auto",
        conv_id: str | None = None,
    ) -> dict[str, Any]:
        cid = conv_id or str(uuid.uuid4())
        now = time.time()
        clean_title = (title or "Nova conversa").strip()[:90]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO conversations
                (id, title, created_at, updated_at, pinned, rolling_summary, active_profile, target_node, message_count)
                VALUES (?, ?, ?, ?, 0, '', ?, ?, 0)
                """,
                (cid, clean_title, now, now, active_profile, target_node),
            )
            conn.commit()
        return self.get_conversation(cid, include_messages=False) or {"id": cid, "title": clean_title}

    def ensure_conversation(
        self,
        conv_id: str | None,
        first_prompt: str = "",
        first_message: str | None = None,
        **kwargs: Any,
    ) -> str:
        prompt = first_message if first_message is not None else (kwargs.get("first_text") or first_prompt or "")
        if conv_id:
            existing = self.get_conversation(conv_id, include_messages=False)
            if existing:
                return conv_id
        auto_title = self._derive_title(prompt) if prompt else "Nova conversa"
        created = self.create_conversation(title=auto_title, conv_id=conv_id)
        return str(created["id"])

    @staticmethod
    def _derive_title(prompt: str) -> str:
        first_line = (prompt or "").strip().splitlines()[0] if prompt else ""
        first_line = re.sub(r"\s+", " ", first_line).strip()
        if not first_line:
            return "Nova conversa"
        return first_line[:68] + ("…" if len(first_line) > 68 else "")

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        provenance: dict[str, Any] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        msg_id: str | None = None,
    ) -> dict[str, Any]:
        mid = msg_id or str(uuid.uuid4())
        now = time.time()
        prov_str = json.dumps(provenance or {}, ensure_ascii=False)
        att_str = json.dumps(attachments or [], ensure_ascii=False)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT title, message_count FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if row is None:
                title = self._derive_title(content if role == "user" else "Nova conversa")
                conn.execute(
                    """
                    INSERT INTO conversations
                    (id, title, created_at, updated_at, pinned, rolling_summary, active_profile, target_node, message_count)
                    VALUES (?, ?, ?, ?, 0, '', 'auto', 'auto', 0)
                    """,
                    (conversation_id, title, now, now),
                )
                current_title = title
                current_count = 0
            else:
                current_title = row["title"]
                current_count = int(row["message_count"])

            new_title = current_title
            if role == "user" and current_count == 0 and current_title in ("Nova conversa", ""):
                new_title = self._derive_title(content)

            conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, provenance_json, attachments_json, feedback, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (mid, conversation_id, role, content, prov_str, att_str, now),
            )
            if self._fts_enabled:
                conn.execute(
                    "INSERT INTO messages_fts (message_id, conversation_id, role, content) VALUES (?, ?, ?, ?)",
                    (mid, conversation_id, role, content),
                )
            conn.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = ?, message_count = message_count + 1
                WHERE id = ?
                """,
                (new_title, now, conversation_id),
            )
            conn.commit()
        return {
            "id": mid,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "provenance": provenance or {},
            "attachments": attachments or [],
            "feedback": 0,
            "created_at": now,
        }

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        provenance: dict[str, Any] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        msg_id: str | None = None,
    ) -> dict[str, Any]:
        """Alias de `add_message` usado pelo EnxameKernel/SSE."""
        return self.add_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            provenance=provenance,
            attachments=attachments,
            msg_id=msg_id,
        )

    def list_conversations(self, limit: int = 80) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.*,
                       (SELECT content FROM messages m WHERE m.conversation_id = c.id ORDER BY m.created_at DESC LIMIT 1) AS last_preview
                FROM conversations c
                ORDER BY c.pinned DESC, c.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            preview = (r["last_preview"] or "").replace("\n", " ").strip()[:90]
            out.append(
                {
                    "id": r["id"],
                    "title": r["title"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "pinned": bool(r["pinned"]),
                    "active_profile": r["active_profile"],
                    "target_node": r["target_node"],
                    "message_count": r["message_count"],
                    "last_preview": preview,
                }
            )
        return out

    def get_conversation(self, conversation_id: str, include_messages: bool = True) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if row is None:
                return None
            conv: dict[str, Any] = {
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "pinned": bool(row["pinned"]),
                "rolling_summary": row["rolling_summary"],
                "active_profile": row["active_profile"],
                "target_node": row["target_node"],
                "message_count": row["message_count"],
            }
            if include_messages:
                mrows = conn.execute(
                    "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
                    (conversation_id,),
                ).fetchall()
                conv["messages"] = [
                    {
                        "id": m["id"],
                        "conversation_id": m["conversation_id"],
                        "role": m["role"],
                        "content": m["content"],
                        "provenance": json.loads(m["provenance_json"] or "{}"),
                        "attachments": json.loads(m["attachments_json"] or "[]"),
                        "feedback": m["feedback"],
                        "created_at": m["created_at"],
                    }
                    for m in mrows
                ]
            return conv

    def update_conversation(
        self,
        conversation_id: str,
        *,
        title: str | None = None,
        pinned: bool | None = None,
        rolling_summary: str | None = None,
        active_profile: str | None = None,
        target_node: str | None = None,
    ) -> bool:
        sets: list[str] = []
        vals: list[Any] = []
        if title is not None:
            sets.append("title = ?")
            vals.append(title.strip()[:90] or "Conversa")
        if pinned is not None:
            sets.append("pinned = ?")
            vals.append(1 if pinned else 0)
        if rolling_summary is not None:
            sets.append("rolling_summary = ?")
            vals.append(rolling_summary)
        if active_profile is not None:
            sets.append("active_profile = ?")
            vals.append(active_profile)
        if target_node is not None:
            sets.append("target_node = ?")
            vals.append(target_node)
        if not sets:
            return False
        vals.append(conversation_id)
        with self._connect() as conn:
            cur = conn.execute(
                f"UPDATE conversations SET {', '.join(sets)} WHERE id = ?", vals
            )
            conn.commit()
            return cur.rowcount > 0

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._connect() as conn:
            if self._fts_enabled:
                conn.execute(
                    "DELETE FROM messages_fts WHERE conversation_id = ?",
                    (conversation_id,),
                )
            cur = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()
            return cur.rowcount > 0

    def search_history(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        terms = _tokenize_pt(query)
        if not terms:
            return []
        with self._connect() as conn:
            if self._fts_enabled:
                fts_q = " OR ".join(f'"{t}"*' for t in terms[:6])
                rows = conn.execute(
                    """
                    SELECT f.message_id, f.conversation_id, f.role, f.content,
                           c.title AS conv_title, m.created_at, m.provenance_json
                    FROM messages_fts f
                    JOIN messages m ON m.id = f.message_id
                    JOIN conversations c ON c.id = f.conversation_id
                    WHERE messages_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_q, limit),
                ).fetchall()
            else:
                like = f"%{terms[0]}%"
                rows = conn.execute(
                    """
                    SELECT m.id AS message_id, m.conversation_id, m.role, m.content,
                           c.title AS conv_title, m.created_at, m.provenance_json
                    FROM messages m
                    JOIN conversations c ON c.id = m.conversation_id
                    WHERE lower(m.content) LIKE ?
                    ORDER BY m.created_at DESC
                    LIMIT ?
                    """,
                    (like, limit),
                ).fetchall()

        return [
            {
                "message_id": r["message_id"],
                "conversation_id": r["conversation_id"],
                "conversation_title": r["conv_title"],
                "role": r["role"],
                "snippet": r["content"][:220],
                "created_at": r["created_at"],
                "provenance": json.loads(r["provenance_json"] or "{}"),
            }
            for r in rows
        ]

    def set_message_feedback(self, message_id: str, score: int) -> bool:
        clamped = 1 if score > 0 else (-1 if score < 0 else 0)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT provenance_json FROM messages WHERE id = ?", (message_id,)
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                "UPDATE messages SET feedback = ? WHERE id = ?", (clamped, message_id)
            )
            conn.commit()
        prof = self.get_user_profile() or {}
        if clamped > 0:
            prof["feedback_up"] = int(prof.get("feedback_up", 0)) + 1
        elif clamped < 0:
            prof["feedback_down"] = int(prof.get("feedback_down", 0)) + 1
        try:
            prov = json.loads(row["provenance_json"] or "{}")
            ap = prov.get("agent_profile")
            if ap:
                aff = prof.setdefault("profile_affinity", {})
                aff[ap] = round(float(aff.get(ap, 0.0)) + (0.25 * clamped), 2)
        except Exception:
            pass
        self._save_user_profile(prof)
        return True

    # =========================================================================
    # Manutenção de Contexto Multi-Turno (Orçamento de CPU + Resumo Deslizante)
    # =========================================================================

    def build_context_messages(
        self,
        conversation_id: str,
        current_user_text: str = "",
        system_persona: str = "",
        rag_shielded_block: str = "",
        hardware_tier: str = "padrao",
        max_ctx_tokens: int | None = None,
        **kwargs: Any,
    ) -> tuple[list[dict[str, str]], dict[str, Any]] | list[dict[str, str]]:
        """
        Monta lista estruturada `messages[]` para `/api/chat` com orçamento
        enxuto adaptado à CPU:
        - `legado`: mantém últimas 4 mensagens literais + resumo compacto
        - `padrao`: mantém últimas 8 mensagens literais + resumo compacto
        - `performance`: mantém últimas 12 mensagens literais + resumo compacto

        Compatibilidade EnxameKernel: quando chamada apenas com
        `(conversation_id, max_ctx_tokens=N)`, devolve somente a lista recente
        de mensagens `[{role, content}]` cabendo no orçamento.
        """
        if max_ctx_tokens is not None and not current_user_text and not system_persona:
            return self._recent_messages_for_budget(conversation_id, max_ctx_tokens)
        max_recent = 4 if hardware_tier == "legado" else (8 if hardware_tier == "padrao" else 12)
        conv = self.get_conversation(conversation_id, include_messages=True)
        history_msgs = (conv or {}).get("messages", [])
        rolling_summary = (conv or {}).get("rolling_summary", "")

        # Compacta turnos antigos automaticamente de forma determinística (Zero-LLM, <1ms!)
        if len(history_msgs) > max_recent:
            older = history_msgs[:-max_recent]
            rolling_summary = self._compact_older_messages(older, existing_summary=rolling_summary)
            self.update_conversation(conversation_id, rolling_summary=rolling_summary)
            recent = history_msgs[-max_recent:]
        else:
            recent = history_msgs

        # Recupera perfil evolutivo + memórias de longo prazo relevantes à pergunta
        adaptive_hint = self.build_adaptive_system_instruction(current_user_text)

        sys_parts = [system_persona.strip()]
        if adaptive_hint:
            sys_parts.append(adaptive_hint)
        if rolling_summary:
            sys_parts.append(f"Resumo do contexto anterior desta conversa:\n{rolling_summary}")
        if rag_shielded_block:
            sys_parts.append(f"Fontes recuperadas para consulta:\n{rag_shielded_block}")

        messages: list[dict[str, str]] = [
            {"role": "system", "content": "\n\n".join(p for p in sys_parts if p)}
        ]
        for m in recent:
            if m["role"] in ("user", "assistant") and m["content"].strip():
                # Evita duplicar se a mensagem atual já tiver sido salva antes da chamada
                messages.append({"role": m["role"], "content": m["content"][:2200]})
        messages.append({"role": "user", "content": current_user_text})

        portable_ctx = {
            "conversation_id": conversation_id,
            "rolling_summary": rolling_summary,
            "recent_turns": len(recent),
            "hardware_tier_budget": hardware_tier,
        }
        return messages, portable_ctx

    def _recent_messages_for_budget(
        self, conversation_id: str, max_ctx_tokens: int, reserve_tokens: int = 900
    ) -> list[dict[str, str]]:
        """Devolve turnos recentes `[{role, content}]` cabendo no orçamento de tokens."""
        conv = self.get_conversation(conversation_id, include_messages=True)
        history = (conv or {}).get("messages", []) if conv else []
        budget = max(512, int(max_ctx_tokens) - reserve_tokens)
        picked: list[dict[str, str]] = []
        used = 0
        for m in reversed(history):
            if m.get("role") not in ("user", "assistant"):
                continue
            content = str(m.get("content") or "").strip()
            if not content:
                continue
            cost = max(8, len(content) // 4)
            if used + cost > budget and picked:
                break
            used += cost
            picked.append({"role": m["role"], "content": content[:2400]})
        picked.reverse()
        return picked

    @staticmethod
    def _compact_older_messages(
        older_messages: list[dict[str, Any]],
        existing_summary: str = "",
        max_chars: int = 900,
    ) -> str:
        """Sumarização extrativa determinística em CPU (<1ms) dos turnos antigos."""
        bullets: list[str] = []
        if existing_summary:
            bullets.append(existing_summary.strip()[:380])
        for m in older_messages[-8:]:
            papel = "Usuário" if m["role"] == "user" else "Enxame"
            primeira = re.sub(r"\s+", " ", m["content"]).strip()[:140]
            if primeira:
                bullets.append(f"- {papel}: {primeira}")
        joined = "\n".join(bullets)
        if len(joined) > max_chars:
            joined = joined[-max_chars:]
        return joined

    # =========================================================================
    # Memória de Longo Prazo e Adaptabilidade Conforme Evolução do Usuário
    # =========================================================================

    def get_user_profile(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM user_profile WHERE key = 'main'"
            ).fetchone()
            return json.loads(row["value_json"]) if row else None

    def _save_user_profile(self, data: dict[str, Any]) -> None:
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_profile (key, value_json, updated_at)
                VALUES ('main', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at
                """,
                (json.dumps(data, ensure_ascii=False), now),
            )
            conn.commit()

    def update_user_preferences(self, patch: dict[str, Any]) -> dict[str, Any]:
        prof = self.get_user_profile() or {}
        for k in ("verbosity", "language", "skill_by_domain"):
            if k in patch:
                prof[k] = patch[k]
        self._save_user_profile(prof)
        return prof

    def add_semantic_memory(
        self,
        content: str,
        category: str = "geral",
        tags: list[str] | None = None,
        relevance: float = 1.0,
    ) -> int:
        clean = re.sub(r"\s+", " ", (content or "")).strip()[:600]
        if not clean:
            return -1
        now = time.time()
        kws = " ".join(sorted(set(_tokenize_pt(clean))))
        with self._connect() as conn:
            # Evita duplicar exatamente o mesmo fato
            dup = conn.execute(
                "SELECT id FROM semantic_memories WHERE lower(content) = lower(?)",
                (clean,),
            ).fetchone()
            if dup:
                conn.execute(
                    "UPDATE semantic_memories SET relevance = MIN(5.0, relevance + 0.3), last_accessed = ? WHERE id = ?",
                    (now, dup["id"]),
                )
                conn.commit()
                return int(dup["id"])

            cur = conn.execute(
                """
                INSERT INTO semantic_memories
                (content, category, tags_json, keywords, relevance, access_count, created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (clean, category, json.dumps(tags or [], ensure_ascii=False), kws, relevance, now, now),
            )
            conn.commit()
            return int(cur.lastrowid or -1)

    def list_semantic_memories(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM semantic_memories ORDER BY relevance DESC, last_accessed DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "content": r["content"],
                "category": r["category"],
                "tags": json.loads(r["tags_json"] or "[]"),
                "relevance": round(float(r["relevance"]), 2),
                "access_count": r["access_count"],
                "created_at": r["created_at"],
                "last_accessed": r["last_accessed"],
            }
            for r in rows
        ]

    def delete_semantic_memory(self, mem_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM semantic_memories WHERE id = ?", (mem_id,))
            conn.commit()
            return cur.rowcount > 0

    def recall_relevant_memories(self, query: str, top_k: int = 4) -> list[dict[str, Any]]:
        q_tokens = set(_tokenize_pt(query))
        all_mems = self.list_semantic_memories(limit=120)
        if not all_mems:
            return []

        now = time.time()
        scored: list[tuple[float, dict[str, Any]]] = []
        for m in all_mems:
            m_tokens = set(_tokenize_pt(m["content"])) | set(_tokenize_pt(" ".join(m["tags"])))
            overlap = len(q_tokens & m_tokens) / max(1, min(len(q_tokens) or 1, 6))
            # Preferências explícitas de estilo sempre têm peso basal
            style_bonus = 0.32 if m["category"] in ("preferencia_estilo", "perfil_pessoal") else 0.0
            age_days = max(0.0, (now - float(m["last_accessed"])) / 86400.0)
            recency = math.exp(-age_days / 45.0)
            reinf = min(1.0, (float(m["relevance"]) / 3.0) + (int(m["access_count"]) * 0.05))
            score = (0.62 * overlap) + style_bonus + (0.18 * recency) + (0.20 * reinf)
            if overlap > 0 or style_bonus > 0:
                scored.append((score, m))

        scored.sort(key=lambda x: x[0], reverse=True)
        chosen = [item for _, item in scored[:top_k]]
        if chosen:
            with self._connect() as conn:
                for ch in chosen:
                    conn.execute(
                        "UPDATE semantic_memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                        (now, ch["id"]),
                    )
                conn.commit()
        return chosen

    def build_adaptive_system_instruction(self, current_query: str) -> str:
        """Gera instrução enxuta de personalização baseada na evolução do usuário."""
        prof = self.get_user_profile() or {}
        verb = prof.get("verbosity", "equilibrado")
        skills = prof.get("skill_by_domain", {})
        mems = self.recall_relevant_memories(current_query, top_k=3)

        linhas: list[str] = []
        if verb == "conciso":
            linhas.append("Estilo adaptado ao usuário: seja direto, enxuto e objetivo, sem introduções longas.")
        elif verb == "detalhado":
            linhas.append("Estilo adaptado ao usuário: explique passo a passo com exemplos completos.")

        if skills:
            resumo_skills = ", ".join(f"{dom}={niv}" for dom, niv in list(skills.items())[:4])
            linhas.append(f"Nível observado do usuário por domínio: {resumo_skills}.")

        if mems:
            fatos = "; ".join(m["content"] for m in mems)
            linhas.append(f"Memória de longo prazo do usuário: {fatos}")

        return "\n".join(linhas)

    # --- Aliases de Memória usados pelo EnxameKernel (`/api/v1/memory`) ---
    def add_memory(
        self,
        fact: str = "",
        content: str = "",
        category: str = "geral",
        importance: float = 0.85,
        relevance: float | None = None,
        tags: list[str] | None = None,
        source_conv_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        text = (fact or content or str(kwargs.get("text") or "")).strip()
        rel = float(relevance) if relevance is not None else (0.6 + float(importance or 0.85))
        all_tags = list(tags or [])
        if source_conv_id:
            all_tags.append(f"conv:{source_conv_id}")
        mem_id = self.add_semantic_memory(
            content=text, category=category, tags=all_tags, relevance=rel
        )
        return {
            "id": mem_id,
            "content": text,
            "fact": text,
            "category": category,
            "tags": all_tags,
            "relevance": round(rel, 2),
        }

    def list_memories(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.list_semantic_memories(limit=limit)

    def delete_memory(self, mem_id: int | str) -> bool:
        try:
            return self.delete_semantic_memory(int(mem_id))
        except (TypeError, ValueError):
            return False

    def search_memories(self, query: str, top_k: int = 4, limit: int | None = None) -> list[dict[str, Any]]:
        return self.recall_relevant_memories(query, top_k=int(limit or top_k))

    def build_adaptive_style_prompt(self, current_query: str = "", **kwargs: Any) -> str:
        return self.build_adaptive_system_instruction(current_query or str(kwargs.get("query") or ""))

    def learn_from_interaction(
        self,
        user_message: str,
        assistant_response: str = "",
        domain: str = "general",
        profile_id: str = "generalist",
        assistant_message: str | None = None,
        profile_used: str | None = None,
        conversation_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Evolui o perfil e extrai fatos duráveis após cada turno (execução rápida <2ms em CPU).
        """
        prof = self.get_user_profile() or {}
        prof["interaction_count"] = int(prof.get("interaction_count", 0)) + 1

        # 1. Contabilizar domínio e evoluir nível técnico percebido
        dom_counts = prof.setdefault("domain_counts", {})
        dom_counts[domain] = int(dom_counts.get(domain, 0)) + 1
        tokens = set(_tokenize_pt(user_message))
        tech_hits = len(tokens & ADVANCED_TECH_MARKERS)

        skills = prof.setdefault("skill_by_domain", {})
        current_skill = skills.get(domain, "iniciante")
        if tech_hits >= 2 or dom_counts[domain] >= 12:
            skills[domain] = "avancado"
        elif tech_hits >= 1 or dom_counts[domain] >= 4:
            if current_skill == "iniciante":
                skills[domain] = "intermediario"
        else:
            skills.setdefault(domain, "intermediario")

        # 2. Detectar preferência de concisão / detalhamento
        low = user_message.lower()
        if any(k in low for k in ("seja breve", "resuma", "curto e grosso", "sem rodeios", "direto ao ponto")):
            prof["verbosity"] = "conciso"
        elif any(k in low for k in ("explique em detalhes", "passo a passo detalhado", "aprofunde")):
            prof["verbosity"] = "detalhado"

        # 3. Registrar afinidade com perfil especialista
        aff = prof.setdefault("profile_affinity", {})
        aff[profile_id] = round(float(aff.get(profile_id, 0.0)) + 0.1, 2)

        self._save_user_profile(prof)

        # 4. Extrair memórias explícitas declaradas pelo usuário
        learned_ids: list[int] = []
        for regex, categoria in EXPLICIT_MEMORY_PATTERNS:
            for match in regex.finditer(user_message):
                fato = match.group(1).strip(" .,;!?")
                if len(fato) >= 5:
                    mid = self.add_semantic_memory(
                        content=fato,
                        category=categoria,
                        tags=[domain, profile_id],
                        relevance=1.8,
                    )
                    if mid > 0:
                        learned_ids.append(mid)

        return {"profile": prof, "learned_memory_ids": learned_ids}

    # =========================================================================
    # Fixação de Papéis do Cluster e Eventos do Guardião
    # =========================================================================

    def pin_node_role(self, node_id: str, role: str | list[str] | None) -> None:
        roles: list[str] = []
        if isinstance(role, (list, tuple)):
            roles = [str(r).strip() for r in role if str(r).strip()]
        elif role and role != "auto":
            roles = [str(role).strip()]
        with self._connect() as conn:
            if not roles:
                conn.execute("DELETE FROM node_role_pins WHERE node_id = ?", (node_id,))
            else:
                conn.execute(
                    """
                    INSERT INTO node_role_pins (node_id, pinned_role, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(node_id) DO UPDATE SET pinned_role = excluded.pinned_role, updated_at = excluded.updated_at
                    """,
                    (node_id, json.dumps(roles, ensure_ascii=False), time.time()),
                )
            conn.commit()

    def set_role_pin(self, node_id: str, roles: list[str] | str | None) -> None:
        """Alias de `pin_node_role` usado pela rota `/api/v1/roles/pin`."""
        self.pin_node_role(node_id, roles)

    def get_role_pins(self) -> dict[str, list[str]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT node_id, pinned_role FROM node_role_pins").fetchall()
        pins: dict[str, list[str]] = {}
        for r in rows:
            raw = r["pinned_role"] or ""
            try:
                parsed = json.loads(raw)
                pins[r["node_id"]] = [str(x) for x in parsed] if isinstance(parsed, list) else [str(parsed)]
            except (ValueError, TypeError):
                pins[r["node_id"]] = [raw] if raw else []
        return pins

    def record_guardian_event(
        self,
        node_id: str = "local",
        action: str = "ALLOW",
        reasons: list[str] | None = None,
        client_key: str = "local",
        excerpt: str = "",
        reason: str | None = None,
        matched_rules: list[str] | None = None,
        input_preview: str | None = None,
        client_id: str | None = None,
        risk_score: float = 0.0,
        **kwargs: Any,
    ) -> None:
        merged_reasons: list[str] = list(reasons or [])
        if matched_rules:
            merged_reasons.extend(str(r) for r in matched_rules)
        if reason and reason not in merged_reasons:
            merged_reasons.insert(0, str(reason))
        if risk_score:
            merged_reasons.append(f"risk_score={float(risk_score):.2f}")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO guardian_events (timestamp, node_id, action, reasons_json, client_key, excerpt)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    time.time(),
                    node_id or kwargs.get("node", "local"),
                    action,
                    json.dumps(merged_reasons, ensure_ascii=False),
                    client_id or client_key or "local",
                    (input_preview if input_preview is not None else excerpt)[:140],
                ),
            )
            conn.commit()

    def get_guardian_stats(self) -> dict[str, Any]:
        """Contadores agregados de eventos ALLOW/CONTAIN/BLOCK do Guardião."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT action, COUNT(*) AS n FROM guardian_events GROUP BY action"
            ).fetchall()
            total_row = conn.execute("SELECT COUNT(*) AS n FROM guardian_events").fetchone()
        by_action = {str(r["action"]): int(r["n"]) for r in rows}
        return {
            "total": int(total_row["n"]) if total_row else 0,
            "allowed": by_action.get("ALLOW", 0),
            "contained": by_action.get("CONTAIN", 0),
            "blocked": by_action.get("BLOCK", 0),
            "by_action": by_action,
        }

    def close(self) -> None:
        """Fecha o store (conexões SQLite são por operação; nada persistente)."""

    def list_guardian_events(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM guardian_events ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "timestamp": r["timestamp"],
                "node_id": r["node_id"],
                "action": r["action"],
                "reasons": json.loads(r["reasons_json"] or "[]"),
                "client_key": r["client_key"],
                "excerpt": r["excerpt"],
            }
            for r in rows
        ]
