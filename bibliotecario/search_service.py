from __future__ import annotations

import json
import os
import time
import hashlib
from dataclasses import dataclass
from typing import Any

from core.exp.secure_logger import log_safe_query, log_safe_user_action, setup_secure_logger
from core.ollama.client import OllamaClient, OllamaGenerateRequest

from .embeddings import EmbeddingService
from .indexer import IndexedChunk, LocalDocumentIndexer
from .lancedb_store import LanceDBStore
from .translator import PTBRTranslator
from .web_client import WebSearchClient
from .zim_reader import ZimSearchClient

# Configurar logger seguro para o Bibliotecário
logger = setup_secure_logger(
    name='bibliotecario.search_service',
    level=os.getenv('LOG_LEVEL', 'INFO'),
    log_file=os.getenv('BIB_LOG_FILE', '/var/log/enxame/bibliotecario.log'),
    console_output=True,
)


@dataclass(slots=True)
class SearchResult:
    answer: str
    metadata: dict[str, Any]


class SearchPipelineService:
    def __init__(self) -> None:
        zim_dir = os.getenv('BIB_ZIM_DIR', '/data/zim')
        ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        self.model = os.getenv('BIB_MODEL', 'gemma2:9b')

        self.translator = PTBRTranslator(enabled=os.getenv('TRANSLATION_ENABLED', '1') == '1')
        self.embeddings = EmbeddingService()
        # Indexa diretórios do usuário (Documents, Desktop, enxame, BIB_DOCS_DIR), ignorando arquivos do sistema.
        self.indexer = LocalDocumentIndexer(embeddings=self.embeddings)
        self.lancedb = LanceDBStore(embeddings=self.embeddings)
        self.zim = ZimSearchClient(zim_dir=zim_dir)
        self.web = WebSearchClient()
        self.ollama = OllamaClient(ollama_url)

        self._cache = None
        self._memory_cache: dict[str, str] = {}
        self._cache_ttl = int(os.getenv('REDIS_CACHE_TTL_SECONDS', '3600'))

    async def initialize(self) -> None:
        await self._init_cache()
        chunks = self.indexer.rebuild()
        await self.lancedb.upsert_chunks(chunks)

    async def _init_cache(self) -> None:
        redis_url = os.getenv('REDIS_URL', 'redis://redis-bibliotecario:6379/0')
        try:
            from redis.asyncio import from_url  # type: ignore

            self._cache = from_url(redis_url, decode_responses=True)
            await self._cache.ping()
            logger.info('Redis conectado em %s', redis_url)
        except Exception as exc:  # pragma: no cover - depende de runtime
            logger.warning('Redis indisponível, cache em memória: %s', exc)
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
            'Você é o Bibliotecário do ENXAME. Responda em português brasileiro técnico e objetivo. '
            'Se o contexto não for suficiente, diga explicitamente as limitações.\n\n'
            f'Pergunta: {query}\n'
            f'Fonte primária: {source}\n\n'
            f'Contexto:\n{context}'
        )
        response = await self.ollama.generate(
            OllamaGenerateRequest(model=self.model, prompt=prompt, temperature=0.2, num_ctx=8192)
        )
        answer = self.translator.to_pt_br(response)
        
        # Salva no Cofre Semântico (LanceDB) para agilizar futuras queries similares
        try:
            import json
            await self.lancedb.index_document(
                text=query, 
                metadata={
                    "answer": answer, 
                    "source_type": "synthesized", 
                    "original_source": source,
                    "timestamp": time.time()
                },
                # Usamos o hash da query como ID para evitar duplicatas exatas
                chunk_id=f"cache_{hashlib.sha256(query.encode()).hexdigest()[:16]}"
            )
        except Exception as exc:
            logger.debug('Falha ao salvar resposta no cofre semântico: %s', exc)
            
        return answer

    async def generate_file_summary(self, file_path: str, text: str) -> str:
        """Gera um resumo conciso de um arquivo para facilitar a busca."""
        prompt = (
            "Você é um assistente de organização de arquivos. Analise o conteúdo do arquivo abaixo "
            "e escreva UMA ÚNICA FRASE (máximo 20 palavras) que resuma do que se trata o documento. "
            "Seja objetivo e técnico.\n\n"
            f"Arquivo: {file_path}\n"
            f"Conteúdo:\n{text[:4000]}" # Limite para evitar estouro de contexto
        )
        response = await self.ollama.generate(
            OllamaGenerateRequest(model=self.model, prompt=prompt, temperature=0.1, num_ctx=4096)
        )
        return self.translator.to_pt_br(response).strip()

    async def background_rag_summarizer(self) -> None:
        """Rotina de ociosidade: localiza arquivos indexados e gera resumos via RAG."""
        logger.info("[RAG-Worker] Iniciando rotina de resumo em ociosidade...")
        while True:
            try:
                # 1. Localiza arquivos que precisam de resumo
                files = self.indexer.get_files_for_summarization()
                
                for file_path in files:
                    # Verifica se o arquivo já tem resumo no LanceDB (simplificado: busca por path)
                    # Para otimizar, poderíamos ter um set de 'resumidos' em memória.
                    
                    # Extrai texto para resumir
                    text, _ = self.indexer._extract_text(file_path)
                    if not text:
                        continue
                        
                    # Gera o resumo usando o LLM
                    summary = await self.generate_file_summary(str(file_path), text)
                    logger.info(f"[RAG-Worker] Resumido: {file_path.name} -> {summary}")
                    
                    # Atualiza a entrada no LanceDB adicionando o resumo aos metadados de todos os chunks desse arquivo
                    # Como o LanceDB é append-only em algumas versões, faremos o upsert dos chunks com o novo resumo
                    chunks = self.indexer.rebuild() # Recarrega chunks atuais
                    file_chunks = [c for c in chunks if c.source_path == str(file_path)]
                    
                    for chunk in file_chunks:
                        if chunk.metadata is None: chunk.metadata = {}
                        chunk.metadata['rag_summary'] = summary
                    
                    await self.lancedb.upsert_chunks(file_chunks)
                    
                    # Pausa curta para não travar a CPU/Ollama
                    await asyncio.sleep(2)
                
                logger.info("[RAG-Worker] Ciclo de resumização concluído. Dormindo...")
                await asyncio.sleep(3600) # Roda a cada hora
                
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("[RAG-Worker] Erro na rotina de RAG: %s", exc)
                await asyncio.sleep(60)


    async def reindex_callback(self, chunks: list[IndexedChunk]) -> None:
        await self.lancedb.upsert_chunks(chunks)

    async def auto_reindex_loop(self) -> None:
        await self.indexer.auto_reindex_loop(self.reindex_callback)

    async def search(self, query: str, allow_internet: bool = True) -> SearchResult:
        """
        Pipeline de busca com logging seguro, controle de acesso à internet e Cache Semântico (Cofre).
        """
        started = time.perf_counter()

        # Log seguro da query
        log_safe_query(logger, query, context='search_start')
        log_safe_user_action(logger, action='search_query', details={'allow_internet': allow_internet})

        query_pt = self.translator.to_pt_br(query)
        trace: list[dict[str, Any]] = []

        # 0) Cache Semântico (Cofre de Respostas)
        # Busca respostas já sintetizadas para perguntas similares
        logger.info('[pipeline] etapa=0 semantic_cache')
        semantic_hits = await self.lancedb.search_similar(query_pt, top_k=1)
        # Threshold rigoroso para evitar respostas imprecisas (ex: 0.97)
        if semantic_hits and semantic_hits[0].score >= 0.97:
            try:
                import json
                payload = json.loads(semantic_hits[0].metadata)
                payload.setdefault('metadata', {}).setdefault('pipeline', trace)
                payload['metadata']['latency_ms'] = int((time.perf_counter() - started) * 1000)
                payload['metadata']['source'] = 'semantic_cache'
                logger.info('[pipeline] semantic_cache_hit=true latency_ms=%d', payload['metadata']['latency_ms'])
                return SearchResult(answer=str(payload.get('answer', '')), metadata=payload.get('metadata', {}))
            except Exception:
                logger.debug('Falha ao decodificar hit do cache semântico')

        logger.info('[pipeline] etapa=1 redis_cache')

        # 1) Cache Redis
        cache_key = f'bibliotecario:query:{hashlib.sha256(query_pt.strip().lower().encode()).hexdigest()[:16]}'
        cached = await self._cache_get(cache_key)
        trace.append({'stage': 'redis_cache', 'hit': bool(cached)})
        if cached:
            payload = json.loads(cached)
            payload.setdefault('metadata', {}).setdefault('pipeline', trace)
            payload['metadata']['latency_ms'] = int((time.perf_counter() - started) * 1000)
            logger.info('[pipeline] cache_hit=true latency_ms=%d', payload['metadata']['latency_ms'])
            return SearchResult(answer=str(payload.get('answer', '')), metadata=payload.get('metadata', {}))

        logger.info('[pipeline] etapa=2 lancedb')
        # 2) LanceDB (busca vetorial embedded)
        lancedb_hits = await self.lancedb.search_similar(query_pt, top_k=4)
        trace.append({'stage': 'lancedb', 'hit': bool(lancedb_hits), 'count': len(lancedb_hits)})
        if lancedb_hits:
            context = '\n\n'.join(f'[score={h.score:.3f}] {h.text}\n(origem: {h.source_path})' for h in lancedb_hits)
            answer = await self._synthesize(query_pt, context, source='lancedb')
            metadata = {
                'source': 'lancedb',
                'sources': [h.source_path for h in lancedb_hits],
                'pipeline': trace,
                'translated': True,
                'latency_ms': int((time.perf_counter() - started) * 1000),
            }
            await self._cache_set(cache_key, json.dumps({'answer': answer, 'metadata': metadata}, ensure_ascii=False))
            logger.info('[pipeline] lancedb_success=true latency_ms=%d', metadata['latency_ms'])
            return SearchResult(answer=answer, metadata=metadata)

        logger.info('[pipeline] etapa=3 local_files')
        # 3) Arquivos locais
        local_hits = await self._local_file_search(query_pt, limit=4)
        trace.append({'stage': 'local_files', 'hit': bool(local_hits), 'count': len(local_hits)})
        if local_hits:
            context = '\n\n'.join(f'{c.text}\n(origem: {c.source_path})' for c in local_hits)
            answer = await self._synthesize(query_pt, context, source='arquivos_locais')
            metadata = {
                'source': 'local_files',
                'sources': [h.source_path for h in local_hits],
                'pipeline': trace,
                'translated': True,
                'latency_ms': int((time.perf_counter() - started) * 1000),
            }
            await self._cache_set(cache_key, json.dumps({'answer': answer, 'metadata': metadata}, ensure_ascii=False))
            logger.info('[pipeline] local_files_success=true latency_ms=%d', metadata['latency_ms'])
            return SearchResult(answer=answer, metadata=metadata)

        logger.info('[pipeline] etapa=4 zim')
        # 4) ZIM
        zim_hits = self.zim.search(query_pt, limit_per_file=2)
        trace.append({'stage': 'zim', 'hit': bool(zim_hits), 'count': len(zim_hits)})
        if zim_hits:
            context = '\n\n'.join(f'{h.title}: {h.snippet}\n(origem: {h.source_file})' for h in zim_hits[:6])
            answer = await self._synthesize(query_pt, context, source='zim')
            metadata = {
                'source': 'zim',
                'sources': [h.source_file for h in zim_hits[:6]],
                'pipeline': trace,
                'translated': True,
                'latency_ms': int((time.perf_counter() - started) * 1000),
            }
            await self._cache_set(cache_key, json.dumps({'answer': answer, 'metadata': metadata}, ensure_ascii=False))
            logger.info('[pipeline] zim_success=true latency_ms=%d', metadata['latency_ms'])
            return SearchResult(answer=answer, metadata=metadata)

        if allow_internet:
            logger.warning('[pipeline] etapa=5 internet (último recurso) - permitido apenas para Bibliotecário/Juiz')
            # 5) Internet (último recurso) - apenas Bibliotecário e Juiz têm permissão
            # Notifica o usuário que a pesquisa na internet será realizada
            logger.info('[pipeline] Notificando usuário: Iniciando pesquisa na internet...')
            web_hits = await self.web.search(query_pt)
            trace.append({'stage': 'internet', 'hit': bool(web_hits), 'count': len(web_hits), 'last_resort': True})
            if web_hits:
                context = '\n\n'.join(f'{h.title}: {h.snippet}\nURL: {h.url}' for h in web_hits[:5])
                answer = await self._synthesize(query_pt, context, source='internet')
                metadata = {
                    'source': 'internet',
                    'sources': [h.url for h in web_hits[:5]],
                    'pipeline': trace,
                    'translated': True,
                    'latency_ms': int((time.perf_counter() - started) * 1000),
                    'internet_used': True,
                    'user_notification': 'Pesquisa na internet realizada para completar a resposta'
                }
                await self._cache_set(
                    cache_key, json.dumps({'answer': answer, 'metadata': metadata}, ensure_ascii=False)
                )
                logger.info('[pipeline] internet_success=true latency_ms=%d', metadata['latency_ms'])
                return SearchResult(answer=answer, metadata=metadata)

        else:
            trace.append({'stage': 'internet', 'skipped': True, 'reason': 'disabled_by_cluster_policy'})
            logger.debug('[pipeline] internet bloqueado por política do cluster')

        fallback = 'Não encontrei evidências suficientes nas etapas locais da busca distribuída.'
        metadata = {
            'source': 'none',
            'sources': [],
            'pipeline': trace,
            'translated': True,
            'latency_ms': int((time.perf_counter() - started) * 1000),
        }
        await self._cache_set(cache_key, json.dumps({'answer': fallback, 'metadata': metadata}, ensure_ascii=False))
        logger.info('[pipeline] fallback_result latency_ms=%d', metadata['latency_ms'])
        return SearchResult(answer=fallback, metadata=metadata)
