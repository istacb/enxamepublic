from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WebSearchHit:
    title: str
    snippet: str
    url: str


class WebSearchClient:
    """Cliente web usado apenas como último recurso da busca."""

    async def search(self, query: str) -> list[WebSearchHit]:
        q = (query or "").strip()
        if not q:
            return []
        url = "https://api.duckduckgo.com/"
        params = {"q": q, "format": "json", "no_redirect": 1, "no_html": 1}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Falha na busca web: %s", exc)
            return []

        hits: list[WebSearchHit] = []
        abstract = str(data.get("AbstractText", "")).strip()
        abstract_url = str(data.get("AbstractURL", "")).strip()
        heading = str(data.get("Heading", "Resultado web")).strip() or "Resultado web"
        if abstract:
            hits.append(WebSearchHit(title=heading, snippet=abstract, url=abstract_url))

        for item in data.get("RelatedTopics", [])[:5]:
            if isinstance(item, dict) and item.get("Text"):
                hits.append(
                    WebSearchHit(
                        title="DuckDuckGo",
                        snippet=str(item.get("Text", "")).strip(),
                        url=str(item.get("FirstURL", "")).strip(),
                    )
                )
        return hits
