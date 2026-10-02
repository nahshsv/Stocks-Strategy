from __future__ import annotations
import json
from pathlib import Path

STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)


def load_state(filename: str, default: dict) -> dict:
    path = STATE_DIR / filename
    if not path.exists():
        return default.copy()

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default.copy()


def save_state(filename: str, state: dict) -> None:
    path = STATE_DIR / filename
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True),
        encoding="utf-8",
    )
