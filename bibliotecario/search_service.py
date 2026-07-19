from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from core.ollama.client import OllamaClient, OllamaGenerateRequest

from .embeddings import EmbeddingService
from .indexer import IndexedChunk, LocalDocumentIndexer
from .qdrant_store import QdrantStore
from .translator import PTBRTranslator
from .web_client import WebSearchClient
from .zim_reader import ZimSearchClient

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SearchResult:
    answer: str
    metadata: dict[str, Any]


class SearchPipelineService:
    def __init__(self) -> None:
        docs_dir = os.getenv("BIB_DOCS_DIR", "/data/docs")
        zim_dir = os.getenv("BIB_ZIM_DIR", "/data/zim")
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model = os.getenv("BIB_MODEL", "gemma2:9b")

        self.translator = PTBRTranslator(enabled=os.getenv("TRANSLATION_ENABLED", "1") == "1")
        self.embeddings = EmbeddingService()
        self.indexer = LocalDocumentIndexer(docs_dir=docs_dir, embeddings=self.embeddings)
        self.qdrant = QdrantStore(embeddings=self.embeddings)
        self.zim = ZimSearchClient(zim_dir=zim_dir)
        self.web = WebSearchClient()
        self.ollama = OllamaClient(ollama_url)

        self._cache = None
        self._memory_cache: dict[str, str] = {}
        self._cache_ttl = int(os.getenv("REDIS_CACHE_TTL_SECONDS", "3600"))

    async def initialize(self) -> None:
        await self._init_cache()
        chunks = self.indexer.rebuild()
        await self.qdrant.upsert_chunks(chunks)

    async def _init_cache(self) -> None:
        redis_url = os.getenv("REDIS_URL", "redis://redis-bibliotecario:6379/0")
        try:
            from redis.asyncio import from_url  # type: ignore

            self._cache = from_url(redis_url, decode_responses=True)
            await self._cache.ping()
            logger.info("Redis conectado em %s", redis_url)
        except Exception as exc:  # pragma: no cover - depende de runtime
            logger.warning("Redis indisponível, cache em memória: %s", exc)
            self._cache = None

    async def _cache_get(self, key: str) -> str | None:
        if self._cache is not None:
            return await self._cache.get(key)
        return self._memory_cache.get(key)

    async def _cache_set(self, key: str, value: str) -> None:
        if self._cache is not None:
            await self._cache.set(key, value, ex=self._cache_ttl)
            return
        self._memory_cache[key] = value

    async def _local_file_search(self, query: str, limit: int = 5) -> list[IndexedChunk]:
        q = query.lower()
        matched: list[IndexedChunk] = []
        for chunk in self.indexer.chunks:
            if q in chunk.text.lower() or any(tok in chunk.text.lower() for tok in q.split()):
                matched.append(chunk)
            if len(matched) >= limit:
                break
        return matched

    async def _synthesize(self, query: str, context: str, source: str) -> str:
        prompt = (
            "Você é o Bibliotecário do ENXAME. Responda em português brasileiro técnico e objetivo. "
            "Se o contexto não for suficiente, diga explicitamente as limitações.\n\n"
            f"Pergunta: {query}\n"
            f"Fonte primária: {source}\n\n"
            f"Contexto:\n{context}"
        )
        response = await self.ollama.generate(
            OllamaGenerateRequest(model=self.model, prompt=prompt, temperature=0.2, num_ctx=8192)
        )
        return self.translator.to_pt_br(response)

    async def reindex_callback(self, chunks: list[IndexedChunk]) -> None:
        await self.qdrant.upsert_chunks(chunks)

    async def auto_reindex_loop(self) -> None:
        await self.indexer.auto_reindex_loop(self.reindex_callback)

    async def search(self, query: str, allow_internet: bool = True) -> SearchResult:
        started = time.perf_counter()
        query_pt = self.translator.to_pt_br(query)
        trace: list[dict[str, Any]] = []

        logger.info("[pipeline] etapa=1 redis_cache query=%s", query_pt)
        # 1) Cache Redis
        cache_key = f"bibliotecario:query:{query_pt.strip().lower()}"
        cached = await self._cache_get(cache_key)
        trace.append({"stage": "redis_cache", "hit": bool(cached)})
        if cached:
            payload = json.loads(cached)
            payload.setdefault("metadata", {}).setdefault("pipeline", trace)
            payload["metadata"]["latency_ms"] = int((time.perf_counter() - started) * 1000)
            return SearchResult(answer=str(payload.get("answer", "")), metadata=payload.get("metadata", {}))

        logger.info("[pipeline] etapa=2 qdrant")
        # 2) Qdrant
        qdrant_hits = await self.qdrant.search(query_pt, limit=4)
        trace.append({"stage": "qdrant", "hit": bool(qdrant_hits), "count": len(qdrant_hits)})
        if qdrant_hits:
            context = "\n\n".join(
                f"[score={h.score:.3f}] {h.text}\n(origem: {h.source_path})" for h in qdrant_hits
            )
            answer = await self._synthesize(query_pt, context, source="qdrant")
            metadata = {
                "source": "qdrant",
                "sources": [h.source_path for h in qdrant_hits],
                "pipeline": trace,
                "translated": True,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
            await self._cache_set(cache_key, json.dumps({"answer": answer, "metadata": metadata}, ensure_ascii=False))
            return SearchResult(answer=answer, metadata=metadata)

        logger.info("[pipeline] etapa=3 local_files")
        # 3) Arquivos locais
        local_hits = await self._local_file_search(query_pt, limit=4)
        trace.append({"stage": "local_files", "hit": bool(local_hits), "count": len(local_hits)})
        if local_hits:
            context = "\n\n".join(f"{c.text}\n(origem: {c.source_path})" for c in local_hits)
            answer = await self._synthesize(query_pt, context, source="arquivos_locais")
            metadata = {
                "source": "local_files",
                "sources": [h.source_path for h in local_hits],
                "pipeline": trace,
                "translated": True,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
            await self._cache_set(cache_key, json.dumps({"answer": answer, "metadata": metadata}, ensure_ascii=False))
            return SearchResult(answer=answer, metadata=metadata)

        logger.info("[pipeline] etapa=4 zim")
        # 4) ZIM
        zim_hits = self.zim.search(query_pt, limit_per_file=2)
        trace.append({"stage": "zim", "hit": bool(zim_hits), "count": len(zim_hits)})
        if zim_hits:
            context = "\n\n".join(
                f"{h.title}: {h.snippet}\n(origem: {h.source_file})" for h in zim_hits[:6]
            )
            answer = await self._synthesize(query_pt, context, source="zim")
            metadata = {
                "source": "zim",
                "sources": [h.source_file for h in zim_hits[:6]],
                "pipeline": trace,
                "translated": True,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
            await self._cache_set(cache_key, json.dumps({"answer": answer, "metadata": metadata}, ensure_ascii=False))
            return SearchResult(answer=answer, metadata=metadata)

        if allow_internet:
            logger.info("[pipeline] etapa=5 internet (último recurso)")
            # 5) Internet (último recurso)
            web_hits = await self.web.search(query_pt)
            trace.append({"stage": "internet", "hit": bool(web_hits), "count": len(web_hits), "last_resort": True})
            if web_hits:
                context = "\n\n".join(f"{h.title}: {h.snippet}\nURL: {h.url}" for h in web_hits[:5])
                answer = await self._synthesize(query_pt, context, source="internet")
                metadata = {
                    "source": "internet",
                    "sources": [h.url for h in web_hits[:5]],
                    "pipeline": trace,
                    "translated": True,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "internet_used": True,
                }
                await self._cache_set(cache_key, json.dumps({"answer": answer, "metadata": metadata}, ensure_ascii=False))
                return SearchResult(answer=answer, metadata=metadata)
        else:
            trace.append({"stage": "internet", "skipped": True, "reason": "disabled_by_cluster_policy"})

        fallback = "Não encontrei evidências suficientes nas etapas locais da busca distribuída."
        metadata = {
            "source": "none",
            "sources": [],
            "pipeline": trace,
            "translated": True,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
        await self._cache_set(cache_key, json.dumps({"answer": fallback, "metadata": metadata}, ensure_ascii=False))
        return SearchResult(answer=fallback, metadata=metadata)
