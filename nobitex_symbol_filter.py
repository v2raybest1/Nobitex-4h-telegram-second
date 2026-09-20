
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

    req = urllib.request.Request(url, headers={"User-Agent": "Nobitex-Filter"})
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
        "text": text
    }).encode()

    urllib.request.urlopen(
        urllib.request.Request(url, data=data),
        timeout=20
    )


def get_usdt_symbols():
    data = api_get("/market/stats")

    markets = data.get("stats", data)

    if isinstance(markets, dict):
        symbols = markets.keys()
    else:
        symbols = []

    return sorted(
        [s for s in symbols if isinstance(s, str) and s.endswith("USDT")]
    )


def get_candles(symbol):
    now = datetime.now(timezone.utc)

    params = {
        "symbol": symbol,
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


def calc_atr(candles):
    tr = []

    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i-1]["close"]

        tr.append(max(h-l, abs(h-pc), abs(l-pc)))

    atr = statistics.mean(tr)
    return atr / candles[-1]["close"] * 100


def calc_volume(candles):
    values = [x["volume"] * x["close"] for x in candles]

    mean = statistics.mean(values)
    median = statistics.median(values)
    std = statistics.stdev(values)

    return mean, median, std / mean if mean else 0


def main():
    results = []

    symbols = get_usdt_symbols()
    print("Symbols:", len(symbols))

    for symbol in symbols:
        try:
            candles = get_candles(symbol)

            if len(candles) < 1000:
                continue

            mean, median, cv = calc_volume(candles)

            row = {
                "symbol": symbol,
                "atr_percent_60d": round(calc_atr(candles), 4),
                "avg_hour_value": round(mean, 2),
                "median_hour_value": round(median, 2),
                "volume_cv": round(cv, 4)
            }

            row["score"] = round(
                row["atr_percent_60d"] * row["median_hour_value"] / (1 + cv),
                2
            )

            results.append(row)

        except Exception as e:
            print("ERROR", symbol, e)

    results.sort(key=lambda x: x["score"], reverse=True)

    with open("symbol_ranking.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    report = "Nobitex Symbol Ranking\n\n"

    for i, r in enumerate(results, 1):
        line = (
            f"{i}) {r['symbol']} | "
            f"ATR:{r['atr_percent_60d']}% | "
            f"MedianVol:{r['median_hour_value']} | "
            f"CV:{r['volume_cv']} | "
            f"Score:{r['score']}"
        )
        print(line)
        report += line + "\n"

    telegram_send(report[:4000])


if __name__ == "__main__":
    main()
