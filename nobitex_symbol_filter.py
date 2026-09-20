import json
import os
import statistics
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE_URL = "https://apiv2.nobitex.ir"


def api_get(path, params=None):
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Nobitex-Symbol-Filter"}
    )

    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def telegram_send(text):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text[:4000]
    }).encode()

    urllib.request.urlopen(
        urllib.request.Request(url, data=data),
        timeout=20
    )


def get_usdt_symbols():
    data = api_get("/market/stats")

    raw = data.get("stats", {})

    print("RAW SYMBOL COUNT:", len(raw))

    symbols = []

    for s in raw.keys():
        if isinstance(s, str) and s.lower().endswith("-usdt"):
            symbols.append(
                s.replace("-", "").upper()
            )

    print("USDT SYMBOLS:", symbols)
    return sorted(set(symbols))


def get_candles(symbol):
    now = datetime.now(timezone.utc)

    params = {
        "symbol": symbol.lower(),
        "resolution": "60",
        "from": int(now.timestamp()) - 60 * 86400,
        "to": int(now.timestamp())
    }

    data = api_get("/market/udf/history", params)

    candles = []

    for i in range(len(data.get("t", []))):
        candles.append({
            "high": float(data["h"][i]),
            "low": float(data["l"][i]),
            "close": float(data["c"][i]),
            "volume": float(data["v"][i])
        })

    return candles


def atr_percent(candles):
    trs = []

    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i-1]["close"]

        trs.append(max(h-l, abs(h-pc), abs(l-pc)))

    return statistics.mean(trs) / candles[-1]["close"] * 100


def volume_metrics(candles):
    values = [c["volume"] * c["close"] for c in candles]

    mean = statistics.mean(values)
    median = statistics.median(values)
    std = statistics.stdev(values)

    return {
        "avg_hour_value": round(mean, 2),
        "median_hour_value": round(median, 2),
        "volume_cv": round(std / mean, 4) if mean else 0
    }


def main():
    results = []

    symbols = get_usdt_symbols()
    print("Symbols:", len(symbols))

    for symbol in symbols:
        try:
            candles = get_candles(symbol)

            if len(candles) < 1000:
                print("SKIP LOW DATA:", symbol, len(candles))
                continue

            row = {
                "symbol": symbol,
                "atr_percent_60d": round(atr_percent(candles), 4),
                **volume_metrics(candles)
            }

            row["score"] = round(
                row["atr_percent_60d"] *
                row["median_hour_value"] /
                (1 + row["volume_cv"]),
                2
            )

            results.append(row)
            print("DONE:", row)

        except Exception as e:
            print("ERROR:", symbol, e)

    results.sort(key=lambda x: x["score"], reverse=True)

    with open("symbol_ranking.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    report = "Nobitex Symbol Ranking\n\n"

    for i, r in enumerate(results, 1):
        report += (
            f"{i}) {r['symbol']} | "
            f"ATR {r['atr_percent_60d']}% | "
            f"Median {r['median_hour_value']} | "
            f"CV {r['volume_cv']} | "
            f"Score {r['score']}\n"
        )

    print(report)
    telegram_send(report)


if __name__ == "__main__":
    main()
