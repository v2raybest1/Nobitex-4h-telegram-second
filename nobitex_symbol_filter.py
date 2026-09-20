import json
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


def get_usdt_symbols():
    """
    دریافت نمادها و فیلتر USDT.
    در صورت تغییر ساختار API فقط این تابع نیاز به اصلاح دارد.
    """
    data = api_get("/market/stats")

    markets = data.get("stats", data)

    symbols = []

    if isinstance(markets, dict):
        symbols = list(markets.keys())

    elif isinstance(markets, list):
        symbols = [
            x.get("symbol")
            for x in markets
            if isinstance(x, dict)
        ]

    return sorted(
        set(
            s for s in symbols
            if isinstance(s, str) and s.endswith("USDT")
        )
    )


def get_candles(symbol, days=60):
    now = datetime.now(timezone.utc)

    params = {
        "symbol": symbol,
        "resolution": "60",
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


def calculate_atr_percent(candles):
    tr = []

    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i-1]["close"]

        tr.append(max(
            h-l,
            abs(h-pc),
            abs(l-pc)
        ))

    atr = statistics.mean(tr)
    return atr / candles[-1]["close"] * 100


def calculate_volume(candles):
    values = [
        c["volume"] * c["close"]
        for c in candles
    ]

    mean = statistics.mean(values)
    median = statistics.median(values)
    std = statistics.stdev(values)

    return {
        "avg_hour_value": round(mean, 2),
        "median_hour_value": round(median, 2),
        "volume_cv": round(std / mean, 4) if mean else 0
    }


def score(row):
    # حرکت بیشتر + نقدینگی پایدارتر
    return row["atr_percent"] * row["median_hour_value"] / (1 + row["volume_cv"])


def main():
    symbols = get_usdt_symbols()

    print("USDT symbols:", len(symbols))

    results = []

    for symbol in symbols:
        try:
            candles = get_candles(symbol)

            if len(candles) < 1000:
                continue

            row = {
                "symbol": symbol,
                "atr_percent": round(calculate_atr_percent(candles), 4),
                **calculate_volume(candles)
            }

            row["score"] = score(row)
            results.append(row)

            print("DONE", symbol)

        except Exception as e:
            print("ERROR", symbol, e)

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    with open("symbol_ranking.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(json.dumps(results[:5], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
