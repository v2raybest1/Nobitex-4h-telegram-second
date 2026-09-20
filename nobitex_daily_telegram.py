
# ============================================================
# Nobitex Daily Telegram Scanner - 22 Symbols
# DIRECT Nobitex 4H candles (resolution=240)
# NO 30m aggregation
# Pure Python standard library - NO pip install, NO tzdata
# ============================================================

import json
import math
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

TEHRAN = timezone(timedelta(hours=3, minutes=30))

BASE_URL = "https://apiv2.nobitex.ir"
OHLC_PATH = "/market/udf/history"
TIMEOUT = 20

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "ZECUSDT",
    "SOLUSDT",
    "XAUTUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    
    
    "BNBUSDT",
    "AAVEUSDT",
    "UNIUSDT",
    "WLDUSDT",
    "NEARUSDT",
    "1K_SHIBUSDT",
    "LINKUSDT",
    "SUIUSDT",
    "1M_PEPEUSDT",
    "HYPEUSDT",
    "ENAUSDT",
    
    "AVAXUSDT",
    "FILUSDT",
    "DOTUSDT",
]

DISPLAY_NAMES = {
    "BTCUSDT": "BTC/USDT",
    "ETHUSDT": "ETH/USDT",
    "ZECUSDT": "ZEC/USDT",
    "SOLUSDT": "SOL/USDT",
    "XAUTUSDT": "XAUT/USDT",
    "XRPUSDT": "XRP/USDT",
    "DOGEUSDT": "DOGE/USDT",
    "ADAUSDT": "ADA/USDT",
    
    
    "BNBUSDT": "BNB/USDT",
    "AAVEUSDT": "AAVE/USDT",
    "UNIUSDT": "UNI/USDT",
    "WLDUSDT": "WLD/USDT",
    "NEARUSDT": "NEAR/USDT",
    "1K_SHIBUSDT": "1K_SHIB/USDT",
    "LINKUSDT": "LINK/USDT",
    "SUIUSDT": "SUI/USDT",
    "1M_PEPEUSDT": "1M_PEPE/USDT",
    "HYPEUSDT": "HYPE/USDT",
    "ENAUSDT": "ENA/USDT",
    
    "AVAXUSDT": "AVAX/USDT",
    "FILUSDT": "FIL/USDT",
    "DOTUSDT": "DOT/USDT",
}

DISPLAY_FACTOR = {}

# Enough direct 4H history for EMA100/RSI/StochRSI warm-up.
HISTORY_DAILY_CANDLES = 320
ONE_DAY = 24 * 3600

RSI14_DOWN_CONFIRMED = 58
K_DOWN_CONFIRMED = 78
RSI14_UP_CONFIRMED = 42
K_UP_CONFIRMED = 22

RSI14_DOWN_NEAR = 54
K_DOWN_NEAR = 73
RSI14_UP_NEAR = 46
K_UP_NEAR = 27

EMA_BORDERLINE_ATR = 0.7

RANGE_ADX_DI_LENGTH = 14
RANGE_ADX_SMOOTHING = 14
RANGE_ADX_MAX = 20.0

RANGE_CHOP_LENGTH = 14
RANGE_CHOP_MIN = 61.8


def http_get_json(path, params):
    query = urllib.parse.urlencode(params)
    url = BASE_URL + path + "?" + query

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 GitHubActions NobitexDailyScanner/1.0",
            "Accept": "application/json",
            "Connection": "close",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            raw = response.read().decode("utf-8", errors="replace")
            date_header = response.headers.get("Date")
            try:
                payload = json.loads(raw)
            except Exception:
                raise RuntimeError("پاسخ JSON نامعتبر است: " + raw[:180])
            return payload, date_header

    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        raise RuntimeError(f"HTTP {e.code}: {body[:180]}")

    except urllib.error.URLError as e:
        raise RuntimeError(f"خطای اتصال: {e.reason}")

    except TimeoutError:
        raise RuntimeError("اتصال به نوبیتکس Timeout شد")


def parse_server_time(date_header):
    if not date_header:
        raise RuntimeError("هدر Date سرور نوبیتکس دریافت نشد")

    try:
        dt = parsedate_to_datetime(date_header)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        raise RuntimeError("زمان سرور نوبیتکس قابل اعتبارسنجی نیست")


def connection_probe():
    now_utc = datetime.now(timezone.utc)
    to_ts = int(now_utc.timestamp())
    from_ts = to_ts - (3 * ONE_DAY)

    payload, date_header = http_get_json(
        OHLC_PATH,
        {
            "symbol": "BTCUSDT",
            "resolution": "D",
            "from": from_ts,
            "to": to_ts,
        },
    )

    if not isinstance(payload, dict):
        raise RuntimeError("پاسخ تست اتصال نامعتبر است")

    status = str(payload.get("s", "")).lower()
    if status not in ("ok", "no_data"):
        raise RuntimeError(
            "پاسخ تست اتصال نامعتبر: " +
            str(payload.get("errmsg", payload))[:180]
        )

    return parse_server_time(date_header)


def fetch_daily_history(symbol, server_utc):
    to_ts = int(server_utc.timestamp())

    # ask for a slightly wider window than strictly needed
    from_ts = to_ts - ((HISTORY_DAILY_CANDLES + 10) * ONE_DAY)

    payload, date_header = http_get_json(
        OHLC_PATH,
        {
            "symbol": symbol,
            "resolution": "D",
            "from": from_ts,
            "to": to_ts,
        },
    )

    server_from_response = parse_server_time(date_header)

    if not isinstance(payload, dict):
        raise RuntimeError("داده دریافت نشد")

    status = str(payload.get("s", "")).lower()

    if status == "no_data":
        raise RuntimeError("داده دریافت نشد")

    if status != "ok":
        raise RuntimeError(
            str(payload.get("errmsg", "پاسخ OHLC نامعتبر است"))
        )

    required = ["t", "o", "h", "l", "c", "v"]
    if any(k not in payload for k in required):
        raise RuntimeError("داده‌ها ناقص یا نامعتبر بودند")

    lengths = [len(payload[k]) for k in required]
    if not lengths or min(lengths) == 0:
        raise RuntimeError("داده دریافت نشد")

    if len(set(lengths)) != 1:
        raise RuntimeError("داده‌ها ناقص یا نامعتبر بودند")

    rows = []

    for i in range(lengths[0]):
        try:
            ts = int(payload["t"][i])
            start_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
            start_teh = start_utc.astimezone(TEHRAN)

            rows.append({
                "ts": ts,
                "start": start_teh,
                "end": start_teh + timedelta(days=1),
                "open": float(payload["o"][i]),
                "high": float(payload["h"][i]),
                "low": float(payload["l"][i]),
                "close": float(payload["c"][i]),
                "volume": float(payload["v"][i]),
            })
        except Exception:
            raise RuntimeError("داده‌ها ناقص یا نامعتبر بودند")

    rows.sort(key=lambda x: x["ts"])

    # deduplicate
    dedup = {}
    for r in rows:
        dedup[r["ts"]] = r
    rows = [dedup[k] for k in sorted(dedup)]

    return rows, server_from_response


def validate_and_select_complete(rows, server_utc):
    if len(rows) < 120:
        return False, "کندل روزانه کافی نیست", None

    # User-defined daily boundary: 00:00 Tehran.
    # Fail visibly if Nobitex returns a different direct-D alignment.
    bad = []
    for r in rows[-150:]:
        st = r["start"]
        if st.hour != 0 or st.minute != 0 or st.second != 0:
            bad.append(st)

    if bad:
        sample = bad[-1].strftime("%Y-%m-%d %H:%M:%S")
        return (
            False,
            "مرزبندی کندل روزانه نوبیتکس با 00:00 تهران منطبق نیست "
            f"(نمونه شروع کندل: {sample} تهران)",
            None,
        )

    recent = rows[-150:]
    for prev, cur in zip(recent, recent[1:]):
        if cur["ts"] - prev["ts"] != ONE_DAY:
            return False, "توالی کندل‌های روزانه ناقص است", None

    server_teh = server_utc.astimezone(TEHRAN)

    complete = [
        r for r in rows
        if r["end"] <= server_teh
    ]

    if len(complete) < 120:
        return False, "کندل روزانه کافی نیست", None

    return True, None, complete


def sma(values):
    return sum(values) / len(values) if values else None


def tv_ema(values, length):
    out = [None] * len(values)
    if len(values) < length:
        return out

    seed = sma(values[:length])
    out[length - 1] = seed

    alpha = 2.0 / (length + 1.0)
    prev = seed

    for i in range(length, len(values)):
        prev = alpha * values[i] + (1 - alpha) * prev
        out[i] = prev

    return out


def tv_rma(values, length):
    out = [None] * len(values)
    if len(values) < length:
        return out

    seed = sma(values[:length])
    out[length - 1] = seed

    alpha = 1.0 / length
    prev = seed

    for i in range(length, len(values)):
        prev = alpha * values[i] + (1 - alpha) * prev
        out[i] = prev

    return out



def true_ranges(candles):
    """
    TradingView/Wilder True Range series.
    """
    out = []
    prev_close = None

    for c in candles:
        high = c["high"]
        low = c["low"]

        if prev_close is None:
            tr = high - low
        else:
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )

        out.append(tr)
        prev_close = c["close"]

    return out


def tv_adx(candles, di_length=14, adx_smoothing=14):
    """
    Wilder-style ADX using +DM/-DM, True Range and RMA smoothing.
    Only ADX is returned; +DI/-DI are internal and are NOT used
    for signal direction.
    """
    n = len(candles)
    out = [None] * n

    if n < (di_length + adx_smoothing + 1):
        return out

    trs = []
    plus_dm = []
    minus_dm = []

    for i in range(1, n):
        cur = candles[i]
        prev = candles[i - 1]

        up_move = cur["high"] - prev["high"]
        down_move = prev["low"] - cur["low"]

        plus_dm.append(
            up_move if up_move > down_move and up_move > 0 else 0.0
        )
        minus_dm.append(
            down_move if down_move > up_move and down_move > 0 else 0.0
        )

        tr = max(
            cur["high"] - cur["low"],
            abs(cur["high"] - prev["close"]),
            abs(cur["low"] - prev["close"]),
        )
        trs.append(tr)

    sm_tr = tv_rma(trs, di_length)
    sm_plus = tv_rma(plus_dm, di_length)
    sm_minus = tv_rma(minus_dm, di_length)

    dx = [None] * len(trs)

    for i in range(len(trs)):
        if (
            sm_tr[i] is None
            or sm_plus[i] is None
            or sm_minus[i] is None
        ):
            continue

        if sm_tr[i] <= 0:
            plus_di = 0.0
            minus_di = 0.0
        else:
            plus_di = 100.0 * sm_plus[i] / sm_tr[i]
            minus_di = 100.0 * sm_minus[i] / sm_tr[i]

        denom = plus_di + minus_di
        if denom <= 0:
            dx[i] = 0.0
        else:
            dx[i] = (
                100.0
                * abs(plus_di - minus_di)
                / denom
            )

    first_dx = next((i for i, v in enumerate(dx) if v is not None), None)
    if first_dx is None:
        return out

    valid_dx = [v for v in dx[first_dx:] if v is not None]
    sm_adx = tv_rma(valid_dx, adx_smoothing)

    for k, value in enumerate(sm_adx):
        if value is None:
            continue

        transition_index = first_dx + k
        candle_index = transition_index + 1

        if candle_index < n:
            out[candle_index] = value

    return out


def tv_chop(candles, length=14):
    """
    Choppiness Index:
    100 * log10(sum(TR, n) / (highestHigh - lowestLow)) / log10(n)
    """
    n = len(candles)
    out = [None] * n

    if n < length or length <= 1:
        return out

    trs = true_ranges(candles)
    log_len = math.log10(length)

    for i in range(length - 1, n):
        start = i - length + 1
        window = candles[start:i + 1]

        sum_tr = sum(trs[start:i + 1])
        highest = max(c["high"] for c in window)
        lowest = min(c["low"] for c in window)
        price_range = highest - lowest

        if sum_tr <= 0 or price_range <= 0:
            continue

        value = (
            100.0
            * math.log10(sum_tr / price_range)
            / log_len
        )

        # Numerical protection only.
        out[i] = max(0.0, min(100.0, value))

    return out


def is_range_market(ind):
    """
    Range label is informational only.
    It never creates or blocks a trading signal.
    """
    return (
        ind["ADX14"] < RANGE_ADX_MAX
        and ind["CHOP14"] >= RANGE_CHOP_MIN
    )


def tv_atr(candles, length):
    """
    Wilder/TradingView-style ATR:
    True Range, then RMA(length).
    """
    if not candles:
        return []

    return tv_rma(true_ranges(candles), length)

def tv_rsi(closes, length):
    out = [None] * len(closes)
    if len(closes) < length + 1:
        return out

    gains = []
    losses = []

    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))

    avg_gains = tv_rma(gains, length)
    avg_losses = tv_rma(losses, length)

    for j in range(len(gains)):
        ag = avg_gains[j]
        al = avg_losses[j]

        if ag is None or al is None:
            continue

        idx = j + 1

        if ag == 0 and al == 0:
            out[idx] = 50.0
        elif al == 0:
            out[idx] = 100.0
        else:
            rs = ag / al
            out[idx] = 100 - (100 / (1 + rs))

    return out


def rolling_min_max(values, end_index, length):
    start = end_index - length + 1
    if start < 0:
        return None, None

    window = values[start:end_index + 1]
    if any(v is None for v in window):
        return None, None

    return min(window), max(window)


def tv_stoch_rsi_k(closes, rsi_length=20, stoch_length=20, k_smoothing=5):
    rsi = tv_rsi(closes, rsi_length)
    raw = [None] * len(closes)

    for i in range(len(closes)):
        lo, hi = rolling_min_max(rsi, i, stoch_length)
        if lo is None:
            continue

        if hi == lo:
            raw[i] = 0.0
        else:
            raw[i] = 100.0 * (rsi[i] - lo) / (hi - lo)

    k = [None] * len(closes)

    for i in range(len(closes)):
        start = i - k_smoothing + 1
        if start < 0:
            continue

        window = raw[start:i + 1]
        if any(v is None for v in window):
            continue

        k[i] = sum(window) / k_smoothing

    return k


def compute_last_indicators(candles):
    closes = [c["close"] for c in candles]

    ema50 = tv_ema(closes, 50)[-1]
    ema100 = tv_ema(closes, 100)[-1]
    rsi14 = tv_rsi(closes, 14)[-1]
    k = tv_stoch_rsi_k(closes, 20, 20, 5)[-1]
    atr50 = tv_atr(candles, 50)[-1]
    adx14 = tv_adx(
        candles,
        RANGE_ADX_DI_LENGTH,
        RANGE_ADX_SMOOTHING,
    )[-1]
    chop14 = tv_chop(candles, RANGE_CHOP_LENGTH)[-1]

    vals = [
        ema50,
        ema100,
        rsi14,
        k,
        atr50,
        adx14,
        chop14,
    ]

    if any(v is None or not math.isfinite(v) for v in vals):
        raise RuntimeError("محاسبات قابل اعتبارسنجی نیست")

    if atr50 <= 0:
        raise RuntimeError("ATR50 نامعتبر است")

    return {
        "EMA50": ema50,
        "EMA100": ema100,
        "RSI14": rsi14,
        "K": k,
        "ATR50": atr50,
        "ADX14": adx14,
        "CHOP14": chop14,
    }


def classify(ind):
    ema50 = ind["EMA50"]
    ema100 = ind["EMA100"]
    rsi14 = ind["RSI14"]
    k = ind["K"]

    atr50 = ind["ATR50"]

    if ema100 == 0 or atr50 <= 0:
        return None, None, None

    diff_pct = abs(ema50 - ema100) / abs(ema100) * 100.0
    ema_gap_atr = abs(ema50 - ema100) / atr50

    if ema50 < ema100 and rsi14 > RSI14_DOWN_CONFIRMED and k > K_DOWN_CONFIRMED:
        return "قطعی", "نزولی", diff_pct

    if ema50 > ema100 and rsi14 < RSI14_UP_CONFIRMED and k < K_UP_CONFIRMED:
        return "قطعی", "صعودی", diff_pct

    near_down = rsi14 > RSI14_DOWN_NEAR and k > K_DOWN_NEAR
    near_up = rsi14 < RSI14_UP_NEAR and k < K_UP_NEAR
    borderline = ema_gap_atr < EMA_BORDERLINE_ATR

    if near_down and (borderline or ema50 < ema100):
        return "نزدیک", "نزولی", diff_pct

    if near_up and (borderline or ema50 > ema100):
        return "نزدیک", "صعودی", diff_pct

    return None, None, diff_pct


def fmt_num(x):
    x = float(x)
    ax = abs(x)

    if ax >= 1000:
        return f"{x:,.2f}"
    if ax >= 1:
        return f"{x:.6f}".rstrip("0").rstrip(".")
    return f"{x:.10f}".rstrip("0").rstrip(".")


def analyze_symbol(symbol, server_utc):
    try:
        rows, response_server_utc = fetch_daily_history(symbol, server_utc)

        ok, reason, complete = validate_and_select_complete(
            rows,
            response_server_utc
        )

        if not ok:
            return {"ok": False, "reason": reason}

        ind = compute_last_indicators(complete)
        alert_type, direction, diff_pct = classify(ind)
        last = complete[-1]

        range_market = (
            is_range_market(ind)
            if alert_type is not None
            else False
        )

        return {
            "ok": True,
            "ind": ind,
            "alert_type": alert_type,
            "direction": direction,
            "diff_pct": diff_pct,
            "is_range": range_market,
            "start": last["start"],
            "end": last["end"],
        }

    except Exception as e:
        msg = str(e)
        low = msg.lower()

        if "invalid" in low or "symbol" in low or "نماد" in msg:
            reason = "بازار USDT این نماد در نوبیتکس در دسترس نیست"
        elif (
            "http" in low
            or "اتصال" in msg
            or "timeout" in low
            or "داده دریافت نشد" in msg
        ):
            reason = "داده دریافت نشد (" + msg[:180] + ")"
        else:
            reason = "محاسبات قابل اعتبارسنجی نیست (" + msg[:180] + ")"

        return {"ok": False, "reason": reason}




def concise_error(reason):
    text = " ".join(str(reason).split())
    low = text.lower()
    if "توالی کندل‌های 4h ناقص" in low:
        return "توالی کندل‌های 4H ناقص است"
    if "مرزبندی کندل 4h" in low:
        return "مرزبندی کندل 4H نامعتبر است"
    if "کندل کافی نیست" in text:
        return "کندل کافی نیست"
    if "بازار usdt" in low:
        return "بازار USDT در دسترس نیست"
    if "داده دریافت نشد" in text or "timeout" in low or "اتصال" in text or "http" in low:
        return "داده دریافت نشد"
    if "محاسبات قابل اعتبارسنجی نیست" in text:
        return "محاسبات قابل اعتبارسنجی نیست"
    return text[:120] if text else "خطای نامشخص داده"


def scan_all():
    try:
        server_utc = connection_probe()
    except Exception as e:
        now_teh = datetime.now(timezone.utc).astimezone(TEHRAN)
        return {
            "global_error": str(e),
            "run_time": now_teh,
            "server_time": None,
            "healthy": [],
            "alerts": [],
            "errors": [],
            "interval": None,
            "inconsistent": False,
        }

    healthy = []
    alerts = []
    errors = []

    for symbol in SYMBOLS:
        name = DISPLAY_NAMES[symbol]
        result = analyze_symbol(symbol, server_utc)
        if not result["ok"]:
            errors.append((name, concise_error(result["reason"])))
            continue
        healthy.append((symbol, name, result))
        if result["alert_type"] is not None:
            alerts.append((symbol, name, result))

    intervals = {}
    for symbol, name, result in healthy:
        key = (result["start"], result["end"])
        intervals.setdefault(key, []).append(name)

    interval = None
    inconsistent = len(intervals) > 1
    if len(intervals) == 1:
        interval = next(iter(intervals.keys()))

    return {
        "global_error": None,
        "run_time": server_utc.astimezone(TEHRAN),
        "server_time": server_utc,
        "healthy": healthy,
        "alerts": alerts,
        "errors": errors,
        "interval": interval,
        "inconsistent": inconsistent,
    }


def gregorian_to_jalali(gy, gm, gd):
    """
    Convert Gregorian date to Jalali (Solar Hijri) without external packages.
    Returns (jy, jm, jd).
    """
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]

    gy -= 1600
    gm -= 1
    gd -= 1

    g_day_no = (
        365 * gy
        + (gy + 3) // 4
        - (gy + 99) // 100
        + (gy + 399) // 400
    )

    for i in range(gm):
        g_day_no += g_days_in_month[i]

    # Gregorian leap year adjustment after February.
    gy_full = gy + 1600
    is_g_leap = (
        gy_full % 4 == 0
        and (gy_full % 100 != 0 or gy_full % 400 == 0)
    )
    if gm > 1 and is_g_leap:
        g_day_no += 1

    g_day_no += gd

    j_day_no = g_day_no - 79

    j_np = j_day_no // 12053
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    jm = 0
    while jm < 11 and j_day_no >= j_days_in_month[jm]:
        j_day_no -= j_days_in_month[jm]
        jm += 1

    jd = j_day_no + 1

    return jy, jm + 1, jd


def to_persian_digits(text):
    return str(text).translate(
        str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    )


def format_jalali_date(dt):
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    return to_persian_digits(f"{jy:04d}/{jm:02d}/{jd:02d}")


def build_report_message(scan):
    if scan.get("global_error"):
        run_time = scan["run_time"]
        return "\n".join([
            "❌ Nobitex Daily",
            f"زمان اجرا: {run_time.strftime('%H:%M')} تهران",
            "اسکن انجام نشد — اتصال/زمان سرور نوبیتکس قابل اعتبارسنجی نبود.",
        ])

    lines = ["📊 Nobitex Daily"]
    interval = scan.get("interval")
    if interval is not None:
        start, end = interval
        lines.append(
            f"کندل: {format_jalali_date(start)}"
        )
    else:
        lines.append("کندل: قابل تعیین نیست")

    lines.append(f"داده سالم: {len(scan.get('healthy', []))}/{len(SYMBOLS)}")
    lines.append("")

    if scan.get("inconsistent"):
        lines.append("⚠️ آخرین کندل کامل روزانه نمادهای سالم یکسان نیست.")
    else:
        alerts = scan.get("alerts", [])
        if alerts:
            for _symbol, name, result in alerts:
                alert_type = result["alert_type"]
                direction = result["direction"]
                if direction == "صعودی":
                    marker = "🟢⭐ " if alert_type == "قطعی" else "🟢 "
                else:
                    marker = "🔴⭐ " if alert_type == "قطعی" else "🔴 "

                range_label = " ⚪ رنج" if result.get("is_range") else ""
                lines.append(
                    f"{marker}{name} — {alert_type} {direction}{range_label}"
                )

                ind = result["ind"]
                ema_gap_atr = (
                    abs(ind["EMA50"] - ind["EMA100"]) / ind["ATR50"]
                )
                lines.append(f"EMA Gap: {ema_gap_atr:.3f} ATR")
                lines.append(f"RSI14: {ind['RSI14']:.2f}")
                lines.append(f"StochRSI K: {ind['K']:.2f}")
        else:
            lines.append("✅ هیچ سیگنال قطعی یا نزدیکی روزانه وجود ندارد.")

    errors = scan.get("errors", [])
    if errors:
        lines.extend(["", "⚠️ مشکل داده:"])
        for name, reason in errors:
            lines.append(f"{name} — {concise_error(reason)}")

    return "\n".join(lines).rstrip()


def split_message(text, limit=3800):
    if limit < 100:
        raise ValueError("limit must be at least 100 characters")
    if len(text) <= limit:
        return [text]

    continuation = "📊 ادامه گزارش Nobitex Daily\n"
    chunks = []
    current = ""

    for original_line in text.splitlines():
        line = original_line
        while len(line) > limit:
            available = limit - len(current) - (1 if current else 0)
            if available <= 0:
                chunks.append(current)
                current = continuation
                available = limit - len(current) - 1
            part = line[:available]
            current = current + ("\n" if current else "") + part
            line = line[available:]
            if len(current) >= limit:
                chunks.append(current)
                current = continuation

        candidate = line if not current else current + "\n" + line
        if len(candidate) <= limit:
            current = candidate
        else:
            chunks.append(current)
            current = continuation + line

    if current:
        chunks.append(current)

    return chunks



def get_telegram_credentials():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    missing = []
    if not token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not chat_id:
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        raise RuntimeError(
            "GitHub Secret تنظیم نشده است: " + ", ".join(missing)
        )
    return token, chat_id


def send_telegram(text, token, chat_id, retries=3):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps(
        {"chat_id": str(chat_id), "text": text},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "NobitexDailyTelegram/1.0",
        },
        method="POST",
    )

    last_error = None
    attempts = max(1, int(retries))

    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                raw = response.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw)
            except Exception:
                raise RuntimeError("پاسخ Telegram JSON معتبر نیست")
            if not isinstance(data, dict) or data.get("ok") is not True:
                desc = ""
                if isinstance(data, dict):
                    desc = str(data.get("description", ""))
                raise RuntimeError(
                    "Telegram ارسال پیام را نپذیرفت" +
                    (f": {desc[:160]}" if desc else "")
                )
            return

        except urllib.error.HTTPError as e:
            code = int(getattr(e, "code", 0) or 0)
            last_error = RuntimeError(f"Telegram HTTP {code}")
            transient = code == 429 or code >= 500
            if not transient or attempt == attempts:
                raise last_error

        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_error = RuntimeError(
                "خطای اتصال به Telegram: " + str(getattr(e, "reason", e))[:120]
            )
            if attempt == attempts:
                raise last_error

        except RuntimeError as e:
            last_error = e
            if attempt == attempts:
                raise

        if attempt < attempts:
            time.sleep(min(2 ** (attempt - 1), 4))

    raise last_error or RuntimeError("ارسال پیام Telegram ناموفق بود")


def main():
    try:
        token, chat_id = get_telegram_credentials()
    except RuntimeError as e:
        print(f"❌ {e}")
        return 2

    scan = scan_all()
    message = build_report_message(scan)
    chunks = split_message(message, limit=3800)

    try:
        for chunk in chunks:
            send_telegram(chunk, token, chat_id)
    except Exception as e:
        print("❌ ارسال گزارش به Telegram ناموفق بود:", e)
        return 3

    print(message)
    print(f"✅ Telegram: {len(chunks)} پیام ارسال شد.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
