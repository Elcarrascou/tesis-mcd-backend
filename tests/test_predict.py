"""Tests del endpoint /predict/{symbol}.

Se mockea Yahoo y los modelos: el CI no debe depender de la red ni de correr
torch/prophet de verdad. Aquí se valida el contrato del endpoint (forma de la
respuesta, manejo de errores), no la calidad de las predicciones.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api import predict as predict_mod
from app.main import app
from app.models.base import Prediction

client = TestClient(app)


class _FakeModel:
    name = "fake"

    def predict_one(self, symbol: str, df: pd.DataFrame) -> Prediction:
        return Prediction(
            model=self.name,
            symbol=symbol,
            prediction_type="signal",
            signal="buy",
            confidence=80.0,
            horizon_days=5,
        )


def _fake_df() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    return pd.DataFrame({"Close": range(10)}, index=idx)


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setattr(predict_mod, "get_history", lambda *a, **k: _fake_df())
    monkeypatch.setattr(predict_mod, "_models", lambda: [_FakeModel()])


def test_predict_ok():
    r = client.get("/predict/nvda")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "NVDA"  # normaliza a mayúsculas
    assert body["predictions"][0]["signal"] == "buy"
    assert body["errors"] == {}


def test_predict_empty_data(monkeypatch):
    monkeypatch.setattr(predict_mod, "get_history", lambda *a, **k: pd.DataFrame())
    r = client.get("/predict/ZZZZ")
    assert r.status_code == 404
