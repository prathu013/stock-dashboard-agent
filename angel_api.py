"""
angel_api.py — optional Angel One SmartAPI integration (FREE for Angel One
account holders). Provides TRUE real-time NSE/BSE prices and historical candles.

Setup (free):
  1. Open a free Angel One trading account.
  2. Go to https://smartapi.angelbroking.com -> create app -> get API key.
  3. In ⚙ Settings, enter: client code, password, API key, and the TOTP from
     your authenticator app (same one used for Angel One login).
  4. Requires:  pip install smartapi-python

Everything here is optional — without credentials the dashboard uses its
free sources (Yahoo / Google Finance / CoinGecko).
"""
import datetime
import time
import threading

_lock = threading.Lock()
_session = {"obj": None, "ts": 0.0, "error": None}
_token_cache = {}


def configured(settings):
    return bool(settings.get("angel_enabled") and
                settings.get("angel_api_key") and
                settings.get("angel_client_code") and
                settings.get("angel_password") and
                settings.get("angel_totp"))


def _connect(settings):
    """Create & cache a SmartConnect session. Returns (obj or None, error)."""
    now = time.time()
    with _lock:
        if _session["obj"] and now - _session["ts"] < 6 * 3600:
            return _session["obj"], _session["error"]
    try:
        from smartapi import SmartConnect
    except ImportError:
        err = "smartapi-python not installed (run: pip install smartapi-python)"
        with _lock:
            _session["error"] = err
        return None, err
    try:
        obj = SmartConnect(api_key=settings["angel_api_key"])
        data = obj.generateSession(
            settings["angel_client_code"],
            settings["angel_password"],
            settings["angel_totp"])
        if not data or not data.get("data"):
            err = "Angel login failed — check client code / password / TOTP"
            with _lock:
                _session["error"] = err
            return None, err
        with _lock:
            _session["obj"] = obj
            _session["ts"] = now
            _session["error"] = None
        return obj, None
    except Exception as e:
        err = f"Angel login error: {e}"
        with _lock:
            _session["error"] = err
        return None, err


def _exchange_for(symbol):
    return "NSE" if symbol.endswith(".NS") else "BSE" if symbol.endswith(".BO") else "NSE"


def _code_for(symbol):
    return symbol[:-3] if symbol.endswith((".NS", ".BO")) else symbol


def _token(obj, symbol):
    if symbol in _token_cache:
        return _token_cache[symbol]
    exchange = _exchange_for(symbol)
    code = _code_for(symbol)
    try:
        res = obj.searchScrip(exchange, code)
        if res and res.get("data"):
            for item in res["data"]:
                if item.get("symbol") == code and str(item.get("exch_seg") or "").upper() == exchange:
                    tok = item.get("token")
                    _token_cache[symbol] = tok
                    return tok
        # relaxed fallback: first item with matching symbol
        if res and res.get("data"):
            for item in res["data"]:
                if item.get("symbol") == code:
                    tok = item.get("token")
                    _token_cache[symbol] = tok
                    return tok
    except Exception:
        pass
    return None


def ltp(symbols, settings):
    """Real-time last prices for a list of NSE/BSE symbols. Returns {sym: price}."""
    if not configured(settings) or not symbols:
        return {}
    obj, _ = _connect(settings)
    if not obj:
        return {}
    out = {}
    for s in symbols:
        tok = _token(obj, s)
        if not tok:
            continue
        try:
            res = obj.ltpData(_exchange_for(s), _code_for(s), tok)
            d = res.get("data") if res else None
            if d and d.get("ltp"):
                out[s] = float(d["ltp"])
        except Exception:
            continue
    return out


def candles(symbol, settings, days=90):
    """Historical daily candles for one NSE/BSE symbol."""
    obj, _ = _connect(settings)
    if not obj:
        return None
    tok = _token(obj, symbol)
    if not tok:
        return None
    todate = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    fromdate = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    try:
        res = obj.getCandleData({
            "exchange": _exchange_for(symbol), "symboltoken": tok,
            "interval": "ONE_DAY", "fromdate": fromdate, "todate": todate})
        rows = res.get("data") if res else None
        if not rows:
            return None
        opens, highs, lows, closes = [], [], [], []
        for row in rows:
            opens.append(row[1]); highs.append(row[2])
            lows.append(row[3]); closes.append(row[4])
        return {"open": opens, "high": highs, "low": lows, "close": closes}
    except Exception:
        return None
