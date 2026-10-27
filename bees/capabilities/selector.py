"""
Seleção de modelo recomendado baseado em recursos de hardware.

Implementa BEE-0003 — Seção 9.
"""

from __future__ import annotations

from .discovery import ModelInfo


def recommend_model(
    available_models: list[ModelInfo],
    ram_gb: float,
    gpu_vram_gb: float,
    has_gpu: bool,
) -> str | None:
    """
    Recomendar melhor modelo baseado em recursos disponíveis.
    
    Diretrizes de seleção:
    - 1B-3B: Mínimo 4GB RAM
    - 4B-7B: Mínimo 8GB RAM
    - 8B-10B: Mínimo 16GB RAM (ou 8GB VRAM com GPU)
    - >10B: Não recomendar nesta fase
    
    Critérios de score:
    - RAM adequada: +10 pontos
    - RAM limitada mas aceitável (70%): +5 pontos
    - GPU com VRAM suficiente: +20 pontos
    - GPU com VRAM parcial (50%): +10 pontos
    - Modelo já carregado: +15 pontos
    - Modelo de chat: +5 pontos
    
    Args:
        available_models: Lista de modelos disponíveis.
        ram_gb: RAM total da máquina em GB.
        gpu_vram_gb: VRAM da GPU em GB (0 se sem GPU).
        has_gpu: True se GPU disponível.
    
    Returns:
        Nome do modelo recomendado ou None se nenhum adequado.
    """
    if not available_models:
        return None
    
    candidates: list[tuple[float, str, float]] = []
    
    for model in available_models:
        # Pular embeddings para geração de texto
        if model.is_embedding:
            continue
        
        # Extrair tamanho em bilhões de parâmetros
        param_str = model.parameter_size.upper()
        
        if "B" in param_str:
            try:
                billions = float(param_str.replace("B", ""))
            except ValueError:
                continue
        elif "M" in param_str:
            # Modelos muito pequenos (<1B), ignorar nesta fase
            continue
        else:
            # Tamanho desconhecido, pular
            continue
        
        # Ignorar modelos grandes (>10B) nesta fase
        if billions > 10:
            continue
        
        # Calcular score baseado em adequação ao hardware
        score = 0.0
        
        # RAM adequada?
        # Regra prática: 1.5GB RAM por bilhão de parâmetros
        min_ram = billions * 1.5
        
        if ram_gb >= min_ram:
            score += 10
        elif ram_gb >= min_ram * 0.7:
            score += 5  # RAM limitada mas aceitável
        
        # GPU ajuda muito
        if has_gpu and gpu_vram_gb > 0:
            if gpu_vram_gb >= billions:
                # Modelo cabe inteiro na VRAM
                score += 20
            elif gpu_vram_gb >= billions * 0.5:
                # Modelo parcialmente na VRAM
                score += 10
        
        # Preferir modelos já carregados (evita load time)
        if model.is_loaded:
            score += 15
        
        # Preferir modelos de chat para assistente
        if model.supports_chat:
            score += 5
        
        # Bonus por contexto maior
        if model.context_length >= 8000:
            score += 3
        elif model.context_length >= 4096:
            score += 1
        
        candidates.append((score, model.name, billions))
    
    if not candidates:
        return None
    
    # Ordenar por score (maior primeiro), depois por tamanho (menor primeiro para empate)
    # Isso favorece modelos menores quando scores são iguais (mais eficientes)
    candidates.sort(key=lambda x: (-x[0], x[2]))
    
    return candidates[0][1]


def get_model_recommendations_table() -> list[dict[str, str]]:
    """
    Retornar tabela de referência de recomendações.
    
    Returns:
        Lista de dicionários com recomendações por configuração.
    """
    return [
        {
            "ram": "4GB",
            "gpu_vram": "0GB",
            "recommended": "phi3:3.8b, gemma2:2b, qwen2:1.5b",
        },
        {
            "ram": "8GB",
            "gpu_vram": "0GB",
            "recommended": "llama3:8b, gemma2:9b, mistral:7b",
        },
        {
            "ram": "8GB",
            "gpu_vram": "4GB",
            "recommended": "llama3:8b (GPU accelerated), gemma2:9b",
        },
        {
            "ram": "16GB",
            "gpu_vram": "8GB",
            "recommended": "llama3:8b, mixtral:8x7b (quantizado), gemma2:9b",
        },
        {
            "ram": "32GB+",
            "gpu_vram": "12GB+",
            "recommended": "Modelos maiores conforme necessidade",
        },
    ]


def calculate_min_requirements(parameter_size: str) -> dict[str, float]:
    """
    Calcular requisitos mínimos para um modelo.
    
    Args:
        parameter_size: Tamanho do modelo (ex: "8B", "9B", "80M").
    
    Returns:
        Dicionário com requisitos mínimos de RAM e VRAM.
    """
    param_str = parameter_size.upper()
    
    if "B" in param_str:
        try:
            billions = float(param_str.replace("B", ""))
        except ValueError:
            return {"min_ram_gb": 0.0, "min_vram_gb": 0.0, "recommended_ram_gb": 0.0}
        
        # Requisitos
        min_ram = billions * 1.5  # Mínimo absoluto
        recommended_ram = billions * 2.0  # Recomendado para performance
        min_vram = billions  # Para rodar inteiramente na GPU
        
        return {
            "min_ram_gb": min_ram,
            "recommended_ram_gb": recommended_ram,
            "min_vram_gb": min_vram,
        }
    elif "M" in param_str:
        # Modelos pequenos (<1B)
        return {
            "min_ram_gb": 2.0,
            "recommended_ram_gb": 4.0,
            "min_vram_gb": 0.0,
        }
    else:
        return {
            "min_ram_gb": 0.0,
            "recommended_ram_gb": 0.0,
            "min_vram_gb": 0.0,
        }
