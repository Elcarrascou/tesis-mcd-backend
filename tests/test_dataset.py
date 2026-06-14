import numpy as np
import pandas as pd

from app.ml.dataset import (
    FEATURE_COLS,
    build_feature_matrix,
    make_risk_labels,
    make_signal_labels,
)


def _fake_ohlcv(n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Close": close, "Volume": rng.integers(1_000, 5_000, n)}, index=idx
    )


def test_feature_matrix_columns():
    feats = build_feature_matrix(_fake_ohlcv())
    assert list(feats.columns) == FEATURE_COLS
    assert not feats.isna().any().any()


def test_signal_labels_domain():
    labels = make_signal_labels(_fake_ohlcv())
    assert set(labels.unique()) <= {"buy", "sell", "hold"}


def test_risk_labels_domain():
    labels = make_risk_labels(_fake_ohlcv())
    assert set(labels.unique()) <= {"bajo", "medio", "alto"}
