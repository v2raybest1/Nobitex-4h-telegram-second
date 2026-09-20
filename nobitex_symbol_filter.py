import statistics

# Nobitex 1H symbol ranking scanner
# This is the base version. API endpoints will be connected after verification.

def atr_percent(candles):
    trs = []
    for i in range(1, len(candles)):
        h = float(candles[i]['high'])
        l = float(candles[i]['low'])
        pc = float(candles[i-1]['close'])
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))

    atr = sum(trs) / len(trs)
    close = float(candles[-1]['close'])
    return atr / close * 100


def volume_stats(candles):
    values = [float(c['volume']) * float(c['close']) for c in candles]

    mean = statistics.mean(values)
    median = statistics.median(values)
    std = statistics.stdev(values) if len(values) > 1 else 0

    return {
        'mean_hourly_value': mean,
        'median_hourly_value': median,
        'volume_cv': std / mean if mean else 0
    }


def main():
    print('Nobitex symbol filter ready')


if __name__ == '__main__':
    main()
