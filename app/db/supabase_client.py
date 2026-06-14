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
