"""
technicals.py — candlestick indicators, support/resistance and pattern detection
(pure functions, no network).

Consumes OHLC series (lists, oldest -> newest) and returns indicators + patterns
used by the "Technicals" panel in the detail modal.
"""


def ema_series(values, n):
    """Exponential moving average series (list aligned to input)."""
    if not values or len(values) < n:
        return [None] * len(values)
    k = 2.0 / (n + 1)
    out = [None] * len(values)
    out[n - 1] = sum(values[:n]) / n
    for i in range(n, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def sma_series(values, n):
    out = [None] * len(values)
    for i in range(n - 1, len(values)):
        out[i] = sum(values[i - n + 1:i + 1]) / n
    return out


def macd(closes):
    """Returns (macd_line, signal_line, histogram) lists."""
    e12 = ema_series(closes, 12)
    e26 = ema_series(closes, 26)
    line = [None if e12[i] is None or e26[i] is None else e12[i] - e26[i]
            for i in range(len(closes))]
    # signal = EMA(9) of macd line (on the non-None tail)
    vals = [x for x in line if x is not None]
    sig_tail = ema_series(vals, 9) if len(vals) >= 9 else []
    signal = [None] * len(closes)
    if sig_tail:
        start = len(closes) - len(sig_tail)
        for j, v in enumerate(sig_tail):
            signal[start + j] = v
    hist = [None if line[i] is None or signal[i] is None else line[i] - signal[i]
            for i in range(len(closes))]
    return line, signal, hist


def cross_detected(series_a, series_b, lookback=3):
    """True if A crossed ABOVE B within the last `lookback` bars."""
    for i in range(max(0, len(series_a) - lookback), len(series_a) - 1):
        a0, b0 = series_a[i], series_b[i]
        a1, b1 = series_a[i + 1], series_b[i + 1]
        if None in (a0, b0, a1, b1):
            continue
        if a0 <= b0 and a1 > b1:
            return True
    return False


def local_extrema(values, window=3):
    highs, lows = [], []
    for i in range(window, len(values) - window):
        seg = values[i - window:i + window + 1]
        if values[i] == max(seg):
            highs.append(values[i])
        if values[i] == min(seg):
            lows.append(values[i])
    return highs, lows


def support_resistance(closes, price=None):
    """Nearest support below and resistance above the current price."""
    price = price or closes[-1]
    highs, lows = local_extrema(closes, 3)
    supports = sorted([l for l in lows if l < price])
    resistances = sorted([h for h in highs if h > price])
    support = supports[-1] if supports else min(closes)
    resistance = resistances[0] if resistances else max(closes)
    return support, resistance


def candlestick_patterns(opens, highs, lows, closes):
    """Detect simple patterns on the LAST completed candle."""
    if not opens or not closes or len(closes) < 2:
        return []
    o, h, l, c = opens[-1], highs[-1], lows[-1], closes[-1]
    body = abs(c - o)
    rng = (h - l) or 1e-9
    upper = h - max(o, c)
    lower = min(o, c) - l
    prev_o, prev_c = opens[-2], closes[-2]
    prev_body = abs(prev_c - prev_o)

    pats = []
    if body <= 0.1 * rng:
        pats.append({"name": "Doji", "meaning": "Indecision — possible reversal"})
    if body >= 0.6 * rng and prev_c < prev_o and c > o and o <= prev_c and c >= prev_o:
        pats.append({"name": "Bullish Engulfing", "meaning": "Buyers took control — bullish"})
    if body >= 0.6 * rng and prev_c > prev_o and c < o and o >= prev_c and c <= prev_o:
        pats.append({"name": "Bearish Engulfing", "meaning": "Sellers took control — bearish"})
    if lower >= 2 * body and upper <= 0.35 * body and c > o:
        pats.append({"name": "Hammer", "meaning": "Rejection of lows — bullish reversal"})
    if upper >= 2 * body and lower <= 0.35 * body and c < o:
        pats.append({"name": "Shooting Star", "meaning": "Rejection of highs — bearish reversal"})
    return pats


def build_technicals(closes, opens=None, highs=None, lows=None, price=None):
    """
    Full technicals payload for the last ~60 candles.
    Returns dict with candles, indicators, patterns, support/resistance.
    """
    n = len(closes)
    if n < 30:
        return None
    closes = closes[-60:]
    opens = (opens or [None] * n)[-60:]
    highs = (highs or [None] * n)[-60:]
    lows = (lows or [None] * n)[-60:]
    n = len(closes)

    price = price or closes[-1]
    macd_line, macd_signal, macd_hist = macd(closes)
    s20 = sma_series(closes, 20)
    s50 = sma_series(closes, 50)
    golden = cross_detected(s20, s50, 5)
    death = cross_detected(s50, s20, 5)
    support, resistance = support_resistance(closes, price)
    patterns = candlestick_patterns(opens, highs, lows, closes)

    # RSI via analysis module
    try:
        import analysis
        rsi_val = analysis.rsi(closes, 14)
    except Exception:
        rsi_val = None

    def r(x):
        return None if x is None else round(float(x), 4)

    def rl(lst):
        return [r(x) for x in lst]

    last_macd = macd_line[-1]
    last_signal = macd_signal[-1]
    macd_state = None
    if last_macd is not None and last_signal is not None:
        if last_macd > last_signal and macd_line[-2] is not None and macd_signal[-2] is not None and macd_line[-2] <= macd_signal[-2]:
            macd_state = "bullish crossover (recent)"
        elif last_macd < last_signal:
            macd_state = "bearish (below signal)"
        elif last_macd > last_signal:
            macd_state = "bullish (above signal)"

    return {
        "candles": {
            "opens": rl(opens),
            "highs": rl(highs),
            "lows": rl(lows),
            "closes": rl(closes),
        },
        "rsi": round(rsi_val, 1) if rsi_val is not None else None,
        "macd": {
            "line": r(last_macd),
            "signal": r(last_signal),
            "hist": r(macd_hist[-1]),
            "state": macd_state,
        },
        "golden_cross": golden,
        "death_cross": death,
        "sma20": r(s20[-1]),
        "sma50": r(s50[-1]),
        "support": r(support),
        "resistance": r(resistance),
        "patterns": patterns,
    }
