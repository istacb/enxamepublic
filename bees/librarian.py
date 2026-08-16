#!/usr/bin/env python3
"""
LocalBeeLibrarian — Bibliotecário Local da Abelha
=================================================
Implementa pipeline RAG offline-first:
1. Memória semântica (SQLite)
2. RAG local (LanceDB + embeddings)
3. Arquivos locais (busca textual)
4. ZIM (Wikipedia offline)
5. Web (último recurso, se habilitado)

Reutiliza componentes do `bibliotecario/` existente.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.exp.secure_logger import setup_secure_logger, log_safe_query
from core.ollama.client import OllamaClient, OllamaGenerateRequest

# Reutilizar componentes do bibliotecario existente
import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from bibliotecario.embeddings import EmbeddingService
from bibliotecario.indexer import IndexedChunk, LocalDocumentIndexer
from bibliotecario.lancedb_store import LanceDBStore
from bibliotecario.zim_reader import ZimSearchClient
from bibliotecario.web_client import WebSearchClient

logger = setup_secure_logger(
    name="bee.librarian",
    level=os.getenv("LOG_LEVEL", "INFO"),
    console_output=True,
)


@dataclass(slots=True)
class SearchResult:
    answer: str
    confidence: float
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)


class LocalBeeLibrarian:
    """
    Bibliotecário Local da Abelha - Offline First.
    
    Pipeline de busca:
    1. Cache em memória (rápido)
    2. Memória semântica (SQLite via BeeMemory)
    3. LanceDB (busca vetorial embeddings)
    4. Arquivos locais (busca textual)
    5. ZIM (Wikipedia offline)
    6. Web (apenas se allow_web=True)
    """

    def __init__(
        self,
        data_dir: Path,
        ollama_url: str = "http://localhost:11434",
        model: str = "llama3.2:3b",
        memory: Any = None,  # BeeMemory
    ) -> None:
        self.data_dir = Path(data_dir)
        self.ollama_url = ollama_url
        self.model = model
        self.memory = memory

        self._cache: dict[str, SearchResult] = {}
        self._cache_ttl = 3600

        # Componentes RAG
        self.embeddings = EmbeddingService()
        self.indexer = LocalDocumentIndexer(
            docs_dir=str(self.data_dir / "documents"),
            embeddings=self.embeddings,
        )
        self.lancedb = LanceDBStore(embeddings=self.embeddings)
        self.zim = ZimSearchClient(zim_dir=str(self.data_dir / "zim"))
        self.web = WebSearchClient()
        self.ollama = OllamaClient(ollama_url)

        # Stats
        self._stats = {"queries": 0, "cache_hits": 0, "stages": {}}

    async def initialize(self) -> None:
        """Inicializa todos os componentes."""
        # LanceDB
        lancedb_path = self.data_dir / "lancedb"
        lancedb_path.mkdir(parents=True, exist_ok=True)
        await self.lancedb.initialize(str(lancedb_path))

        # Indexar documentos existentes
        chunks = self.indexer.rebuild()
        if chunks:
            await self.lancedb.upsert_chunks(chunks)
            logger.info(f"Indexados {len(chunks)} chunks do diretório local")

        # Verificar ZIM
        zim_count = len(list((self.data_dir / "zim").glob("*.zim"))) if (self.data_dir / "zim").exists() else 0
        if zim_count > 0:
            logger.info(f"Encontrados {zim_count} arquivos ZIM")

        logger.info("Bibliotecário Local inicializado")

    async def close(self) -> None:
        """Fecha conexões."""
        await self.lancedb.close()
        await self.ollama.close()

    def has_ocr(self) -> bool:
        """Verifica se OCR está disponível."""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def has_zim(self) -> bool:
        """Verifica se há arquivos ZIM."""
        zim_dir = self.data_dir / "zim"
        return zim_dir.exists() and any(zim_dir.glob("*.zim"))

    def get_available_models(self) -> list[str]:
        """Retorna modelos disponíveis no Ollama."""
        try:
            import httpx
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.ollama_url}/api/tags")
                if resp.status_code == 200:
                    return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            pass
        return []

    def _cache_key(self, query: str) -> str:
        return f"lib:{hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]}"

    async def _cache_get(self, key: str) -> SearchResult | None:
        if key in self._cache:
            self._stats["cache_hits"] += 1
            return self._cache[key]
        return None

    async def _cache_set(self, key: str, result: SearchResult) -> None:
        self._cache[key] = result
        if len(self._cache) > 1000:
            # Limpar cache antigo (simplificado)
            keys = list(self._cache.keys())[:500]
            for k in keys:
                self._cache.pop(k, None)

    async def quick_knowledge_check(self, subject: str, keywords: list[str] | None = None) -> dict[str, Any]:
        """
        Verificação rápida se tem conhecimento sobre assunto.
        Não executa RAG completo, apenas busca no índice.
        """
        query = subject + " " + " ".join(keywords or [])
        query_lower = query.lower()

        # Verificar LanceDB
        hits = await self.lancedb.search_similar(query_lower, top_k=3)
        if hits:
            return {
                "has_knowledge": True,
                "confidence": min(hits[0].score * 1.2, 1.0),
                "document_count": len(hits),
                "topics": [h.source_path for h in hits[:5]],
            }

        # Verificar arquivos locais
        local_hits = []
        for chunk in self.indexer.chunks:
            if query_lower in chunk.text.lower():
                local_hits.append(chunk)
            if len(local_hits) >= 3:
                break

        if local_hits:
            return {
                "has_knowledge": True,
                "confidence": 0.6,
                "document_count": len(local_hits),
                "topics": [h.source_path for h in local_hits[:5]],
            }

        return {"has_knowledge": False, "confidence": 0.0, "document_count": 0, "topics": []}

    async def search(self, query: str, max_results: int = 10) -> dict[str, Any]:
        """
        Pipeline completo de busca OFFLINE-FIRST:
        1. Cache
        2. Memória semântica (via BeeMemory)
        3. LanceDB (vetorial)
        4. Arquivos locais (textual)
        5. ZIM (offline)
        6. Web (se permitido)
        """
        started = time.perf_counter()
        self._stats["queries"] += 1
        log_safe_query(logger, query, context="search_start")

        query_clean = query.strip()
        cache_key = self._cache_key(query_clean)

        # 1. CACHE
        cached = await self._cache_get(cache_key)
        if cached:
            self._record_stage("cache", True, latency_ms=int((time.perf_counter() - started) * 1000))
            return self._result_to_dict(cached)

        trace: list[dict[str, Any]] = []

        # 2. MEMÓRIA SEMÂNTICA (via BeeMemory)
        if self.memory:
            mem_result = await self.memory.search_semantic(query_clean)
            if mem_result and mem_result.get("confidence", 0) > 0.75:
                result = SearchResult(
                    answer=mem_result["response"],
                    confidence=mem_result["confidence"],
                    source="memory",
                    metadata={"source_type": "semantic_memory"},
                )
                await self._cache_set(cache_key, result)
                self._record_stage("memory", True, latency_ms=int((time.perf_counter() - started) * 1000))
                return self._result_to_dict(result)

        trace.append({"stage": "memory", "hit": False})

        # 3. LANCEDB (Busca Vetorial)
        lancedb_hits = await self.lancedb.search_similar(query_clean, top_k=max_results)
        trace.append({"stage": "lancedb", "hit": bool(lancedb_hits), "count": len(lancedb_hits)})
        if lancedb_hits:
            context = "\n\n".join(
                f"[score={h.score:.3f}] {h.text}\n(origem: {h.source_path})" for h in lancedb_hits
            )
            answer = await self._synthesize(query_clean, context, "lancedb")
            result = SearchResult(
                answer=answer,
                confidence=min(lancedb_hits[0].score * 1.1, 1.0),
                source="lancedb",
                metadata={"source_type": "vector_search", "sources": [h.source_path for h in lancedb_hits]},
                sources=[h.source_path for h in lancedb_hits],
            )
            await self._cache_set(cache_key, result)
            self._record_stage("lancedb", True, latency_ms=int((time.perf_counter() - started) * 1000))
            return self._result_to_dict(result)

        # 4. ARQUIVOS LOCAIS (Busca Textual)
        local_hits = await self._local_file_search(query_clean, limit=max_results)
        trace.append({"stage": "local_files", "hit": bool(local_hits), "count": len(local_hits)})
        if local_hits:
            context = "\n\n".join(f"{c.text}\n(origem: {c.source_path})" for c in local_hits)
            answer = await self._synthesize(query_clean, context, "arquivos_locais")
            result = SearchResult(
                answer=answer,
                confidence=0.6,
                source="local_files",
                metadata={"source_type": "text_search", "sources": [h.source_path for h in local_hits]},
                sources=[h.source_path for h in local_hits],
            )
            await self._cache_set(cache_key, result)
            self._record_stage("local_files", True, latency_ms=int((time.perf_counter() - started) * 1000))
            return self._result_to_dict(result)

        # 5. ZIM (Wikipedia Offline)
        zim_hits = self.zim.search(query_clean, limit_per_file=2)
        trace.append({"stage": "zim", "hit": bool(zim_hits), "count": len(zim_hits)})
        if zim_hits:
            context = "\n\n".join(f"{h.title}: {h.snippet}\n(origem: {h.source_file})" for h in zim_hits[:5])
            answer = await self._synthesize(query_clean, context, "zim")
            result = SearchResult(
                answer=answer,
                confidence=0.5,
                source="zim",
                metadata={"source_type": "zim_offline", "sources": [h.source_file for h in zim_hits[:5]]},
                sources=[h.source_file for h in zim_hits[:5]],
            )
            await self._cache_set(cache_key, result)
            self._record_stage("zim", True, latency_ms=int((time.perf_counter() - started) * 1000))
            return self._result_to_dict(result)

        # 6. WEB (Último recurso - apenas se permitido via config)
        # NOTA: O serviço Bee controla allow_web, aqui apenas expõe o método
        trace.append({"stage": "web", "skipped": True, "reason": "not_allowed_by_default"})

        # Fallback
        fallback = "Não encontrei informação relevante nas minhas fontes locais."
        result = SearchResult(
            answer=fallback,
            confidence=0.0,
            source="none",
            metadata={"pipeline_trace": trace, "fallback": True},
        )
        await self._cache_set(cache_key, result)
        self._record_stage("fallback", True, latency_ms=int((time.perf_counter() - started) * 1000))
        return self._result_to_dict(result)

    async def _local_file_search(self, query: str, limit: int = 5) -> list[IndexedChunk]:
        """Busca textual simples nos chunks indexados."""
        q = query.lower()
        matched: list[IndexedChunk] = []
        for chunk in self.indexer.chunks:
            if q in chunk.text.lower() or any(tok in chunk.text.lower() for tok in q.split()):
                matched.append(chunk)
            if len(matched) >= limit:
                break
        return matched

    async def _synthesize(self, query: str, context: str, source: str) -> str:
        """Gera resposta usando modelo local com contexto."""
        prompt = (
            "Você é o Bibliotecário da Abelha no sistema Enxame. "
            "Responda em português brasileiro técnico e objetivo. "
            "Baseie-se APENAS no contexto fornecido.\n\n"
            f"Pergunta: {query}\n"
            f"Fonte: {source}\n\n"
            f"Contexto:\n{context}"
        )
        try:
            response = await self.ollama.generate(
                OllamaGenerateRequest(
                    model=self.model,
                    prompt=prompt,
                    temperature=0.2,
                    num_ctx=8192,
                )
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Erro na síntese: {e}")
            return f"Erro ao gerar resposta: {e}"

    async def search_web(self, query: str) -> dict[str, Any]:
        """Busca na web (apenas para fallback controlado pelo serviço)."""
        web_hits = await self.web.search(query)
        if not web_hits:
            return {"answer": "Nenhum resultado na web.", "confidence": 0.0, "source": "web"}

        context = "\n\n".join(f"{h.title}: {h.snippet}\nURL: {h.url}" for h in web_hits[:5])
        answer = await self._synthesize(query, context, "internet")
        return {
            "answer": answer,
            "confidence": 0.4,
            "source": "web",
            "sources": [h.url for h in web_hits[:5]],
        }

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Geração direta via modelo local."""
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        try:
            response = await self.ollama.generate(
                OllamaGenerateRequest(
                    model=self.model,
                    prompt=full_prompt,
                    temperature=temperature,
                    num_ctx=4096,
                )
            )
            return {"generation": response.strip(), "model": self.model}
        except Exception as e:
            logger.error(f"Erro na geração: {e}")
            return {"generation": f"Erro: {e}", "model": self.model}

    def _result_to_dict(self, result: SearchResult) -> dict[str, Any]:
        return {
            "answer": result.answer,
            "confidence": result.confidence,
            "source": result.source,
            "metadata": result.metadata,
            "sources": result.sources,
        }

    def _record_stage(self, stage: str, hit: bool, latency_ms: int) -> None:
        self._stats["stages"][stage] = self._stats["stages"].get(stage, 0) + 1
        logger.info(f"[pipeline] stage={stage} hit={hit} latency_ms={latency_ms}")

    def get_stats(self) -> dict[str, Any]:
        return self._stats.copy()