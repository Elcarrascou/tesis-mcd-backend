"""Tests del consolidador del agente (determinista, sin red ni LLM)."""

from __future__ import annotations

from app.agent.consolidate import consolidate
from app.agent.execute import intended_order
from app.models.base import Prediction

_PTYPE = {"lstm": "price", "xgboost": "signal", "prophet": "trend", "random_forest": "risk"}


def _p(model, signal, conf, value=None, h=5):
    ptype = _PTYPE[model]
    return Prediction(
        model=model, symbol="TEST", prediction_type=ptype,
        predicted_value=value, signal=signal, confidence=conf, horizon_days=h,
    )


def _set(lstm, xgb, prophet, risk, conf=70.0):
    return [
        _p("lstm", lstm, conf, value=100.0),
        _p("xgboost", xgb, conf),
        _p("prophet", prophet, conf, value=100.0),
        _p("random_forest", risk, 60.0),
    ]


def test_all_bullish_buy():
    c = consolidate("TEST", _set("up", "buy", "up", "bajo"))
    assert c.action == "buy"
    assert c.score > 0.15
    assert 40.0 <= c.confidence <= 95.0


def test_all_bearish_sell():
    c = consolidate("TEST", _set("down", "sell", "down", "bajo"))
    assert c.action == "sell"
    assert c.score < -0.15


def test_weak_high_risk_rebalance():
    # señales que casi se cancelan + riesgo alto → rebalance
    c = consolidate("TEST", _set("up", "hold", "down", "alto", conf=50.0))
    assert abs(c.score) < 0.15
    assert c.action == "rebalance"


def test_weak_low_risk_hold():
    c = consolidate("TEST", _set("up", "hold", "down", "bajo", conf=50.0))
    assert abs(c.score) < 0.15
    assert c.action == "hold"


def test_confidence_bounds_and_row():
    c = consolidate("TEST", _set("up", "buy", "up", "bajo"))
    row = c.to_row(engine="rule-based")
    assert set(row) == {"symbol", "action", "confidence", "rationale", "engine"}
    assert row["action"] in {"buy", "sell", "hold", "rebalance"}
    assert 0 <= row["confidence"] <= 100


def test_intended_order_stub():
    buy = consolidate("TEST", _set("up", "buy", "up", "bajo"))
    order = intended_order(buy)
    assert order["status"] == "intended"
    assert order["broker"] is None  # nunca toca un broker real
    assert order["side"] == "buy"

    hold = consolidate("TEST", _set("up", "hold", "down", "bajo", conf=50.0))
    assert intended_order(hold) is None  # hold no genera orden


def test_missing_random_forest_defaults_medio():
    preds = [_p("lstm", "up", 70.0, value=100.0), _p("xgboost", "buy", 70.0)]
    c = consolidate("TEST", preds)
    assert c.risk == "medio"
    assert c.action == "buy"
