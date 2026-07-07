"""Re-seed coherente del portafolio demo con precios REALES de Yahoo (Bloque 2).

Problema que corrige: el seed original usaba precios inventados (~2024), NVDA
tenía costo pre-split (620 vs ~62 post split 10:1) y `performance` arrancaba en
mayo con retornos fabricados mientras el benchmark se calculaba desde enero.
Ante la comisión, nada de eso resiste una verificación contra el mercado real.

Modelo resultante (auditable contra Yahoo Finance):
- Las 6 posiciones se COMPRAN el primer día hábil >= INCEPTION_DATE al precio de
  cierre real de ese día (auto-ajustado por splits/dividendos).
- `movements` = exactamente esas 6 compras (sin broker aún; `alpaca_order_id`
  queda NULL hasta la Fase I con Alpaca paper).
- `performance` se reconstruye día hábil a día hábil desde inception hasta hoy:
  total_value = sum(qty * close) + caja fija; retorno acumulado vs capital
  inicial (costo + caja); retorno diario encadenado; benchmark = buy&hold ECH.
- `portfolio` conserva las cantidades y se revalúa al último cierre.

Uso:
    python -m app.pipeline.reseed            # dry-run (imprime plan)
    python -m app.pipeline.reseed --write    # reemplaza movements/performance + portfolio
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

import pandas as pd

from app.data.yahoo import get_history
from app.db.supabase_client import (
    replace_movements,
    replace_performance,
    upsert_portfolio,
)
from app.pipeline.snapshot import BENCHMARK_SYMBOL, CASH_USD, INCEPTION_DATE

# Cantidades del portafolio demo (se conservan; solo cambia el costo al real).
QUANTITIES: dict[str, float] = {
    "AAPL": 40,
    "GOOGL": 30,
    "MSFT": 25,
    "NVDA": 18,
    "SQM": 35,
    "TSLA": 22,
}

# Hora de ejecución de las compras seed (UTC, poco después de la apertura NYSE).
_BUY_HOUR_UTC = 14


def _naive(s: pd.Series) -> pd.Series:
    """Serie de cierres con índice sin timezone (comparable con Timestamps naive)."""
    if s.index.tz is not None:
        s = s.copy()
        s.index = s.index.tz_localize(None)
    return s


def build_reseed(
    closes: dict[str, pd.Series],
    benchmark: pd.Series,
    quantities: dict[str, float],
    *,
    inception: str,
    cash: float,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Calcula movements, portfolio y performance desde series de cierres reales.

    Función pura (sin red ni Supabase) para poder testearla. `closes` y
    `benchmark` son series diarias de cierre indexadas por fecha.
    """
    inception_ts = pd.Timestamp(inception)
    closes = {sym: _naive(s) for sym, s in closes.items()}
    benchmark = _naive(benchmark)

    # Calendario: días hábiles del benchmark desde inception (NYSE, igual que
    # los símbolos del portafolio). Forward-fill cubre feriados puntuales.
    calendar = benchmark.loc[inception_ts:].index
    if len(calendar) == 0:
        raise ValueError(f"Benchmark sin datos desde {inception}")
    buy_date = calendar[0]

    # Compras al cierre real del primer día hábil.
    movements: list[dict] = []
    avg_prices: dict[str, float] = {}
    for i, (sym, qty) in enumerate(sorted(quantities.items())):
        series = closes[sym].loc[buy_date:]
        if series.empty:
            raise ValueError(f"Sin cierre de {sym} en {buy_date.date()}")
        price = float(series.iloc[0])
        avg_prices[sym] = price
        executed = datetime(
            buy_date.year, buy_date.month, buy_date.day,
            _BUY_HOUR_UTC, 31 + i * 3, 0, tzinfo=UTC,
        )
        movements.append(
            {
                "symbol": sym,
                "side": "buy",
                "quantity": qty,
                "price": round(price, 4),
                "amount": round(qty * price, 2),
                "alpaca_order_id": None,
                "executed_at": executed.isoformat(),
            }
        )

    cost_basis = sum(quantities[s] * avg_prices[s] for s in quantities)
    initial_capital = cost_basis + cash

    # Serie diaria de performance sobre el calendario del benchmark.
    aligned = {
        sym: closes[sym].reindex(calendar).ffill() for sym in quantities
    }
    bench0 = float(benchmark.loc[calendar[0]])
    performance: list[dict] = []
    prev_total: float | None = None
    for day in calendar:
        equity = sum(quantities[s] * float(aligned[s].loc[day]) for s in quantities)
        total = equity + cash
        daily = (total / prev_total - 1) * 100 if prev_total else 0.0
        cumulative = (total / initial_capital - 1) * 100 if initial_capital else 0.0
        bench = (float(benchmark.reindex(calendar).ffill().loc[day]) / bench0 - 1) * 100
        performance.append(
            {
                "snapshot_date": day.date().isoformat(),
                "total_value": round(total, 2),
                "daily_return_pct": round(daily, 4),
                "cumulative_return_pct": round(cumulative, 4),
                "benchmark_return_pct": round(bench, 4),
            }
        )
        prev_total = total

    # Portfolio revaluado al último día del calendario.
    last_day = calendar[-1]
    now_iso = datetime.now(UTC).isoformat()
    last_total = performance[-1]["total_value"]
    portfolio: list[dict] = []
    for sym, qty in sorted(quantities.items()):
        price = float(aligned[sym].loc[last_day])
        market_value = qty * price
        portfolio.append(
            {
                "symbol": sym,
                "quantity": qty,
                "avg_price": round(avg_prices[sym], 4),
                "current_price": round(price, 4),
                "market_value": round(market_value, 2),
                "unrealized_pnl": round((price - avg_prices[sym]) * qty, 2),
                "weight_pct": round(market_value / last_total * 100, 3) if last_total else 0.0,
                "updated_at": now_iso,
            }
        )

    return movements, portfolio, performance


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-seed coherente: movements + performance + portfolio con precios reales"
    )
    parser.add_argument("--write", action="store_true", help="escribe en Supabase")
    args = parser.parse_args()

    symbols = sorted(QUANTITIES)
    print(f"Descargando 1y de cierres reales: {symbols} + benchmark {BENCHMARK_SYMBOL}")
    closes = {s: get_history(s, period="1y")["Close"] for s in symbols}
    benchmark = get_history(BENCHMARK_SYMBOL, period="1y")["Close"]

    movements, portfolio, performance = build_reseed(
        closes, benchmark, QUANTITIES, inception=INCEPTION_DATE, cash=CASH_USD,
    )

    print(f"\nCompras seed ({movements[0]['executed_at'][:10]}):")
    for m in movements:
        print(f"  {m['symbol']:6} {m['quantity']:>4} x {m['price']:10.2f} = {m['amount']:10.2f}")
    cost = sum(m["amount"] for m in movements)
    print(f"  Costo total {cost:.2f} + caja {CASH_USD:.2f} = capital {cost + CASH_USD:.2f}")

    print("\nPortfolio revaluado:")
    for r in portfolio:
        print(
            f"  {r['symbol']:6} avg={r['avg_price']:9.2f} px={r['current_price']:9.2f} "
            f"pnl={r['unrealized_pnl']:10.2f} w={r['weight_pct']:6.2f}%"
        )

    first, last = performance[0], performance[-1]
    print(
        f"\nPerformance: {len(performance)} días hábiles "
        f"({first['snapshot_date']} -> {last['snapshot_date']})"
    )
    print(
        f"  Final: total={last['total_value']:.2f} cum={last['cumulative_return_pct']:+.2f}% "
        f"bench {BENCHMARK_SYMBOL}={last['benchmark_return_pct']:+.2f}%"
    )

    if args.write:
        replace_movements(movements)
        replace_performance(performance)
        upsert_portfolio(portfolio)
        print(
            f"\n[ok] movements({len(movements)}) + performance({len(performance)}) "
            f"reemplazados; portfolio({len(portfolio)}) revaluado"
        )
    else:
        print("\nDRY-RUN: usar --write para reemplazar en Supabase")


if __name__ == "__main__":
    main()
