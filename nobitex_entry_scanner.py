
# v24 Final Integrated
# - Nobitex 4H closed candles
# - EMA20 confirmation
# - Telegram alerts
# - Change detection
# - First run baseline (no alert)
# - Long/Short grouping

import os, json, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime, timedelta, timezone

STATE_FILE = Path("entry_watchlist_state.json")
REPORT_FILE = Path("entry_last_report.json")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BASE_URL = "https://apiv2.nobitex.ir"
TEHRAN = timezone(timedelta(hours=3, minutes=30))


def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def telegram(text):
    if not TOKEN or not CHAT_ID:
        return
    body = json.dumps({"chat_id": CHAT_ID, "text": text}, ensure_ascii=False).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=10)


def ema(values, length=20):
    if len(values) < length:
        return None
    a = 2 / (length + 1)
    result = values[0]
    for v in values[1:]:
        result = a * v + (1-a) * result
    return result


def fetch(symbol):
    now = datetime.now(timezone.utc)
    url = BASE_URL + "/market/udf/history?" + urllib.parse.urlencode({
        "symbol": symbol,
        "resolution": "240",
        "from": int(now.timestamp()) - 150 * 14400,
        "to": int(now.timestamp())
    })
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.loads(r.read().decode())

    candles = []
    now_teh = now.astimezone(TEHRAN)

    for i, ts in enumerate(data.get("t", [])):
        start = datetime.fromtimestamp(int(ts), timezone.utc).astimezone(TEHRAN)
        end = start + timedelta(hours=4)
        if end <= now_teh:
            candles.append({
                "close": float(data["c"][i]),
                "range": f"{start:%H}-{end:%H}"
            })
    return candles


def scan_item(direction, item):
    candles = fetch(item["symbol"])
    closes = [x["close"] for x in candles]
    e20 = ema(closes)

    if e20 is None:
        return

    ok = closes[-1] > e20 if direction == "long" else closes[-1] < e20

    if ok:
        item["status"] = "confirmed"
        item["confirm_candles"] = item.get("confirm_candles", 0) + 1
    else:
        item["status"] = "waiting"
        item["confirm_candles"] = 0

    item["candle"] = candles[-1]["range"]


def snapshot(state):
    out = {}
    for d in ["long", "short"]:
        for s, item in state[d].items():
            out[s] = {
                "direction": d,
                "status": item.get("status"),
                "confirm_candles": item.get("confirm_candles", 0)
            }
    return out


def report_changes(state):
    new = snapshot(state)
    old = load(REPORT_FILE, None)

    if old is None:
        save(REPORT_FILE, new)
        return

    changes = []
    for symbol, val in new.items():
        if old.get(symbol) != val:
            changes.append((symbol, val))

    save(REPORT_FILE, new)

    if not changes:
        return

    all_items = (
        list(state.get("long", {}).values())
        + list(state.get("short", {}).values())
    )

    if not all_items:
        return

    candle = all_items[0].get("candle", "نامشخص")

    lines = [
        "🎯 Entry Watch 4H",
        f"کندل: {candle} تهران",
        "",
    ]

    for direction, title in [("long", "🟢 LONG"), ("short", "🔴 SHORT")]:
        selected = [x for x in changes if x[1]["direction"] == direction]
        if selected:
            lines.append(title)
            for symbol, item in selected:
                mark = "✅" if item["status"] == "confirmed" else "⏳"
                lines.append(f"{symbol} {mark} ({item['confirm_candles']})")

    telegram("\n".join(lines))


def main():
    state = load(STATE_FILE, {"long": {}, "short": {}})
    for d in ["long", "short"]:
        for symbol, item in state[d].items():
            item["symbol"] = symbol
            scan_item(d, item)

    save(STATE_FILE, state)
    report_changes(state)


if __name__ == "__main__":
    main()
