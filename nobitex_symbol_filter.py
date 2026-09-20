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

    body = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text[:4000]
    }).encode()

    urllib.request.urlopen(
        urllib.request.Request(url, data=body),
        timeout=20
    )


def get_usdt_symbols():
    data = api_get("/market/stats")
    stats = data.get("stats", {})

    symbols = []

    for s in stats:
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


def daily_volume_from_4h(candles):
    """
    تبدیل کندل 4H به ارزش معاملات روزانه واقعی:
    هر 6 کندل 4 ساعته = یک روز
    """

    daily_values = []

    for i in range(0, len(candles)-5, 6):
        total = 0

        for c in candles[i:i+6]:
            total += c["volume"] * c["close"]

        daily_values.append(total)

    if not daily_values:
        return 0, 0

    return (
        statistics.mean(daily_values),
        statistics.median(daily_values)
    )


def volume_cv(candles):
    values = [c["volume"] * c["close"] for c in candles]

    if len(values) < 2:
        return 0

    mean = statistics.mean(values)

    if mean == 0:
        return 0

    return statistics.stdev(values) / mean


def normalize(items, key):
    values = [x[key] for x in items]

    mn = min(values)
    mx = max(values)

    if mx == mn:
        return {id(x): 100 for x in items}

    return {
        id(x): ((x[key]-mn)/(mx-mn))*100
        for x in items
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

            avg_daily, median_daily = daily_volume_from_4h(candles_4h)

            cv = volume_cv(candles_4h)

            # فیلترهای اصلی
            if median_daily < 80000:
                print("SKIP LOW DAILY:", symbol, round(median_daily, 2))
                continue

            if cv > 3:
                print("SKIP UNSTABLE:", symbol, round(cv, 3))
                continue

            results.append({
                "symbol": symbol,
                "atr_1h_20d": round(atr, 4),
                "avg_daily_value": round(avg_daily, 2),
                "median_daily_value": round(median_daily, 2),
                "volume_cv": round(cv, 4)
            })

        except Exception as e:
            print("ERROR", symbol, e)

    if not results:
        print("NO RESULTS")
        return

    atr_rank = normalize(results, "atr_1h_20d")
    vol_rank = normalize(results, "median_daily_value")

    for r in results:
        stability = max(0, 100 - r["volume_cv"] * 20)

        r["score"] = round(
            atr_rank[id(r)] * 0.5 +
            vol_rank[id(r)] * 0.3 +
            stability * 0.2,
            2
        )

    results.sort(key=lambda x: x["score"], reverse=True)

    with open("symbol_ranking.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    report = "Nobitex Symbol Filter V5\n\n"

    for i, r in enumerate(results, 1):
        report += (
            f"{i}) {r['symbol']} | "
            f"ATR:{r['atr_1h_20d']}% | "
            f"DailyMedian:{r['median_daily_value']} | "
            f"CV:{r['volume_cv']} | "
            f"Score:{r['score']}\n"
        )

    print(report)
    telegram_send(report)


if __name__ == "__main__":
    main()
