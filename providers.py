"""
providers.py — optional free API-key providers (Twelve Data, Finnhub, Alpha
Vantage). If the user pastes a key in ⚙ Settings, these become extra/fallback
price sources. Without keys, the dashboard keeps working on CoinGecko/Yahoo.

Free-plan note (rough, may change):
  - Twelve Data: 8 req/min, 800 req/day, real-time for many US symbols
  - Finnhub: 60 req/min, free US real-time quotes
  - Alpha Vantage: very limited free (25 req/day), 15-min delayed
"""
import time

import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
SESSION = requests.Session()
SESSION.headers.update(UA)
try:
    from requests.adapters import HTTPAdapter
    for _proto in ("http://", "https://"):
        SESSION.mount(_proto, HTTPAdapter(pool_connections=20, pool_maxsize=20))
except Exception:
    pass


def twelvedata_quote(symbol, key):
    try:
        r = SESSION.get("https://api.twelvedata.com/quote",
                        params={"symbol": symbol, "apikey": key}, timeout=10)
        j = r.json()
        if "price" in j and j["price"]:
            return {
                "symbol": symbol,
                "name": j.get("name") or symbol,
                "price": float(j["price"]),
                "change_pct": (float(j.get("percent_change")) if j.get("percent_change") else None),
                "currency": (j.get("currency") or "USD").upper(),
            }
    except Exception:
        pass
    return None


def finnhub_quote(symbol, key):
    try:
        r = SESSION.get("https://finnhub.io/api/v1/quote",
                        params={"symbol": symbol, "token": key}, timeout=10)
        j = r.json()
        c = j.get("c")
        if c:
            prev = j.get("pc") or c
            pct = ((c - prev) / prev * 100.0) if prev else None
            return {
                "symbol": symbol,
                "name": symbol,
                "price": float(c),
                "change_pct": round(pct, 2) if pct is not None else None,
                "currency": "USD",
            }
    except Exception:
        pass
    return None


def alpha_quote(symbol, key):
    try:
        r = SESSION.get("https://www.alphavantage.co/query",
                        params={"function": "GLOBAL_QUOTE", "symbol": symbol,
                                "apikey": key}, timeout=10)
        j = r.json().get("Global Quote") or {}
        price = j.get("05. price")
        if price:
            prev = j.get("08. previous close") or price
            pct = ((float(price) - float(prev)) / float(prev) * 100.0) if prev else None
            return {
                "symbol": symbol,
                "name": symbol,
                "price": float(price),
                "change_pct": round(pct, 2) if pct is not None else None,
                "currency": "USD",
            }
    except Exception:
        pass
    return None


def provider_quote(symbol, settings):
    """Try each configured provider in order for a quote. Returns None if none work."""
    k = settings.get("twelve_data_key")
    if k:
        q = twelvedata_quote(symbol, k)
        if q:
            return q
    k = settings.get("finnhub_key")
    if k:
        q = finnhub_quote(symbol, k)
        if q:
            return q
    k = settings.get("alpha_vantage_key")
    if k:
        q = alpha_quote(symbol, k)
        if q:
            return q
    return None
