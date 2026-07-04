from __future__ import annotations

import hashlib
import os
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class LocalSearchResult:
    found: bool
    source: str
    snippets: list[str]
    sources: list[str]

    def as_dict(self) -> dict:
        return {
            "found": self.found,
            "source": self.source,
            "snippets": self.snippets,
            "sources": self.sources,
        }


class LocalSearchEngine:
    """Busca local padrão para todos os nós (cache -> arquivos -> zim local)."""

    def __init__(self, docs_dir: str, zim_dir: str, cache_size: int = 256) -> None:
        self.docs_dir = Path(docs_dir)
        self.zim_dir = Path(zim_dir)
        self.cache_size = max(16, cache_size)
        self._cache: OrderedDict[str, LocalSearchResult] = OrderedDict()

    def search(self, query: str, limit: int = 5) -> LocalSearchResult:
        key = self._cache_key(query)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached

        file_hit = self._search_local_files(query, limit=limit)
        if file_hit.found:
            self._cache_set(key, file_hit)
            return file_hit

        zim_hit = self._search_local_zim(query, limit=limit)
        self._cache_set(key, zim_hit)
        return zim_hit

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()

    def _cache_set(self, key: str, value: LocalSearchResult) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)

    def _search_local_files(self, query: str, limit: int = 5) -> LocalSearchResult:
        terms = [t for t in query.lower().split() if t]
        snippets: list[str] = []
        sources: list[str] = []

        if not self.docs_dir.exists():
            return LocalSearchResult(False, "local_files", [], [])

        for path in self.docs_dir.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {
                ".txt",
                ".md",
                ".json",
                ".yaml",
                ".yml",
                ".py",
                ".js",
                ".ts",
                ".log",
                ".csv",
            }:
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                low = content.lower()
                if not terms or all(term in low for term in terms[:2]) or any(term in low for term in terms):
                    snippet = content[:300].strip().replace("\n", " ")
                    if snippet:
                        snippets.append(snippet)
                        sources.append(str(path))
            except Exception:
                continue

            if len(snippets) >= limit:
                break

        return LocalSearchResult(bool(snippets), "local_files", snippets, sources)

    def _search_local_zim(self, query: str, limit: int = 5) -> LocalSearchResult:
        if not self.zim_dir.exists():
            return LocalSearchResult(False, "zim", [], [])

        query_low = query.lower()
        snippets: list[str] = []
        sources: list[str] = []

        # Estratégia compatível sem dependências nativas obrigatórias:
        # busca por nome de arquivo e fragmentos textuais no início do arquivo.
        for path in self.zim_dir.rglob("*.zim"):
            name = path.name.lower()
            matched = query_low in name or any(tok in name for tok in query_low.split())
            preview = ""
            if not matched:
                try:
                    with path.open("rb") as f:
                        head = f.read(1024 * 64)
                    preview = head.decode("utf-8", errors="ignore")
                    matched = query_low in preview.lower()
                except Exception:
                    matched = False

            if matched:
                snippets.append((preview[:240] if preview else f"Arquivo ZIM: {path.name}").strip())
                sources.append(str(path))

            if len(snippets) >= limit:
                break

        return LocalSearchResult(bool(snippets), "zim", snippets, sources)

    def list_zim_files(self) -> list[str]:
        if not self.zim_dir.exists():
            return []
        return sorted(str(p) for p in self.zim_dir.rglob("*.zim"))

    @staticmethod
    def compute_partition_owner(path: str, node_ids: list[str]) -> str | None:
        if not node_ids:
            return None
        digest = hashlib.sha1(path.encode("utf-8")).hexdigest()
        idx = int(digest, 16) % len(node_ids)
        return sorted(node_ids)[idx]

    def distributed_plan(self, node_ids: list[str]) -> dict[str, list[str]]:
        plan: dict[str, list[str]] = {node: [] for node in sorted(node_ids)}
        for zim_file in self.list_zim_files():
            owner = self.compute_partition_owner(zim_file, node_ids)
            if owner is not None:
                plan.setdefault(owner, []).append(zim_file)
        return plan

    def apply_plan(self, node_id: str, plan: dict[str, list[str]]) -> list[str]:
        allowed = set(plan.get(node_id, []))
        if not allowed:
            return []
        kept: list[str] = []
        for path in self.zim_dir.rglob("*.zim"):
            if str(path) in allowed:
                kept.append(str(path))
        return sorted(kept)
