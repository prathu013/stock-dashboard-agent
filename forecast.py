"""
forecast.py — lightweight price projection (trend regression + volatility band).

Given a daily close series, projects a central price for the next 7 and 30
trading days using a linear regression over the last 30 closes, with a
±1 standard-deviation band from daily-return volatility.

This is a statistical extrapolation for education — NOT a guarantee.
"""


def _linreg(y):
    """Linear fit of y over x=0..n-1 -> (slope, intercept)."""
    n = len(y)
    if n < 2:
        return None
    sx = n * (n - 1) / 2.0
    sy = sum(y)
    sxy = sum(i * v for i, v in enumerate(y))
    sxx = sum(i * i for i in range(n))
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def _daily_returns(closes):
    rets = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            rets.append(closes[i] / closes[i - 1] - 1.0)
    return rets


def forecast(closes):
    """Returns a forecast dict, or None if insufficient data."""
    if not closes or len(closes) < 20:
        return None
    closes = [c for c in closes if c is not None]
    if len(closes) < 20:
        return None

    current = closes[-1]
    recent = closes[-30:] if len(closes) >= 30 else closes
    fit = _linreg(recent)
    rets = _daily_returns(closes[-60:])
    if not rets:
        return None

    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1) if len(rets) > 1 else 0.0
    sigma = var ** 0.5

    def project(days):
        if fit:
            central = current + fit[0] * days
        else:
            central = current * (1 + mean) ** days
        band = sigma * (days ** 0.5)
        lo = central * (1 - band)
        hi = central * (1 + band)
        return central, lo, hi

    p7, l7, h7 = project(7)
    p30, l30, h30 = project(30)

    up7 = (p7 / current - 1.0) * 100.0
    up30 = (p30 / current - 1.0) * 100.0

    if up30 > 5:
        direction = "Uptrend"
    elif up30 < -5:
        direction = "Downtrend"
    else:
        direction = "Sideways"

    def rnd(x):
        return round(x, 2)

    return {
        "current": rnd(current),
        "direction": direction,
        "p7": rnd(p7), "p7_low": rnd(l7), "p7_high": rnd(h7),
        "up7": rnd(up7),
        "p30": rnd(p30), "p30_low": rnd(l30), "p30_high": rnd(h30),
        "up30": rnd(up30),
        "volatility": rnd(sigma * 100),
        "days_used": len(closes),
    }
