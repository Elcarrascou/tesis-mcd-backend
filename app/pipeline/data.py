"""Carga de históricos para el universo de símbolos."""

from __future__ import annotations

import pandas as pd

from app.data.yahoo import get_history


def load_histories(symbols: list[str], period: str = "5y") -> dict[str, pd.DataFrame]:
    """Descarga histórico de cada símbolo. Omite los que fallen."""
    out: dict[str, pd.DataFrame] = {}
    for s in symbols:
        try:
            out[s] = get_history(s, period=period)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {s}: {e}")
    return out
