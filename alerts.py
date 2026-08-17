"""
alerts.py — price alerts (persistent, checked by a background poller).

An alert fires when an asset's live price crosses a level:
  direction "above" -> fire when current >= level
  direction "below" -> fire when current <= level
"""
import os
import json
import time
import uuid
import threading
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
ALERTS_FILE = os.path.join(DATA_DIR, "alerts.json")

_lock = threading.Lock()


def load_alerts():
    try:
        with open(ALERTS_FILE) as f:
            items = json.load(f)
        return items if isinstance(items, list) else []
    except Exception:
        return []


def save_alerts(items):
    with _lock:
        with open(ALERTS_FILE, "w") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)


def add_alert(typ, symbol, ticker, name, currency, direction, level):
    level = float(level)
    if direction not in ("above", "below"):
        raise ValueError("direction must be 'above' or 'below'")
    if level <= 0:
        raise ValueError("level must be positive")
    items = load_alerts()
    # avoid exact duplicates
    for it in items:
        if (it["type"] == typ and it["symbol"] == symbol and
                it["direction"] == direction and it["level"] == level and not it["triggered"]):
            return items
    alert = {
        "id": uuid.uuid4().hex[:10],
        "type": typ, "symbol": symbol, "ticker": ticker or symbol,
        "name": name or symbol, "currency": currency or "INR",
        "direction": direction, "level": level,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "triggered": False, "triggered_at": None, "triggered_price": None,
    }
    items.append(alert)
    save_alerts(items)
    return items


def delete_alert(alert_id):
    items = [a for a in load_alerts() if a.get("id") != alert_id]
    save_alerts(items)
    return items


def check_alerts(get_price):
    """
    get_price(type, symbol) -> current price or None.
    Returns the list of newly triggered alerts (marked in storage).
    """
    items = load_alerts()
    changed = False
    newly = []
    now = datetime.now(timezone.utc).isoformat()
    for a in items:
        if a.get("triggered"):
            continue
        price = get_price(a["type"], a["symbol"])
        if price is None:
            continue
        hit = (a["direction"] == "above" and price >= a["level"]) or \
              (a["direction"] == "below" and price <= a["level"])
        if hit:
            a["triggered"] = True
            a["triggered_at"] = now
            a["triggered_price"] = price
            changed = True
            newly.append(a)
    if changed:
        save_alerts(items)
    return newly
