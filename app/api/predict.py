"""Endpoint de inferencia on-demand: GET /predict/{symbol}.

La web (StockAnalyzer del portal) llama aquí para obtener las 4 predicciones ML
reales de un símbolo, en vez de la edge function DEMO de Supabase.

Los modelos se cargan UNA sola vez por proceso (lazy singleton) para no pagar el
costo de leer artefactos en cada request. Prophet se reajusta por serie dentro de
`predict_one` (no tiene artefacto).
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException

from app.constants import UNIVERSE
from app.data.yahoo import get_history
from app.models import BaseModel, all_models

router = APIRouter(tags=["ml"])


@lru_cache
def _models() -> list[BaseModel]:
    """Modelos cargados una vez. Los que no tienen artefacto siguen igual."""
    models = all_models()
    for m in models:
        try:
            m.load()
        except FileNotFoundError:
            # Sin artefacto (p.ej. entrenar primero). El modelo igual se omite
            # limpiamente en /predict si predict_one falla.
            pass
    return models


@router.get("/predict/{symbol}")
def predict(symbol: str) -> dict:
    """Devuelve las predicciones de los 4 modelos para `symbol`.

    No escribe en Supabase (lectura on-demand para la web). El cron diario es el
    que persiste (`app.pipeline.predict --write`).
    """
    symbol = symbol.upper().strip()
    try:
        df = get_history(symbol, period="2y")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Yahoo: {e}") from e
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"Sin datos para {symbol}")

    predictions = []
    errors = {}
    for m in _models():
        try:
            predictions.append(m.predict_one(symbol, df).to_row())
        except Exception as e:  # noqa: BLE001
            errors[m.name] = str(e)

    if not predictions:
        raise HTTPException(status_code=500, detail=f"Modelos fallaron: {errors}")

    return {
        "symbol": symbol,
        "in_universe": symbol in UNIVERSE,
        "predictions": predictions,
        "errors": errors,
    }
