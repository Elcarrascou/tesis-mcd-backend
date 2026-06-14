"""Entrena los 4 modelos y guarda artefactos en artifacts/.

Uso:
    python -m app.pipeline.train
"""

from __future__ import annotations

from app.constants import UNIVERSE
from app.models import all_models
from app.pipeline.data import load_histories


def main() -> None:
    print("Descargando históricos (5y)…")
    data = load_histories(UNIVERSE, period="5y")
    print(f"  {len(data)}/{len(UNIVERSE)} símbolos OK\n")

    for model in all_models():
        print(f"Entrenando {model.name}…")
        model.fit(data)
        model.save()
        print("  [ok] guardado en artifacts/")
    print("\nListo. Artefactos entrenados.")


if __name__ == "__main__":
    main()
