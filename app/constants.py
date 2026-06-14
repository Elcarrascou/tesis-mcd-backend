"""Constantes de dominio del sistema."""

from __future__ import annotations

# Universo de acciones que el sistema analiza (mismo del portafolio demo + benchmark).
# IPSA chileno (^IPSA) y Dow Jones (^DJI) como contexto de mercado de la tesis.
UNIVERSE: list[str] = ["NVDA", "MSFT", "AAPL", "TSLA", "GOOGL", "SQM"]

# Modelos válidos (coinciden con el CHECK de la tabla ml_predictions).
MODELS: list[str] = ["lstm", "xgboost", "prophet", "random_forest"]
