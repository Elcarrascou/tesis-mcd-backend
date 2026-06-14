"""Prophet (Meta) — tendencia y estacionalidad.

Prophet ajusta una serie a la vez, así que el modelo se reentrena por símbolo en
`predict_one` (es barato). `fit`/`save`/`load` no persisten estado global.

Nota Windows: cmdstanpy necesita `tbb.dll` en el PATH para correr el modelo Stan
compilado que trae Prophet. Si falta, falla con un error enmascarado por la
codificación local. `_ensure_tbb_on_path()` la agrega automáticamente.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path


def _ensure_tbb_on_path() -> None:
    """En Windows, agrega el directorio de tbb.dll (bundled en Prophet) al PATH."""
    if os.name != "nt":
        return
    import prophet  # noqa: PLC0415

    base = Path(prophet.__file__).parent / "stan_model"
    for tbb_dir in base.glob("cmdstan-*/stan/lib/stan_math/lib/tbb"):
        os.environ["PATH"] = str(tbb_dir) + os.pathsep + os.environ.get("PATH", "")
        try:
            os.add_dll_directory(str(tbb_dir))
        except (AttributeError, OSError):
            pass
        break


_ensure_tbb_on_path()

import pandas as pd  # noqa: E402
from prophet import Prophet  # noqa: E402

from app.models.base import ARTIFACTS_DIR, BaseModel, Prediction  # noqa: E402

# Prophet/cmdstanpy son ruidosos: bajar el nivel de log.
logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

HORIZON = 30


class ProphetTrendModel(BaseModel):
    name = "prophet"
    prediction_type = "trend"

    def fit(self, datasets: dict[str, pd.DataFrame]) -> None:
        # Prophet se ajusta por serie en inferencia; nada global que entrenar.
        return None

    def predict_one(self, symbol: str, df: pd.DataFrame) -> Prediction:
        ds = pd.to_datetime(df.index)
        if ds.tz is not None:
            ds = ds.tz_localize(None)
        dfp = pd.DataFrame({"ds": ds, "y": df["Close"].to_numpy()})

        m = Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=True)
        m.fit(dfp)
        future = m.make_future_dataframe(periods=HORIZON)
        fc = m.predict(future).iloc[-1]

        last_close = float(df["Close"].iloc[-1])
        yhat = float(fc["yhat"])
        width = float(fc["yhat_upper"] - fc["yhat_lower"])
        conf = 100 * (1 - width / (2 * abs(yhat))) if yhat else 50.0
        conf = float(min(95.0, max(50.0, conf)))

        return Prediction(
            model=self.name,
            symbol=symbol,
            prediction_type=self.prediction_type,
            predicted_value=round(yhat, 4),
            signal="up" if yhat >= last_close else "down",
            confidence=round(conf, 2),
            horizon_days=HORIZON,
        )

    def save(self, directory: Path = ARTIFACTS_DIR) -> None:
        directory.mkdir(parents=True, exist_ok=True)

    def load(self, directory: Path = ARTIFACTS_DIR) -> None:
        return None
