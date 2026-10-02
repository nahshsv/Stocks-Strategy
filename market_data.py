from __future__ import annotations
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf


def _download(symbol: str, interval: str, days: int) -> pd.DataFrame:
    end = datetime.utcnow() + timedelta(days=1)
    start = end - timedelta(days=days)

    df = yf.download(
        symbol,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
        prepost=False,
    )

    if df is None or df.empty:
        raise RuntimeError(f"No data for {symbol} @ {interval}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def get_bars(symbol: str, timeframe: str) -> pd.DataFrame:
    if timeframe == "30m":
        return _download(symbol, "30m", 60)

    if timeframe == "1h":
        return _download(symbol, "1h", 120)

    if timeframe == "2h":
        hourly = _download(symbol, "1h", 180)
        return hourly.resample("2h").agg(
            {
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum",
            }
        ).dropna()

    if timeframe == "1d":
        return _download(symbol, "1d", 450)

    raise ValueError(f"Unsupported timeframe: {timeframe}")
