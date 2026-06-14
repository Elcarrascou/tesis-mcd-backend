"""Construcción de matriz de features y etiquetas para los modelos supervisados.

Separa dos responsabilidades:
- `build_feature_matrix`: una fila de features por día (insumo de XGBoost/RF).
- `make_signal_labels` / `make_risk_labels`: etiquetas supervisadas mirando al futuro.

Los features de inferencia puntual viven en `app/data/features.py`; aquí está la
versión "por fila" usada para entrenar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Columnas de features (orden estable: lo consumen los modelos en inferencia).
FEATURE_COLS: list[str] = [
    "ret1",
    "ret5",
    "rsi14",
    "sma20_ratio",
    "sma50_ratio",
    "vol20",
    "momentum20",
    "volume_ratio",
]


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Matriz de features por día a partir de un histórico OHLCV. Sin NaN."""
    close = df["Close"]
    volume = df.get("Volume", pd.Series(1.0, index=df.index))
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    ret1 = close.pct_change()

    feats = pd.DataFrame(
        {
            "ret1": ret1,
            "ret5": close.pct_change(5),
            "rsi14": _rsi(close, 14),
            "sma20_ratio": close / sma20 - 1,
            "sma50_ratio": close / sma50 - 1,
            "vol20": ret1.rolling(20).std(),
            "momentum20": close / close.shift(20) - 1,
            "volume_ratio": volume / volume.rolling(20).mean(),
        }
    )
    return feats.replace([np.inf, -np.inf], np.nan).dropna()


def make_signal_labels(df: pd.DataFrame, horizon: int = 5, thr: float = 0.01) -> pd.Series:
    """Etiqueta de señal según retorno futuro a `horizon` días.

    buy si sube más de `thr`, sell si baja más de `thr`, si no hold.
    """
    close = df["Close"]
    fwd = close.shift(-horizon) / close - 1
    label = pd.Series("hold", index=close.index, dtype="object")
    label[fwd > thr] = "buy"
    label[fwd < -thr] = "sell"
    return label


def make_risk_labels(df: pd.DataFrame, horizon: int = 20) -> pd.Series:
    """Etiqueta de riesgo según volatilidad realizada futura (anualizada %).

    Umbrales fijos e interpretables: <20% bajo, 20–35% medio, >35% alto.
    """
    ret1 = df["Close"].pct_change()
    fwd_vol = ret1.shift(-1).rolling(horizon).std().shift(-(horizon - 1)) * np.sqrt(252) * 100
    label = pd.Series("medio", index=df.index, dtype="object")
    label[fwd_vol < 20] = "bajo"
    label[fwd_vol > 35] = "alto"
    return label[fwd_vol.notna()]
