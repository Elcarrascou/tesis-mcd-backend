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

# Peso objetivo máximo por activo (a plena confianza). El tamaño escala con la
# confianza de la decisión, así una señal fuerte mueve más capital que una débil.
TARGET_WEIGHT_PCT = 15.0


def size_order(
    c: Consolidation,
    side: str,
    *,
    price: float | None,
    portfolio_value: float | None,
    current_qty: float = 0.0,
) -> float | None:
    """Cantidad de acciones de la orden (Fase H3). None si falta contexto.

    - buy: lleva la posición hacia el peso objetivo escalado por confianza.
    - sell/reduce: recorta la posición actual en proporción a la confianza.
    Devuelve entero de acciones (>=0); None si no hay precio/valor de portafolio.
    """
    if not price or not portfolio_value or price <= 0:
        return None
    conf = max(0.0, min(1.0, c.confidence / 100.0))
    if side == "buy":
        target_notional = conf * (TARGET_WEIGHT_PCT / 100.0) * portfolio_value
        target_qty = target_notional / price
        return float(max(0, round(target_qty - current_qty)))
    # sell / reduce: recorta la posición existente según confianza.
    return float(max(0, min(current_qty, round(current_qty * conf))))


def intended_order(
    c: Consolidation,
    *,
    price: float | None = None,
    portfolio_value: float | None = None,
    current_qty: float = 0.0,
) -> dict | None:
    """Construye la orden intencionada (sin enviarla). None si no hay que operar."""
    side = _ACTION_SIDE.get(c.action)
    if side is None:
        return None
    qty = size_order(
        c, side, price=price, portfolio_value=portfolio_value, current_qty=current_qty
    )
    return {
        "symbol": c.symbol,
        "side": side,
        "quantity": qty,  # None si no se pasó precio/valor de portafolio
        "confidence": round(c.confidence, 2),
        "status": "intended",  # nunca 'filled': no se envía a broker
        "broker": None,
        "note": "Orden NO enviada — ejecución real (Alpaca) pendiente para Fase final.",
    }
