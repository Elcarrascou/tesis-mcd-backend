"""Ingesta de datos de mercado desde Yahoo Finance (gratis, vía yfinance).

Materia prima de toda la tesis. El resto del sistema pide históricos aquí sin
preocuparse de cómo se descargan.
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf


def get_history(symbol: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """Histórico OHLCV ajustado. Columnas: Open, High, Low, Close, Volume.

    period: '6mo', '1y', '2y', '5y', 'max'…
    interval: '1d', '1wk', '1mo'…
    """
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval, auto_adjust=True)
    if df.empty:
        raise ValueError(f"Sin datos para el símbolo '{symbol}'")
    return df.dropna()


def get_quote(symbol: str) -> dict:
    """Cotización puntual: último precio y variación % vs cierre anterior."""
    df = get_history(symbol, period="5d", interval="1d")
    last = float(df["Close"].iloc[-1])
    prev = float(df["Close"].iloc[-2]) if len(df) > 1 else last
    change_pct = (last - prev) / prev * 100 if prev else 0.0
    return {"symbol": symbol.upper(), "price": last, "change_pct": change_pct}
