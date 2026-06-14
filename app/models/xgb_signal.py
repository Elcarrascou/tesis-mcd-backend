"""XGBoost — señal de compra/venta (clasificación)."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from app.ml.dataset import FEATURE_COLS, build_feature_matrix, make_signal_labels
from app.models.base import ARTIFACTS_DIR, BaseModel, Prediction

CLASSES = ["sell", "hold", "buy"]  # índices 0,1,2
HORIZON = 5


class XGBoostSignalModel(BaseModel):
    name = "xgboost"
    prediction_type = "signal"

    def __init__(self) -> None:
        self.clf = XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="multi:softprob",
            num_class=3,
            eval_metric="mlogloss",
            tree_method="hist",
        )

    def fit(self, datasets: dict[str, pd.DataFrame]) -> None:
        X_parts, y_parts = [], []
        for df in datasets.values():
            feats = build_feature_matrix(df)
            labels = make_signal_labels(df, horizon=HORIZON)
            idx = feats.index.intersection(labels.index)
            if idx.empty:
                continue
            X_parts.append(feats.loc[idx, FEATURE_COLS])
            y_parts.append(labels.loc[idx])
        if not X_parts:
            raise ValueError("Sin datos para entrenar XGBoost")
        X = pd.concat(X_parts)
        y = pd.Categorical(pd.concat(y_parts), categories=CLASSES).codes
        self.clf.fit(X.to_numpy(), y)

    def predict_one(self, symbol: str, df: pd.DataFrame) -> Prediction:
        feats = build_feature_matrix(df)
        x = feats[FEATURE_COLS].to_numpy()[-1:]
        proba = self.clf.predict_proba(x)[0]
        k = int(np.argmax(proba))
        return Prediction(
            model=self.name,
            symbol=symbol,
            prediction_type=self.prediction_type,
            signal=CLASSES[k],
            confidence=round(float(proba[k]) * 100, 2),
            horizon_days=HORIZON,
        )

    def _path(self, directory: Path) -> Path:
        return directory / "xgboost_signal.joblib"

    def save(self, directory: Path = ARTIFACTS_DIR) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.clf, self._path(directory))

    def load(self, directory: Path = ARTIFACTS_DIR) -> None:
        self.clf = joblib.load(self._path(directory))
