"""Consolidación de las 4 predicciones ML en una decisión unificada.

Lógica determinista y explicable (sin LLM): combina las señales direccionales de
LSTM, XGBoost y Prophet en un *score* en [-1, 1], modulado por el riesgo del
Random Forest, y la traduce en una acción (`buy`/`sell`/`hold`/`rebalance`) con
una confianza y un razonamiento base.

El LLM (ver `llm_router.py`) solo *reescribe* este razonamiento en lenguaje
natural; la decisión en sí nace aquí, así es auditable y reproducible para el
comité.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.base import Prediction

# Peso de cada modelo en el voto direccional (suman 1). El Random Forest no vota
# dirección: gobierna el riesgo (multiplicador de confianza / tamaño).
DIR_WEIGHTS: dict[str, float] = {"lstm": 0.35, "xgboost": 0.40, "prophet": 0.25}

# Voto direccional según la señal de cada modelo.
SIGNAL_VOTE: dict[str, float] = {
    "buy": 1.0, "up": 1.0,
    "sell": -1.0, "down": -1.0,
    "hold": 0.0,
}

# Multiplicador de confianza según el riesgo (Random Forest).
RISK_MULT: dict[str, float] = {"bajo": 1.0, "medio": 0.85, "alto": 0.6}

BUY_THRESHOLD = 0.15  # |score| mínimo para actuar (señales suelen ser débiles)


@dataclass
class Consolidation:
    """Decisión unificada por activo (mapea a la tabla ai_decisions)."""

    symbol: str
    action: str  # buy | sell | hold | rebalance
    confidence: float  # 0-100
    score: float  # [-1, 1], dirección+fuerza del consenso
    risk: str  # bajo | medio | alto
    rationale: str  # razonamiento determinista base
    details: dict = field(default_factory=dict)

    def to_row(self, engine: str, rationale: str | None = None) -> dict:
        """Fila para insertar en ai_decisions."""
        return {
            "symbol": self.symbol,
            "action": self.action,
            "confidence": round(self.confidence, 2),
            "rationale": rationale or self.rationale,
            "engine": engine,
        }


def _by_model(preds: list[Prediction]) -> dict[str, Prediction]:
    return {p.model: p for p in preds}


def consolidate(symbol: str, preds: list[Prediction]) -> Consolidation:
    """Fusiona las predicciones de un activo en una decisión unificada."""
    m = _by_model(preds)
    risk = (m["random_forest"].signal if "random_forest" in m else "medio") or "medio"
    risk_mult = RISK_MULT.get(risk, 0.85)

    # Voto direccional ponderado por confianza de cada modelo.
    num = 0.0
    den = 0.0
    agree_dir: list[float] = []
    for name, w in DIR_WEIGHTS.items():
        if name not in m:
            continue
        p = m[name]
        vote = SIGNAL_VOTE.get((p.signal or "hold").lower(), 0.0)
        conf = (p.confidence or 50.0) / 100.0
        num += w * conf * vote
        den += w
        if vote != 0.0:
            agree_dir.append(vote)
    score = round(num / den, 3) if den else 0.0

    # Acción según score y riesgo.
    if score >= BUY_THRESHOLD:
        action = "buy"
    elif score <= -BUY_THRESHOLD:
        action = "sell"
    elif risk == "alto":
        action = "rebalance"  # sin dirección clara + riesgo alto → reducir exposición
    else:
        action = "hold"

    # Confianza: promedio de confianzas direccionales * acuerdo * riesgo.
    confs = [(m[n].confidence or 50.0) for n in DIR_WEIGHTS if n in m]
    base_conf = sum(confs) / len(confs) if confs else 50.0
    if agree_dir:
        final_sign = 1.0 if score >= 0 else -1.0
        agreement = sum(1 for v in agree_dir if v == final_sign) / len(agree_dir)
    else:
        agreement = 0.5
    confidence = float(min(95.0, max(40.0, base_conf * (0.5 + 0.5 * agreement) * risk_mult)))

    details = {
        "lstm": _summ(m.get("lstm")),
        "xgboost": _summ(m.get("xgboost")),
        "prophet": _summ(m.get("prophet")),
        "random_forest": _summ(m.get("random_forest")),
        "score": round(score, 3),
        "risk": risk,
    }
    rationale = _rationale(symbol, action, score, risk, confidence, m)
    return Consolidation(symbol, action, confidence, score, risk, rationale, details)


def _summ(p: Prediction | None) -> dict | None:
    if p is None:
        return None
    return {
        "signal": p.signal,
        "value": p.predicted_value,
        "confidence": p.confidence,
        "horizon_days": p.horizon_days,
    }


def _rationale(symbol: str, action: str, score: float, risk: str, conf: float, m: dict) -> str:
    """Razonamiento determinista (base para el LLM o fallback directo)."""
    parts: list[str] = []
    if "lstm" in m:
        s = m["lstm"].signal
        parts.append(f"LSTM proyecta precio {'al alza' if s == 'up' else 'a la baja'}")
    if "prophet" in m:
        s = m["prophet"].signal
        parts.append(f"Prophet ve tendencia {'alcista' if s == 'up' else 'bajista'} a 30d")
    if "xgboost" in m:
        parts.append(f"XGBoost señala '{m['xgboost'].signal}'")
    if "random_forest" in m:
        parts.append(f"riesgo {risk}")
    detalle = "; ".join(parts)
    return (
        f"{symbol}: {detalle}. Score unificado {score:+.2f} → "
        f"{action.upper()} (confianza {conf:.0f}%)."
    )
