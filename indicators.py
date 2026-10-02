from __future__ import annotations
import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.where(avg_loss != 0, 100.0)


def wma(series: pd.Series, period: int) -> pd.Series:
    weights = np.arange(1, period + 1, dtype=float)

    def calc(x):
        return float(np.dot(x, weights) / weights.sum())

    return series.rolling(period).apply(calc, raw=True)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def crossed_above(a: pd.Series, b: pd.Series) -> bool:
    x = pd.concat([a, b], axis=1).dropna()
    if len(x) < 2:
        return False
    return bool(x.iloc[-2, 0] <= x.iloc[-2, 1] and x.iloc[-1, 0] > x.iloc[-1, 1])


def crossed_below(a: pd.Series, b: pd.Series) -> bool:
    x = pd.concat([a, b], axis=1).dropna()
    if len(x) < 2:
        return False
    return bool(x.iloc[-2, 0] >= x.iloc[-2, 1] and x.iloc[-1, 0] < x.iloc[-1, 1])
