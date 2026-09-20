# Nobitex Entry Manager
# Free GitHub Actions + cron-job.org scheduler
# Telegram commands:
# /addlong SYMBOL
# /addshort SYMBOL
# /remove SYMBOL
# /removeall
# /remove all
# /watchlist

import os
import json
import urllib.request
import urllib.parse
from pathlib import Path

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STATE_FILE = Path("entry_watchlist_state.json")
OFFSET_FILE = Path("telegram_offset.json")


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def send_message(text, chat_id=None):
    data = urllib.parse.urlencode({
        "chat_id": chat_id or CHAT_ID,
        "text": text
    }).encode()

    urllib.request.urlopen(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=data,
        timeout=10
    )


def load_state():
    return load_json(STATE_FILE, {"long": {}, "short": {}})


def save_state(state):
    save_json(STATE_FILE, state)


def add_symbol(direction, symbol):
    state = load_state()
    symbol = symbol.upper()

    state[direction][symbol] = {
        "status": "waiting",
        "confirm_candles": 0
    }

    other = "short" if direction == "long" else "long"
    state[other].pop(symbol, None)

    save_state(state)


def remove_symbol(symbol):
    state = load_state()
    symbol = symbol.upper()

    state["long"].pop(symbol, None)
    state["short"].pop(symbol, None)

    save_state(state)


def remove_all():
    state = load_state()

    long_count = len(state.get("long", {}))
    short_count = len(state.get("short", {}))

    state["long"] = {}
    state["short"] = {}

    save_state(state)

    return long_count, short_count


def watchlist():
    state = load_state()
    lines = ["🎯 Entry Watchlist", "", "🟢 LONG"]

    if state["long"]:
        for s, v in state["long"].items():
            mark = "✅" if v["status"] == "confirmed" else "⏳"
            lines.append(f"{s} {mark}")
    else:
        lines.append("خالی")

    lines += ["", "🔴 SHORT"]

    if state["short"]:
        for s, v in state["short"].items():
            mark = "✅" if v["status"] == "confirmed" else "⏳"
            lines.append(f"{s} {mark}")
    else:
        lines.append("خالی")

    return "\n".join(lines)


def handle(text):
    parts = text.split()

    if not parts:
        return None

    cmd = parts[0].lower()

    if cmd == "/watchlist":
        return watchlist()

    if cmd == "/addlong" and len(parts) == 2:
        add_symbol("long", parts[1])
        return f"✅ {parts[1].upper()} اضافه شد\n🟢 LONG"

    if cmd == "/addshort" and len(parts) == 2:
        add_symbol("short", parts[1])
        return f"✅ {parts[1].upper()} اضافه شد\n🔴 SHORT"

    if cmd == "/removeall" and len(parts) == 1:
        long_count, short_count = remove_all()
        return (
            "✅ کل Entry Watchlist پاک شد\n"
            f"🟢 LONG حذف‌شده: {long_count}\n"
            f"🔴 SHORT حذف‌شده: {short_count}"
        )

    if (
        cmd == "/remove"
        and len(parts) == 2
        and parts[1].lower() == "all"
    ):
        long_count, short_count = remove_all()
        return (
            "✅ کل Entry Watchlist پاک شد\n"
            f"🟢 LONG حذف‌شده: {long_count}\n"
            f"🔴 SHORT حذف‌شده: {short_count}"
        )

    if cmd == "/remove" and len(parts) == 2:
        remove_symbol(parts[1])
        return f"✅ {parts[1].upper()} حذف شد"

    return None


def main():
    offset = load_json(OFFSET_FILE, {"offset": 0})["offset"]

    url = (
        f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        f"?timeout=1&offset={offset}"
    )

    data = json.loads(
        urllib.request.urlopen(url, timeout=10).read()
    )

    for update in data.get("result", []):
        offset = update["update_id"] + 1
        msg = update.get("message", {})
        text = msg.get("text")

        if text:
            answer = handle(text)
            if answer:
                send_message(answer, msg["chat"]["id"])

    save_json(OFFSET_FILE, {"offset": offset})


if __name__ == "__main__":
    main()
