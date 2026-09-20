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
    stats = data.get("stats", {})

    symbols = []

    for s in stats.keys():
        if isinstance(s, str) and s.endswith("-usdt"):
            symbols.append(s.replace("-", "").upper())

    return sorted(set(symbols))


def get_candles(symbol, resolution, days):
    now = datetime.now(timezone.utc)

    params = {
        "symbol": symbol.lower(),
        "resolution": str(resolution),
        "from": int(now.timestamp()) - days * 86400,
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


def volume_stats(candles):
    values = [
        c["volume"] * c["close"]
        for c in candles
    ]

    mean = statistics.mean(values)
    median = statistics.median(values)
    std = statistics.stdev(values) if len(values) > 1 else 0

    return mean, median, std / mean if mean else 0


def normalize(values):
    if not values:
        return {}

    mn = min(values)
    mx = max(values)

    if mx == mn:
        return {v: 100 for v in values}

    return {
        v: (v - mn) / (mx - mn) * 100
        for v in values
    }


def main():
    results = []

    symbols = get_usdt_symbols()

    print("Symbols:", len(symbols))

    for symbol in symbols:
        try:
            candles_1h = get_candles(symbol, 60, 20)
            candles_4h = get_candles(symbol, 240, 60)

            if len(candles_1h) < 400 or len(candles_4h) < 300:
                print("SKIP DATA:", symbol, len(candles_1h), len(candles_4h))
                continue

            atr = atr_percent(candles_1h)
            avg4h, median4h, cv = volume_stats(candles_4h)

            daily_value = median4h * 6

            # hard filters
            if daily_value < 80000:
                print("SKIP LOW VOLUME:", symbol, daily_value)
                continue

            if cv > 3:
                print("SKIP UNSTABLE:", symbol, cv)
                continue

            results.append({
                "symbol": symbol,
                "atr": round(atr, 4),
                "median_4h_value": round(median4h, 2),
                "avg_4h_value": round(avg4h, 2),
                "daily_value_est": round(daily_value, 2),
                "cv": round(cv, 4)
            })

        except Exception as e:
            print("ERROR", symbol, e)

    atr_scores = normalize([x["atr"] for x in results])
    liq_scores = normalize([x["median_4h_value"] for x in results])
    cv_scores = {
        id(x): max(0, 100 - x["cv"] * 20)
        for x in results
    }

    for x in results:
        x["score"] = round(
            atr_scores[x["atr"]] * 0.5 +
            liq_scores[x["median_4h_value"]] * 0.3 +
            cv_scores[id(x)] * 0.2,
            2
        )

    results.sort(key=lambda x: x["score"], reverse=True)

    with open("symbol_ranking.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    report = "Nobitex Symbol Filter V4\n\n"

    for i, r in enumerate(results, 1):
        report += (
            f"{i}) {r['symbol']} | "
            f"ATR:{r['atr']}% | "
            f"Daily:{r['daily_value_est']} | "
            f"CV:{r['cv']} | "
            f"Score:{r['score']}\n"
        )

    print(report)
    telegram_send(report)


if __name__ == "__main__":
    main()
