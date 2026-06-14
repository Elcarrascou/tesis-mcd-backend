"""Tests de las métricas de evaluación (sin red ni modelos)."""

from __future__ import annotations

import numpy as np

from app.ml import metrics as M


def test_rmse_mae_perfect():
    y = [1.0, 2.0, 3.0]
    assert M.rmse(y, y) == 0.0
    assert M.mae(y, y) == 0.0


def test_rmse_known_value():
    # errores 1 y -1 -> RMSE=1, MAE=1
    assert M.rmse([0.0, 0.0], [1.0, -1.0]) == 1.0
    assert M.mae([0.0, 0.0], [1.0, -1.0]) == 1.0


def test_mape_ignores_zero_true():
    assert M.mape([0.0, 100.0], [50.0, 110.0]) == 10.0  # solo cuenta el 100->110


def test_directional_accuracy():
    base = [10.0, 10.0, 10.0, 10.0]
    true = [11.0, 9.0, 12.0, 8.0]  # sube, baja, sube, baja
    pred = [12.0, 9.5, 9.0, 7.0]  # sube, baja, BAJA(mal), baja -> 3/4
    assert M.directional_accuracy(base, true, pred) == 75.0


def test_accuracy_and_f1():
    yt = ["buy", "sell", "hold", "buy"]
    yp = ["buy", "sell", "hold", "sell"]
    assert M.accuracy(yt, yp) == 75.0
    assert 0.0 <= M.f1_macro(yt, yp) <= 100.0


def test_cumulative_return():
    # +10% luego +10% -> 21%
    assert abs(M.cumulative_return([0.1, 0.1]) - 21.0) < 1e-9
    assert M.cumulative_return([]) == 0.0


def test_max_drawdown():
    # sube 10%, baja 50% -> caída desde pico 1.1 a 0.55 = -50%
    dd = M.max_drawdown([0.1, -0.5])
    assert abs(dd - (-50.0)) < 1e-9
    assert M.max_drawdown([0.1, 0.1]) == 0.0


def test_sharpe_zero_variance():
    assert M.sharpe_ratio([0.01, 0.01, 0.01]) == 0.0
    assert M.sharpe_ratio([0.01]) == 0.0


def test_sharpe_positive():
    rng = np.random.default_rng(0)
    rets = rng.normal(0.001, 0.01, 300)
    assert M.sharpe_ratio(rets) > 0
