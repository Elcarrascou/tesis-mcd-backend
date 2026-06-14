"""Features técnicos: transforman precios crudos en los insumos de los modelos.

Son los mismos indicadores que el portal ya muestra en el StockAnalyzer
(RSI, SMA, volatilidad, momentum, drawdown), pero calculados de forma rigurosa
en Python — esta es la versión que defiende la tesis.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> float:
    """Relative Strength Index del último punto."""
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_series = 100 - 100 / (1 + rs)
    return float(rsi_series.iloc[-1])


def annualized_vol_pct(close: pd.Series) -> float:
    """Volatilidad anualizada (%) a partir de retornos diarios."""
    returns = close.pct_change().dropna()
    return float(returns.std() * np.sqrt(252) * 100)


def momentum_pct(close: pd.Series, window: int = 20) -> float:
    """Retorno (%) en una ventana de `window` días."""
    if len(close) <= window:
        return 0.0
    return float((close.iloc[-1] / close.iloc[-1 - window] - 1) * 100)


def max_drawdown_pct(close: pd.Series) -> float:
    """Caída máxima (%) desde un máximo previo."""
    cummax = close.cummax()
    drawdown = (close - cummax) / cummax
    return float(drawdown.min() * 100)


def compute_features(df: pd.DataFrame) -> dict:
    """Vector de features técnicos a partir de un histórico OHLCV."""
    close = df["Close"]
    return {
        "days": int(len(df)),
        "rsi14": rsi(close, 14),
        "sma20": float(close.rolling(20).mean().iloc[-1]),
        "sma50": float(close.rolling(50).mean().iloc[-1]),
        "vol_annual_pct": annualized_vol_pct(close),
        "momentum20_pct": momentum_pct(close, 20),
        "max_drawdown_pct": max_drawdown_pct(close),
    }
