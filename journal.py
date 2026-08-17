"""
journal.py — trading journal with FIFO realized P&L.

Trades are stored in data/journal.json. Buys add to a position; sells reduce it
(FIFO). Realized P&L, win-rate, best/worst trades are computed from matched
buy/sell lots.
"""
import os
import json
import uuid
import threading
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
JOURNAL_FILE = os.path.join(DATA_DIR, "journal.json")

_lock = threading.Lock()


def load():
    try:
        with open(JOURNAL_FILE) as f:
            items = json.load(f)
        return items if isinstance(items, list) else []
    except Exception:
        return []


def save(items):
    with _lock:
        with open(JOURNAL_FILE, "w") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)


def add_trade(side, symbol, name, qty, price, currency, fees=0.0, date=None):
    side = side.lower()
    if side not in ("buy", "sell"):
        raise ValueError("side must be buy or sell")
    items = load()
    items.append({
        "id": uuid.uuid4().hex[:10],
        "side": side,
        "symbol": symbol,
        "name": name or symbol,
        "qty": float(qty),
        "price": float(price),
        "fees": float(fees or 0),
        "currency": currency or "INR",
        "date": date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    })
    save(items)
    return items


def delete_trade(trade_id):
    items = [t for t in load() if t.get("id") != trade_id]
    save(items)
    return items


def _realized(items):
    """FIFO matching per (symbol, currency). Returns stats + closed trades."""
    positions = {}
    closed = []
    for t in sorted(items, key=lambda x: x["date"]):
        key = (t["symbol"], t["currency"])
        pos = positions.setdefault(key, [])   # list of lots: {qty, price, fees, date}
        if t["side"] == "buy":
            pos.append({"qty": t["qty"], "price": t["price"], "fees": t["fees"], "date": t["date"]})
        else:
            qty_left = t["qty"]
            while qty_left > 0 and pos:
                lot = pos[0]
                if lot["qty"] <= qty_left:
                    qty = lot["qty"]
                    pos.pop(0)
                else:
                    qty = qty_left
                    lot["qty"] -= qty_left
                qty_left -= qty
                pnl = (t["price"] - lot["price"]) * qty - lot["fees"] - t["fees"] * (qty / t["qty"] if t["qty"] else 1)
                closed.append({
                    "symbol": t["symbol"], "name": t["name"], "currency": t["currency"],
                    "qty": qty, "buy_price": lot["price"], "sell_price": t["price"],
                    "buy_date": lot["date"], "sell_date": t["date"],
                    "pnl": round(pnl, 2),
                })
    return positions, closed


def stats():
    items = load()
    positions, closed = _realized(items)
    wins = [c for c in closed if c["pnl"] > 0]
    losses = [c for c in closed if c["pnl"] <= 0]
    total_pnl = sum(c["pnl"] for c in closed)
    by_cur = {}
    for c in closed:
        by_cur[c["currency"]] = by_cur.get(c["currency"], 0.0) + c["pnl"]
    best = max(closed, key=lambda c: c["pnl"]) if closed else None
    worst = min(closed, key=lambda c: c["pnl"]) if closed else None
    # open positions summary
    open_pos = []
    for (sym, cur), lots in positions.items():
        qty = sum(l["qty"] for l in lots)
        if qty <= 0:
            continue
        cost = sum(l["qty"] * l["price"] for l in lots)
        name = next((t["name"] for t in reversed(items)
                     if t["symbol"] == sym and t["currency"] == cur), sym)
        open_pos.append({"symbol": sym, "name": name, "currency": cur,
                         "qty": round(qty, 6), "avg_cost": round(cost / qty, 2),
                         "invested": round(cost, 2)})
    return {
        "trades": items,
        "closed": closed,
        "open_positions": open_pos,
        "total_pnl": round(total_pnl, 2),
        "by_currency": {k: round(v, 2) for k, v in by_cur.items()},
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "wins": len(wins), "losses": len(losses), "n_closed": len(closed),
        "avg_win": round(sum(c["pnl"] for c in wins) / len(wins), 2) if wins else None,
        "avg_loss": round(sum(c["pnl"] for c in losses) / len(losses), 2) if losses else None,
        "best": best, "worst": worst,
    }
