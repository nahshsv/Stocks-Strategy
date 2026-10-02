from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal
import yaml

from market_data import get_bars
from state_utils import load_state, save_state
from telegram_utils import send_message


STATE_FILE = "longterm_state.json"


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["longterm"]


def now_texas():
    return datetime.now(ZoneInfo("America/Chicago"))


def current_month() -> str:
    return now_texas().strftime("%Y-%m")


def trading_days_left_in_month() -> int:
    now = now_texas()

    next_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1)
    last_day = next_month - timedelta(days=1)

    cal = mcal.get_calendar("NYSE")
    sched = cal.schedule(
        start_date=now.date(),
        end_date=last_day.date(),
    )

    return len(sched)


def deploy_fraction(day_change: float, ladder: list[dict]) -> float:
    """
    Return the strongest matching deployment level.

    Example:
      -0.5% -> 0.25
      -1.0% -> 0.50
      -2.0% -> 1.00
    """
    matches = [
        float(item["deploy_fraction"])
        for item in ladder
        if day_change <= float(item["threshold"])
    ]

    return max(matches) if matches else 0.0


def main():
    cfg = load_config()

    if not cfg.get("enabled", True):
        return

    month = current_month()

    state = load_state(
        STATE_FILE,
        {
            "month": month,
            "allocated": {},
            "alerted_fraction": {},
            "month_end_alerted": {},
        },
    )

    # Reset state automatically when a new month starts.
    if state.get("month") != month:
        state = {
            "month": month,
            "allocated": {},
            "alerted_fraction": {},
            "month_end_alerted": {},
        }

    # Backward compatibility if an older state file exists.
    state.setdefault("allocated", {})
    state.setdefault("alerted_fraction", {})
    state.setdefault("month_end_alerted", {})

    days_left = trading_days_left_in_month()
    monthly_budget = float(cfg["monthly_budget"])

    for symbol, weight in cfg["allocation"].items():
        try:
            target = monthly_budget * float(weight)
            allocated = float(state["allocated"].get(symbol, 0.0))
            remaining = max(0.0, target - allocated)

            if remaining <= 0:
                continue

            daily = get_bars(symbol, "1d")

            if len(daily) < 2:
                continue

            previous_close = float(daily["Close"].iloc[-2])
            current_price = float(daily["Close"].iloc[-1])

            day_change = current_price / previous_close - 1.0

            current_fraction = deploy_fraction(
                day_change,
                cfg["red_day_ladder"],
            )

            previous_alerted_fraction = float(
                state["alerted_fraction"].get(symbol, 0.0)
            )

            amount = 0.0
            reason = ""
            new_fraction_to_record = previous_alerted_fraction

            # -----------------------------------------
            # RED-DAY LADDER
            # -----------------------------------------
            # Alert again only if the market reaches a
            # stronger dip level than already alerted.
            #
            # Example:
            # 10 AM -> -0.6% => 25%
            # 2 PM  -> -1.3% => 50%
            #
            # The second alert recommends only the
            # incremental amount needed to reach 50%.
            # -----------------------------------------
            if current_fraction > previous_alerted_fraction:
                desired_cumulative = target * current_fraction

                amount = max(
                    0.0,
                    min(
                        remaining,
                        desired_cumulative - allocated,
                    ),
                )

                if amount > 0:
                    reason = (
                        f"Red-day level increased: {day_change:.2%} "
                        f"({previous_alerted_fraction:.0%} -> {current_fraction:.0%} of monthly bucket)"
                    )
                    new_fraction_to_record = current_fraction

            # -----------------------------------------
            # MONTH-END FALLBACK
            # -----------------------------------------
            # If no stronger dip appears and there is
            # still money left near month-end, alert once
            # to deploy the remaining ETF bucket.
            # -----------------------------------------
            elif days_left <= int(cfg["force_buy_last_trading_days"]):
                if not bool(state["month_end_alerted"].get(symbol, False)):
                    amount = remaining
                    reason = (
                        f"Month-end DCA fallback "
                        f"({days_left} trading day(s) left)"
                    )

            if amount <= 0:
                continue

            total_monthly_allocated = sum(
                float(v) for v in state["allocated"].values()
            )

            projected_total = min(
                monthly_budget,
                total_monthly_allocated + amount,
            )

            msg = (
                f"🟢 *LONG-TERM BOT — BUY WINDOW*\n\n"
                f"*{symbol}*\n"
                f"Today: {day_change:.2%}\n"
                f"Reason: {reason}\n\n"
                f"Monthly target: ${target:.2f}\n"
                f"Already recorded: ${allocated:.2f}\n"
                f"Remaining bucket: ${remaining:.2f}\n\n"
                f"Suggested buy now: *${amount:.2f}*\n\n"
                f"Projected monthly total if purchased: "
                f"${projected_total:.2f} / ${monthly_budget:.2f}\n\n"
                f"Signal only — buy manually, then record the purchase."
            )

            send_message("longterm", msg)

            # Record alert level so the 2 PM run does not repeat
            # the same red-day level seen at 10 AM.
            if current_fraction > previous_alerted_fraction:
                state["alerted_fraction"][symbol] = new_fraction_to_record

            # Month-end fallback should alert only once per symbol.
            if (
                days_left <= int(cfg["force_buy_last_trading_days"])
                and current_fraction <= previous_alerted_fraction
            ):
                state["month_end_alerted"][symbol] = True

        except Exception as exc:
            print(f"[LONGTERM ERROR] {symbol}: {exc}")

    save_state(STATE_FILE, state)


if __name__ == "__main__":
    main()
