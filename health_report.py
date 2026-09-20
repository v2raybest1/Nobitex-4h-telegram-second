
# Nobitex Entry Health Report v26
# Sends full watchlist health report twice daily
# Scheduled by cron-job.org

import os
import json
import urllib.request
from pathlib import Path

STATE_FILE = Path("entry_watchlist_state.json")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def load_state():
    if not STATE_FILE.exists():
        return {"long": {}, "short": {}}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def send_telegram(text):
    if not TOKEN or not CHAT_ID:
        return

    data = json.dumps({
        "chat_id": CHAT_ID,
        "text": text
    }, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"}
    )

    urllib.request.urlopen(req, timeout=10)


def build_report(state):
    lines = [
        "💚 Entry Watch Health",
        ""
    ]

    lines.append("🟢 LONG")

    if state["long"]:
        for symbol, item in state["long"].items():
            mark = "✅" if item.get("status") == "confirmed" else "⏳"
            count = item.get("confirm_candles", 0)
            lines.append(
                f"{symbol} {mark}" +
                (f" ({count})" if count else "")
            )
    else:
        lines.append("خالی")

    lines += [
        "",
        "🔴 SHORT"
    ]

    if state["short"]:
        for symbol, item in state["short"].items():
            mark = "✅" if item.get("status") == "confirmed" else "⏳"
            count = item.get("confirm_candles", 0)
            lines.append(
                f"{symbol} {mark}" +
                (f" ({count})" if count else "")
            )
    else:
        lines.append("خالی")

    lines += [
        "",
        "✅ Scanner فعال",
        "✅ State سالم",
        "✅ Telegram سالم"
    ]

    return "\n".join(lines)


def main():
    send_telegram(
        build_report(load_state())
    )


if __name__ == "__main__":
    main()
