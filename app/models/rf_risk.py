"""Random Forest — clasificación de riesgo (bajo/medio/alto)."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from app.ml.dataset import FEATURE_COLS, build_feature_matrix, make_risk_labels
from app.models.base import ARTIFACTS_DIR, BaseModel, Prediction

CLASSES = ["bajo", "medio", "alto"]
HORIZON = 20


class RandomForestRiskModel(BaseModel):
    name = "random_forest"
    prediction_type = "risk"

    def __init__(self) -> None:
        self.clf = RandomForestClassifier(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )

    def fit(self, datasets: dict[str, pd.DataFrame]) -> None:
        X_parts, y_parts = [], []
        for df in datasets.values():
            feats = build_feature_matrix(df)
            labels = make_risk_labels(df, horizon=HORIZON)
            idx = feats.index.intersection(labels.index)
            if idx.empty:
                continue
            X_parts.append(feats.loc[idx, FEATURE_COLS])
            y_parts.append(labels.loc[idx])
        if not X_parts:
            raise ValueError("Sin datos para entrenar Random Forest")
        X = pd.concat(X_parts)
        y = pd.concat(y_parts).astype(str)
        self.clf.fit(X.to_numpy(), y)

    def predict_one(self, symbol: str, df: pd.DataFrame) -> Prediction:
        feats = build_feature_matrix(df)
        x = feats[FEATURE_COLS].to_numpy()[-1:]
        proba = self.clf.predict_proba(x)[0]
        classes = list(self.clf.classes_)
        k = int(np.argmax(proba))
        return Prediction(
            model=self.name,
            symbol=symbol,
            prediction_type=self.prediction_type,
            signal=classes[k],
            confidence=round(float(proba[k]) * 100, 2),
            horizon_days=HORIZON,
        )

    def _path(self, directory: Path) -> Path:
        return directory / "random_forest_risk.joblib"

    def save(self, directory: Path = ARTIFACTS_DIR) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.clf, self._path(directory))

    def load(self, directory: Path = ARTIFACTS_DIR) -> None:
        self.clf = joblib.load(self._path(directory))
