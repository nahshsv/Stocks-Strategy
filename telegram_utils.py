from __future__ import annotations
import os
import requests


def send_message(bot_type: str, text: str) -> bool:
    """
    bot_type:
      trading  -> TRADING_BOT_TOKEN + TRADING_CHAT_ID
      longterm -> LONGTERM_BOT_TOKEN + LONGTERM_CHAT_ID
    """
    prefix = bot_type.upper()
    token = os.getenv(f"{prefix}_BOT_TOKEN", "")
    chat_id = os.getenv(f"{prefix}_CHAT_ID", "")

    if not token or not chat_id:
        print(f"[{bot_type}] Telegram secrets missing; printing message instead.")
        print(text)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        response = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=15,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        print(f"[Telegram error] {exc}")
        return False
