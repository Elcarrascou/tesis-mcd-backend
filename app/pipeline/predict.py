"""Corre inferencia con los 4 modelos y (opcional) escribe en Supabase.

Uso:
    python -m app.pipeline.predict            # dry-run (solo imprime)
    python -m app.pipeline.predict --write    # además inserta en ml_predictions
"""

from __future__ import annotations

import argparse

from app.constants import UNIVERSE
from app.data.yahoo import get_history
from app.db.supabase_client import insert_predictions
from app.models import all_models


def main() -> None:
    parser = argparse.ArgumentParser(description="Inferencia ML → ml_predictions")
    parser.add_argument("--write", action="store_true", help="escribe en Supabase")
    parser.add_argument("--symbols", nargs="*", default=UNIVERSE)
    args = parser.parse_args()

    models = all_models()
    for m in models:
        try:
            m.load()
        except FileNotFoundError:
            print(f"  (sin artefacto para {m.name}; entrena con app.pipeline.train)")

    rows = []
    for sym in args.symbols:
        try:
            df = get_history(sym, period="2y")
        except Exception as e:  # noqa: BLE001
            print(f"  ! {sym}: {e}")
            continue
        for m in models:
            try:
                pred = m.predict_one(sym, df)
                rows.append(pred.to_row())
                print(
                    f"  {sym:6} {m.name:14} "
                    f"val={pred.predicted_value} signal={pred.signal} "
                    f"conf={pred.confidence} h={pred.horizon_days}d"
                )
            except Exception as e:  # noqa: BLE001
                print(f"  ! {sym}/{m.name}: {e}")

    if args.write:
        insert_predictions(rows)
        print(f"\n[ok] {len(rows)} filas escritas en ml_predictions")
    else:
        print(f"\nDRY-RUN: {len(rows)} filas generadas (usar --write para guardar)")


if __name__ == "__main__":
    main()
