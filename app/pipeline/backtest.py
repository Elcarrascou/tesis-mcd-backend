"""Backtesting walk-forward y evaluación de los 4 modelos (Fase C).

Material central para la defensa ante el comité: mide cómo se habrían comportado
los modelos *fuera de muestra*, reentrenando solo con datos del pasado en cada
punto (sin fuga de información / look-ahead).

Esquema (por modelo y símbolo):
- Ventana expansiva con reentrenamiento periódico (`--retrain-folds`).
- En cada ancla `t` se reentrena con `df[:t]` y se predice con `predict_one`
  sobre `df[:t]` — exactamente igual que la inferencia en producción.
- Se compara la predicción con el resultado realizado en `t + horizonte`.

Métricas:
- Regresión (LSTM precio, Prophet tendencia): RMSE, MAE, MAPE, precisión direccional.
- Clasificación (XGBoost señal, Random Forest riesgo): accuracy, F1 macro.
- Estrategia: retorno acumulado / Sharpe / max drawdown vs. buy&hold del universo
  y de los índices de contexto (^IPSA, ^DJI).

Uso:
    python -m app.pipeline.backtest                 # todos los modelos, dry-run
    python -m app.pipeline.backtest --write         # + guarda en model_metrics
    python -m app.pipeline.backtest --models lstm xgboost --no-strategy
    python -m app.pipeline.backtest --max-symbols 2 --retrain-folds 2   # smoke
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

import numpy as np
import pandas as pd

from app.constants import UNIVERSE
from app.data.yahoo import get_history
from app.db.supabase_client import insert_metrics
from app.ml import metrics as M
from app.ml.dataset import make_risk_labels, make_signal_labels
from app.models.base import BaseModel
from app.models.lstm_price import HORIZON as LSTM_H
from app.models.lstm_price import LSTMPriceModel
from app.models.prophet_trend import HORIZON as PROPHET_H
from app.models.prophet_trend import ProphetTrendModel
from app.models.rf_risk import HORIZON as RF_H
from app.models.rf_risk import RandomForestRiskModel
from app.models.xgb_signal import HORIZON as XGB_H
from app.models.xgb_signal import XGBoostSignalModel

# Índices de contexto de mercado de la tesis (benchmark buy&hold) → etiqueta.
# Yahoo dejó de publicar ^IPSA en 2019, así que se usa el ETF ECH (iShares MSCI
# Chile) como proxy del mercado chileno/IPSA. ^DJI (Dow Jones) sí está vigente.
BENCHMARKS: dict[str, str] = {"ECH": "IPSA proxy (ETF Chile)", "^DJI": "Dow Jones"}

MIN_TRAIN = 252  # ~1 año de datos mínimo antes de la primera predicción


def _label_signal(df: pd.DataFrame) -> pd.Series:
    return make_signal_labels(df, horizon=XGB_H)


def _label_risk(df: pd.DataFrame) -> pd.Series:
    return make_risk_labels(df, horizon=RF_H)


# Configuración de backtest por modelo. `step` espacia las anclas (Prophet y RF
# usan horizontes largos y reentrenan caro, así que se evalúan con menos puntos).
BT_CONFIG: dict[str, dict] = {
    "lstm": {
        "factory": LSTMPriceModel, "kind": "reg", "horizon": LSTM_H, "step": 5, "label_fn": None,
    },
    "xgboost": {
        "factory": XGBoostSignalModel, "kind": "clf", "horizon": XGB_H, "step": 5,
        "label_fn": _label_signal,
    },
    "prophet": {
        "factory": ProphetTrendModel, "kind": "reg", "horizon": PROPHET_H, "step": 21,
        "label_fn": None,
    },
    "random_forest": {
        "factory": RandomForestRiskModel, "kind": "clf", "horizon": RF_H, "step": 10,
        "label_fn": _label_risk,
    },
}


# ──────────────────────────────────────────────────────────────────────────
# Walk-forward por modelo
# ──────────────────────────────────────────────────────────────────────────
def _fold_edges(lo: int, hi: int, folds: int) -> list[int]:
    return sorted({int(x) for x in np.linspace(lo, hi, folds + 1)})


def walk_forward_symbol(
    model: BaseModel,
    symbol: str,
    df: pd.DataFrame,
    horizon: int,
    kind: str,
    label_fn: Callable[[pd.DataFrame], pd.Series] | None,
    retrain_folds: int,
    step: int,
) -> list[dict]:
    """Genera predicciones fuera de muestra para un símbolo (ventana expansiva)."""
    n = len(df)
    end = n - horizon
    if end <= MIN_TRAIN:
        return []

    closes = df["Close"].to_numpy(dtype=float)
    labels = label_fn(df) if label_fn is not None else None
    edges = _fold_edges(MIN_TRAIN, end, retrain_folds)
    records: list[dict] = []

    for j in range(len(edges) - 1):
        a, b = edges[j], edges[j + 1]
        try:
            model.fit({symbol: df.iloc[:a]})  # entrena solo con el pasado
        except Exception as e:  # noqa: BLE001
            print(f"    ! fit {model.name}/{symbol} fold {j}: {e}")
            continue
        for i in range(a, b, step):
            if i + horizon >= n:
                break
            try:
                pred = model.predict_one(symbol, df.iloc[: i + 1])
            except Exception:  # noqa: BLE001
                continue
            if kind == "reg":
                if pred.predicted_value is None:
                    continue
                records.append(
                    {
                        "base": closes[i],
                        "true": closes[i + horizon],
                        "pred": float(pred.predicted_value),
                    }
                )
            else:
                date = df.index[i]
                if labels is None or date not in labels.index:
                    continue
                records.append(
                    {
                        "true_label": str(labels.loc[date]),
                        "pred_label": str(pred.signal),
                        "proba": pred.proba,
                    }
                )
    return records


def _metrics_from_records(
    model: str, kind: str, horizon: int, symbol, recs: list[dict]
) -> list[dict]:
    """Convierte registros de walk-forward en filas de model_metrics."""
    if not recs:
        return []
    rows: list[dict] = []

    def add(metric: str, value: float) -> None:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return
        rows.append(
            {
                "model": model,
                "symbol": symbol,
                "task": "price/trend" if kind == "reg" else "signal/risk",
                "metric": metric,
                "value": round(float(value), 4),
                "n_samples": len(recs),
                "horizon_days": horizon,
            }
        )

    if kind == "reg":
        base = [r["base"] for r in recs]
        true = [r["true"] for r in recs]
        pred = [r["pred"] for r in recs]
        add("rmse", M.rmse(true, pred))
        add("mae", M.mae(true, pred))
        add("mape", M.mape(true, pred))
        add("dir_acc", M.directional_accuracy(base, true, pred))
    else:
        true = [r["true_label"] for r in recs]
        pred = [r["pred_label"] for r in recs]
        add("accuracy", M.accuracy(true, pred))
        add("f1_macro", M.f1_macro(true, pred))
        probas = [r.get("proba") for r in recs]
        if all(p is not None for p in probas):
            labels = sorted({c for p in probas for c in p} | set(true))
            add("auc", M.auc_macro(true, probas, labels))
    return rows


def backtest_models(
    histories: dict[str, pd.DataFrame], model_names: list[str], retrain_folds: int
) -> list[dict]:
    """Backtest walk-forward de los modelos pedidos. Devuelve filas de métricas."""
    all_rows: list[dict] = []
    for name in model_names:
        cfg = BT_CONFIG[name]
        print(f"\n[{name}] walk-forward (horizonte {cfg['horizon']}d, {retrain_folds} folds)…")
        pooled: list[dict] = []
        for sym, df in histories.items():
            model = cfg["factory"]()
            recs = walk_forward_symbol(
                model, sym, df, cfg["horizon"], cfg["kind"], cfg["label_fn"],
                retrain_folds, cfg["step"],
            )
            if not recs:
                print(f"    {sym:6} sin datos suficientes")
                continue
            pooled.extend(recs)
            for row in _metrics_from_records(name, cfg["kind"], cfg["horizon"], sym, recs):
                all_rows.append(row)
            _print_metric_line(sym, name, cfg["kind"], recs)
        # Fila agregada (symbol = None → métrica global del modelo).
        for row in _metrics_from_records(name, cfg["kind"], cfg["horizon"], None, pooled):
            row["n_folds"] = retrain_folds
            all_rows.append(row)
        _print_metric_line("GLOBAL", name, cfg["kind"], pooled)
    return all_rows


def _print_metric_line(label: str, model: str, kind: str, recs: list[dict]) -> None:
    if not recs:
        return
    if kind == "reg":
        true = [r["true"] for r in recs]
        pred = [r["pred"] for r in recs]
        base = [r["base"] for r in recs]
        print(
            f"    {label:6} {model:14} n={len(recs):4} "
            f"RMSE={M.rmse(true, pred):8.3f} MAE={M.mae(true, pred):8.3f} "
            f"MAPE={M.mape(true, pred):6.2f}% "
            f"dirAcc={M.directional_accuracy(base, true, pred):5.1f}%"
        )
    else:
        true = [r["true_label"] for r in recs]
        pred = [r["pred_label"] for r in recs]
        print(
            f"    {label:6} {model:14} n={len(recs):4} "
            f"acc={M.accuracy(true, pred):5.1f}% F1={M.f1_macro(true, pred):5.1f}%"
        )


# ──────────────────────────────────────────────────────────────────────────
# Backtest de estrategia (señal XGBoost) vs benchmarks
# ──────────────────────────────────────────────────────────────────────────
def strategy_backtest(
    histories: dict[str, pd.DataFrame], retrain_folds: int, step: int = XGB_H
) -> list[dict]:
    """Estrategia long-only equiponderada guiada por la señal de XGBoost.

    En cada rebalanceo se invierte por igual en los símbolos con señal 'buy'
    (resto en efectivo). Se compara con buy&hold equiponderado del universo y con
    los índices de contexto.
    """
    common = None
    for df in histories.values():
        common = df.index if common is None else common.intersection(df.index)
    if common is None:
        return []
    common = common.sort_values()
    n = len(common)
    end = n - step
    if end <= MIN_TRAIN:
        print("\n[strategy] histórico insuficiente para backtest de estrategia")
        return []

    edges = _fold_edges(MIN_TRAIN, end, retrain_folds)
    model = XGBoostSignalModel()
    strat_rets: list[float] = []
    bh_rets: list[float] = []

    print(f"\n[strategy] backtest long-only (rebalanceo cada {step}d, {retrain_folds} folds)…")
    for j in range(len(edges) - 1):
        a, b = edges[j], edges[j + 1]
        train_date = common[a]
        try:
            model.fit({s: df.loc[:train_date] for s, df in histories.items()})
        except Exception as e:  # noqa: BLE001
            print(f"    ! fit estrategia fold {j}: {e}")
            continue
        for i in range(a, b, step):
            if i + step >= n:
                break
            d0, d1 = common[i], common[i + step]
            picks: list[float] = []
            all_rets: list[float] = []
            for s, df in histories.items():
                c0 = float(df["Close"].loc[d0])
                c1 = float(df["Close"].loc[d1])
                r = c1 / c0 - 1
                all_rets.append(r)
                try:
                    if model.predict_one(s, df.loc[:d0]).signal == "buy":
                        picks.append(r)
                except Exception:  # noqa: BLE001
                    continue
            strat_rets.append(float(np.mean(picks)) if picks else 0.0)
            bh_rets.append(float(np.mean(all_rets)) if all_rets else 0.0)

    ppy = max(1, round(M.TRADING_DAYS / step))
    rows = _strategy_metric_rows("strategy", strat_rets, step, ppy)
    rows += _strategy_metric_rows("buy_hold_universe", bh_rets, step, ppy)
    rows += _benchmark_rows(common[edges[0]], common[end - 1], step, ppy)

    for tag, rets in (("strategy", strat_rets), ("buy_hold_universe", bh_rets)):
        print(
            f"    {tag:20} cumRet={M.cumulative_return(rets):7.2f}% "
            f"Sharpe={M.sharpe_ratio(rets, ppy):5.2f} maxDD={M.max_drawdown(rets):7.2f}%"
        )
    return rows


def _strategy_metric_rows(name: str, rets: list[float], step: int, ppy: int) -> list[dict]:
    if not rets:
        return []
    base = {
        "model": name, "symbol": None, "task": "strategy",
        "horizon_days": step, "n_samples": len(rets),
    }
    return [
        {**base, "metric": "cum_return", "value": round(M.cumulative_return(rets), 4)},
        {**base, "metric": "sharpe", "value": round(M.sharpe_ratio(rets, ppy), 4)},
        {**base, "metric": "max_drawdown", "value": round(M.max_drawdown(rets), 4)},
    ]


def _benchmark_rows(start: pd.Timestamp, end: pd.Timestamp, step: int, ppy: int) -> list[dict]:
    """Retorno acumulado buy&hold de los índices de contexto en la misma ventana."""
    rows: list[dict] = []
    for idx, label in BENCHMARKS.items():
        try:
            b = get_history(idx, period="max")["Close"]
            if b.index.tz is not None:
                b.index = b.index.tz_localize(None)
            s = start.tz_localize(None) if getattr(start, "tzinfo", None) else start
            e = end.tz_localize(None) if getattr(end, "tzinfo", None) else end
            if b.index.max() < s:  # datos del benchmark anteriores a la ventana
                print(f"    ! benchmark {idx}: sin datos en la ventana (desactualizado)")
                continue
            p0 = float(b.loc[:s].iloc[-1])
            p1 = float(b.loc[:e].iloc[-1])
            cum = (p1 / p0 - 1) * 100
            daily = b.loc[s:e].pct_change().dropna()
            rows.append(
                {
                    "model": f"benchmark_{idx.strip('^').lower()}",
                    "symbol": idx,
                    "task": "benchmark",
                    "metric": "cum_return",
                    "value": round(cum, 4),
                    "horizon_days": step,
                    "n_samples": len(daily),
                    "notes": label,
                }
            )
            print(f"    benchmark {idx:8} ({label}) cumRet={cum:7.2f}% (buy&hold)")
        except Exception as e:  # noqa: BLE001
            print(f"    ! benchmark {idx}: {e}")
    return rows


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Backtesting walk-forward → model_metrics")
    parser.add_argument("--models", nargs="*", default=list(BT_CONFIG), choices=list(BT_CONFIG))
    parser.add_argument("--symbols", nargs="*", default=UNIVERSE)
    parser.add_argument("--period", default="5y")
    parser.add_argument("--retrain-folds", type=int, default=4)
    parser.add_argument("--max-symbols", type=int, default=None, help="limita símbolos (smoke)")
    parser.add_argument("--no-strategy", action="store_true", help="omite backtest de estrategia")
    parser.add_argument("--write", action="store_true", help="escribe en model_metrics")
    args = parser.parse_args()

    symbols = args.symbols[: args.max_symbols] if args.max_symbols else args.symbols
    print(f"Descargando históricos ({args.period}) de {symbols}…")
    histories: dict[str, pd.DataFrame] = {}
    for s in symbols:
        try:
            histories[s] = get_history(s, period=args.period)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {s}: {e}")
    if not histories:
        print("Sin datos. Aborto.")
        return

    rows = backtest_models(histories, args.models, args.retrain_folds)
    if not args.no_strategy:
        rows += strategy_backtest(histories, args.retrain_folds)

    print(f"\n{len(rows)} filas de métricas generadas.")
    if args.write:
        insert_metrics(rows)
        print(f"[ok] {len(rows)} filas escritas en model_metrics")
    else:
        print("DRY-RUN: usar --write para guardar en Supabase")


if __name__ == "__main__":
    main()
