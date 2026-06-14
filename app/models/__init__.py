"""Modelos ML de la tesis. Interfaz común en base.py."""

from __future__ import annotations

from app.models.base import BaseModel, Prediction
from app.models.lstm_price import LSTMPriceModel
from app.models.prophet_trend import ProphetTrendModel
from app.models.rf_risk import RandomForestRiskModel
from app.models.xgb_signal import XGBoostSignalModel


def all_models() -> list[BaseModel]:
    """Instancia los 4 modelos en orden canónico."""
    return [
        LSTMPriceModel(),
        XGBoostSignalModel(),
        ProphetTrendModel(),
        RandomForestRiskModel(),
    ]


__all__ = [
    "BaseModel",
    "Prediction",
    "LSTMPriceModel",
    "XGBoostSignalModel",
    "ProphetTrendModel",
    "RandomForestRiskModel",
    "all_models",
]
