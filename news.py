"""
news.py — free news headlines + lightweight keyword sentiment.

Primary source: Google News RSS (no key). Optional fallback: Yahoo Finance
search news. Sentiment is a simple positive/negative keyword score (no AI
API needed) — an honest, dependency-free signal.
"""
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

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

POSITIVE = re.compile(
    r"\b(rally|rallying|surge|surges|soar|soars|jump|jumps|gain|gains|profit|profits|"
    r"beat|beats|upgrade|upgraded|bullish|record|records|rise|rises|rising|strong|"
    r"growth|upbeat|buy|buys|win|wins|top|tops|outperform|exceed|exceeds|boost|boosts|"
    r"positive|breakout|all-?time)\b", re.I)
NEGATIVE = re.compile(
    r"\b(fall|falls|falling|drop|drops|dropping|crash|crashes|crashing|loss|losses|"
    r"miss|misses|downgrade|downgraded|bearish|plunge|plunges|decline|declines|weak|"
    r"sell|sells|sell-?off|debt|lawsuit|fraud|probe|probes|risk|risks|tumble|tumbles|"
    r"slump|slumps|underperform|negative|warning|warns|penalty|fine|fined)\b", re.I)


def _clean(title):
    return re.sub(r"\s+", " ", title or "").strip()


def _sentiment(items):
    pos = neg = 0
    for it in items:
        t = it["title"] + " " + it.get("source", "")
        pos += len(POSITIVE.findall(t))
        neg += len(NEGATIVE.findall(t))
    if pos + neg == 0:
        label, score = "Neutral", 0.0
    elif pos == neg:
        label, score = "Mixed", 0.0
    elif pos > neg:
        label, score = "Positive", round(pos / (pos + neg) * 100, 0)
    else:
        label, score = "Negative", round(-neg / (pos + neg) * 100, 0)
    return {"positive": pos, "negative": neg, "label": label, "score": score}


def google_news(query, limit=10):
    url = "https://news.google.com/rss/search"
    params = {"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"}
    try:
        r = SESSION.get(url, params=params, timeout=12)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
        items = []
        for it in root.findall(".//item")[:limit]:
            title = _clean(it.findtext("title"))
            if not title:
                continue
            source = ""
            t = title.split(" - ")
            if len(t) >= 2:
                title, source = t[0], t[-1]
            pub = ""
            try:
                pd = it.findtext("pubDate")
                if pd:
                    pub = parsedate_to_datetime(pd).astimezone(timezone.utc).strftime("%d %b %Y")
            except Exception:
                pub = ""
            items.append({
                "title": _clean(title),
                "source": source,
                "date": pub,
                "url": it.findtext("link") or "",
            })
        return items
    except Exception:
        return []


def fetch_news(symbol, name, typ="stock"):
    """
    Build a query suited to the asset and return {items, sentiment}.
    """
    if typ == "crypto":
        q = f"{name} crypto price"
    else:
        # use the short display name without exchange suffix
        base = name
        q = f"{base} share price"
    items = google_news(q, 10)
    if not items:
        q2 = f"{symbol} stock"
        items = google_news(q2, 10)
    return {"items": items, "sentiment": _sentiment(items), "query": q}
