from __future__ import annotations
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from state_utils import load_state, save_state

STATE_FILE = "longterm_state.json"

parser = argparse.ArgumentParser()
parser.add_argument("symbol")
parser.add_argument("amount", type=float)
args = parser.parse_args()

month = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m")

state = load_state(
    STATE_FILE,
    {
        "month": month,
        "allocated": {},
        "last_alert_date": {},
    },
)

if state.get("month") != month:
    state = {
        "month": month,
        "allocated": {},
        "last_alert_date": {},
    }

symbol = args.symbol.upper()
state["allocated"][symbol] = float(
    state["allocated"].get(symbol, 0.0)
) + args.amount

save_state(STATE_FILE, state)

print(
    f"Recorded ${args.amount:.2f} purchase for {symbol}. "
    f"Month total for {symbol}: ${state['allocated'][symbol]:.2f}"
)
