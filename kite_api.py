"""
kite_api.py — optional Zerodha Kite integration for TRUE real-time NSE prices
and your real holdings. Requires a free Zerodha account and your own API
key/access token (created at https://developers.kite.trade). Everything here is
optional — without credentials the dashboard uses its free sources.

kiteconnect is imported lazily so the app runs even if it isn't installed.
"""
import threading
import time

_cache = {"ts": 0.0, "ltp": {}, "positions": None}
_lock = threading.Lock()


def _client(settings):
    try:
        import kiteconnect
    except ImportError:
        return None
    key = settings.get("zerodha_api_key") or settings.get("kite_api_key")
    token = settings.get("zerodha_access_token") or settings.get("kite_access_token")
    if not key or not token:
        return None
    return kiteconnect.KiteConnect(api_key=key, access_token=token)


def _to_kite_symbol(sym):
    """RELIANCE.NS -> NSE:RELIANCE, AAPL stays as-is (NSE only for .NS/.BO)."""
    if sym.endswith(".NS"):
        return "NSE:" + sym[:-3]
    if sym.endswith(".BO"):
        return "BSE:" + sym[:-3]
    return sym


def configured(settings):
    return bool(settings.get("zerodha_api_key") or settings.get("kite_api_key")) and \
           bool(settings.get("zerodha_access_token") or settings.get("kite_access_token"))


def get_ltp(symbols, settings, ttl=2.0):
    """Batched live quotes for NSE/BSE symbols. Returns {sym: price} (cached 2s)."""
    if not configured(settings):
        return {}
    now = time.time()
    with _lock:
        if _cache["ltp"] and now - _cache["ts"] < ttl:
            return {s: _cache["ltp"].get(s) for s in symbols if _cache["ltp"].get(s)}
    client = _client(settings)
    if not client:
        return {}
    kite_syms = [_to_kite_symbol(s) for s in symbols if _to_kite_symbol(s).startswith(("NSE:", "BSE:"))]
    if not kite_syms:
        return {}
    try:
        quotes = client.quote(kite_syms)  # may raise on wrong token
        out = {}
        for s, ks in zip(symbols, kite_syms):
            q = quotes.get(ks)
            if q and q.get("last_price"):
                out[s] = q["last_price"]
        with _lock:
            _cache["ltp"].update(out)
            _cache["ts"] = now
        return out
    except Exception:
        return {}


def get_positions(settings):
    """Your live positions from Kite (needs the positions scope)."""
    if not configured(settings):
        return None
    now = time.time()
    with _lock:
        if _cache["positions"] and now - _cache["ts"] < 30:
            return _cache["positions"]
    client = _client(settings)
    if not client:
        return None
    try:
        positions = client.positions().get("net", [])
        out = [{
            "symbol": p.get("tradingsymbol"),
            "exchange": p.get("exchange"),
            "qty": p.get("quantity"),
            "avg": p.get("average_price"),
            "ltp": p.get("last_price"),
            "pnl": p.get("pnl"),
        } for p in positions if (p.get("quantity") or 0) != 0]
        with _lock:
            _cache["positions"] = out
            _cache["ts"] = now
        return out
    except Exception:
        return None
