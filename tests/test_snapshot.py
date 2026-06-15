"""Tests del snapshot operacional (Fase G2).

Se prueba la función pura `build_snapshot` (sin red ni Supabase): valuación de
posiciones, caja, totales y retornos.
"""

from __future__ import annotations

from app.pipeline.snapshot import build_snapshot

# Dos posiciones simples: costo total = 10*100 + 5*200 = 2000.
_POSITIONS = [
    {"symbol": "AAA", "quantity": 10, "avg_price": 100.0},
    {"symbol": "BBB", "quantity": 5, "avg_price": 200.0},
]
_PRICES = {"AAA": 110.0, "BBB": 200.0}  # AAA +10%, BBB plano


def _build(**kw):
    return build_snapshot(_POSITIONS, _PRICES, snapshot_date="2026-06-15", **kw)


def test_valuation_and_pnl():
    pf, _ = _build(cash=0.0)
    by_sym = {r["symbol"]: r for r in pf}
    assert by_sym["AAA"]["market_value"] == 1100.0  # 10 * 110
    assert by_sym["AAA"]["unrealized_pnl"] == 100.0  # (110-100)*10
    assert by_sym["BBB"]["market_value"] == 1000.0
    assert by_sym["BBB"]["unrealized_pnl"] == 0.0


def test_weights_sum_to_100_without_cash():
    pf, _ = _build(cash=0.0)
    assert round(sum(r["weight_pct"] for r in pf), 1) == 100.0


def test_cash_reduces_weights_and_lifts_total():
    pf, perf = _build(cash=1000.0)
    # equity 2100 + caja 1000 = 3100
    assert perf["total_value"] == 3100.0
    # pesos sobre total con caja → suman < 100
    assert sum(r["weight_pct"] for r in pf) < 100.0


def test_cumulative_return_vs_initial_capital():
    # equity 2100, cash 0, costo 2000 → +5%
    _, perf = _build(cash=0.0)
    assert perf["cumulative_return_pct"] == 5.0


def test_daily_return_chained_from_prev():
    _, perf = _build(cash=0.0, prev_total_value=2000.0)
    # 2100 / 2000 - 1 = +5%
    assert perf["daily_return_pct"] == 5.0


def test_daily_return_none_when_no_prev():
    _, perf = _build(cash=0.0)
    assert perf["daily_return_pct"] == 0.0


def test_benchmark_passthrough_and_none():
    _, perf = _build(cash=0.0, benchmark_return_pct=12.345678)
    assert perf["benchmark_return_pct"] == 12.3457
    _, perf2 = _build(cash=0.0)
    assert perf2["benchmark_return_pct"] is None
