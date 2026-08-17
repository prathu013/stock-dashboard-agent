"""
advisor.py — the AI Financial Advisor.

Combines, for a given asset:
  - technical score & signal (from the Auto Picks engine)
  - fundamentals (P/E, dividend yield)
  - news sentiment (keyword score)
  - price forecast direction
into ONE clear recommendation with a 0-100 "advisor score", reasons and risks.

Also provides ask_advisor(): a lightweight, dependency-free chat parser that
answers "Should I buy X?", "best stocks today", "my portfolio", etc.
"""
import re

BUY_BANDS = [
    (75, "STRONG BUY"),
    (60, "BUY"),
    (45, "HOLD"),
    (30, "SELL"),
    (-1, "STRONG SELL"),
]


def band(score):
    for threshold, label in BUY_BANDS:
        if score >= threshold:
            return label
    return "STRONG SELL"


def _fund_adj(fund):
    """Fundamentals adjustment (-15..+15)."""
    if not fund:
        return 0.0, []
    adj = 0.0
    reasons = []
    pe = fund.get("pe")
    if pe is not None:
        if 0 < pe <= 15:
            adj += 7
            reasons.append(f"Attractive P/E {pe:.1f} (value)")
        elif 0 < pe <= 25:
            adj += 3
            reasons.append(f"Reasonable P/E {pe:.1f}")
        elif pe > 50:
            adj -= 6
            reasons.append(f"Expensive P/E {pe:.1f}")
        elif pe < 0:
            adj -= 4
            reasons.append("Company has negative earnings")
    div = fund.get("div_yield")
    if div:
        if div >= 3:
            adj += 4
            reasons.append(f"Solid dividend yield {div}%")
        elif div >= 1.5:
            adj += 2
            reasons.append(f"Pays dividend {div}%")
    if fund.get("pb") is not None and 0 < fund["pb"] < 1.5:
        adj += 3
        reasons.append(f"Below book value (P/B {fund['pb']:.1f})")
    return adj, reasons


def _news_adj(sentiment):
    if not sentiment:
        return 0.0, None
    pos, neg = sentiment.get("positive", 0), sentiment.get("negative", 0)
    if pos + neg == 0:
        return 0.0, "News is neutral"
    score = (pos - neg) / (pos + neg) * 15.0   # -15..+15
    label = sentiment.get("label", "Neutral")
    return round(score, 1), f"News sentiment {label} ({pos} pos / {neg} neg mentions)"


def recommend(tech, fund=None, sentiment=None, forecast=None, currency="INR"):
    """
    tech: {score(-100..100), signal, trend, rsi, ...} or None
    fund: {pe, div_yield, pb, ...} or None
    sentiment: news sentiment dict or None
    forecast: forecast dict (direction, up7, up30) or None
    Returns an advisor dict.
    """
    reasons = []
    risks = []
    score = 50.0

    if tech and tech.get("score") is not None:
        score = (tech["score"] + 100.0) / 2.0        # map -100..100 -> 0..100
        reasons.append(f"Technical score {tech['score']} — {tech.get('signal')}")
        rsi = tech.get("rsi")
        if rsi is not None:
            if rsi >= 70:
                risks.append(f"RSI {rsi} — overbought, pullback possible")
            elif rsi <= 30:
                reasons.append(f"RSI {rsi} — oversold, bounce possible")
    else:
        risks.append("No technical history available")

    fadj, freasons = _fund_adj(fund)
    score += fadj
    reasons += freasons
    if not fund:
        risks.append("No fundamentals data (small/illiquid asset)")

    nadj, nmsg = _news_adj(sentiment)
    score += nadj
    if nmsg:
        reasons.append(nmsg)

    if forecast:
        if forecast.get("direction") == "Uptrend":
            score += 4
            reasons.append(f"Forecast: uptrend (+{forecast.get('up30', 0)}% 30-day projection)")
        elif forecast.get("direction") == "Downtrend":
            score -= 5
            risks.append(f"Forecast: downtrend ({forecast.get('up30', 0)}% 30-day projection)")
        else:
            reasons.append("Forecast: sideways")

    score = max(0.0, min(100.0, score))
    verdict = band(score)

    if verdict in ("STRONG BUY", "BUY") and forecast and forecast.get("direction") == "Downtrend":
        risks.append("Momentum is currently down — consider waiting or buying in parts")
    if verdict in ("SELL", "STRONG SELL") and tech and tech.get("score", 0) > 40:
        risks.append("Technical trend still positive — it may be a dip, not a breakdown")

    return {
        "score": round(score, 1),
        "verdict": verdict,
        "reasons": reasons[:6],
        "risks": risks[:4],
        "components": {
            "technical": tech.get("signal") if tech else None,
            "fundamental_score": round(fadj, 1),
            "news_score": nmsg,
            "forecast": (forecast or {}).get("direction"),
        },
    }


# ---------------------------------------------------------------- ask-me chat
FILLERS = re.compile(
    r"(?i)\b(should i|should we|do i|can i|is it good to|is it a good idea to|"
    r"what about|how about|how is|how are|tell me about|thoughts on|opinion on|"
    r"what do you think about|whats? the price of|price of|give me advice on|"
    r"advice on|analy|scan|check|recommend|rate|review)\b")
BUY_WORDS = re.compile(r"(?i)\b(buy|invest|add|enter)\b")
SELL_WORDS = re.compile(r"(?i)\b(sell|exit|book profit|liquidate)\b")


def _strip(question):
    q = FILLERS.sub(" ", question)
    for w in ("should", "i", "we", "you", "please", "plz", "the", "a", "an",
              "today", "now", "right now", "for me", "buy", "sell", "hold",
              "invest", "investing", "purchase", "book", "enter", "exit",
              "?", "？", "."):
        try:
            q = re.sub(r"\b" + re.escape(w) + r"\b", " ", q, flags=re.I)
        except re.error:
            q = q.replace(w, " ")
    return re.sub(r"\s+", " ", q).strip()


def resolve_asset(question, search_fn, top_coins):
    """Try to find an asset mentioned in the question.
    search_fn(q) -> list of search results. Returns (type, symbol, name, currency) or None."""
    q = _strip(question)
    if not q:
        return None
    # direct coin match first
    for cid, ticker in top_coins:
        name = cid.replace("-", " ").title()
        if name.lower() in q.lower() or ticker.lower() == q.lower():
            return ("crypto", cid, name, "INR")
    # try search with the full remaining text
    res = search_fn(q) or []
    # try shorter prefixes too
    words = q.split()
    for n in (3, 2):
        if len(words) >= n and not res:
            res = search_fn(" ".join(words[:n])) or []
    if not res:
        return None

    # rank results: exact ticker/name match first, prefer Indian stocks for
    # ambiguous names (e.g. "reliance" -> Reliance Industries, "TCS" -> TCS.NS)
    ql = q.lower()

    def score(r):
        tk = (r.get("ticker") or "").lower()
        base = tk.split(".")[0]
        nm = (r.get("name") or "").lower()
        s = 0
        if base == ql:
            s += 120
        elif nm == ql:
            s += 100
        elif nm.startswith(ql):
            s += 70
        elif ql in nm:
            s += 55
        elif ql in base:
            s += 45
        if r["type"] == "stock_in":
            s += 15
        return s

    r = max(res, key=score)
    return (r["type"], r["symbol"], r["name"], r.get("currency", "INR"))
