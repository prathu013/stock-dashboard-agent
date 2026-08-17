"""
Daily Stock & Crypto Analyzer
- Market movers (top gainers/losers) for Crypto, Indian stocks, US stocks
- Personal watchlist with live profit/loss (₹ for INR assets, $ for US assets)
- Free data, no API key:
    Crypto   -> CoinGecko (primary, INR) with OKX / Coinbase Exchange fallback
    Stocks   -> Yahoo Finance (NSE .NS symbols + US tickers)

Run:  python app.py   ->  http://0.0.0.0:8000
"""
import os
import json
import re
import time
import uuid
import threading
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from flask import Flask, request, jsonify, send_from_directory, send_file

import analysis
import funds as funds_mod
import alerts as alerts_mod
import report as report_mod
import forecast as forecast_mod
import mailer as mailer_mod
import technicals as technicals_mod
import news as news_mod
import portfolio as portfolio_mod
import advisor as advisor_mod
import planner as planner_mod
import journal as journal_mod
import providers as providers_mod
import kite_api as kite_mod
import telegram_bot as telegram_mod
import google_finance as gf_mod
import angel_api as angel_mod

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
os.makedirs(DATA_DIR, exist_ok=True)
WATCHLIST_FILE = os.path.join(DATA_DIR, "watchlist.json")

app = Flask(__name__, static_folder=os.path.join(BASE, "static"), static_url_path="")

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
SESSION = requests.Session()
SESSION.headers.update(UA)

# ---------------------------------------------------------------- universes
NIFTY50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "BHARTIARTL.NS", "SBIN.NS", "ITC.NS", "LT.NS", "HINDUNILVR.NS",
    "AXISBANK.NS", "KOTAKBANK.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "HCLTECH.NS", "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS", "NTPC.NS",
    "POWERGRID.NS", "M&M.NS", "TMCV.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "TATASTEEL.NS", "JSWSTEEL.NS", "GRASIM.NS", "BAJAJFINSV.NS", "NESTLEIND.NS",
    "WIPRO.NS", "TECHM.NS", "COALINDIA.NS", "ONGC.NS", "BPCL.NS",
    "DRREDDY.NS", "CIPLA.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS",
    "INDUSINDBK.NS", "SBILIFE.NS", "HDFCLIFE.NS", "DIVISLAB.NS", "BRITANNIA.NS",
    "HINDALCO.NS", "APOLLOHOSP.NS", "TATACONSUM.NS", "UPL.NS", "LTTS.NS",
]

US50 = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "BRK-B",
    "JPM", "LLY", "V", "UNH", "XOM", "ORCL", "MA", "HD", "PG", "COST", "JNJ",
    "ABBV", "NFLX", "AMD", "CRM", "BAC", "CVX", "KO", "WMT", "MRK", "PEP",
    "ADBE", "TMO", "CSCO", "ACN", "MCD", "IBM", "LIN", "ABT", "GE", "CAT",
    "INTU", "QCOM", "TXN", "AMGN", "PFE", "DIS", "GS", "MS", "VZ", "NKE",
]

# ---------------------------------------------------------------- caches
_movers_cache = {"ts": 0.0, "data": None}
_movers_lock = threading.Lock()
_detail_cache = {"data": {}}   # key -> (ts, payload)
_detail_lock = threading.Lock()
_watch_lock = threading.Lock()
_fx_cache = {"ts": 0.0, "rate": None}

MOVERS_TTL = 150
DETAIL_TTL = 300


# ---------------------------------------------------------------- persistence
def load_watchlist():
    try:
        with open(WATCHLIST_FILE) as f:
            items = json.load(f)
        return items if isinstance(items, list) else []
    except Exception:
        return []


def save_watchlist(items):
    with _watch_lock:
        with open(WATCHLIST_FILE, "w") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------- data fetchers
def yahoo_chart(symbol, rng="5d"):
    """Quote + N-day sparkline for a Yahoo symbol (e.g. RELIANCE.NS, AAPL)."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        r = SESSION.get(url, params={"range": rng, "interval": "1d"}, timeout=8)
        if r.status_code != 200:
            return None
        results = r.json().get("chart", {}).get("result")
        if not results:
            return None
        res = results[0]
        meta = res.get("meta", {})
        price = meta.get("regularMarketPrice")
        if price is None:
            return None
        prev = meta.get("chartPreviousClose") or meta.get("previousClose") or price
        spark = None
        try:
            closes = res["indicators"]["quote"][0].get("close") or []
            spark = [c for c in closes if c is not None]
        except Exception:
            spark = None
        change = price - prev if prev else 0.0
        pct = (change / prev * 100.0) if prev else 0.0
        return {
            "symbol": symbol,
            "name": meta.get("shortName") or meta.get("longName") or symbol,
            "price": price,
            "prev_close": prev,
            "change": change,
            "change_pct": pct,
            "currency": (meta.get("currency") or "USD").upper(),
            "sparkline": spark,
        }
    except Exception:
        pass
    # ---- Google Finance fallback (free, no key) ----
    try:
        gq = gf_mod.quote(symbol)
        if gq and gq.get("price"):
            return {
                "symbol": symbol,
                "name": gq.get("name") or symbol,
                "price": gq["price"],
                "prev_close": None,
                "change": None,
                "change_pct": gq.get("change_pct"),
                "currency": gq.get("currency") or "USD",
                "sparkline": None,
            }
    except Exception:
        pass
    return None


def coingecko_get(path, params=None, retries=3):
    """CoinGecko GET with retry/backoff (their free tier rate-limits now and then)."""
    url = "https://api.coingecko.com/api/v3" + path
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params or {}, timeout=15)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(1.2 * (attempt + 1))
    return None


def usd_inr():
    """USD->INR rate from Yahoo (INR=X), cached 10 min."""
    now = time.time()
    if _fx_cache["rate"] and now - _fx_cache["ts"] < 600:
        return _fx_cache["rate"]
    d = yahoo_chart("INR=X", "5d")
    if d and d.get("price"):
        _fx_cache["rate"] = float(d["price"])
        _fx_cache["ts"] = now
        return _fx_cache["rate"]
    return _fx_cache["rate"]


def okx_get(path, params, retries=3):
    """OKX public GET with retry (their rate limiter occasionally returns 51001)."""
    url = "https://www.okx.com/api/v5/market" + path
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=12)
            if r.status_code == 200:
                j = r.json()
                if j.get("code") == "0":
                    return j
        except Exception:
            pass
        time.sleep(0.8 * (attempt + 1))
    return None


def okx_crypto_movers():
    """Fallback: all OKX spot tickers (USDT pairs) in one call."""
    j = okx_get("/tickers", {"instType": "SPOT"})
    if not j:
        return None
    fx = usd_inr() or 1.0
    items = []
    for t in j.get("data", []):
        inst = t.get("instId", "")
        if not inst.endswith("-USDT"):
            continue
        base = inst[:-5]
        if base.endswith(("3L", "3S", "5L", "5S", "2L", "2S", "BULL", "BEAR")):
            continue
        try:
            last = float(t.get("last") or 0)
            open24 = float(t.get("open24h") or 0)
            vol = float(t.get("volCcy24h") or 0)
        except (TypeError, ValueError):
            continue
        if last <= 0 or open24 <= 0 or vol < 800000:   # meaningful liquidity
            continue
        pct = (last - open24) / open24 * 100.0
        items.append({
            "id": base.lower(), "ticker": base, "name": base,
            "price": last * fx, "change_pct": pct,
            "sparkline": [], "currency": "INR", "_vol": vol,
        })
    if not items:
        return None
    by_vol = sorted(items, key=lambda x: x["_vol"], reverse=True)
    for it in by_vol:
        it.pop("_vol", None)
    items.sort(key=lambda x: -x["change_pct"])
    return {"gainers": items[:12], "losers": list(reversed(items[-12:])),
            "all": by_vol, "count": len(items), "source": "okx"}


def okx_coin_detail(base):
    """Fallback detail for one coin from OKX (daily candles), converted to INR."""
    inst = base.upper() + "-USDT"
    j = okx_get("/candles", {"instId": inst, "bar": "1D", "limit": "8"})
    if not j:
        return None
    rows = (j.get("data") or [])[::-1]          # oldest first
    try:
        closes = [float(x[4]) for x in rows]
    except (TypeError, ValueError, IndexError):
        return None
    if not closes:
        return None
    fx = usd_inr() or 1.0
    t = okx_get("/ticker", {"instId": inst})
    last = closes[-1]
    if t and t.get("data"):
        try:
            last = float(t["data"][0].get("last") or last)
        except (TypeError, ValueError):
            pass
    pct = ((last - closes[-2]) / closes[-2] * 100.0) if len(closes) >= 2 else None
    return {
        "name": base, "symbol": base.lower(), "ticker": base,
        "price": last * fx, "change_pct": pct,
        "sparkline": [c * fx for c in closes], "currency": "INR",
    }


# ---------------------------------------------------------------- movers
def _crypto_movers():
    coins = coingecko_get("/coins/markets", {
        "vs_currency": "inr", "order": "market_cap_desc", "per_page": 250,
        "page": 1, "sparkline": "true", "price_change_percentage": "24h",
    })
    if coins is None:
        return okx_crypto_movers() or {"gainers": [], "losers": [], "all": [], "count": 0}

    items = []
    for c in coins:
        pct = c.get("price_change_percentage_24h_in_currency")
        if pct is None:
            continue
        items.append({
            "id": c.get("id"),
            "ticker": (c.get("symbol") or "?").upper(),
            "name": c.get("name"),
            "price": c.get("current_price"),
            "change_pct": pct,
            "sparkline": (c.get("sparkline_in_7d") or {}).get("price") or [],
            "currency": "INR",
        })
    by_mcap = list(items)                       # CoinGecko returns market-cap order
    items.sort(key=lambda x: -x["change_pct"])
    return {"gainers": items[:12], "losers": list(reversed(items[-12:])),
            "all": by_mcap, "count": len(items), "source": "coingecko"}


def _stock_movers(symbols):
    out = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = {ex.submit(yahoo_chart, s, "5d"): s for s in symbols}
        for fut in as_completed(futures):
            d = fut.result()
            if d:
                out.append(d)
    out = [d for d in out if d["change_pct"] is not None]
    out.sort(key=lambda x: -x["change_pct"])
    return {"gainers": out[:10], "losers": list(reversed(out[-10:])),
            "all": out, "count": len(out)}


def build_movers():
    with _movers_lock:
        if _movers_cache["data"] and time.time() - _movers_cache["ts"] < MOVERS_TTL:
            return _movers_cache["data"]

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_crypto = ex.submit(_crypto_movers)
        f_in = ex.submit(_stock_movers, NIFTY50)
        f_us = ex.submit(_stock_movers, US50)
        crypto = f_crypto.result()
        stocks_in = f_in.result()
        stocks_us = f_us.result()

    data = {
        "crypto": crypto,
        "stocks_in": stocks_in,
        "stocks_us": stocks_us,
        "updated_at": time.time(),
    }
    with _movers_lock:
        _movers_cache["ts"] = time.time()
        _movers_cache["data"] = data
    return data


def movers_crypto_map():
    """id -> coin item from the cached movers (avoids extra CoinGecko calls)."""
    m = _movers_cache["data"]
    if not m:
        return {}
    return {c["id"]: c for c in (m["crypto"].get("all") or [])}


# ---------------------------------------------------------------- watchlist
def build_watchlist():
    items = load_watchlist()
    cache_map = movers_crypto_map()
    missing_ids = [i["symbol"] for i in items
                   if i["type"] == "crypto" and i["symbol"] not in cache_map]
    cmap = dict(cache_map)
    if missing_ids:
        coins = coingecko_get("/coins/markets", {
            "vs_currency": "inr", "ids": ",".join(missing_ids),
            "sparkline": "true", "price_change_percentage": "24h",
        }) or []
        for c in coins:
            cmap[c["id"]] = c

    # live price overrides: Zerodha Kite / Angel One (true real-time NSE)
    settings = mailer_mod.load_settings()
    kite_prices = {}
    angel_prices = {}
    in_syms = [i["symbol"] for i in items if i["type"] == "stock_in"]
    if settings.get("zerodha_enabled") and in_syms:
        try:
            kite_prices = kite_mod.get_ltp(in_syms, settings)
        except Exception:
            kite_prices = {}
    if settings.get("angel_enabled") and in_syms:
        try:
            angel_prices = angel_mod.ltp(in_syms, settings)
        except Exception:
            angel_prices = {}

    out = []
    for it in items:
        cur = change_pct = spark = None
        if it["type"] == "crypto":
            c = cmap.get(it["symbol"])
            if c:
                if "ticker" in c:            # from movers cache (already processed)
                    cur = c["price"]
                    change_pct = c["change_pct"]
                    spark = c["sparkline"]
                else:                        # raw coin from coins/markets
                    cur = c.get("current_price")
                    change_pct = c.get("price_change_percentage_24h_in_currency")
                    spark = (c.get("sparkline_in_7d") or {}).get("price")
        else:
            d = yahoo_chart(it["symbol"], "5d")
            if d:
                cur = d["price"]
                change_pct = d["change_pct"]
                spark = d["sparkline"]
            else:
                # Yahoo failed -> Google Finance fallback (free, no key)
                if settings.get("google_finance_enabled", True):
                    gq = gf_mod.quote(it["symbol"])
                    if gq and gq.get("price"):
                        cur = gq["price"]
                        change_pct = gq.get("change_pct")
            # provider key override for US/other symbols (if keys set)
            if it["type"] != "stock_in":
                pq = providers_mod.provider_quote(it["symbol"], settings)
                if pq and pq.get("price"):
                    cur = pq["price"]
                    change_pct = pq.get("change_pct")
            # Zerodha / Angel One live price wins for Indian stocks
            if it["type"] == "stock_in" and it["symbol"] in kite_prices:
                cur = kite_prices[it["symbol"]]
            if it["type"] == "stock_in" and it["symbol"] in angel_prices:
                cur = angel_prices[it["symbol"]]

        bp = float(it.get("buy_price") or 0)
        qty = float(it.get("qty") or 0)
        invested = bp * qty
        value = cur * qty if cur is not None else None
        pnl = (value - invested) if value is not None else None
        pnl_pct = ((cur - bp) / bp * 100.0) if cur is not None and bp else None

        out.append({
            "id": it["id"], "type": it["type"], "symbol": it["symbol"],
            "ticker": it.get("ticker") or it["symbol"],
            "name": it.get("name") or it["symbol"],
            "currency": it.get("currency") or ("USD" if it["type"] == "stock_us" else "INR"),
            "buy_price": bp, "qty": qty, "added_at": it.get("added_at"),
            "current_price": cur, "change_pct": change_pct, "sparkline": spark,
            "invested": invested, "value": value, "pnl": pnl, "pnl_pct": pnl_pct,
        })

    totals = {
        "INR": {"invested": 0.0, "value": 0.0, "pnl": 0.0, "count": 0},
        "USD": {"invested": 0.0, "value": 0.0, "pnl": 0.0, "count": 0},
    }
    for o in out:
        t = totals.get(o["currency"], totals["USD"])
        t["invested"] += o["invested"]
        if o["value"] is not None:
            t["value"] += o["value"]
        if o["pnl"] is not None:
            t["pnl"] += o["pnl"]
        t["count"] += 1
    return {"items": out, "totals": totals}


# ---------------------------------------------------------------- search & detail
def search(q):
    results = []
    coins = coingecko_get("/search", {"query": q}, retries=2)
    if coins:
        for c in coins.get("coins", [])[:6]:
            results.append({
                "type": "crypto", "symbol": c["id"],
                "ticker": (c.get("symbol") or "?").upper(),
                "name": c.get("name"), "currency": "INR", "market": "Crypto",
            })
    try:
        r = SESSION.get("https://query1.finance.yahoo.com/v1/finance/search",
                        params={"q": q, "quotesCount": 12, "newsCount": 0}, timeout=8)
        if r.status_code == 200:
            for item in r.json().get("quotes", []):
                if item.get("quoteType") not in ("EQUITY", "ETF", "MUTUALFUND", "INDEX"):
                    continue
                sym = item.get("symbol") or ""
                if not sym or sym.startswith("^"):
                    continue
                exch = item.get("exchDisp") or ""
                if ".NS" in sym or ".BO" in sym or "NSE" in exch or "BSE" in exch:
                    typ, cur, market = "stock_in", "INR", "NSE/BSE"
                else:
                    typ, cur, market = "stock_us", "USD", exch or "US"
                results.append({
                    "type": typ, "symbol": sym, "ticker": sym,
                    "name": item.get("shortname") or item.get("longname") or sym,
                    "currency": cur, "market": market,
                })
    except Exception:
        pass
    return results[:14]


def get_detail(typ, sym):
    key = f"{typ}:{sym}"
    now = time.time()
    with _detail_lock:
        cached = _detail_cache["data"].get(key)
        if cached and now - cached[0] < DETAIL_TTL:
            return cached[1]

    data = None
    if typ == "crypto":
        cm = movers_crypto_map()
        coin = cm.get(sym)
        if coin:
            data = {"name": coin["name"], "symbol": coin["id"], "ticker": coin["ticker"],
                    "price": coin["price"], "change_pct": coin["change_pct"],
                    "sparkline": coin["sparkline"], "currency": "INR"}
        else:
            j = coingecko_get(f"/coins/{sym}/market_chart",
                              {"vs_currency": "inr", "days": "7", "interval": "daily"})
            if j:
                prices = [p[1] for p in j.get("prices", [])]
                data = {"name": sym, "symbol": sym, "ticker": sym.upper(),
                        "price": prices[-1] if prices else None, "change_pct": None,
                        "sparkline": prices, "currency": "INR"}
            else:
                data = okx_coin_detail(sym)
    else:
        data = yahoo_chart(sym, "5d")

    if data:
        with _detail_lock:
            _detail_cache["data"][key] = (now, data)
    return data


# ---------------------------------------------------------------- signals engine
_signals_cache = {"ts": 0.0, "data": None, "busy": False}
_signals_lock = threading.Lock()
_crypto_hist_cache = {}   # id -> (ts, payload)
_hist_lock = threading.Lock()

SIGNALS_TTL = 600          # stocks refresh every 10 min
CRYPTO_HIST_TTL = 21600    # crypto history cached 6 h


def yahoo_history(symbol, rng="3mo"):
    """Daily closes/highs/lows for a Yahoo symbol + current quote."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        r = SESSION.get(url, params={"range": rng, "interval": "1d"}, timeout=10)
        if r.status_code != 200:
            return None
        res = r.json().get("chart", {}).get("result")
        if not res:
            return None
        res = res[0]
        meta = res.get("meta", {})
        q = res["indicators"]["quote"][0]
        closes = [c for c in (q.get("close") or []) if c is not None]
        highs = [h for h in (q.get("high") or []) if h is not None]
        lows = [l for l in (q.get("low") or []) if l is not None]
        opens = [o for o in (q.get("open") or []) if o is not None]
        if not closes:
            return None
        price = meta.get("regularMarketPrice") or closes[-1]
        prev = meta.get("chartPreviousClose") or meta.get("previousClose") or price
        return {
            "symbol": symbol,
            "name": meta.get("shortName") or meta.get("longName") or symbol,
            "currency": (meta.get("currency") or "USD").upper(),
            "price": price,
            "change_pct": ((price - prev) / prev * 100.0) if prev else 0.0,
            "closes": closes, "highs": highs, "lows": lows, "opens": opens,
        }
    except Exception:
        return None


def _okx_candles(inst, limit=90):
    j = okx_get("/candles", {"instId": inst, "bar": "1D", "limit": str(limit)})
    if not j or not j.get("data"):
        return None
    rows = (j["data"])[::-1]  # oldest first
    try:
        o = [float(x[1]) for x in rows]
        h = [float(x[2]) for x in rows]
        l = [float(x[3]) for x in rows]
        c = [float(x[4]) for x in rows]
        return {"open": o, "high": h, "low": l, "close": c}
    except (TypeError, ValueError, IndexError):
        return None


def _coingecko_ohlc(coin_id, days=90):
    j = coingecko_get(f"/coins/{coin_id}/ohlc", {"vs_currency": "inr", "days": str(days)}, retries=2)
    if not j:
        return None
    try:
        o = [x[1] for x in j]
        h = [x[2] for x in j]
        l = [x[3] for x in j]
        c = [x[4] for x in j]
        return {"open": o, "high": h, "low": l, "close": c}
    except (TypeError, ValueError, IndexError):
        return None


def crypto_ohlc(coin_id, ticker):
    """Daily OHLC for a coin, in INR. OKX first (fast), CoinGecko fallback."""
    with _hist_lock:
        cached = _crypto_hist_cache.get(coin_id)
        if cached and time.time() - cached[0] < CRYPTO_HIST_TTL:
            return cached[1]

    data = None
    if ticker:
        data = _okx_candles(f"{ticker.upper()}-USDT", 90)
        if data:
            fx = usd_inr() or 1.0
            data = {k: ([v * fx for v in arr] if arr else arr) for k, arr in data.items()}
    if data is None:
        data = _coingecko_ohlc(coin_id, 90)
    if data:
        with _hist_lock:
            _crypto_hist_cache[coin_id] = (time.time(), data)
    return data


# Top coins by market cap (stable list) — used for the signals universe so we
# don't depend on CoinGecko's flaky /coins/markets ordering or OKX volume order.
TOP_COINS = [
    ("bitcoin", "BTC"), ("ethereum", "ETH"), ("bnb", "BNB"),
    ("solana", "SOL"), ("xrp", "XRP"), ("cardano", "ADA"),
    ("dogecoin", "DOGE"), ("tron", "TRX"), ("avalanche-2", "AVAX"),
    ("chainlink", "LINK"), ("polkadot", "DOT"), ("polygon-ecosystem-token", "POL"),
    ("litecoin", "LTC"), ("bitcoin-cash", "BCH"), ("shiba-inu", "SHIB"),
    ("the-open-network", "TON"), ("uniswap", "UNI"), ("near", "NEAR"),
    ("aptos", "APT"), ("sui", "SUI"),
]


def coin_quote(coin_id, ticker):
    """Current price + 24h change for a coin (₹). Multiple fallbacks."""
    cm = movers_crypto_map()
    c = cm.get(coin_id)
    if c:
        return {"price": c["price"], "change_pct": c["change_pct"], "name": c["name"]}
    j = coingecko_get("/simple/price",
                      {"ids": coin_id, "vs_currencies": "inr",
                       "include_24hr_change": "true"}, retries=2)
    if j and coin_id in j:
        d = j[coin_id]
        return {"price": d.get("inr"), "change_pct": d.get("inr_24h_change"),
                "name": coin_id.replace("-", " ").title()}
    if ticker:
        t = okx_get("/ticker", {"instId": f"{ticker.upper()}-USDT"})
        if t and t.get("data"):
            d = t["data"][0]
            try:
                last = float(d["last"])
                open24 = float(d["open24h"])
                fx = usd_inr() or 1.0
                pct = (last - open24) / open24 * 100.0 if open24 else None
                return {"price": last * fx, "change_pct": pct, "name": ticker.upper()}
            except (TypeError, ValueError, KeyError):
                pass
    return None


def _signal_for_stock(hist):
    a = analysis.analyze(hist["closes"], hist["highs"], hist["lows"],
                         {"price": hist["price"]})
    if not a:
        return None
    return {
        "type": "stock_in" if hist["symbol"].endswith((".NS", ".BO")) else "stock_us",
        "symbol": hist["symbol"], "ticker": hist["symbol"],
        "name": hist["name"], "currency": hist["currency"],
        "price": hist["price"], "change_pct": hist["change_pct"],
        "sparkline": hist["closes"], **a,
    }


def _signal_for_crypto(coin_id, ticker):
    quote = coin_quote(coin_id, ticker)
    ohlc = crypto_ohlc(coin_id, ticker)
    if not ohlc or not ohlc.get("close") or len(ohlc["close"]) < 30:
        return None
    closes = ohlc["close"]
    # skip stablecoins / pegged assets (they barely move, so they can't trend)
    hi, lo = max(closes), min(closes)
    if lo > 0 and (hi / lo - 1.0) < 0.02:
        return None
    price = (quote or {}).get("price") or closes[-1]
    a = analysis.analyze(closes, ohlc.get("high"), ohlc.get("low"),
                         {"price": price})
    if not a:
        return None
    return {
        "type": "crypto", "symbol": coin_id, "ticker": ticker,
        "name": (quote or {}).get("name") or coin_id.replace("-", " ").title(),
        "currency": "INR", "price": price,
        "change_pct": (quote or {}).get("change_pct"),
        "sparkline": closes, **a,
    }


def _empty_signals():
    return {"crypto": [], "stocks_in": [], "stocks_us": [],
            "overview": {}, "updated_at": time.time()}


def wait_for_signals(timeout=20):
    """Block briefly until the signals cache is populated (or timeout)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        d = build_signals() or {}
        if d.get("stocks_in") or d.get("crypto"):
            return d
        time.sleep(2)
    return build_signals() or _empty_signals()


def build_signals():
    """Analyse crypto (top 30), NIFTY 50 and US 50 -> scored buy/sell signals.

    NEVER returns None: callers (advisor, API) rely on dict access.
    """
    with _signals_lock:
        if _signals_cache["data"] and time.time() - _signals_cache["ts"] < SIGNALS_TTL:
            return _signals_cache["data"]
        if _signals_cache["busy"]:
            # another thread is building; return what we have (or empty)
            return _signals_cache["data"] or _empty_signals()

    _signals_cache["busy"] = True
    try:
        try:
            build_movers()  # warms the crypto quote cache for coin_quote()
        except Exception:
            pass

        crypto_items, in_items, us_items = [], [], []
        with ThreadPoolExecutor(max_workers=12) as ex:
            f_crypto = {ex.submit(_signal_for_crypto, cid, tk): (cid, tk) for cid, tk in TOP_COINS}
            f_in = {ex.submit(yahoo_history, s, "3mo"): s for s in NIFTY50}
            f_us = {ex.submit(yahoo_history, s, "3mo"): s for s in US50}
            for fut in as_completed(f_crypto):
                r = fut.result()
                if r:
                    crypto_items.append(r)
            for fut in as_completed(f_in):
                r = fut.result()
                if r:
                    s = _signal_for_stock(r)
                    if s:
                        in_items.append(s)
            for fut in as_completed(f_us):
                r = fut.result()
                if r:
                    s = _signal_for_stock(r)
                    if s:
                        us_items.append(s)

        def sortit(lst):
            lst.sort(key=lambda x: -x["score"])
            return lst

        data = {
            "crypto": sortit(crypto_items),
            "stocks_in": sortit(in_items),
            "stocks_us": sortit(us_items),
            "overview": _build_overview(crypto_items, in_items, us_items),
            "updated_at": time.time(),
        }
        with _signals_lock:
            _signals_cache["ts"] = time.time()
            _signals_cache["data"] = data
            _signals_cache["busy"] = False
        return data
    except Exception:
        with _signals_lock:
            _signals_cache["busy"] = False
        # fall back to whatever we had, or an empty structure (never None)
        return _signals_cache["data"] or _empty_signals()


def _build_overview(crypto_items, in_items, us_items):
    ov = {}
    for key, items, label in (("crypto", crypto_items, "Crypto"),
                              ("stocks_in", in_items, "Indian stocks"),
                              ("stocks_us", us_items, "US stocks")):
        if not items:
            ov[key] = {"label": label, "count": 0, "buys": 0, "sells": 0,
                       "top": None, "avg_score": None, "avg_change": None}
            continue
        buys = sum(1 for i in items if i["signal"] in ("STRONG BUY", "BUY"))
        sells = sum(1 for i in items if i["signal"] in ("SELL", "STRONG SELL"))
        avg_score = sum(i["score"] for i in items) / len(items)
        changes = [i["change_pct"] for i in items if i["change_pct"] is not None]
        top = items[0]
        ov[key] = {
            "label": label, "count": len(items),
            "buys": buys, "sells": sells, "holds": len(items) - buys - sells,
            "top": {"name": top["name"], "ticker": top["ticker"], "signal": top["signal"],
                    "score": top["score"], "price": top["price"], "currency": top["currency"],
                    "target": top["target"], "stop": top["stop"],
                    "pnl_pct_target": top["pnl_pct_target"], "pnl_pct_stop": top["pnl_pct_stop"],
                    "hold_label": top["hold_label"]},
            "avg_score": round(avg_score, 1),
            "avg_change": round(sum(changes) / len(changes), 2) if changes else None,
        }
    return ov


# ---------------------------------------------------------------- screener (fundamentals)
_screen_cache = {"ts": 0.0, "data": None, "busy": False}
_screen_lock = threading.Lock()
SCREEN_TTL = 1800


def _fundamentals(symbol):
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        info = t.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            return None
        rate = info.get("trailingAnnualDividendRate") or 0.0
        div_yield = (rate / price * 100.0) if price else None
        return {
            "symbol": symbol,
            "name": info.get("shortName") or info.get("longName") or symbol,
            "currency": (info.get("currency") or
                         ("INR" if symbol.endswith((".NS", ".BO")) else "USD")),
            "price": price,
            "pe": info.get("trailingPE"),
            "fwd_pe": info.get("forwardPE"),
            "market_cap": info.get("marketCap"),
            "div_yield": round(div_yield, 2) if div_yield is not None else None,
            "pb": info.get("priceToBook"),
            "hi52": info.get("fiftyTwoWeekHigh"),
            "lo52": info.get("fiftyTwoWeekLow"),
            "sector": info.get("sector") or info.get("industry"),
            "avg_volume": info.get("averageVolume"),
        }
    except Exception:
        return None


def build_screener():
    with _screen_lock:
        if _screen_cache["data"] and time.time() - _screen_cache["ts"] < SCREEN_TTL:
            return _screen_cache["data"]
        if _screen_cache["busy"]:
            return _screen_cache["data"]
    _screen_cache["busy"] = True
    try:
        # attach our technical signal score where available
        try:
            sig = build_signals()
            score_map = {}
            for it in (sig.get("stocks_in") or []) + (sig.get("stocks_us") or []):
                score_map[it["symbol"]] = {"score": it["score"], "signal": it["signal"]}
        except Exception:
            score_map = {}

        def enrich(sym):
            f = _fundamentals(sym)
            if not f:
                return None
            f.update(score_map.get(sym, {}))
            return f

        in_items, us_items = [], []
        with ThreadPoolExecutor(max_workers=10) as ex:
            f_in = {ex.submit(enrich, s): s for s in NIFTY50}
            f_us = {ex.submit(enrich, s): s for s in US50}
            for fut in as_completed(f_in):
                r = fut.result()
                if r:
                    in_items.append(r)
            for fut in as_completed(f_us):
                r = fut.result()
                if r:
                    us_items.append(r)
        in_items.sort(key=lambda x: -(x.get("score") or -999))
        us_items.sort(key=lambda x: -(x.get("score") or -999))
        data = {"stocks_in": in_items, "stocks_us": us_items, "updated_at": time.time()}
        with _screen_lock:
            _screen_cache["ts"] = time.time()
            _screen_cache["data"] = data
            _screen_cache["busy"] = False
        return data
    except Exception:
        with _screen_lock:
            _screen_cache["busy"] = False
        raise


# ---------------------------------------------------------------- portfolio tools
def history_closes(typ, sym, days):
    """Daily closes for backtest/compare/forecast."""
    if typ == "crypto":
        o = crypto_ohlc(sym, None)
        if o and o.get("close"):
            return o["close"]
        # longer history via CoinGecko market_chart (daily, INR)
        j = coingecko_get(f"/coins/{sym}/market_chart",
                          {"vs_currency": "inr", "days": str(days), "interval": "daily"},
                          retries=2)
        if j:
            return [p[1] for p in j.get("prices", [])]
        return None
    rng = {30: "1mo", 90: "3mo", 180: "6mo", 365: "1y", 730: "2y",
           1095: "5y", 1825: "10y"}.get(days, "1y")
    h = yahoo_history(sym, rng)
    return h["closes"] if h else None


def backtest(typ, sym, amount, days):
    closes = history_closes(typ, sym, days)
    if not closes or len(closes) < 10:
        return None
    closes = [c for c in closes if c]
    if len(closes) < 10:
        return None
    start, end = closes[0], closes[-1]
    if start <= 0:
        return None
    value = amount * (end / start)
    pnl = value - amount
    pnl_pct = (end / start - 1.0) * 100.0
    years = days / 365.0
    cagr = ((end / start) ** (1.0 / years) - 1.0) * 100.0 if years > 0 and end > 0 else None
    return {
        "amount": amount, "value": value, "pnl": pnl, "pnl_pct": pnl_pct,
        "cagr": cagr, "start_price": start, "end_price": end,
        "sparkline": closes,
    }


def compare_two(t1, s1, t2, s2):
    c1 = history_closes(t1, s1, 90)
    c2 = history_closes(t2, s2, 90)
    if not c1 or not c2:
        return None
    c1 = [x for x in c1 if x]
    c2 = [x for x in c2 if x]
    n = min(len(c1), len(c2), 60)
    if n < 10:
        return None
    c1, c2 = c1[-n:], c2[-n:]

    def norm(cl):
        return [round(v / cl[0] * 100.0, 2) for v in cl]

    def stats(cl):
        ret = (cl[-1] / cl[0] - 1.0) * 100.0
        rs = [cl[i] / cl[i - 1] - 1.0 for i in range(1, len(cl))]
        mean = sum(rs) / len(rs)
        vol = (sum((r - mean) ** 2 for r in rs) / (len(rs) - 1)) ** 0.5 * (252 ** 0.5) * 100.0 if len(rs) > 1 else None
        peak = cl[0]
        mdd = 0.0
        for v in cl:
            peak = max(peak, v)
            mdd = max(mdd, (peak - v) / peak * 100.0)
        return {"ret": round(ret, 2), "vol": round(vol, 2) if vol is not None else None,
                "mdd": round(mdd, 2), "last": cl[-1]}
    return {"a": {"norm": norm(c1), "stats": stats(c1)},
            "b": {"norm": norm(c2), "stats": stats(c2)}}


# ---------------------------------------------------------------- P&L history
PNL_FILE = os.path.join(DATA_DIR, "pnl_history.json")
_pnl_lock = threading.Lock()


def snapshot_pnl():
    try:
        wl = build_watchlist()
    except Exception:
        return None
    totals = wl.get("totals", {})
    inr = totals.get("INR", {})
    usd = totals.get("USD", {})
    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "inr_pnl": round(inr.get("pnl", 0.0), 2),
        "inr_value": round(inr.get("value", 0.0), 2),
        "inr_invested": round(inr.get("invested", 0.0), 2),
        "usd_pnl": round(usd.get("pnl", 0.0), 2),
        "usd_value": round(usd.get("value", 0.0), 2),
        "usd_invested": round(usd.get("invested", 0.0), 2),
        "n_items": len(wl.get("items", [])),
    }
    with _pnl_lock:
        hist = []
        try:
            with open(PNL_FILE) as f:
                hist = json.load(f)
        except Exception:
            hist = []
        if hist and hist[-1].get("date") == entry["date"]:
            hist[-1] = entry
        else:
            hist.append(entry)
            hist = hist[-365:]
        with open(PNL_FILE, "w") as f:
            json.dump(hist, f, indent=2)
    return hist


def pnl_history():
    try:
        with open(PNL_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def clear_pnl_history():
    with _pnl_lock:
        if os.path.exists(PNL_FILE):
            os.remove(PNL_FILE)
    return []


# ---------------------------------------------------------------- technicals, market mood, portfolio
INDICES = [
    ("^NSEI", "NIFTY 50", "INR"),
    ("^BSESN", "SENSEX", "INR"),
    ("^NSEBANK", "BANK NIFTY", "INR"),
    ("^GSPC", "S&P 500", "USD"),
    ("^IXIC", "NASDAQ", "USD"),
    ("^DJI", "DOW JONES", "USD"),
]

_market_cache = {"ts": 0.0, "data": None}
_market_lock = threading.Lock()
MARKET_TTL = 90


def _candles_for(typ, sym):
    """OHLC lists (last ~60) + current price + currency + name."""
    if typ == "crypto":
        ticker = dict(TOP_COINS).get(sym)
        o = crypto_ohlc(sym, ticker)
        if not o or not o.get("close"):
            return None
        n = min(60, len(o["close"]))
        return {
            "name": (movers_crypto_map().get(sym) or {}).get("name") or sym.title(),
            "currency": "INR",
            "price": o["close"][-1],
            "opens": o["open"][-n:], "highs": o["high"][-n:],
            "lows": o["low"][-n:], "closes": o["close"][-n:],
        }
    h = yahoo_history(sym, "3mo")
    if not h or not h.get("closes"):
        # Angel One real candles for NSE/BSE symbols (optional, free)
        s = mailer_mod.load_settings()
        if s.get("angel_enabled") and sym.endswith((".NS", ".BO")):
            a = angel_mod.candles(sym, s, days=90)
            if a and a.get("close") and len(a["close"]) >= 30:
                n = min(60, len(a["close"]))
                return {
                    "name": sym, "currency": "INR", "price": a["close"][-1],
                    "opens": a["open"][-n:], "highs": a["high"][-n:],
                    "lows": a["low"][-n:], "closes": a["close"][-n:],
                }
        return None
    n = min(60, len(h["closes"]))
    return {
        "name": h["name"], "currency": h["currency"], "price": h["price"],
        "opens": h["opens"][-n:], "highs": h["highs"][-n:],
        "lows": h["lows"][-n:], "closes": h["closes"][-n:],
    }


def build_market():
    with _market_lock:
        if _market_cache["data"] and time.time() - _market_cache["ts"] < MARKET_TTL:
            return _market_cache["data"]

    indices = []
    for sym, name, cur in INDICES:
        d = yahoo_chart(sym, "5d")
        if d:
            indices.append({"symbol": sym, "name": name, "currency": cur,
                            "price": d["price"], "change_pct": d["change_pct"]})

    # breadth & sector performance from the movers + screener caches
    mov = _movers_cache.get("data")
    if not mov:
        try:
            build_movers()
        except Exception:
            pass
        mov = _movers_cache.get("data")
    breadth = None
    sectors = []
    if mov and mov.get("stocks_in"):
        items = mov["stocks_in"].get("all") or (
            mov["stocks_in"].get("gainers") or []) + (mov["stocks_in"].get("losers") or [])
        adv = sum(1 for i in items if (i.get("change_pct") or 0) > 0)
        dec = sum(1 for i in items if (i.get("change_pct") or 0) < 0)
        unch = len(items) - adv - dec
        breadth = {"advancers": adv, "decliners": dec, "unchanged": unch,
                   "total": len(items)}
        # sector map from screener cache if available
        sec_map = {}
        if _screen_cache.get("data"):
            for i in _screen_cache["data"].get("stocks_in", []):
                if i.get("sector"):
                    sec_map[i["symbol"]] = i["sector"]
        by_sector = {}
        for i in items:
            sec = sec_map.get(i["symbol"], "Other")
            by_sector.setdefault(sec, []).append(i.get("change_pct") or 0.0)
        sectors = [{"sector": s, "change_pct": round(sum(v) / len(v), 2),
                    "n": len(v)} for s, v in by_sector.items()]
        sectors.sort(key=lambda x: -x["change_pct"])

    data = {"indices": indices, "breadth": breadth, "sectors": sectors,
            "updated_at": time.time()}
    with _market_lock:
        _market_cache["ts"] = time.time()
        _market_cache["data"] = data
    return data


def _annual_vol(closes):
    if not closes or len(closes) < 25:
        return None
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))
            if closes[i - 1] and closes[i - 1] > 0]
    if len(rets) < 20:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return round((var ** 0.5) * (252 ** 0.5) * 100.0, 2)


def build_portfolio_health():
    wl = build_watchlist()
    items = wl.get("items", [])
    if not items:
        return None

    # per-holding annualised volatility from 90-day history
    vols = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {}
        for it in items:
            if it["type"] == "crypto":
                ticker = dict(TOP_COINS).get(it["symbol"])
                futures[ex.submit(crypto_ohlc, it["symbol"], ticker)] = it["id"]
            else:
                futures[ex.submit(yahoo_history, it["symbol"], "3mo")] = it["id"]
        for fut in as_completed(futures):
            iid = futures[fut]
            try:
                r = fut.result()
                closes = (r or {}).get("closes") or (r or {}).get("close")
                vols[iid] = _annual_vol(closes)
            except Exception:
                vols[iid] = None

    h = portfolio_mod.health(items, vols)
    tax = portfolio_mod.tax_estimate(items)
    return {"health": h, "tax": tax, "totals": wl.get("totals", {})}


# ---------------------------------------------------------------- routes
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/movers")
def api_movers():
    return jsonify(build_movers())


@app.route("/api/signals")
def api_signals():
    return jsonify(build_signals())


@app.route("/api/watchlist", methods=["GET", "POST"])
def api_watchlist():
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
        typ = body.get("type")
        symbol = body.get("symbol")
        if not typ or not symbol:
            return jsonify({"error": "type and symbol required"}), 400
        if typ not in ("crypto", "stock_in", "stock_us"):
            return jsonify({"error": "type must be crypto, stock_in or stock_us"}), 400
        try:
            buy_price = float(body.get("buy_price"))
            qty = float(body.get("qty"))
        except (TypeError, ValueError):
            return jsonify({"error": "buy_price and qty must be numbers"}), 400
        if buy_price <= 0 or qty <= 0:
            return jsonify({"error": "buy_price and qty must be positive"}), 400
        items = load_watchlist()
        if any(i["symbol"] == symbol and i["type"] == typ for i in items):
            return jsonify({"error": "Already in your watchlist"}), 409
        item = {
            "id": uuid.uuid4().hex[:10],
            "type": typ,
            "symbol": symbol,
            "ticker": body.get("ticker") or symbol,
            "name": body.get("name") or symbol,
            "buy_price": buy_price,
            "qty": qty,
            "currency": body.get("currency") or ("USD" if typ == "stock_us" else "INR"),
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        items.append(item)
        save_watchlist(items)
        snapshot_pnl()
        return jsonify(build_watchlist())
    return jsonify(build_watchlist())


@app.route("/api/watchlist/<item_id>", methods=["DELETE"])
def api_watchlist_delete(item_id):
    items = load_watchlist()
    items = [i for i in items if i.get("id") != item_id]
    save_watchlist(items)
    snapshot_pnl()
    return jsonify(build_watchlist())


@app.route("/api/search")
def api_search():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"results": []})
    return jsonify({"results": search(q)})


@app.route("/api/detail")
def api_detail():
    typ = request.args.get("type") or ""
    sym = request.args.get("symbol") or ""
    if not typ or not sym:
        return jsonify({"error": "type and symbol required"}), 400
    data = get_detail(typ, sym)
    if not data:
        return jsonify({"error": "Could not fetch data"}), 502
    return jsonify(data)


# ---------------------------------------------------------------- mutual funds
@app.route("/api/funds")
def api_funds():
    try:
        data = funds_mod.build_funds()
    except Exception as e:
        return jsonify({"error": str(e), "funds": []}), 502
    return jsonify(data)


# ---------------------------------------------------------------- alerts
def quick_price(typ, sym):
    """Lightweight current price for the alert checker."""
    try:
        if typ == "crypto":
            cm = movers_crypto_map()
            c = cm.get(sym)
            if c:
                return c["price"]
            d = get_detail(typ, sym)
            return d["price"] if d else None
        d = yahoo_chart(sym, "1d")
        return d["price"] if d else None
    except Exception:
        return None


@app.route("/api/alerts", methods=["GET", "POST"])
def api_alerts():
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
        try:
            items = alerts_mod.add_alert(
                body.get("type"), body.get("symbol"), body.get("ticker"),
                body.get("name"), body.get("currency"), body.get("direction"),
                body.get("level"))
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"alerts": items})
    return jsonify({"alerts": alerts_mod.load_alerts()})


@app.route("/api/alerts/targetstop", methods=["POST"])
def api_alerts_targetstop():
    """One call -> two alerts (target above, stop below) for an auto pick."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        items = alerts_mod.load_alerts()
        if body.get("target"):
            items = alerts_mod.add_alert(
                body.get("type"), body.get("symbol"), body.get("ticker"),
                body.get("name"), body.get("currency"), "above", body.get("target"))
        if body.get("stop"):
            items = alerts_mod.add_alert(
                body.get("type"), body.get("symbol"), body.get("ticker"),
                body.get("name"), body.get("currency"), "below", body.get("stop"))
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"alerts": items})


@app.route("/api/alerts/<alert_id>", methods=["DELETE"])
def api_alerts_delete(alert_id):
    return jsonify({"alerts": alerts_mod.delete_alert(alert_id)})


# ---------------------------------------------------------------- daily report
@app.route("/api/report")
def api_report():
    try:
        sig = build_signals()
    except Exception:
        sig = _signals_cache.get("data")
    try:
        fnd = funds_mod.build_funds()
    except Exception:
        fnd = funds_mod._funds_cache.get("data")
    mov = _movers_cache.get("data") or build_movers()
    try:
        wl = build_watchlist()
    except Exception:
        wl = None
    path, fname = report_mod.generate_pdf(signals=sig, funds=fnd, movers=mov, watchlist=wl)
    return send_file(path, as_attachment=True, download_name=fname, mimetype="application/pdf")


# ---------------------------------------------------------------- screener
@app.route("/api/screener")
def api_screener():
    return jsonify(build_screener())


# ---------------------------------------------------------------- portfolio tools
@app.route("/api/backtest")
def api_backtest():
    typ = request.args.get("type") or ""
    sym = request.args.get("symbol") or ""
    try:
        amount = float(request.args.get("amount") or 0)
        days = int(request.args.get("days") or 365)
    except (TypeError, ValueError):
        return jsonify({"error": "amount and days must be numbers"}), 400
    if amount <= 0 or not typ or not sym:
        return jsonify({"error": "type, symbol and a positive amount are required"}), 400
    res = backtest(typ, sym, amount, days)
    if not res:
        return jsonify({"error": "Could not fetch history for this asset"}), 502
    return jsonify(res)


@app.route("/api/compare")
def api_compare():
    res = compare_two(request.args.get("type1") or "", request.args.get("symbol1") or "",
                      request.args.get("type2") or "", request.args.get("symbol2") or "")
    if not res:
        return jsonify({"error": "Could not fetch data for both assets"}), 502
    return jsonify(res)


@app.route("/api/forecast")
def api_forecast():
    typ = request.args.get("type") or ""
    sym = request.args.get("symbol") or ""
    closes = history_closes(typ, sym, 90)
    f = forecast_mod.forecast(closes) if closes else None
    if not f:
        return jsonify({"error": "Not enough history to forecast"}), 502
    return jsonify(f)


# ---------------------------------------------------------------- P&L history
@app.route("/api/pnlhistory", methods=["GET", "POST", "DELETE"])
def api_pnlhistory():
    if request.method == "POST":
        return jsonify({"history": snapshot_pnl() or []})
    if request.method == "DELETE":
        return jsonify({"history": clear_pnl_history()})
    return jsonify({"history": pnl_history()})


# ---------------------------------------------------------------- settings (email + api keys + zerodha)
@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
        cur = mailer_mod.load_settings()
        merged = {**cur, **body}
        # preserve existing secrets when the field is left blank
        for k in ("smtp_pass", "zerodha_access_token", "zerodha_api_secret",
                  "angel_password", "angel_totp"):
            if not body.get(k):
                merged[k] = cur.get(k)
        saved = mailer_mod.save_settings(merged)
        return jsonify({"settings": mailer_mod.public_settings(), "saved": True})
    return jsonify({"settings": mailer_mod.public_settings()})


@app.route("/api/settings/test", methods=["POST"])
def api_settings_test():
    ok, msg = mailer_mod.send_email(
        "✅ Test email — Daily Market Analyzer",
        "Your email alerts are configured correctly.\n\n"
        "You will now receive an email whenever a price alert triggers.\n"
        "— Daily Market Analyzer")
    return jsonify({"ok": ok, "message": msg})


# ---------------------------------------------------------------- technicals
@app.route("/api/technicals")
def api_technicals():
    typ = request.args.get("type") or ""
    sym = request.args.get("symbol") or ""
    c = _candles_for(typ, sym)
    if not c:
        return jsonify({"error": "Could not fetch candles"}), 502
    t = technicals_mod.build_technicals(
        c["closes"], c["opens"], c["highs"], c["lows"], price=c["price"])
    if not t:
        return jsonify({"error": "Not enough history"}), 502
    t["name"] = c["name"]
    t["currency"] = c["currency"]
    t["price"] = c["price"]
    return jsonify(t)


# ---------------------------------------------------------------- news
@app.route("/api/news")
def api_news():
    typ = request.args.get("type") or "stock"
    sym = request.args.get("symbol") or ""
    name = request.args.get("name") or sym
    ntype = "crypto" if typ == "crypto" else "stock"
    return jsonify(news_mod.fetch_news(sym, name, ntype))


# ---------------------------------------------------------------- market mood
@app.route("/api/market")
def api_market():
    return jsonify(build_market())


# ---------------------------------------------------------------- portfolio health & tax
@app.route("/api/portfolio")
def api_portfolio():
    data = build_portfolio_health()
    if not data:
        return jsonify({"error": "No picks yet — add assets to My Picks"}), 404
    return jsonify(data)


# ---------------------------------------------------------------- AI financial advisor
def _tech_for(typ, sym):
    """Find the signal dict for an asset from the cached signals engine."""
    try:
        sig = build_signals()
    except Exception:
        sig = _signals_cache.get("data")
    if not sig:
        return None
    for key in ("crypto", "stocks_in", "stocks_us"):
        for it in sig.get(key, []):
            if it["symbol"] == sym:
                return it
    return None


def _fund_for(sym):
    if _screen_cache.get("data"):
        for it in _screen_cache["data"].get("stocks_in", []) + _screen_cache["data"].get("stocks_us", []):
            if it["symbol"] == sym:
                return it
    return None


def _forecast_for(typ, sym):
    closes = history_closes(typ, sym, 90)
    return forecast_mod.forecast(closes) if closes else None


def _advise_asset(typ, sym, name, currency):
    tech = _tech_for(typ, sym)
    fund = _fund_for(sym) if typ in ("stock_in", "stock_us") else None
    try:
        sentiment = news_mod.fetch_news(sym, name, "crypto" if typ == "crypto" else "stock").get("sentiment")
    except Exception:
        sentiment = None
    fc = _forecast_for(typ, sym)
    rec = advisor_mod.recommend(tech, fund, sentiment, fc, currency)
    rec.update({
        "type": typ, "symbol": sym, "name": name, "currency": currency,
        "price": (tech or {}).get("price"),
        "change_pct": (tech or {}).get("change_pct"),
    })
    return rec


@app.route("/api/advisor")
def api_advisor():
    typ = request.args.get("type") or ""
    sym = request.args.get("symbol") or ""
    name = request.args.get("name") or sym
    currency = request.args.get("currency") or "INR"
    try:
        return jsonify(_advise_asset(typ, sym, name, currency))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/advisor/ask", methods=["POST"])
def api_advisor_ask():
    body = request.get_json(force=True, silent=True) or {}
    q = (body.get("question") or "").strip()
    if not q:
        return jsonify({"answer": "Ask me something like: 'Should I buy Reliance?', 'best stocks today', 'my portfolio', or 'plan for ₹50 lakh in 10 years'."})

    ql = q.lower()

    # --- greetings ---
    if re.search(r"\b(hi|hello|hey|namaste)\b", ql) and len(q) < 12:
        return jsonify({"answer": "Hi! I'm your financial advisor. Ask me things like:\n• 'Should I buy Reliance?'\n• 'Best Indian stocks today'\n• 'Best mutual funds'\n• 'My portfolio health'\n• 'Plan ₹50 lakh in 10 years'"})

    # --- portfolio queries ---
    if re.search(r"portfolio|my picks|my holdings|how am i doing", ql):
        try:
            p = build_portfolio_health()
        except Exception:
            p = None
        if not p:
            return jsonify({"answer": "You don't have any picks yet. Go to My Picks and add the stocks/coins you hold with your buy price, then I can analyze your portfolio."})
        h = p.get("health") or {}
        tx = (p.get("tax") or {}).get("totals") or {}
        ans = ["Here's your portfolio:"]
        ans.append(f"• Total value: ₹{h.get('total', 0):,.0f}")
        ans.append(f"• Diversification: {h.get('diversification')}% ({h.get('divers_label')})")
        ans.append(f"• Risk: {h.get('risk_label')} (volatility {h.get('weighted_vol')}%)")
        ans.append(f"• Largest holding: {h.get('top', {}).get('name')} ({h.get('top', {}).get('share')}%)")
        if tx.get("grand_total"):
            ans.append(f"• Est. capital-gains tax if sold today: ₹{tx['grand_total']:,.0f}")
        for a in h.get("advice") or []:
            ans.append(f"• {a}")
        return jsonify({"answer": "\n".join(ans)})

    # --- goal planning queries ---
    gm = re.search(r"(\d[\d,.]*)\s*(lakh|lac|cr|crore|k|thousand)?", ql)
    if re.search(r"plan|goal|target|need|want.*(lakh|cr|crore|rupee|₹|rs)", ql) and re.search(r"\byear|yr|years\b", ql):
        yrs = re.search(r"(\d+)\s*(year|yr|years)", ql)
        years = int(yrs.group(1)) if yrs else 10
        amount = 5000000
        if gm:
            try:
                amt = float(gm.group(1).replace(",", ""))
                unit = (gm.group(2) or "").lower()
                mult = {"lakh": 1e5, "lac": 1e5, "cr": 1e7, "crore": 1e7, "k": 1e3, "thousand": 1e3}.get(unit, 1)
                amount = amt * mult
            except Exception:
                pass
        exp = 12.0 if years >= 5 else 9.0
        plan = planner_mod.goal_plan(amount, years, expected_return=exp)
        ans = [f"To reach ₹{amount:,.0f} in {years} years (assuming {exp}% return):"]
        if "required_monthly" in plan:
            ans.append(f"• You need to invest ₹{plan['required_monthly']:,.0f} every month (SIP), OR")
            ans.append(f"• ₹{plan['lumpsum_needed']:,.0f} as a one-time lumpsum today.")
        else:
            ans.append(f"• Your plan will grow to ₹{plan['projected']:,.0f} (you invest ₹{plan['invested']:,.0f}).")
        if years <= 3:
            ans.append("• For this short horizon, prefer debt/hybrid funds (lower risk).")
        elif years <= 5:
            ans.append("• Prefer hybrid + large-cap index funds.")
        else:
            ans.append("• Prefer flexi-cap / mid-cap / small-cap equity funds via SIP.")
        return jsonify({"answer": "\n".join(ans)})

    # --- best/top queries ---
    if re.search(r"best (indian )?stocks|top (indian )?stocks|what stocks|which stocks", ql):
        sig = wait_for_signals(20) or {}
        items = [x for x in sig.get("stocks_in", []) if x["signal"] in ("STRONG BUY", "BUY")][:5]
        if not items:
            return jsonify({"answer": "The free data source is busy right now. Please try again in a moment — "
                                      "or open the 🤖 Auto Picks tab to watch the scan live."})
        ans = ["Today's best Indian stocks (ranked by score):"]
        for i, x in enumerate(items, 1):
            ans.append(f"{i}. {x['name']} — {x['signal']} (score {x['score']}) · ₹{x['price']:,.0f} · target ₹{x['target']:,.0f} · stop ₹{x['stop']:,.0f}")
        return jsonify({"answer": "\n".join(ans)})

    if re.search(r"best crypto|top crypto|which crypto|what crypto", ql):
        sig = wait_for_signals(20) or {}
        items = [x for x in sig.get("crypto", []) if x["signal"] in ("STRONG BUY", "BUY")][:5]
        if not items:
            return jsonify({"answer": "The free crypto data source is busy right now. Please try again in a moment."})
        ans = ["Top crypto picks right now:"]
        for i, x in enumerate(items, 1):
            ans.append(f"{i}. {x['name']} — {x['signal']} · ₹{x['price']:,.0f}")
        return jsonify({"answer": "\n".join(ans)})

    if re.search(r"best (mutual )?fund|top (mutual )?fund|which fund|what fund", ql):
        try:
            funds = funds_mod.build_funds().get("funds", [])[:5]
        except Exception:
            funds = []
        if not funds:
            return jsonify({"answer": "I couldn't load fund data — try again in a moment."})
        ans = ["Best mutual funds right now (by score):"]
        for i, f in enumerate(funds, 1):
            ans.append(f"{i}. {f['name'][:44]} — {f['rating']} ({f['score']}) · 1Y {f['r1y']}% · 3Y {f['r3y']}%")
        return jsonify({"answer": "\n".join(ans)})

    # --- market mood ---
    if re.search(r"market (today|mood|now)|how is (the )?market|nifty|sensex", ql):
        try:
            m = build_market()
        except Exception:
            m = None
        if not m:
            return jsonify({"answer": "I couldn't load the market — try again."})
        ans = ["Market right now:"]
        for i in m.get("indices", [])[:3]:
            ans.append(f"• {i['name']}: {i['price']:,.0f} ({i['change_pct']:+.2f}%)")
        b = m.get("breadth")
        if b:
            ans.append(f"• NIFTY breadth: {b['advancers']} up / {b['decliners']} down")
        return jsonify({"answer": "\n".join(ans)})

    # --- asset-specific advice ---
    resolved = advisor_mod.resolve_asset(q, search, TOP_COINS)
    if not resolved:
        return jsonify({"answer": "I didn't catch which stock/coin you mean. Try naming it — e.g. 'Should I buy Reliance?', 'Sell bitcoin?', or 'How is TCS?'"})
    typ, sym, name, currency = resolved
    rec = _advise_asset(typ, sym, name, currency)
    verdict = rec["verdict"]
    ans = [f"**{name}** — my advice: **{verdict}** (advisor score {rec['score']}/100)"]
    if rec.get("price"):
        c = "₹" if currency == "INR" else "$"
        ans.append(f"Price now: {c}{rec['price']:,.2f}")
    ans.append("Reasons:")
    for r in rec.get("reasons", []):
        ans.append(f"• {r}")
    if rec.get("risks"):
        ans.append("Risks:")
        for r in rec["risks"]:
            ans.append(f"• {r}")
    ans.append("⚠️ Not financial advice — always use a stop-loss and invest only what you can afford to lose.")
    return jsonify({"answer": "\n".join(ans), "advice": rec})


# ---------------------------------------------------------------- planner
@app.route("/api/planner/risk", methods=["POST"])
def api_planner_risk():
    body = request.get_json(force=True, silent=True) or {}
    try:
        age = int(body.get("age") or 30)
        years = int(body.get("horizon") or 10)
        appetite = str(body.get("appetite") or "moderate").lower()
        stability = str(body.get("stability") or "moderate").lower()
        amount = float(body.get("amount") or 100000)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid inputs"}), 400
    # validation
    if not (18 <= age <= 100):
        return jsonify({"error": "Age must be between 18 and 100"}), 400
    if not (1 <= years <= 40):
        return jsonify({"error": "Horizon must be between 1 and 40 years"}), 400
    if amount < 0:
        return jsonify({"error": "Amount cannot be negative"}), 400
    if appetite not in ("conservative", "moderate", "aggressive"):
        appetite = "moderate"
    if stability not in ("stable", "moderate", "uncertain"):
        stability = "moderate"
    prof = planner_mod.risk_profile(age, years, appetite, stability)
    # attach real suggestions
    try:
        sig = build_signals()
        top_stocks = [x for x in sig.get("stocks_in", []) if x["signal"] in ("STRONG BUY", "BUY")][:3]
        top_crypto = [x for x in sig.get("crypto", []) if x["signal"] in ("STRONG BUY", "BUY")][:3]
        top_funds = funds_mod.build_funds().get("funds", [])[:4]
    except Exception:
        top_stocks = top_crypto = top_funds = []
    plan = planner_mod.allocation_plan(amount, prof["allocation"], top_funds, top_stocks, top_crypto)
    return jsonify({"profile": prof, "plan": plan})


@app.route("/api/planner/goal", methods=["POST"])
def api_planner_goal():
    body = request.get_json(force=True, silent=True) or {}
    try:
        target = float(body.get("target") or 0)
        years = int(body.get("years") or 10)
        monthly = float(body.get("monthly") or 0)
        lumpsum = float(body.get("lumpsum") or 0)
        expected = float(body.get("expected_return") or 12)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid inputs"}), 400
    if target <= 0 or years <= 0:
        return jsonify({"error": "target and years must be positive"}), 400
    plan = planner_mod.goal_plan(target, years, monthly, lumpsum, expected)
    try:
        funds = funds_mod.build_funds().get("funds", [])
    except Exception:
        funds = []
    cats, picks = planner_mod.suggest_horizon(years, funds)
    plan["suggested_categories"] = cats
    plan["suggested_funds"] = [{"name": f["name"], "category": f["category"],
                                "r1y": f["r1y"], "r3y": f["r3y"]} for f in picks]
    return jsonify(plan)


# ---------------------------------------------------------------- trading journal
@app.route("/api/journal", methods=["GET", "POST"])
def api_journal():
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
        try:
            qty = float(body.get("qty") or 0)
            price = float(body.get("price") or 0)
        except (TypeError, ValueError):
            return jsonify({"error": "qty and price must be numbers"}), 400
        if qty <= 0 or price <= 0:
            return jsonify({"error": "qty and price must be positive"}), 400
        if str(body.get("side") or "").lower() not in ("buy", "sell"):
            return jsonify({"error": "side must be 'buy' or 'sell'"}), 400
        if not body.get("symbol"):
            return jsonify({"error": "symbol is required"}), 400
        try:
            journal_mod.add_trade(
                body.get("side"), body.get("symbol"), body.get("name"),
                qty, price, body.get("currency"),
                body.get("fees") or 0, body.get("date"))
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify(journal_mod.stats())
    return jsonify(journal_mod.stats())


@app.route("/api/journal/<trade_id>", methods=["DELETE"])
def api_journal_delete(trade_id):
    journal_mod.delete_trade(trade_id)
    return jsonify(journal_mod.stats())


# ---------------------------------------------------------------- zerodha status
@app.route("/api/zerodha/status")
def api_zerodha_status():
    s = mailer_mod.load_settings()
    return jsonify({
        "configured": bool(kite_mod.configured(s)),
        "enabled": bool(s.get("zerodha_enabled")),
        "positions": kite_mod.get_positions(s) if s.get("zerodha_enabled") else None,
    })


@app.route("/api/angel/status")
def api_angel_status():
    s = mailer_mod.load_settings()
    return jsonify({
        "configured": bool(angel_mod.configured(s)),
        "enabled": bool(s.get("angel_enabled")),
    })


@app.route("/api/angel/test")
def api_angel_test():
    s = mailer_mod.load_settings()
    if not angel_mod.configured(s):
        return jsonify({"ok": False, "message": "Angel One not configured — fill client code, password, API key and TOTP in Settings."})
    prices = angel_mod.ltp(["RELIANCE.NS"], s)
    if prices:
        return jsonify({"ok": True, "message": f"✅ Angel One live: RELIANCE = ₹{prices['RELIANCE.NS']:.2f}"})
    return jsonify({"ok": False, "message": "Connected but no price returned. Check credentials / token and try again."})


# ---------------------------------------------------------------- telegram
@app.route("/api/telegram/status")
def api_telegram_status():
    s = mailer_mod.load_settings()
    return jsonify({
        "configured": telegram_mod.configured(s),
        "enabled": bool(s.get("telegram_enabled")),
        "daily_enabled": bool(s.get("telegram_daily_enabled")),
    })


@app.route("/api/telegram/chatid")
def api_telegram_chatid():
    """Discover the user's chat id from recent bot messages."""
    s = mailer_mod.load_settings()
    token = s.get("telegram_bot_token")
    if not token:
        return jsonify({"error": "Enter your bot token first"}), 400
    cid = telegram_mod.discover_chat_id(token)
    if not cid:
        return jsonify({"error": "No messages found — open Telegram, send any message to your bot, then try again."}), 404
    return jsonify({"chat_id": cid})


@app.route("/api/telegram/test", methods=["POST"])
def api_telegram_test():
    s = mailer_mod.load_settings()
    ok, msg = telegram_mod.send_message(
        "✅ Telegram connected! You will now get price alerts and can chat with "
        "your advisor here. Try /help.", settings=s)
    return jsonify({"ok": ok, "message": msg})


def _telegram_handler(text):
    """Handle a Telegram chat message -> reply text (or None)."""
    t = text.strip()
    low = t.lower()
    if low in ("/start", "/help"):
        return ("📊 Your Market Advisor bot\n\n"
                "Commands:\n"
                "/market — market mood now\n"
                "/best — top stock & crypto picks\n"
                "/funds — top mutual funds\n"
                "/portfolio — your portfolio\n"
                "/ask <question> — e.g. /ask should I buy Reliance?\n"
                "/price RELIANCE — current price")
    if low == "/market":
        try:
            m = build_market()
        except Exception:
            return "Couldn't load market data."
        lines = ["📈 Market now:"]
        for i in m.get("indices", [])[:4]:
            lines.append(f"{i['name']}: {i['price']:,.0f} ({i['change_pct']:+.2f}%)")
        b = m.get("breadth")
        if b:
            lines.append(f"NIFTY breadth: {b['advancers']} up / {b['decliners']} down")
        return "\n".join(lines)
    if low in ("/best", "/picks"):
        try:
            sig = build_signals()
        except Exception:
            return "Couldn't load signals."
        lines = ["⭐ Top picks now:"]
        for i, x in enumerate([x for x in sig.get("stocks_in", []) if x["signal"] in ("STRONG BUY", "BUY")][:4], 1):
            lines.append(f"{i}. {x['name']} — {x['signal']} · ₹{x['price']:,.0f} (target ₹{x['target']:,.0f})")
        for i, x in enumerate([x for x in sig.get("crypto", []) if x["signal"] in ("STRONG BUY", "BUY")][:2], 1):
            lines.append(f"C{i}. {x['name']} — {x['signal']} · ₹{x['price']:,.0f}")
        return "\n".join(lines)
    if low == "/funds":
        try:
            funds = funds_mod.build_funds().get("funds", [])[:4]
        except Exception:
            return "Couldn't load funds."
        lines = ["🪙 Top mutual funds:"]
        for i, f in enumerate(funds, 1):
            lines.append(f"{i}. {f['name'][:40]} — {f['rating']} · 1Y {f['r1y']}% · 3Y {f['r3y']}%")
        return "\n".join(lines)
    if low == "/portfolio":
        try:
            p = build_portfolio_health()
        except Exception:
            p = None
        if not p:
            return "No picks yet. Add stocks in the dashboard's My Picks tab."
        h = p.get("health") or {}
        return (f"💼 Your portfolio: ₹{h.get('total', 0):,.0f}\n"
                f"Diversification: {h.get('diversification')}% ({h.get('divers_label')})\n"
                f"Risk: {h.get('risk_label')}")
    if low.startswith("/price "):
        sym = t[len("/price "):].strip()
        res = search(sym)
        if not res:
            return f"Couldn't find '{sym}'."
        r = res[0]
        d = get_detail(r["type"], r["symbol"])
        if d:
            c = "₹" if r.get("currency") == "INR" else "$"
            return f"{d.get('name')} ({r['ticker']}): {c}{d.get('price'):,.2f}"
        return f"Couldn't get price for '{sym}'."
    if low.startswith("/ask "):
        return _advisor_answer(t[len("/ask "):].strip())
    # anything else -> advisor
    return _advisor_answer(t)


def _advisor_answer(q):
    """Thin wrapper so Telegram can reuse the ask-advisor logic."""
    resolved = advisor_mod.resolve_asset(q, search, TOP_COINS)
    if not resolved:
        return ("I didn't catch which asset. Try '/ask should I buy Reliance?' "
                "or /help for commands.")
    typ, sym, name, currency = resolved
    rec = _advise_asset(typ, sym, name, currency)
    c = "₹" if currency == "INR" else "$"
    lines = [f"**{name}** — {rec['verdict']} (score {rec['score']}/100)"]
    if rec.get("price"):
        lines.append(f"Price: {c}{rec['price']:,.2f}")
    for r in rec.get("reasons", [])[:4]:
        lines.append(f"• {r}")
    if rec.get("risks"):
        for r in rec["risks"][:2]:
            lines.append(f"⚠️ {r}")
    return "\n".join(lines)


def _telegram_loop():
    """Long-poll Telegram in the background so users can chat with the advisor."""
    while True:
        try:
            s = mailer_mod.load_settings()
            if s.get("telegram_enabled") and s.get("telegram_bot_token"):
                telegram_mod.poll(_telegram_handler, mailer_mod.load_settings)
            else:
                time.sleep(30)
        except Exception:
            time.sleep(15)


def _warm_signals():
    """Background: keep the signal cache warm so the Auto Picks tab is instant."""
    while True:
        try:
            build_signals()
        except Exception:
            pass
        time.sleep(SIGNALS_TTL)


def _warm_funds():
    """Background: keep mutual-fund data warm."""
    while True:
        try:
            funds_mod.build_funds()
        except Exception:
            pass
        time.sleep(funds_mod.FUNDS_TTL)


def _alerts_loop():
    """Background: check price alerts every minute + email notifications."""
    while True:
        try:
            newly = alerts_mod.check_alerts(quick_price)
            if newly:
                for a in newly:
                    cur = a.get("currency") == "INR" and "₹" or "$"
                    lvl = f"{cur}{a['level']:,.2f}"
                    hit = f"{cur}{a['triggered_price']:,.2f}"
                    subject = f"🎯 Price Alert: {a['name']} hit {lvl}"
                    body = (f"Your alert for {a['name']} ({a.get('ticker') or a['symbol']}) "
                            f"has triggered.\n\n"
                            f"Condition: {a['direction']} {lvl}\n"
                            f"Current price: {hit}\n"
                            f"Triggered at: {a.get('triggered_at')}\n\n"
                            f"— Daily Market Analyzer")
                    mailer_mod.send_email(subject, body)
                    # also notify via Telegram if configured
                    s = mailer_mod.load_settings()
                    if s.get("telegram_enabled") and telegram_mod.configured(s):
                        tg = (f"🎯 Price Alert: {a['name']} hit {lvl}\n"
                              f"Condition: {a['direction']} {lvl}\n"
                              f"Current price: {hit}")
                        telegram_mod.send_message(tg, settings=s)
        except Exception:
            pass
        time.sleep(60)


def _pnl_snapshot_loop():
    """Background: snapshot your P&L once a day (and every 30 min on same day)."""
    while True:
        try:
            snapshot_pnl()
        except Exception:
            pass
        time.sleep(1800)


def _warm_market():
    while True:
        try:
            build_market()
        except Exception:
            pass
        time.sleep(MARKET_TTL)


def _daily_email_summary():
    """Build a plain-text morning advisory summary."""
    lines = ["📊 Daily Market Advisor — " + datetime.now().strftime("%d %B %Y"), "=" * 44, ""]
    try:
        m = build_market()
        for i in m.get("indices", [])[:3]:
            lines.append(f"{i['name']}: {i['price']:,.0f} ({i['change_pct']:+.2f}%)")
        b = m.get("breadth")
        if b:
            lines.append(f"NIFTY breadth: {b['advancers']} up / {b['decliners']} down")
    except Exception:
        pass
    lines.append("")
    try:
        sig = build_signals()
        lines.append("Top picks today:")
        for i, x in enumerate([x for x in sig.get("stocks_in", []) if x["signal"] in ("STRONG BUY", "BUY")][:3], 1):
            lines.append(f"  {i}. {x['name']} — {x['signal']} · ₹{x['price']:,.0f} (target ₹{x['target']:,.0f}, stop ₹{x['stop']:,.0f})")
    except Exception:
        pass
    lines.append("")
    try:
        funds = funds_mod.build_funds().get("funds", [])[:3]
        lines.append("Top mutual funds:")
        for i, f in enumerate(funds, 1):
            lines.append(f"  {i}. {f['name'][:44]} — {f['rating']} · 1Y {f['r1y']}%")
    except Exception:
        pass
    try:
        p = build_portfolio_health()
        if p and p.get("health"):
            h = p["health"]
            lines.append("")
            lines.append(f"Your portfolio: ₹{h.get('total', 0):,.0f} · {h.get('risk_label')} · {h.get('divers_label')}")
    except Exception:
        pass
    lines += ["", "— Your Daily Market Analyzer", "Not financial advice."]
    return "\n".join(lines)


def _daily_email_loop():
    """Send the advisory email once per day at the configured time (default 08:00)."""
    last_sent_date = None
    while True:
        try:
            s = mailer_mod.load_settings()
            if s.get("daily_email_enabled"):
                hhmm = (s.get("daily_email_time") or "08:00").strip()
                try:
                    hh, mm = (int(x) for x in hhmm.split(":"))
                except Exception:
                    hh, mm = 8, 0
                now = datetime.now()
                if now.hour == hh and now.minute == mm and last_sent_date != now.date():
                    ok, msg = mailer_mod.send_email(
                        f"📊 Morning Advisor — {now.strftime('%d %b %Y')}",
                        _daily_email_summary())
                    if ok:
                        last_sent_date = now.date()
                    # Telegram daily advisory (independent of email)
                    if s.get("telegram_daily_enabled") and telegram_mod.configured(s):
                        telegram_mod.send_message(
                            "📊 " + _daily_email_summary(), settings=s)
        except Exception:
            pass
        time.sleep(30)


if __name__ == "__main__":
    threading.Thread(target=_warm_signals, daemon=True).start()
    threading.Thread(target=_warm_funds, daemon=True).start()
    threading.Thread(target=_alerts_loop, daemon=True).start()
    threading.Thread(target=_pnl_snapshot_loop, daemon=True).start()
    threading.Thread(target=build_screener, daemon=True).start()
    threading.Thread(target=_warm_market, daemon=True).start()
    threading.Thread(target=_daily_email_loop, daemon=True).start()
    threading.Thread(target=_telegram_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)
