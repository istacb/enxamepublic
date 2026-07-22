"""
Enxame OS - Orchestration Layer for Open WebUI.
This module replaces direct user-Ollama communication with a structured agent pipeline.
"""
from .main import router

__all__ = ["router"]