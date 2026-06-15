"""Cliente Supabase server-side.

Usa la clave service_role: salta RLS y permite ESCRIBIR en las tablas
operacionales (ml_predictions, ai_decisions…). Esa clave es secreta y vive solo
en el entorno del backend (config.py) — nunca en el navegador ni en git.

El free tier de Supabase es suficiente para todo el desarrollo.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_client() -> Client:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        raise RuntimeError(
            "Faltan SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY en el entorno (.env)"
        )
    return create_client(s.supabase_url, s.supabase_service_role_key)


def insert_predictions(rows: list[dict]) -> None:
    """Inserta filas en ml_predictions."""
    if not rows:
        return
    get_client().table("ml_predictions").insert(rows).execute()


def insert_decisions(rows: list[dict]) -> None:
    """Inserta filas en ai_decisions."""
    if not rows:
        return
    get_client().table("ai_decisions").insert(rows).execute()


def insert_metrics(rows: list[dict]) -> None:
    """Inserta filas de evaluación/backtest en model_metrics."""
    if not rows:
        return
    get_client().table("model_metrics").insert(rows).execute()


def get_portfolio() -> list[dict]:
    """Lee las posiciones del portafolio (cantidad y costo promedio)."""
    res = (
        get_client()
        .table("portfolio")
        .select("symbol,quantity,avg_price")
        .execute()
    )
    return res.data or []


def upsert_portfolio(rows: list[dict]) -> None:
    """Actualiza la valuación de las posiciones (upsert por symbol único)."""
    if not rows:
        return
    get_client().table("portfolio").upsert(rows, on_conflict="symbol").execute()


def get_last_performance() -> dict | None:
    """Última fila de performance (para el retorno diario encadenado)."""
    res = (
        get_client()
        .table("performance")
        .select("snapshot_date,total_value")
        .order("snapshot_date", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def upsert_performance(row: dict) -> None:
    """Inserta/actualiza la fila diaria de performance (upsert por snapshot_date)."""
    get_client().table("performance").upsert(row, on_conflict="snapshot_date").execute()
