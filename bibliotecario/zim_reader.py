from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ZimHit:
    title: str
    snippet: str
    source_file: str


class ZimSearchClient:
    """Leitura de arquivos .zim com suporte a diferentes variantes do zimply."""

    def __init__(self, zim_dir: str) -> None:
        self.zim_dir = Path(zim_dir)
        self._opened: list[tuple[str, Any]] = []
        self._ready = False

    def _iter_zim_files(self) -> list[Path]:
        if not self.zim_dir.exists():
            return []
        return sorted([p for p in self.zim_dir.rglob("*.zim") if p.is_file()])

    def _open_impl(self, path: Path):
        errors: list[str] = []
        for module_name, class_name in [
            ("zimply", "ZIMFile"),
            ("zimply.zimply", "ZIMFile"),
            ("zimply2", "ZimFile"),
        ]:
            try:
                module = __import__(module_name, fromlist=[class_name])
                cls = getattr(module, class_name)
                return cls(str(path))
            except Exception as exc:  # pragma: no cover - depende do ambiente
                errors.append(f"{module_name}.{class_name}: {exc}")
        raise RuntimeError(" ; ".join(errors))

    def _load(self) -> None:
        if self._ready:
            return
        for path in self._iter_zim_files():
            try:
                zf = self._open_impl(path)
                self._opened.append((str(path), zf))
                logger.info("ZIM carregado: %s", path)
            except Exception as exc:
                logger.warning("Falha ao abrir ZIM %s: %s", path, exc)
        self._ready = True

    def _search_in_zim(self, zf: Any, query: str, limit: int) -> list[dict[str, str]]:
        methods = ["search", "search_articles", "find", "lookup"]
        for m in methods:
            if hasattr(zf, m):
                try:
                    result = getattr(zf, m)(query)
                    if isinstance(result, list):
                        out: list[dict[str, str]] = []
                        for row in result[:limit]:
                            if isinstance(row, dict):
                                out.append(
                                    {
                                        "title": str(row.get("title", row.get("name", "Artigo ZIM"))),
                                        "snippet": str(row.get("snippet", row.get("text", ""))),
                                    }
                                )
                            else:
                                out.append({"title": str(row), "snippet": ""})
                        return out
                except Exception:
                    continue
        return []

    def search(self, query: str, limit_per_file: int = 3) -> list[ZimHit]:
        self._load()
        q = (query or "").strip()
        if not q:
            return []

        all_hits: list[ZimHit] = []
        for source_file, zf in self._opened:
            for row in self._search_in_zim(zf, q, limit_per_file):
                all_hits.append(
                    ZimHit(
                        title=row.get("title", "Artigo ZIM"),
                        snippet=row.get("snippet", ""),
                        source_file=source_file,
                    )
                )
        if not all_hits and os.getenv("ZIM_FALLBACK_SCAN", "1") == "1":
            for source_file, _ in self._opened:
                filename = Path(source_file).name.lower()
                if any(tok in filename for tok in q.lower().split()):
                    all_hits.append(ZimHit(title=Path(source_file).stem, snippet="match por nome de arquivo", source_file=source_file))
        return all_hits
