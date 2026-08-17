"""
funds.py — Indian Mutual Funds analysis (free AMFI data via mfapi.in).

Fetches NAV history for a curated list of popular funds, computes returns
(1m/3m/6m/1y/3y/5y CAGR), volatility, max drawdown, and a 0-100 score + rating.
"""
import os
import json
import time
import threading
import math
from datetime import datetime, timedelta

import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
MASTER_FILE = os.path.join(DATA_DIR, "mf_master.json")

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
SESSION = requests.Session()
SESSION.headers.update(UA)

MASTER_TTL = 7 * 86400          # master list re-fetched weekly
NAV_TTL = 6 * 3600              # NAV history cached 6 h

_lock = threading.Lock()
_master_cache = {"ts": 0.0, "data": None}
_nav_cache = {}

# keyword -> display category (we prefer Direct-Growth plans).
# Keywords match substrings of AMFI scheme names (some funds were renamed).
CURATED = [
    ("Parag Parikh Flexi Cap", "Flexi Cap"),
    ("HDFC Flexi Cap", "Flexi Cap"),
    ("Quant Flexi Cap", "Flexi Cap"),
    ("SBI Large Cap", "Large Cap"),
    ("HDFC Large Cap", "Large Cap"),
    ("ICICI Prudential Bluechip", "Large Cap"),
    ("Mirae Asset Large Cap", "Large Cap"),
    ("Nippon India Large Cap", "Large Cap"),
    ("HDFC Mid Cap", "Mid Cap"),
    ("Kotak Midcap", "Mid Cap"),
    ("Motilal Oswal Midcap", "Mid Cap"),
    ("Quant Small Cap", "Small Cap"),
    ("Nippon India Small Cap", "Small Cap"),
    ("SBI Small Cap", "Small Cap"),
    ("HDFC Small Cap", "Small Cap"),
    ("Axis ELSS", "ELSS"),
    ("Quant ELSS Tax Saver", "ELSS"),
    ("Parag Parikh ELSS", "ELSS"),
    ("UTI Nifty 50 Index", "Index"),
    ("HDFC Nifty 50 Index", "Index"),
    ("Nippon India Index Fund - Nifty", "Index"),
    ("HDFC Balanced Advantage", "Hybrid"),
    ("ICICI Prudential Balanced Advantage", "Hybrid"),
    ("Parag Parikh Conservative Hybrid", "Hybrid"),
    ("HDFC Corporate Bond", "Debt"),
    ("ICICI Prudential Corporate Bond", "Debt"),
    ("SBI Magnum Gilt", "Debt"),
]


def _get(url, timeout=15):
    try:
        r = SESSION.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def master_list():
    """Full AMFI scheme list, cached to disk for a week."""
    with _lock:
        if _master_cache["data"] and time.time() - _master_cache["ts"] < MASTER_TTL:
            return _master_cache["data"]
    data = None
    try:
        if os.path.exists(MASTER_FILE):
            data = json.load(open(MASTER_FILE))
        else:
            data = _get("https://api.mfapi.in/mf")
            if data:
                with open(MASTER_FILE, "w") as f:
                    json.dump(data, f)
    except Exception:
        data = None
    with _lock:
        _master_cache["data"] = data
        _master_cache["ts"] = time.time()
    return data


def resolve_schemes():
    """Map each curated keyword -> best scheme (prefer Direct-Growth)."""
    master = master_list()
    out = {}
    if not master:
        return out
    for kw, cat in CURATED:
        matches = [s for s in master if kw.lower() in s["schemeName"].lower()]
        if not matches:
            continue
        # prefer Direct + Growth, then Growth, then anything; avoid special plans
        def pref(s):
            n = s["schemeName"].lower()
            p = 0
            if "direct" in n:
                p += 3
            elif "regular" in n or "retail" in n:
                p += 1
            if "growth" in n and "idcw" not in n and "dividend" not in n:
                p += 1
            for bad in ("institutional", "pf (", "fixed period", "retirement",
                        "super", "nps", "provident fund", "bonus", "payout"):
                if bad in n:
                    p -= 5
            return p
        best = sorted(matches, key=lambda s: -pref(s))[0]
        out[kw] = {"code": best["schemeCode"], "name": best["schemeName"], "category": cat}
    return out


def nav_history(code):
    with _lock:
        cached = _nav_cache.get(code)
        if cached and time.time() - cached[0] < NAV_TTL:
            return cached[1]
    data = _get(f"https://api.mfapi.in/mf/{code}")
    if not data:
        return None
    # parse [{date: 'dd-mm-yyyy', nav: '123.45'}] oldest -> newest
    rows = []
    for d in data.get("data", []):
        try:
            dt = datetime.strptime(d["date"], "%d-%m-%Y")
            rows.append((dt, float(d["nav"])))
        except (ValueError, KeyError, TypeError):
            continue
    rows.sort(key=lambda x: x[0])
    payload = {
        "meta": data.get("meta", {}),
        "dates": [r[0] for r in rows],
        "navs": [r[1] for r in rows],
    }
    with _lock:
        _nav_cache[code] = (time.time(), payload)
    return payload


def nav_on_or_before(navs, dates, target):
    """NAV on the most recent date <= target."""
    if not navs:
        return None
    best = None
    for d, n in zip(dates, navs):
        if d <= target:
            best = n
        else:
            break
    return best


def cagr(nav_now, nav_then, days):
    if not nav_now or not nav_then or nav_then <= 0 or days <= 0:
        return None
    ratio = nav_now / nav_then
    if ratio <= 0:
        return None
    return (ratio ** (365.0 / days) - 1.0) * 100.0


def vol_annualized(navs):
    if not navs or len(navs) < 30:
        return None
    rets = []
    for i in range(1, len(navs)):
        if navs[i - 1] > 0:
            rets.append(navs[i] / navs[i - 1] - 1.0)
    if len(rets) < 20:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252) * 100.0


def max_drawdown(navs):
    if not navs or len(navs) < 30:
        return None
    peak = navs[0]
    mdd = 0.0
    for n in navs:
        if n > peak:
            peak = n
        dd = (peak - n) / peak if peak else 0.0
        if dd > mdd:
            mdd = dd
    return mdd * 100.0


def analyze_fund(scheme):
    h = nav_history(scheme["code"])
    if not h or len(h["navs"]) < 40:
        return None
    navs, dates = h["navs"], h["dates"]
    now_nav = navs[-1]
    today = dates[-1]

    def base_nav(days):
        t = today - timedelta(days=days)
        return nav_on_or_before(navs, dates, t)

    def simple_ret(days):
        base = base_nav(days)
        if not base or base <= 0:
            return None
        return (now_nav / base - 1.0) * 100.0

    # short horizons -> simple returns; long horizons -> annualised CAGR
    r1m = simple_ret(30)
    r3m = simple_ret(90)
    r6m = simple_ret(182)
    r1y = simple_ret(365)
    r3y = cagr(now_nav, base_nav(1095), 1095)
    r5y = cagr(now_nav, base_nav(1825), 1825)

    vol = vol_annualized(navs)
    mdd = max_drawdown(navs[-756:]) if len(navs) >= 756 else max_drawdown(navs)

    score = 50.0
    if r1y is not None:
        score += 0.8 * r1y
    if r3y is not None:
        score += 0.8 * r3y
    if r6m is not None:
        score += 0.3 * r6m
    if r3m is not None:
        score += 0.2 * r3m
    if r1m is not None:
        score += 0.1 * r1m
    if vol is not None:
        score -= 0.5 * vol
    score = max(0.0, min(100.0, score))

    rating = "Excellent" if score >= 74 else "Good" if score >= 62 else \
             "Average" if score >= 50 else "Weak"

    return {
        "code": scheme["code"],
        "name": scheme["name"],
        "category": scheme["category"],
        "fund_house": (h.get("meta") or {}).get("fund_house"),
        "nav": now_nav,
        "nav_date": today.strftime("%d %b %Y"),
        "r1m": round(r1m, 2) if r1m is not None else None,
        "r3m": round(r3m, 2) if r3m is not None else None,
        "r6m": round(r6m, 2) if r6m is not None else None,
        "r1y": round(r1y, 2) if r1y is not None else None,
        "r3y": round(r3y, 2) if r3y is not None else None,
        "r5y": round(r5y, 2) if r5y is not None else None,
        "volatility": round(vol, 2) if vol is not None else None,
        "max_drawdown": round(mdd, 2) if mdd is not None else None,
        "score": round(score, 1),
        "rating": rating,
    }


_funds_cache = {"ts": 0.0, "data": None}
FUNDS_TTL = 6 * 3600


def build_funds():
    with _lock:
        if _funds_cache["data"] and time.time() - _funds_cache["ts"] < FUNDS_TTL:
            return _funds_cache["data"]
    schemes = resolve_schemes()
    funds = []
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(analyze_fund, s): kw for kw, s in schemes.items()}
        for fut in as_completed(futures):
            try:
                f = fut.result()
                if f:
                    funds.append(f)
            except Exception:
                continue
    funds.sort(key=lambda x: -x["score"])
    data = {
        "funds": funds,
        "top": [f for f in funds if f["rating"] in ("Excellent", "Good")][:8],
        "updated_at": time.time(),
        "categories": sorted({f["category"] for f in funds}),
    }
    with _lock:
        _funds_cache["ts"] = time.time()
        _funds_cache["data"] = data
    return data
