#!/usr/bin/env python3
"""
fast_router.py — Roteador Zero-LLM (<2ms em CPU) e Envelope de Proveniência
===========================================================================
Substitui a classificação lenta via LLM (`_analyze_intent`) por heurísticas
ponderadas instantâneas em CPU, mantendo o caminho invisível ao usuário e
registrando em cada resposta o `ProvenanceStamp` completo (qual máquina,
papel, perfil, modelo, tier de conhecimento e tempo real respondeu).
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

IMAGE_INTENT_REGEX = re.compile(
    r"(?i)^\s*(?:/img\b|/imagem\b|gere\s+(?:uma\s+)?imagem|crie\s+(?:uma\s+)?imagem|"
    r"desenhe\b|ilustre\b|renderize\b|gerar\s+imagem|fa[cç]a\s+(?:uma\s+|um\s+)?(?:imagem|ilustra[cç][aã]o|cartaz|poster|logo))"
)

DOMAIN_KEYWORDS: dict[str, tuple[str, set[str]]] = {
    "coder": (
        "technical",
        {
            "python", "javascript", "typescript", "código", "codigo", "bug", "erro",
            "função", "funcao", "classe", "sql", "api", "git", "bash", "linux",
            "script", "algoritmo", "refatore", "implemente", "teste", "pytest",
            "json", "html", "css", "regex", "compilar", "variável", "loop",
        },
    ),
    "architect": (
        "technical",
        {
            "arquitetura", "escalabilidade", "microserviço", "microkernel", "cluster",
            "orquestração", "orquestracao", "failover", "latência", "latencia", "rede",
            "topologia", "protocolo", "distribuído", "distribuido", "eip", "design",
        },
    ),
    "legal": (
        "legal",
        {
            "lei", "artigo", "jurídico", "juridico", "contrato", "cláusula", "clausula",
            "tribunal", "jurisprudência", "tributário", "civil", "trabalhista", "penal",
            "lgpd", "conformidade", "direito", "advogado", "processo",
        },
    ),
    "medical": (
        "medical",
        {
            "sintoma", "exame", "diagnóstico", "diagnostico", "médico", "medico",
            "saúde", "saude", "tratamento", "medicamento", "clínico", "clinico",
            "paciente", "fisiologia", "anatomia", "hospital",
        },
    ),
    "analyst": (
        "financial",
        {
            "planilha", "dados", "métrica", "metrica", "estatística", "estatistica",
            "financeiro", "custo", "receita", "lucro", "kpi", "relatório", "relatorio",
            "percentual", "média", "media", "projeção", "projecao", "balanço",
        },
    ),
    "researcher": (
        "general",
        {
            "pesquise", "compare", "história", "historia", "artigo", "fonte", "fontes",
            "evidência", "evidencia", "bibliografia", "resumo", "explique", "estudo",
            "análise", "analise", "panorama", "documento", "manual",
        },
    ),
    "creative": (
        "creative",
        {
            "roteiro", "poema", "conto", "história", "slogan", "criativo", "campanha",
            "narrativa", "texto", "redação", "redacao", "ensaio", "ideias",
        },
    ),
}

OFFLINE_UNKNOWN_MARKERS = (
    "[[sem_dados_offline]]",
    "não tenho acesso a informações em tempo real",
    "nao tenho acesso a informacoes em tempo real",
    "não possuo informações atualizadas",
    "não sei responder com certeza sem consultar",
)


@dataclass(slots=True)
class ProvenanceStamp:
    """Identificação auditável de qual máquina, papel e modelo respondeu."""

    machine_alias: str
    node_id: str
    platform: str
    hardware_tier: str
    hardware_tier_label: str
    cluster_role: str
    agent_profile: str
    model: str
    source_tier: str  # rag_local | rag_enxame | modelo_local | internet_fallback | estudio_cpu | sistema_offline
    rag_sources: list[str] = field(default_factory=list)
    route_trace: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.85
    ttft_ms: int = 0
    total_ms: int = 0
    est_tokens_per_sec: float = 0.0
    pacing_notice: str = ""
    guardian_action: str = "ALLOW"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FastIntentRouter:
    """Classificador determinístico instantâneo (<2ms em qualquer CPU)."""

    @staticmethod
    def classify(
        message: str,
        context: dict[str, Any] | None = None,
        user_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ctx = context or {}
        forced_profile = ctx.get("forced_profile")
        text = (message or "").strip()

        # 1. Detectar pedido explícito de geração de imagem
        if ctx.get("mode") == "image" or IMAGE_INTENT_REGEX.search(text):
            clean_img_prompt = IMAGE_INTENT_REGEX.sub("", text).strip(" :,-") or text
            return {
                "task_type": "image",
                "complexity": "medium",
                "domain": "creative",
                "requires_multimodal": True,
                "requires_tools": ["image"],
                "suggested_profile": "creative",
                "image_prompt": clean_img_prompt,
                "estimated_steps": 1,
                "router_mode": "zero_llm_cpu",
            }

        if forced_profile and forced_profile not in ("auto", ""):
            return {
                "task_type": "query",
                "complexity": "medium",
                "domain": "general",
                "requires_multimodal": bool(ctx.get("attachments")),
                "requires_tools": ["search"],
                "suggested_profile": str(forced_profile),
                "estimated_steps": 1,
                "router_mode": "user_pinned",
            }

        tokens = set(re.findall(r"[a-zA-ZÀ-ÿ0-9_]{2,}", text.lower()))
        has_code_fence = "```" in text or "def " in text or "function " in text or "SELECT " in text

        best_profile = "generalist"
        best_domain = "general"
        best_score = 0.0
        affinity = (user_profile or {}).get("profile_affinity", {})

        for prof_id, (domain, kw_set) in DOMAIN_KEYWORDS.items():
            hits = len(tokens & kw_set)
            score = float(hits)
            if prof_id == "coder" and has_code_fence:
                score += 3.0
            if hits > 0 and prof_id in affinity:
                score += max(-0.4, min(0.8, float(affinity[prof_id]) * 0.2))
            if score > best_score:
                best_score = score
                best_profile = prof_id
                best_domain = domain

        word_count = len(text.split())
        if word_count <= 14 and not has_code_fence:
            complexity = "simple"
        elif word_count >= 75 or has_code_fence:
            complexity = "complex"
        else:
            complexity = "medium"

        task_type_map = {
            "coder": "code",
            "architect": "planning",
            "researcher": "research",
            "analyst": "analysis",
            "creative": "creative",
        }

        return {
            "task_type": task_type_map.get(best_profile, "query"),
            "complexity": complexity,
            "domain": best_domain,
            "requires_multimodal": bool(ctx.get("attachments")),
            "requires_tools": ["code"] if best_profile == "coder" else ["search"],
            "suggested_profile": best_profile,
            "estimated_steps": 1,
            "router_mode": "zero_llm_cpu",
        }

    @staticmethod
    def model_signaled_unknown(answer_text: str) -> bool:
        """Verifica se o modelo local admitiu não ter a informação offline."""
        if not answer_text or not answer_text.strip():
            return True
        low = answer_text.lower()
        return any(marker in low for marker in OFFLINE_UNKNOWN_MARKERS)
