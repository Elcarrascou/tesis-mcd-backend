"""Interfaz común de los modelos ML.

Cada modelo:
- entrena con `fit(datasets)` (dict symbol -> histórico OHLCV),
- predice con `predict_one(symbol, df)` devolviendo un dict listo para insertar
  en la tabla `ml_predictions`,
- persiste con `save(dir)` / `load(dir)` en `artifacts/`.
"""

from __future__ import annotations

import abc
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent.parent / "artifacts"


@dataclass
class Prediction:
    """Fila de predicción (mapea 1:1 a ml_predictions)."""

    model: str
    symbol: str
    prediction_type: str
    predicted_value: float | None = None
    signal: str | None = None
    confidence: float | None = None
    horizon_days: int | None = None
    # Probabilidades por clase (solo clasificadores). NO va a ml_predictions; se usa
    # para métricas como AUC ROC en el backtest.
    proba: dict[str, float] | None = None

    def to_row(self) -> dict:
        row = asdict(self)
        row.pop("proba", None)  # no es columna de ml_predictions
        return row


class BaseModel(abc.ABC):
    name: str  # 'lstm' | 'xgboost' | 'prophet' | 'random_forest'
    prediction_type: str  # 'price' | 'signal' | 'trend' | 'risk'

    @abc.abstractmethod
    def fit(self, datasets: dict[str, pd.DataFrame]) -> None: ...

    @abc.abstractmethod
    def predict_one(self, symbol: str, df: pd.DataFrame) -> Prediction: ...

    @abc.abstractmethod
    def save(self, directory: Path = ARTIFACTS_DIR) -> None: ...

    @abc.abstractmethod
    def load(self, directory: Path = ARTIFACTS_DIR) -> None: ...
