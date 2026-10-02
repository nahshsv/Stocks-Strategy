from __future__ import annotations

import os
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

from indicators import rsi, wma, atr, crossed_above, crossed_below
from market_data import get_bars
from state_utils import load_state, save_state
from telegram_utils import send_message


STATE_FILE = "trading_state.json"


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["trading"]


def is_us_market_open() -> bool:
    now = datetime.now(ZoneInfo("America/New_York"))

    if now.weekday() >= 5:
        return False

    return dtime(9, 30) <= now.time() <= dtime(16, 0)


def timeframe_status(df: pd.DataFrame, rsi_period: int, wma_period: int) -> dict:
    r = rsi(df["Close"], rsi_period)
    r_wma = wma(r, wma_period)

    merged = pd.concat(
        [r.rename("rsi"), r_wma.rename("wma")],
        axis=1,
    ).dropna()

    if len(merged) < 2:
        return {"ready": False}

    latest = merged.iloc[-1]

    return {
        "ready": True,
        "rsi": float(latest["rsi"]),
        "wma": float(latest["wma"]),
        "bullish": bool(latest["rsi"] > latest["wma"]),
        "fresh_up": crossed_above(r, r_wma),
        "fresh_down": crossed_below(r, r_wma),
    }


def daily_trend(symbol: str, is_crypto: bool, cfg: dict) -> dict:
    daily = get_bars(symbol, "1d")
    close = daily["Close"]

    fast = close.rolling(int(cfg["daily_sma_fast"])).mean()
    slow = close.rolling(int(cfg["daily_sma_slow"])).mean()

    latest_price = float(close.iloc[-1])
    passed = bool(
        latest_price > fast.iloc[-1]
        and fast.iloc[-1] > slow.iloc[-1]
    )

    result = {
        "price": latest_price,
        "fast_sma": float(fast.iloc[-1]),
        "slow_sma": float(slow.iloc[-1]),
        "passed": passed,
        "relative_strength": None,
    }

    if not is_crypto:
        benchmark = cfg["stock_relative_strength_vs"]
        spy = get_bars(benchmark, "1d")
        lookback = int(cfg["stock_relative_strength_days"])

        stock_ret = close.pct_change(lookback).iloc[-1]
        spy_ret = spy["Close"].pct_change(lookback).iloc[-1]
        relative_strength = float(stock_ret - spy_ret)

        result["relative_strength"] = relative_strength
        result["passed"] = bool(
            result["passed"]
            and relative_strength > 0
        )

    return result


def position_size(account_equity: float, entry: float, stop: float, cfg: dict) -> dict:
    max_sleeve = account_equity * float(cfg["max_trading_sleeve_pct"])
    risk_budget = account_equity * float(cfg["risk_per_trade_pct"])

    stop_pct = (entry - stop) / entry
    raw_position = risk_budget / stop_pct

    position_dollars = min(raw_position, max_sleeve)
    shares = position_dollars / entry

    return {
        "max_sleeve": max_sleeve,
        "risk_budget": risk_budget,
        "position_dollars": position_dollars,
        "shares": shares,
        "risk_pct": stop_pct,
    }


def scan_symbol(symbol: str, is_crypto: bool, cfg: dict, state: dict, account_equity: float):
    tf_data = {}

    for tf in cfg["timeframes"]:
        bars = get_bars(symbol, tf)
        status = timeframe_status(
            bars,
            int(cfg["rsi_period"]),
            int(cfg["rsi_wma_period"]),
        )

        if not status.get("ready"):
            return

        tf_data[tf] = status

    trigger_tf = cfg["timeframes"][0]
    trigger = tf_data[trigger_tf]

    trend = daily_trend(symbol, is_crypto, cfg)

    last_state = state.get(symbol, "NEUTRAL")

    # BUY:
    # - daily trend passes
    # - all selected timeframes have RSI > RSI-WMA
    # - fresh bullish crossover on the trigger timeframe
    buy_signal = (
        trend["passed"]
        and all(x["bullish"] for x in tf_data.values())
        and trigger["fresh_up"]
    )

    # SELL/EXIT alert:
    # - only if we previously alerted BUY
    # - fresh bearish crossover on trigger timeframe
    sell_signal = (
        last_state == "BUY"
        and trigger["fresh_down"]
    )

    if not buy_signal and not sell_signal:
        return

    signal = "BUY" if buy_signal else "SELL"

    if signal == last_state:
        return

    trigger_bars = get_bars(symbol, trigger_tf)
    entry = float(trigger_bars["Close"].iloc[-1])

    a = atr(
        trigger_bars,
        int(cfg["stop"]["atr_period"]),
    ).dropna()

    if a.empty:
        return

    stop = entry - float(cfg["stop"]["atr_multiple"]) * float(a.iloc[-1])

    if signal == "BUY":
        sizing = position_size(
            account_equity,
            entry,
            stop,
            cfg,
        )

        tf_lines = "\n".join(
            [
                f"{tf}: RSI {v['rsi']:.1f} / WMA45 {v['wma']:.1f} ✅"
                for tf, v in tf_data.items()
            ]
        )

        rs_text = (
            "N/A for BTC"
            if is_crypto
            else f"{trend['relative_strength']:.2%} vs SPY"
        )

        msg = (
            f"🟢 *TRADING BOT — BUY*\n\n"
            f"*{symbol}*\n"
            f"Strategy: RSI(14) crossover WMA(45)\n\n"
            f"{tf_lines}\n\n"
            f"Daily trend: ✅\n"
            f"Relative strength: {rs_text}\n\n"
            f"Entry: ${entry:,.2f}\n"
            f"Stop: ${stop:,.2f}\n"
            f"Position size: ${sizing['position_dollars']:,.2f}\n"
            f"Units/shares: {sizing['shares']:.6f}\n"
            f"Risk budget: ${sizing['risk_budget']:.2f}\n"
            f"Trading sleeve cap: ${sizing['max_sleeve']:.2f}\n\n"
            f"Signal only — no real order placed."
        )
    else:
        msg = (
            f"🔴 *TRADING BOT — EXIT ALERT*\n\n"
            f"*{symbol}*\n"
            f"{trigger_tf} RSI crossed below WMA(45).\n"
            f"Current price: ${entry:,.2f}\n\n"
            f"Review the position / stop. "
            f"Signal only — no real order placed."
        )

    send_message("trading", msg)
    state[symbol] = signal


def main():
    cfg = load_config()

    if not cfg.get("enabled", True):
        return

    account_equity = float(
        os.getenv(
            "TRADING_ACCOUNT_EQUITY",
            cfg["account_equity_default"],
        )
    )

    state = load_state(STATE_FILE, {})

    stocks = cfg["symbols"]["stocks"]
    cryptos = cfg["symbols"]["crypto"]

    # BTC runs 24/7.
    for symbol in cryptos:
        try:
            scan_symbol(
                symbol=symbol,
                is_crypto=True,
                cfg=cfg,
                state=state,
                account_equity=account_equity,
            )
        except Exception as exc:
            print(f"[BTC ERROR] {symbol}: {exc}")

    # Stocks only during regular hours if enabled.
    allow_stocks = (
        not cfg.get("stocks_only_during_market_hours", True)
        or is_us_market_open()
    )

    if allow_stocks:
        for symbol in stocks:
            try:
                scan_symbol(
                    symbol=symbol,
                    is_crypto=False,
                    cfg=cfg,
                    state=state,
                    account_equity=account_equity,
                )
            except Exception as exc:
                print(f"[STOCK ERROR] {symbol}: {exc}")
    else:
        print("NYSE regular session closed; stock scan skipped.")

    save_state(STATE_FILE, state)


if __name__ == "__main__":
    main()
