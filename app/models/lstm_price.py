"""LSTM (PyTorch) — predicción de precio futuro.

Modelo global entrenado sobre secuencias de retornos diarios de todos los
símbolos. Predice el retorno a `HORIZON` días y lo convierte a precio objetivo.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

from app.models.base import ARTIFACTS_DIR, BaseModel, Prediction

SEQ_LEN = 30
HORIZON = 5
torch.manual_seed(42)


def _build_sequences(df: pd.DataFrame, seq_len: int, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    close = df["Close"]
    ret = close.pct_change().dropna()
    fwd = close.shift(-horizon) / close - 1
    X, y = [], []
    vals = ret.to_numpy()
    for p in range(seq_len - 1, len(ret)):
        day = ret.index[p]
        target = fwd.loc[day]
        if pd.isna(target):
            continue
        X.append(vals[p - seq_len + 1 : p + 1])
        y.append(float(target))
    if not X:
        return np.empty((0, seq_len)), np.empty((0,))
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


class _Net(nn.Module):
    def __init__(self, hidden: int = 32) -> None:
        super().__init__()
        self.lstm = nn.LSTM(input_size=1, hidden_size=hidden, batch_first=True)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # x: [B, L, 1]
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)


class LSTMPriceModel(BaseModel):
    name = "lstm"
    prediction_type = "price"

    def __init__(self) -> None:
        self.net = _Net()
        self.x_mean = 0.0
        self.x_std = 1.0
        self.y_mean = 0.0
        self.y_std = 1.0
        self.dir_acc = 50.0  # precisión direccional en validación (%)

    def fit(self, datasets: dict[str, pd.DataFrame], epochs: int = 25) -> None:
        Xs, ys = [], []
        for df in datasets.values():
            X, y = _build_sequences(df, SEQ_LEN, HORIZON)
            if len(X):
                Xs.append(X)
                ys.append(y)
        if not Xs:
            raise ValueError("Sin datos para entrenar LSTM")
        X = np.concatenate(Xs)
        y = np.concatenate(ys)

        # Estandarización (guardada para inferencia).
        self.x_mean, self.x_std = float(X.mean()), float(X.std() or 1.0)
        self.y_mean, self.y_std = float(y.mean()), float(y.std() or 1.0)
        Xn = (X - self.x_mean) / self.x_std
        yn = (y - self.y_mean) / self.y_std

        # Split temporal 85/15.
        cut = int(len(Xn) * 0.85)
        xt = torch.tensor(Xn[:cut]).unsqueeze(-1)
        yt = torch.tensor(yn[:cut])
        xv = torch.tensor(Xn[cut:]).unsqueeze(-1)

        opt = torch.optim.Adam(self.net.parameters(), lr=1e-3)
        loss_fn = nn.MSELoss()
        self.net.train()
        for _ in range(epochs):
            opt.zero_grad()
            loss = loss_fn(self.net(xt), yt)
            loss.backward()
            opt.step()

        # Precisión direccional en validación (acierto de signo) → confianza.
        self.net.eval()
        with torch.no_grad():
            if len(xv):
                pred_v = self.net(xv).numpy() * self.y_std + self.y_mean
                actual = y[cut:]
                hits = (np.sign(pred_v) == np.sign(actual)) & (actual != 0)
                self.dir_acc = float(np.mean(hits) * 100)
            else:
                self.dir_acc = 50.0

    def predict_one(self, symbol: str, df: pd.DataFrame) -> Prediction:
        ret = df["Close"].pct_change().dropna().to_numpy()[-SEQ_LEN:]
        if len(ret) < SEQ_LEN:
            raise ValueError(f"Histórico insuficiente para LSTM ({symbol})")
        xn = (ret.astype(np.float32) - self.x_mean) / self.x_std
        self.net.eval()
        with torch.no_grad():
            pred_n = self.net(torch.tensor(xn).reshape(1, SEQ_LEN, 1)).item()
        pred_ret = pred_n * self.y_std + self.y_mean
        last_close = float(df["Close"].iloc[-1])
        target_price = last_close * (1 + pred_ret)
        # Confianza = precisión direccional en validación, acotada.
        conf = float(np.clip(self.dir_acc, 50, 95))
        return Prediction(
            model=self.name,
            symbol=symbol,
            prediction_type=self.prediction_type,
            predicted_value=round(target_price, 4),
            signal="up" if pred_ret >= 0 else "down",
            confidence=round(conf, 2),
            horizon_days=HORIZON,
        )

    def _path(self, directory: Path) -> Path:
        return directory / "lstm_price.pt"

    def save(self, directory: Path = ARTIFACTS_DIR) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": self.net.state_dict(),
                "x_mean": self.x_mean,
                "x_std": self.x_std,
                "y_mean": self.y_mean,
                "y_std": self.y_std,
                "dir_acc": self.dir_acc,
            },
            self._path(directory),
        )

    def load(self, directory: Path = ARTIFACTS_DIR) -> None:
        ckpt = torch.load(self._path(directory), weights_only=True)
        self.net.load_state_dict(ckpt["state_dict"])
        self.x_mean = ckpt["x_mean"]
        self.x_std = ckpt["x_std"]
        self.y_mean = ckpt["y_mean"]
        self.y_std = ckpt["y_std"]
        self.dir_acc = ckpt["dir_acc"]
        self.net.eval()
