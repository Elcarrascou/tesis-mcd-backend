"""Ejecución de órdenes — STUB (Fase D).

Registra la *orden intencionada* que se derivaría de una decisión, pero NO la
envía a ningún broker. La integración real con Alpaca queda explícitamente para
el final del proyecto (ver HANDOFF). Esto permite cerrar el ciclo
predicción→decisión→orden sin riesgo ni dependencias de pago.
"""

from __future__ import annotations

from app.agent.consolidate import Consolidation

# Acción consolidada → lado de la orden intencionada.
_ACTION_SIDE = {"buy": "buy", "sell": "sell", "hold": None, "rebalance": "reduce"}


def intended_order(c: Consolidation) -> dict | None:
    """Construye la orden intencionada (sin enviarla). None si no hay que operar."""
    side = _ACTION_SIDE.get(c.action)
    if side is None:
        return None
    return {
        "symbol": c.symbol,
        "side": side,
        "confidence": round(c.confidence, 2),
        "status": "intended",  # nunca 'filled': no se envía a broker
        "broker": None,
        "note": "Orden NO enviada — ejecución real (Alpaca) pendiente para Fase final.",
    }
