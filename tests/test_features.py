import numpy as np
import pandas as pd

from app.data.features import compute_features


def _fake_history(n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({"Close": close})


def test_compute_features_keys():
    feats = compute_features(_fake_history())
    assert set(feats) == {
        "days",
        "rsi14",
        "sma20",
        "sma50",
        "vol_annual_pct",
        "momentum20_pct",
        "max_drawdown_pct",
    }
    assert feats["days"] == 120
    assert 0 <= feats["rsi14"] <= 100
