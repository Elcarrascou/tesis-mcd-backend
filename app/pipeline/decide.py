"""Pipeline del agente: predicción → consolidación → decisión explicable.

Para cada símbolo corre los 4 modelos, consolida en una decisión unificada
(`app/agent/consolidate.py`), redacta el razonamiento con el motor LLM configurado
(con fallback rule-based) y opcionalmente escribe en `ai_decisions`.

Uso:
    python -m app.pipeline.decide                 # dry-run (imprime)
    python -m app.pipeline.decide --write         # + inserta en ai_decisions
    python -m app.pipeline.decide --engine rule-based   # sin LLM
    python -m app.pipeline.decide --orders        # muestra órdenes intencionadas (stub)
"""

from __future__ import annotations

import argparse

from app.agent.consolidate import consolidate
from app.agent.execute import intended_order
from app.agent.llm_router import generate_rationale
from app.constants import UNIVERSE
from app.data.yahoo import get_history
from app.db.supabase_client import insert_decisions
from app.models import all_models


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente IA → ai_decisions")
    parser.add_argument("--write", action="store_true", help="escribe en Supabase")
    parser.add_argument("--symbols", nargs="*", default=UNIVERSE)
    parser.add_argument("--engine", default=None, help="ollama|anthropic|openai|rule-based")
    parser.add_argument("--orders", action="store_true", help="muestra órdenes intencionadas")
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

        preds = []
        for m in models:
            try:
                preds.append(m.predict_one(sym, df))
            except Exception as e:  # noqa: BLE001
                print(f"  ! {sym}/{m.name}: {e}")
        if not preds:
            continue

        c = consolidate(sym, preds)
        rationale, engine = generate_rationale(c, args.engine)
        rows.append(c.to_row(engine=engine, rationale=rationale))
        print(
            f"\n  {sym:6} {c.action.upper():9} conf={c.confidence:.0f}% "
            f"score={c.score:+.2f} [{engine}]"
        )
        print(f"         {rationale}")
        if args.orders:
            order = intended_order(c)
            print(f"         orden: {order}")

    if args.write:
        insert_decisions(rows)
        print(f"\n[ok] {len(rows)} decisiones escritas en ai_decisions")
    else:
        print(f"\nDRY-RUN: {len(rows)} decisiones generadas (usar --write para guardar)")


if __name__ == "__main__":
    main()
