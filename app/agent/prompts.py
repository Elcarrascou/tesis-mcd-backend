"""Prompts del agente para explicar las decisiones consolidadas.

El LLM NO decide: solo redacta una explicación en español a partir del consolidado
determinista (`consolidate.py`). Así el razonamiento es claro para un inversor sin
inventar la recomendación.
"""

from __future__ import annotations

import json

from app.agent.consolidate import Consolidation

SYSTEM_PROMPT = (
    "Eres OpenClaw, un analista de inversiones que explica decisiones de un "
    "portafolio gestionado por modelos de machine learning. Recibes la decisión "
    "ya tomada (acción, confianza, score y salidas de 4 modelos) y la explicas en "
    "español, claro y conciso (2-3 frases). NO cambies la acción ni inventes datos: "
    "solo justifica con lo entregado. No des asesoría financiera personalizada ni "
    "promesas de rentabilidad."
)


def build_user_prompt(c: Consolidation) -> str:
    """Prompt de usuario con el consolidado serializado."""
    payload = {
        "symbol": c.symbol,
        "action": c.action,
        "confidence_pct": round(c.confidence, 1),
        "score": c.score,
        "risk": c.risk,
        "models": c.details,
    }
    return (
        "Explica esta decisión de inversión en 2-3 frases, en español:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
