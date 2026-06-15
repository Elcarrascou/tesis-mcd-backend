"""Snapshot operacional diario del portafolio (Fase G2).

Revalúa las posiciones con precios de mercado (Yahoo) e inserta una fila diaria
en `performance`, para que el portal (Dashboard / Ganancias) nunca se vea
congelado ante la comisión.

Modelo de datos:
- Las POSICIONES (cantidad, costo promedio) son la fuente de verdad y viven en la
  tabla `portfolio`; este pipeline NO las cambia, solo recalcula su valuación
  (current_price / market_value / unrealized_pnl / weight_pct).
- El portafolio mantiene además una CAJA fija (`CASH_USD`). Por eso
  total_value = equity (suma de market_value) + caja.
- Retorno acumulado = total_value vs capital inicial (costo de las posiciones +
  caja). Retorno diario = total_value vs la última fila de `performance`.
- Benchmark = retorno buy&hold del ETF ECH (proxy del IPSA, ver HANDOFF) desde la
  fecha de inicio del portafolio.

Uso:
    python -m app.pipeline.snapshot            # dry-run (solo imprime)
    python -m app.pipeline.snapshot --write    # + upsert portfolio + performance
    python -m app.pipeline.snapshot --date 2026-06-15 --write   # fecha explícita
"""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime

import pandas as pd

from app.data.yahoo import get_history, get_quote
from app.db.supabase_client import (
    get_last_performance,
    get_portfolio,
    upsert_performance,
    upsert_portfolio,
)

# Caja del portafolio demo (USD). Mantiene el total_value continuo con el seed
# histórico y representa el efectivo no invertido.
CASH_USD = 5000.0

# Fecha de inicio del portafolio: base del retorno acumulado y del benchmark.
INCEPTION_DATE = "2026-01-02"

# Benchmark de contexto: ETF iShares MSCI Chile, proxy del IPSA (Yahoo descontinuó
# ^IPSA en 2019; mismo criterio que app/pipeline/backtest.py).
BENCHMARK_SYMBOL = "ECH"


def fetch_prices(symbols: list[str]) -> dict[str, float]:
    """Último precio de mercado por símbolo (Yahoo)."""
    return {s: float(get_quote(s)["price"]) for s in symbols}


def benchmark_return(symbol: str, since: str) -> float:
    """Retorno buy&hold (%) del benchmark desde `since` hasta hoy."""
    s = get_history(symbol, period="2y")["Close"]
    if s.index.tz is not None:
        s.index = s.index.tz_localize(None)
    since_ts = pd.Timestamp(since)
    past = s.loc[:since_ts]
    p0 = float(past.iloc[-1]) if len(past) else float(s.iloc[0])
    p1 = float(s.iloc[-1])
    return (p1 / p0 - 1) * 100 if p0 else 0.0


def build_snapshot(
    positions: list[dict],
    prices: dict[str, float],
    *,
    snapshot_date: str,
    cash: float = CASH_USD,
    prev_total_value: float | None = None,
    benchmark_return_pct: float | None = None,
) -> tuple[list[dict], dict]:
    """Calcula filas de portfolio (valuación) y la fila diaria de performance.

    Función pura (sin red ni Supabase) para poder testearla.
    """
    cost_basis = sum(float(p["quantity"]) * float(p["avg_price"]) for p in positions)
    initial_capital = cost_basis + cash
    now_iso = datetime.now(UTC).isoformat()

    pf_rows: list[dict] = []
    equity = 0.0
    for p in positions:
        sym = p["symbol"]
        qty = float(p["quantity"])
        avg = float(p["avg_price"])
        price = float(prices[sym])
        market_value = qty * price
        equity += market_value
        pf_rows.append(
            {
                "symbol": sym,
                "current_price": round(price, 4),
                "market_value": round(market_value, 2),
                "unrealized_pnl": round((price - avg) * qty, 2),
                "updated_at": now_iso,
            }
        )

    total_value = equity + cash
    for r in pf_rows:
        r["weight_pct"] = round(r["market_value"] / total_value * 100, 3) if total_value else 0.0

    cumulative = (total_value / initial_capital - 1) * 100 if initial_capital else 0.0
    daily = (total_value / prev_total_value - 1) * 100 if prev_total_value else 0.0

    perf_row = {
        "snapshot_date": snapshot_date,
        "total_value": round(total_value, 2),
        "daily_return_pct": round(daily, 4),
        "cumulative_return_pct": round(cumulative, 4),
        "benchmark_return_pct": (
            round(benchmark_return_pct, 4) if benchmark_return_pct is not None else None
        ),
    }
    return pf_rows, perf_row


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot diario → portfolio + performance")
    parser.add_argument("--write", action="store_true", help="escribe en Supabase")
    parser.add_argument(
        "--date", default=None, help="fecha del snapshot (YYYY-MM-DD); hoy por defecto"
    )
    args = parser.parse_args()

    positions = get_portfolio()
    if not positions:
        print("Sin posiciones en portfolio. Aborto.")
        return

    symbols = [p["symbol"] for p in positions]
    print(f"Revaluando {len(symbols)} posiciones: {symbols}")
    prices = fetch_prices(symbols)

    last = get_last_performance()
    prev_total = float(last["total_value"]) if last else None

    bench: float | None = None
    try:
        bench = benchmark_return(BENCHMARK_SYMBOL, INCEPTION_DATE)
    except Exception as e:  # noqa: BLE001
        print(f"  ! benchmark {BENCHMARK_SYMBOL}: {e}")

    snap_date = args.date or date.today().isoformat()
    pf_rows, perf_row = build_snapshot(
        positions, prices,
        snapshot_date=snap_date, cash=CASH_USD,
        prev_total_value=prev_total, benchmark_return_pct=bench,
    )

    for r in pf_rows:
        print(
            f"  {r['symbol']:6} px={r['current_price']:10.2f} "
            f"mv={r['market_value']:11.2f} pnl={r['unrealized_pnl']:11.2f} "
            f"w={r['weight_pct']:6.2f}%"
        )
    print(
        f"\n  {snap_date}  total={perf_row['total_value']:.2f} "
        f"daily={perf_row['daily_return_pct']:+.2f}% "
        f"cum={perf_row['cumulative_return_pct']:+.2f}% "
        f"bench={perf_row['benchmark_return_pct']}"
    )

    if args.write:
        upsert_portfolio(pf_rows)
        upsert_performance(perf_row)
        print(f"\n[ok] portfolio ({len(pf_rows)} filas) + performance ({snap_date}) actualizados")
    else:
        print("\nDRY-RUN: usar --write para guardar en Supabase")


if __name__ == "__main__":
    main()
