"""Agente IA "OpenClaw" (Fase D).

Consolida las 4 predicciones ML en una decisión unificada y explicable por activo,
y (opcional) enriquece el razonamiento con un motor LLM (Ollama local / Claude /
GPT). La ejecución de órdenes es un stub: registra la orden intencionada SIN tocar
ningún broker (Alpaca queda para el final).
"""

from __future__ import annotations

from app.agent.consolidate import Consolidation, consolidate

__all__ = ["Consolidation", "consolidate"]
