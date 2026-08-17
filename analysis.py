"""
analysis.py — technical analysis & signal engine (pure functions, no network).

Given a price series (closes, highs, lows) it computes:
  - SMA(7/21/50), RSI(14), ATR(14), momentum
  - a -100..+100 score -> STRONG BUY / BUY / HOLD / SELL / STRONG SELL
  - an entry / stop-loss / target plan + risk:reward
  - an estimated holding period and projected profit/loss %

NOTE: these are heuristic estimates for education/analysis, not financial advice.
"""


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def sma(a, n):
    if not a or len(a) < n:
        return None
    return sum(a[-n:]) / n


def rsi(closes, n=14):
    """Wilder's RSI."""
    if not closes or len(closes) < n + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    if len(gains) < n:
        return None
    ag = sum(gains[:n]) / n
    al = sum(losses[:n]) / n
    for i in range(n, len(gains)):
        ag = (ag * (n - 1) + gains[i]) / n
        al = (al * (n - 1) + losses[i]) / n
    if al == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + ag / al)


def atr(highs, lows, closes, n=14):
    """Average True Range (Wilder). Falls back to close-to-close if no H/L."""
    if not closes or len(closes) < n + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        h = highs[i] if highs and i < len(highs) and highs[i] is not None else closes[i]
        l = lows[i] if lows and i < len(lows) and lows[i] is not None else closes[i]
        pc = closes[i - 1]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not trs:
        return None
    if len(trs) <= n:
        return sum(trs) / len(trs)
    a = sum(trs[:n]) / n
    for i in range(n, len(trs)):
        a = (a * (n - 1) + trs[i]) / n
    return a


def pct_change(closes, n):
    if not closes or len(closes) < n + 1:
        return None
    base = closes[-1 - n]
    if not base:
        return None
    return (closes[-1] - base) / base * 100.0


def signal_from_score(score):
    if score >= 55:
        return "STRONG BUY"
    if score >= 20:
        return "BUY"
    if score > -20:
        return "HOLD"
    if score > -55:
        return "SELL"
    return "STRONG SELL"


def hold_label(days):
    if days is None:
        return "—"
    if days <= 7:
        return f"~{max(2, days)} trading days (≈1 week)"
    if days <= 30:
        return f"~{days} trading days (≈{max(2, round(days / 5))} weeks)"
    return f"~{days} trading days (≈{max(1, round(days / 21))} month)"


def analyze(closes, highs=None, lows=None, meta=None):
    """
    Returns a full analysis dict, or None if there isn't enough data.
    meta: {"price": float, "name": str, ...} optional; price defaults to last close.
    """
    if not closes or len(closes) < 30:
        return None

    price = (meta or {}).get("price") or closes[-1]
    highs = highs or [None] * len(closes)
    lows = lows or [None] * len(closes)

    s7 = sma(closes, 7)
    s21 = sma(closes, 21)
    s50 = sma(closes, 50)
    r = rsi(closes, 14)
    a = atr(highs, lows, closes, 14)
    p7 = pct_change(closes, 7)
    p30 = pct_change(closes, 30)

    score = 0.0
    reasons = []

    # --- trend vs moving averages ---
    if s50 is not None:
        if price > s50:
            score += 25
            reasons.append("Above 50-day avg → long-term uptrend")
        else:
            score -= 25
            reasons.append("Below 50-day avg → long-term downtrend")
    if s21 is not None:
        if price > s21:
            score += 15
            reasons.append("Above 21-day avg → short-term strength")
        else:
            score -= 15
            reasons.append("Below 21-day avg → short-term weakness")
    if s7 is not None:
        if price > s7:
            score += 10
        else:
            score -= 10

    # --- RSI ---
    if r is not None:
        if 40 <= r <= 65:
            score += 20
            reasons.append(f"RSI {r:.0f} → healthy momentum")
        elif r >= 75:
            score -= 20
            reasons.append(f"RSI {r:.0f} → overbought, high risk")
        elif r <= 30:
            score += 8
            reasons.append(f"RSI {r:.0f} → oversold, possible bounce")
        elif r > 65:
            score += 5
            reasons.append(f"RSI {r:.0f} → strong but warming up")

    # --- momentum ---
    if p7 is not None:
        score += clamp(p7, -12, 12) * 1.5
        reasons.append(f"{'+' if p7 >= 0 else ''}{p7:.1f}% over 7 days")
    if p30 is not None:
        score += clamp(p30, -30, 30) * 0.8
        reasons.append(f"{'+' if p30 >= 0 else ''}{p30:.1f}% over 30 days")

    score = clamp(score, -100, 100)
    signal = signal_from_score(score)

    # --- trade plan (long) ---
    atr_pct = (a / price * 100.0) if a else None
    entry = price
    stop = entry - 1.5 * a if a else None
    target = entry + 3.0 * a if a else None
    risk = entry - stop if (entry and stop) else None
    reward = target - entry if (entry and target) else None
    rr = (reward / risk) if (reward and risk) else None
    pnl_pct_target = (target / entry - 1) * 100.0 if (entry and target) else None
    pnl_pct_stop = (stop / entry - 1) * 100.0 if (entry and stop) else None

    # --- estimated holding period ---
    # "At its recent pace": target distance divided by the asset's average
    # up-day move over the last 14 days. Falls back to ATR if no up-days.
    hold_days = None
    if entry and target and target > entry:
        up_days = []
        for i in range(1, len(closes)):
            d = (closes[i] / closes[i - 1] - 1.0) * 100.0
            if d > 0:
                up_days.append(d)
        avg_up = sum(up_days[-14:]) / len(up_days[-14:]) if up_days else 0.0
        if avg_up > 0.05:
            hold_days = clamp(int(round(pnl_pct_target / avg_up)), 2, 90)
        elif a and a > 0:
            hold_days = max(2, int(round((target - entry) / a * 1.6)))

    # --- position in 90-day range ---
    valid_hi = [h for h in highs if h is not None] or closes
    valid_lo = [l for l in lows if l is not None] or closes
    hist_high = max(closes) or max(valid_hi)
    hist_low = min(closes) or min(valid_lo)
    rng = hist_high - hist_low
    pos_range = ((price - hist_low) / rng * 100.0) if rng else 50.0

    trend = "Sideways"
    if s21 is not None and s50 is not None:
        if price > s21 > s50:
            trend = "Uptrend"
        elif price < s21 < s50:
            trend = "Downtrend"

    return {
        "price": price,
        "score": round(score, 1),
        "signal": signal,
        "rsi": round(r, 1) if r is not None else None,
        "sma7": round(s7, 2) if s7 is not None else None,
        "sma21": round(s21, 2) if s21 is not None else None,
        "sma50": round(s50, 2) if s50 is not None else None,
        "trend": trend,
        "pct7d": round(p7, 2) if p7 is not None else None,
        "pct30d": round(p30, 2) if p30 is not None else None,
        "atr": round(a, 4) if a is not None else None,
        "atr_pct": round(atr_pct, 2) if atr_pct is not None else None,
        "entry": entry,
        "stop": stop,
        "target": target,
        "rr": round(rr, 2) if rr is not None else None,
        "pnl_pct_target": round(pnl_pct_target, 2) if pnl_pct_target is not None else None,
        "pnl_pct_stop": round(pnl_pct_stop, 2) if pnl_pct_stop is not None else None,
        "hold_days": hold_days,
        "hold_label": hold_label(hold_days),
        "hist_high": hist_high,
        "hist_low": hist_low,
        "pos_range": round(pos_range, 1),
        "reasons": reasons,
    }
