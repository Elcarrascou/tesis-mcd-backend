"""Tests del re-seed coherente (Bloque 2).

Se prueba la función pura `build_reseed` con series sintéticas: compras al
cierre real del primer día hábil, serie de performance encadenada y portfolio
revaluado al último cierre.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.pipeline.reseed import build_reseed

# Calendario: 4 días hábiles desde el 2 de enero.
_DAYS = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"])

# AAA sube 100 -> 110 (+10%); BBB plano en 200. Benchmark sube 50 -> 55 (+10%).
_CLOSES = {
    "AAA": pd.Series([100.0, 104.0, 108.0, 110.0], index=_DAYS),
    "BBB": pd.Series([200.0, 200.0, 200.0, 200.0], index=_DAYS),
}
_BENCH = pd.Series([50.0, 52.0, 54.0, 55.0], index=_DAYS)
_QTY = {"AAA": 10.0, "BBB": 5.0}


def _build(cash: float = 0.0):
    return build_reseed(_CLOSES, _BENCH, _QTY, inception="2026-01-02", cash=cash)


def test_buys_at_first_close_from_inception():
    movements, _, _ = _build()
    by_sym = {m["symbol"]: m for m in movements}
    assert len(movements) == 2
    assert by_sym["AAA"]["price"] == 100.0
    assert by_sym["BBB"]["price"] == 200.0
    assert by_sym["AAA"]["amount"] == 1000.0  # 10 * 100
    assert all(m["side"] == "buy" for m in movements)
    assert all(m["alpaca_order_id"] is None for m in movements)
    assert all(m["executed_at"].startswith("2026-01-02") for m in movements)


def test_inception_on_holiday_uses_next_trading_day():
    movements, _, performance = build_reseed(
        _CLOSES, _BENCH, _QTY, inception="2026-01-03", cash=0.0
    )
    assert movements[0]["executed_at"].startswith("2026-01-05")
    assert performance[0]["snapshot_date"] == "2026-01-05"


def test_performance_series_covers_calendar():
    _, _, performance = _build()
    assert [r["snapshot_date"] for r in performance] == [
        "2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07",
    ]
    # Día 1: capital = costo (sin caja) -> retornos en cero.
    first = performance[0]
    assert first["total_value"] == 2000.0  # 10*100 + 5*200
    assert first["cumulative_return_pct"] == 0.0
    assert first["daily_return_pct"] == 0.0


def test_cumulative_daily_and_benchmark_returns():
    _, _, performance = _build()
    last = performance[-1]
    # equity final 10*110 + 5*200 = 2100 vs capital 2000 -> +5%
    assert last["total_value"] == 2100.0
    assert last["cumulative_return_pct"] == 5.0
    # benchmark 55/50 - 1 = +10%
    assert last["benchmark_return_pct"] == 10.0
    # diario encadenado: día 2 = 2040/2000 - 1 = +2%
    assert performance[1]["daily_return_pct"] == 2.0


def test_cash_lifts_total_and_dilutes_cumulative():
    _, _, performance = _build(cash=1000.0)
    last = performance[-1]
    # total 2100 + 1000 = 3100 vs capital 3000 -> +3.3333%
    assert last["total_value"] == 3100.0
    assert last["cumulative_return_pct"] == pytest.approx(3.3333, abs=1e-4)


def test_portfolio_revalued_at_last_close():
    _, portfolio, _ = _build(cash=1000.0)
    by_sym = {r["symbol"]: r for r in portfolio}
    aaa = by_sym["AAA"]
    assert aaa["avg_price"] == 100.0
    assert aaa["current_price"] == 110.0
    assert aaa["market_value"] == 1100.0
    assert aaa["unrealized_pnl"] == 100.0  # (110-100)*10
    # pesos sobre total con caja -> suman < 100
    assert sum(r["weight_pct"] for r in portfolio) < 100.0


def test_empty_benchmark_since_inception_raises():
    with pytest.raises(ValueError):
        build_reseed(_CLOSES, _BENCH, _QTY, inception="2027-01-01", cash=0.0)
