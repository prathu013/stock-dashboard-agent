"""
google_finance.py — free Google Finance quote scraper (no API key).

Google Finance has no official API and its page markup varies, so this module
uses several fallback patterns. It is a SAFETY NET: if parsing fails we return
None and the app keeps using Yahoo Finance / CoinGecko.
"""
import re

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


def _gf_candidates(symbol):
    if symbol.endswith(".NS"):
        return [symbol[:-3] + ":NSE"]
    if symbol.endswith(".BO"):
        return [symbol[:-3] + ":BOM"]
    if "." in symbol:
        return [symbol]
    return [f"{symbol}:NASDAQ", f"{symbol}:NYSE"]


_PRICE_PATTERNS = [
    re.compile(r'class="N6SYTe"><span[^>]*><span>([^<]+)</span>'),
    re.compile(r'>[₹$]([\d,]+\.\d{2})<'),
]
_TITLE_RE = re.compile(r"<title>([^<]+)</title>")
_CUR_RE = re.compile(r"&nbsp; &middot; &nbsp; ([A-Z]{3})")


def _num(s):
    if not s:
        return None
    try:
        return float(s.replace(",", "").replace("₹", "").replace("$", "")
                     .replace("−", "-").replace("+", "").replace(" ", ""))
    except (TypeError, ValueError):
        return None


def _extract_pct(html):
    """Change % shown next to the 'Today' label (robust-ish)."""
    i = html.find("Today")
    if i == -1:
        return None
    window = html[max(0, i - 500):i]
    matches = re.findall(r">([+\-−]?\d+\.\d{2})%<", window)
    return matches[-1] if matches else None


def _extract_name(html, symbol):
    m = _TITLE_RE.search(html)
    if m:
        t = m.group(1).strip()
        t = t.split(" (")[0].split(" Stock Price")[0]
        if t and len(t) < 80:
            return t
    return symbol


def quote(symbol):
    """Return {symbol, name, price, change_pct, currency} or None."""
    for gf in _gf_candidates(symbol):
        try:
            r = SESSION.get(f"https://www.google.com/finance/quote/{gf}",
                            params={"hl": "en"}, timeout=12)
            if r.status_code != 200:
                continue
            html = r.text
            price = None
            for pat in _PRICE_PATTERNS:
                m = pat.search(html)
                if m:
                    price = _num(m.group(1))
                    if price:
                        break
            if price is None:
                continue
            pct = _num(_extract_pct(html))
            cur = _CUR_RE.search(html)
            currency = cur.group(1) if cur else ("INR" if gf.endswith((":NSE", ":BOM")) else "USD")
            return {
                "symbol": symbol,
                "name": _extract_name(html, symbol),
                "price": price,
                "change_pct": round(pct, 2) if pct is not None else None,
                "currency": currency,
                "source": "google",
            }
        except Exception:
            continue
    return None
