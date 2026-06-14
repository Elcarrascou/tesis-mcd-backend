"""Métricas de evaluación para el backtesting (Fase C).

Funciones puras (numpy / scikit-learn) usadas por `app/pipeline/backtest.py`.
Separadas en su propio módulo para poder testearlas sin red ni modelos.

- Regresión (LSTM precio, Prophet tendencia): RMSE, MAE, precisión direccional.
- Clasificación (XGBoost señal, Random Forest riesgo): accuracy, F1 macro.
- Estrategia/portafolio: retorno acumulado, Sharpe, máximo drawdown.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from sklearn.metrics import accuracy_score, f1_score

TRADING_DAYS = 252


def rmse(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Raíz del error cuadrático medio."""
    a, p = np.asarray(y_true, float), np.asarray(y_pred, float)
    return float(np.sqrt(np.mean((a - p) ** 2)))


def mae(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Error absoluto medio."""
    a, p = np.asarray(y_true, float), np.asarray(y_pred, float)
    return float(np.mean(np.abs(a - p)))


def mape(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Error porcentual absoluto medio (%). Ignora valores reales nulos."""
    a, p = np.asarray(y_true, float), np.asarray(y_pred, float)
    mask = a != 0
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs((a[mask] - p[mask]) / a[mask])) * 100)


def directional_accuracy(
    base: Sequence[float], y_true: Sequence[float], y_pred: Sequence[float]
) -> float:
    """% de veces que el modelo acierta la dirección (sube/baja) vs `base`.

    `base` es el precio actual; `y_true`/`y_pred` los precios futuros real y
    predicho. Mide si el signo del movimiento predicho coincide con el real.
    """
    b = np.asarray(base, float)
    a = np.asarray(y_true, float)
    p = np.asarray(y_pred, float)
    real_dir = np.sign(a - b)
    pred_dir = np.sign(p - b)
    mask = real_dir != 0  # descarta días sin movimiento real
    if not mask.any():
        return float("nan")
    return float(np.mean(real_dir[mask] == pred_dir[mask]) * 100)


def accuracy(y_true: Sequence[str], y_pred: Sequence[str]) -> float:
    """Exactitud de clasificación (%)."""
    if len(y_true) == 0:
        return float("nan")
    return float(accuracy_score(y_true, y_pred) * 100)


def f1_macro(y_true: Sequence[str], y_pred: Sequence[str]) -> float:
    """F1 macro (%). Promedia por clase sin ponderar por soporte."""
    if len(y_true) == 0:
        return float("nan")
    return float(f1_score(y_true, y_pred, average="macro", zero_division=0) * 100)


def cumulative_return(returns: Sequence[float]) -> float:
    """Retorno acumulado (%) a partir de retornos simples por período."""
    r = np.asarray(returns, float)
    if r.size == 0:
        return 0.0
    return float((np.prod(1 + r) - 1) * 100)


def equity_curve(returns: Sequence[float], start: float = 1.0) -> np.ndarray:
    """Curva de capital (producto acumulado de 1+retorno)."""
    r = np.asarray(returns, float)
    return start * np.cumprod(1 + r)


def sharpe_ratio(returns: Sequence[float], periods_per_year: int = TRADING_DAYS) -> float:
    """Sharpe anualizado (rf=0) a partir de retornos por período."""
    r = np.asarray(returns, float)
    if r.size < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1) * np.sqrt(periods_per_year))


def max_drawdown(returns: Sequence[float]) -> float:
    """Máxima caída desde un pico de la curva de capital (%). Valor <= 0."""
    r = np.asarray(returns, float)
    if r.size == 0:
        return 0.0
    curve = np.cumprod(1 + r)
    peak = np.maximum.accumulate(curve)
    return float((curve / peak - 1).min() * 100)
